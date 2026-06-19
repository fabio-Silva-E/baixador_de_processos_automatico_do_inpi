import os
import threading
import time
import psutil
import os

from config.paths import DOWNLOAD_DIR
from config.settings import URL_INPI
from core.selenium_controller import SeleniumController
from core.licenca import dias_restantes
from config.paths import BASE_DIR
from collections import deque
from pathlib import Path
from openpyxl import Workbook, load_workbook

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLineEdit, QListWidget,
    QLabel, QApplication, QTextEdit, QMessageBox, QComboBox
)
from PyQt5.QtCore import QTimer, QDateTime, pyqtSignal

# suas funções internas

from ui.alert_menssenger import mostrar_toast
from .vpn_manager import VPNManager
from core.worker_manager import (
    _processar_proximo,
    _erro_worker,
    _finalizar_processo_atual,
)
from core.download_manager import (_renomear_pdf_para_processo,
                                   _pdf_baixado_com_sucesso,
                                   wait_for_download)
from core.login_manager import (
    login_tres_abas,
    login_inpi,
    garantir_login,
    garantir_acesso_peticiones,
    liberar_acesso_peticiones
)
from core.processo_manager import (
    selecionar_processo,
    atualizar_lista_processos,
    abrir_detalhe_processo,
    tentar_clicar_botao_pdf,
    possui_servico_389_ou_394,
    _registrar_processo_concluido,
    _repetir_processo_atual,
    _fluxo_pdf
)
from core.captcha_manager import (
    iniciar_monitor_captcha,
    _loop_monitor_captcha,
    iniciar_solver_auto,
    detectar_worker_com_captcha,
    _loop_solver_button,
    parar_solver_auto,
    clicar_solver_button,
    clicar_try_again,
    tratar_modal_captcha,
    selenium_get_recaptcha_iframe,
    clicar_imagem, clicar_reload_duplo,
    captcha_travado,
    verificar_sessao_apos_download,
    sessao_expirada,
    aguardar_botao_download
)
import faulthandler


import sys
import traceback
from utils.log_utils import logger


def global_exception(exc_type, exc_value, exc_traceback):
    logger.critical(
        "ERRO FATAL",
        exc_info=(exc_type, exc_value, exc_traceback)
    )


sys.excepthook = global_exception


class MainApp(QWidget):
    dias_restantes = dias_restantes
    aguardar_botao_download = aguardar_botao_download
    captcha_travado = captcha_travado
    verificar_sessao_apos_download = verificar_sessao_apos_download
    sessao_expirada = sessao_expirada
    clicar_reload_duplo = clicar_reload_duplo
    iniciar_monitor_captcha = iniciar_monitor_captcha
    _loop_monitor_captcha = _loop_monitor_captcha
    _fluxo_pdf = _fluxo_pdf
    iniciar_solver_auto = iniciar_solver_auto
    detectar_worker_com_captcha = detectar_worker_com_captcha
    _loop_solver_button = _loop_solver_button
    parar_solver_auto = parar_solver_auto
    clicar_solver_button = clicar_solver_button
    clicar_try_again = clicar_try_again
    tratar_modal_captcha = tratar_modal_captcha
    selenium_get_recaptcha_iframe = selenium_get_recaptcha_iframe
    clicar_imagem = clicar_imagem
    log_signal = pyqtSignal(str)
    selecionar_processo = selecionar_processo
    atualizar_lista_processos = atualizar_lista_processos
    _processar_proximo = _processar_proximo
    _erro_worker = _erro_worker
    _finalizar_processo_atual = _finalizar_processo_atual
    _repetir_processo_atual = _repetir_processo_atual
    tentar_clicar_botao_pdf = tentar_clicar_botao_pdf
    possui_servico_389_ou_394 = possui_servico_389_ou_394
    _registrar_processo_concluido = _registrar_processo_concluido
    abrir_detalhe_processo = abrir_detalhe_processo
    login_tres_abas = login_tres_abas
    login_inpi = login_inpi
    garantir_login = garantir_login
    garantir_acesso_peticiones = garantir_acesso_peticiones
    liberar_acesso_peticiones = liberar_acesso_peticiones
    _renomear_pdf_para_processo = _renomear_pdf_para_processo
    _pdf_baixado_com_sucesso = _pdf_baixado_com_sucesso
    wait_for_download = wait_for_download

    def __init__(self):
        super().__init__()
        self._driver_locks = {
                    1: threading.RLock(),
                    2: threading.RLock(),
                    3: threading.RLock(),
                }
        fault_log = open(
            "faulthandler.log",
            "w",
            encoding="utf-8"
        )

        faulthandler.enable(file=fault_log)

        faulthandler.dump_traceback_later(
            10,
            repeat=True,
            file=fault_log
        )
        process = psutil.Process(os.getpid())
        self.monitor_abas_ativo = False
        self.monitor_abas_thread = None

        self.log_new(
            f"RAM: {process.memory_info().rss / 1024 / 1024:.0f} MB"
        )
        self.solver_img = BASE_DIR / "solver_button.png"

        print(self.solver_img)
        print(self.solver_img.exists())
        self.reload_img = BASE_DIR / "reload_button.png"
        self.modal_try_again_img = BASE_DIR / "modal_try_again.png"
        self.botao_try_again_img = BASE_DIR / "botao_try_again.png"
        self.pyautogui_lock = threading.Lock()

        for img in (
                self.solver_img,
                self.reload_img,
                self.modal_try_again_img,
                self.botao_try_again_img,
        ):
            if not Path(img).exists():
                self.log_new(f"❌ Arquivo não encontrado: {img}")
        self.captcha_estado = {
            1: False,
            2: False,
            3: False
        }
        self.captcha_retry = {
            1: False,
            2: False,
            3: False
        }

        self.log_signal.connect(self._log_ui)

        self.tentativas_por_processo = {}
        self.MAX_TENTATIVAS = 2

        # diretórios de download por worker
        self.download_dirs = {}

        # 1️⃣ Flags e dados
        self.parar_loop = False
        self.loop_ativo = False
        self.processando = {1: False, 2: False, 3: False}

        self.numero_atual = {
            1: None,
            2: None,
            3: None
        }

        self.indice_processo = 0
        self.total_processos = 0
        self.processos_extraidos = 0
        self.arquivo_descartados = "processos_descartados.txt"
        self.arquivo_concluidos = "processos_concluidos.txt"
        self.processos = []
        self.processos_concluidos = set()

        self.vpn = VPNManager()

        # 2️⃣ Criar UI PRIMEIRO
        self._criar_interface()

        # restaura última posição salva
        self.carregar_posicao_janela()

        self._iniciar_monitor_ip()
        # 3️⃣ Carregar dados DEPOIS
        self._carregar_processos_concluidos()
        self.atualizar_lista_processos()

        # 4️⃣ Filtrar concluídos
        self.processos = [
            p for p in self.processos
            if p not in self.processos_concluidos
        ]
        for wid in (1, 2, 3):
            pasta = Path(DOWNLOAD_DIR) / f"worker_{wid}"
            pasta.mkdir(parents=True, exist_ok=True)
            self.download_dirs[wid] = pasta
        self.carregar_usuarios_excel()

        for u in self.usuarios:
            self.combo_usuario.addItem(u["usuario"])
            self.combo_usuario_2.addItem(u["usuario"])
            self.combo_usuario_3.addItem(u["usuario"])

        # conecta primeiro
        self.combo_usuario.currentIndexChanged.connect(
            self.on_usuario_selecionado
        )

        self.combo_usuario_2.currentIndexChanged.connect(
            self.on_usuario_selecionado_2
        )

        self.combo_usuario_3.currentIndexChanged.connect(
            self.on_usuario_selecionado_3
        )

        # depois restaura
        self.carregar_configuracoes()
        # 🔌 CONECTA OS COMBOS AOS MÉTODOS
        self.combo_usuario.currentIndexChanged.connect(self.on_usuario_selecionado)
        self.combo_usuario_2.currentIndexChanged.connect(self.on_usuario_selecionado_2)
        self.combo_usuario_3.currentIndexChanged.connect(self.on_usuario_selecionado_3)

    def _criar_interface(self):
        self.setWindowTitle("INPI - vs(1.4)")
        self.setGeometry(50, 30, 700, 50)

        # 🔹 Layout principal
        self.layout = QHBoxLayout(self)

        # ==================================================
        # 🟦 COLUNA LOGIN
        # ==================================================
        coluna_login = QVBoxLayout()

        self.label_ip = QLabel("🌍 IP: ---")
        coluna_login.addWidget(self.label_ip)
        # ── licença ─────────────────────────────────────────
        #dias = dias_restantes()
        #if dias is not None:
        #    if dias <= 7:
        #        cor = "color: red; font-weight: bold;"
        #        texto = f"⚠️ Licença expira em {dias} dias!"
        #    elif dias <= 30:
        #        cor = "color: orange;"
        #        texto = f"🔑 Licença válida por {dias} dias"
        #    else:
        #        cor = "color: green;"
        #        texto = f"✅ Licença válida por {dias} dias"
        #    self.label_licenca = QLabel(texto)
        #    self.label_licenca.setStyleSheet(cor)
        #    coluna_login.addWidget(self.label_licenca)
        # Em _criar_interface, após criar o botão:
        self.btn_monitor_abas = QPushButton("🧠 Monitor abas: ON")
        self.btn_monitor_abas.setCheckable(True)
        self.btn_monitor_abas.setChecked(True)  # ← começa ligado
        self.btn_monitor_abas.clicked.connect(self.toggle_monitor_abas)

        coluna_login.addWidget(self.btn_monitor_abas)
        # ===== dropdown de timeout =====
        coluna_login.addWidget(QLabel("Timeout Captcha (segundos)"))

        self.combo_timeout = QComboBox()
        self.combo_timeout.addItem("Selecione o timeout")
        self.combo_timeout.model().item(0).setEnabled(False)

        # opções
        self.combo_timeout.addItems(["30", "60", "120", "180", "300"])

        # valor padrão
        self.combo_timeout.setCurrentText("120")

        coluna_login.addWidget(self.combo_timeout)

        coluna_login.addWidget(QLabel("⏱ Intervalo Reload (segundos)"))
        self.combo_intervalo_reload = QComboBox()
        self.combo_intervalo_reload.addItems(["1", "2", "3", "5", "8", "10"])
        self.combo_intervalo_reload.setCurrentText("3")
        coluna_login.addWidget(self.combo_intervalo_reload)


        # ===== USUÁRIO 1 =====
        coluna_login.addWidget(QLabel("Login Aba 1"))
        self.combo_usuario = QComboBox()
        self.combo_usuario.addItem("Selecione o usuário INPI")
        self.combo_usuario.model().item(0).setEnabled(False)

        self.input_usuario = QLineEdit()
        self.input_usuario.setReadOnly(True)

        self.input_senha = QLineEdit()
        self.input_senha.setEchoMode(QLineEdit.Password)
        self.input_senha.setReadOnly(True)

        coluna_login.addWidget(self.combo_usuario)
        coluna_login.addWidget(self.input_usuario)
        coluna_login.addWidget(self.input_senha)

        # ===== USUÁRIO 2 =====
        coluna_login.addWidget(QLabel("Login Aba 2"))
        self.combo_usuario_2 = QComboBox()
        self.combo_usuario_2.addItem("Selecione o usuário INPI")
        self.combo_usuario_2.model().item(0).setEnabled(False)

        self.input_usuario_2 = QLineEdit()
        self.input_senha_2 = QLineEdit()
        self.input_senha_2.setEchoMode(QLineEdit.Password)

        coluna_login.addWidget(self.combo_usuario_2)
        coluna_login.addWidget(self.input_usuario_2)
        coluna_login.addWidget(self.input_senha_2)

        # ===== USUÁRIO 3 =====
        coluna_login.addWidget(QLabel("Login Aba 3"))
        self.combo_usuario_3 = QComboBox()
        self.combo_usuario_3.addItem("Selecione o usuário INPI")
        self.combo_usuario_3.model().item(0).setEnabled(False)

        self.input_usuario_3 = QLineEdit()
        self.input_senha_3 = QLineEdit()
        self.input_senha_3.setEchoMode(QLineEdit.Password)

        coluna_login.addWidget(self.combo_usuario_3)
        coluna_login.addWidget(self.input_usuario_3)
        coluna_login.addWidget(self.input_senha_3)

        self.btn_iniciar = QPushButton("🌐 Abrir site INPI")
        self.btn_iniciar.clicked.connect(self.iniciar_selenium)
        coluna_login.addWidget(self.btn_iniciar)

        coluna_login.addStretch()

        # ==================================================
        # 🟨 COLUNA PROCESSOS
        # ==================================================
        coluna_processos = QVBoxLayout()

        coluna_processos.addWidget(QLabel("📄 Processos"))

        self.lista_processos = QListWidget()
        self.lista_processos.itemClicked.connect(self.selecionar_processo)
        coluna_processos.addWidget(self.lista_processos)

        self.entry_processo = QLineEdit()
        self.entry_processo.setPlaceholderText("Número do processo")
        coluna_processos.addWidget(self.entry_processo)

        self.btn_buscar = QPushButton("▶ Iniciar extração")
        self.btn_buscar.clicked.connect(self.iniciar_processamento_em_lote)
        coluna_processos.addWidget(self.btn_buscar)


        coluna_processos.addWidget(QLabel("🌐 Navegador"))
        self.combo_navegador = QComboBox()
        self.combo_navegador.addItems(["Edge", "Chrome", "Brave"])
        self.combo_navegador.currentTextChanged.connect(self.trocar_navegador)
        coluna_processos.addWidget(self.combo_navegador)




        self.label_status = QLabel("Status: idle")
        coluna_processos.addWidget(self.label_status)

        self.label_contador = QLabel("Processos extraídos: 0 / 0")
        self.label_contador.setStyleSheet("font-size: 11pt; font-weight: bold;")
        coluna_processos.addWidget(self.label_contador)

        coluna_processos.addStretch()

        # ==================================================
        # 🟩 COLUNA LOGS
        # ==================================================
        coluna_logs = QVBoxLayout()

        coluna_logs.addWidget(QLabel("🧾 Logs"))

        self.console_log = QTextEdit()
        self.console_log.setReadOnly(True)
        self.console_log.setStyleSheet("""
            background-color: white;
            color: black;
            font-family: Consolas;
            font-size: 10pt;
        """)
        coluna_logs.addWidget(self.console_log)

        # ==================================================
        # 🔗 ADICIONA AO LAYOUT PRINCIPAL (AGORA SIM)
        # ==================================================
        self.layout.addLayout(coluna_login, 2)
        self.layout.addLayout(coluna_processos, 2)
        self.layout.addLayout(coluna_logs, 3)

    def _log_ui(self, mensagem):
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.console_log.append(f"[{timestamp}] {mensagem}")
        self.console_log.ensureCursorVisible()
        self.label_status.setText(f"Status: {mensagem}")

    def _iniciar_monitor_ip(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.atualizar_ip)
        self.timer.start(5000)
        self.atualizar_ip()

    def atualizar_ip(self):
        ip = self.vpn.ip_atual()
        self.label_ip.setText(f"🌍 IP: {ip}")

    def trocar_navegador(self, texto):
        from core.selenium_controller import SeleniumController
        mapa = {
            "Edge": "edge",
            "Chrome": "chrome",
            #"Firefox": "firefox",
            "Brave": "brave",
        }
        SeleniumController.NAVEGADOR = mapa.get(texto, "edge")
        self.log(f"🌐 Navegador selecionado: {texto} — terá efeito ao reabrir os browsers")

    def obter_intervalo_reload(self) -> int:
        try:
            return int(self.combo_intervalo_reload.currentText())
        except ValueError:
            return 3
        
    def trocar_vpn(self):
        self.log_new("BOTÃO CLICADO")
        self.label_ip.setText("🔄 Trocando VPN...")
        ip = self.vpn.conectar()
        self.label_ip.setText(f"🌍 IP: {ip}")

    def on_usuario_selecionado_2(self, index):
        if index <= 0:
            self.input_usuario_2.clear()
            self.input_senha_2.clear()
            return
        user = self.usuarios[index - 1]
        self.input_usuario_2.setText(user["usuario"])
        self.input_senha_2.setText(user["senha"])

    def on_usuario_selecionado_3(self, index):
        if index <= 0:
            self.input_usuario_3.clear()
            self.input_senha_3.clear()
            return
        user = self.usuarios[index - 1]
        self.input_usuario_3.setText(user["usuario"])
        self.input_senha_3.setText(user["senha"])

    def on_usuario_selecionado(self, index):
        if index == 0:
            self.input_usuario.clear()
            self.input_senha.clear()
            return

        user = self.usuarios[index - 1]  # 👈 deslocamento
        self.input_usuario.setText(user["usuario"])
        self.input_senha.setText(user["senha"])

    def parar_processamento(self):
        if not self.loop_ativo:
            return

        self.loop_ativo = False
        self.processando = {
            1: False,
            2: False,
            3: False
        }

        self.log("🛑 Processamento interrompido pelo usuário.")
        self.label_status.setText("Status: parado")
        self.lista_processos.setEnabled(True)

    def _carregar_processos_concluidos(self):
        if not os.path.exists(self.arquivo_concluidos):
            return

        with open(self.arquivo_concluidos, "r", encoding="utf-8") as f:
            for linha in f:
                numero = linha.strip()
                if numero:
                    self.processos_concluidos.add(numero)

    from collections import deque

    def iniciar_processamento_em_lote(self):

        # 🔐 Verifica se os Chromes estão ativos
        if not all(hasattr(self, f"driver{i}") for i in (1, 2, 3)):
            self.ui_warning(
                "Chrome não iniciado",
                "Abra os três Chromes antes de iniciar a extração."
            )
            self.log_new("⚠️ Tentativa de iniciar lote sem Chromes abertos.")
            return

        if not self.processos:
            self.ui_warning("Aviso", "Nenhum processo carregado.")
            return

        self.loop_ativo = True
        self.lista_processos.setEnabled(False)

        # 🔥 CONVERTE LISTA EM 3 FILAS
        self.processos_1 = deque()
        self.processos_2 = deque()
        self.processos_3 = deque()

        for i, p in enumerate(self.processos):
            if i % 3 == 0:
                self.processos_1.append(p)
            elif i % 3 == 1:
                self.processos_2.append(p)
            else:
                self.processos_3.append(p)

        self.total_processos = len(self.processos)
        self.processos_extraidos = 0
        self._atualizar_contador_ui()

        self.log_new("🚀 Iniciando processamento em lote (3 Chromes)...")

        # 🚀 DISPARA OS 3 WORKERS
        self._processar_proximo(1)
        self._processar_proximo(2)
        self._processar_proximo(3)

    def carregar_usuarios_excel(self):
        self.usuarios = []  # lista de dicts

        caminho = BASE_DIR / "credenciais.xlsx"
        if not caminho.exists():
            self.log_new("⚠️ Arquivo credenciais.xlsx não encontrado.")
            return

        wb = load_workbook(caminho, data_only=True)
        ws = wb.active

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0] or not row[1]:
                continue

            self.usuarios.append({
                "usuario": str(row[0]).strip(),
                "senha": str(row[1]).strip()
            })

    def ui_warning(self, titulo, msg):
        QTimer.singleShot(
            0,
            lambda: QMessageBox.warning(self, titulo, msg)
        )

    def ui_error(self, titulo, msg):
        QTimer.singleShot(
            0,
            lambda: QMessageBox.critical(self, titulo, msg)
        )

    def log(self, mensagem):

        logger.error(mensagem)

        self.log_signal.emit(mensagem)

    def log_new(self, mensagem):

        logger.error(mensagem)

    def iniciar_selenium(self):
        self.log("Iniciando 3 Chromes independentes...")

        try:
            # Fecha se já existir
            if hasattr(self, "driver1") and self.driver1:
                self.selenium1.stop()

            if hasattr(self, "driver2") and self.driver2:
                self.selenium2.stop()

            if hasattr(self, "driver3") and self.driver3:
                self.selenium3.stop()

            time.sleep(3)

            # 🔹 DRIVER 1
            self.selenium1 = SeleniumController()
            self.selenium1.worker_id = 1
            self.driver1 = self.selenium1.start()
            self.driver1.get(URL_INPI)

            # 🔹 DRIVER 2
            self.selenium2 = SeleniumController()
            self.selenium2.worker_id = 2
            self.driver2 = self.selenium2.start()
            self.driver2.get(URL_INPI)

            # 🔹 DRIVER 3
            self.selenium3 = SeleniumController()
            self.selenium3.worker_id = 3
            self.driver3 = self.selenium3.start()
            self.driver3.get(URL_INPI)
            if self.btn_monitor_abas.isChecked():
                for selenium in (self.selenium1, self.selenium2, self.selenium3):
                    selenium.monitor_abas_ativo = True
                    selenium.iniciar_monitor_abas()
            self.log_new("✅ Três Chromes iniciados com sucesso")

            self.iniciar_solver_auto()
            # self.iniciar_try_again_auto()
            self._ultimo_solver_click = 0
            self.iniciar_monitor_captcha()
        except Exception as e:

            QMessageBox.critical(self, "Erro", str(e))

            logger.exception(
                "Erro durante processamento", str(e)
            )

    def _usuario_atual(self, worker_id):
        if worker_id == 1:
            return self.input_usuario
        elif worker_id == 2:
            return self.input_usuario_2
        elif worker_id == 3:
            return self.input_usuario_3
        return None

    def _senha_atual(self, worker_id):
        if worker_id == 1:
            return self.input_senha
        elif worker_id == 2:
            return self.input_senha_2
        elif worker_id == 3:
            return self.input_senha_3
        return None

    def ui_toast(self, mensagem, tempo=2000):
        QTimer.singleShot(
            0,
            lambda m=mensagem, t=tempo: mostrar_toast(m, t)
        )

    def _selenium_por_worker(self, worker_id):
        if worker_id == 1:
            return self.selenium1
        elif worker_id == 2:
            return self.selenium2
        elif worker_id == 3:
            return self.selenium3
        else:
            raise ValueError("Worker inválido")

    def obter_timeout(self) -> int:
        try:
            return int(self.combo_timeout.currentText())
        except ValueError:
            return 120  # fallback seguro

    def _atualizar_contador_ui(self):
        texto = f"Processos extraídos: {self.processos_extraidos} / {self.total_processos}"
        self.label_contador.setText(texto)

    def carregar_posicao_janela(self):
        arquivo = "window_pos.txt"

        if os.path.exists(arquivo):
            try:
                with open(arquivo, "r") as f:
                    x, y = map(int, f.read().split(","))

                self.move(x, y)

            except Exception as e:
                logger.exception(
                    f"Erro durante processamento  {e}"
                )

                self.log_new(
                    f"⚠️ Erro ao restaurar posição da janela: {e}"
                )

    def salvar_posicao_janela(self):
        try:
            with open("window_pos.txt", "w") as f:
                f.write(f"{self.x()},{self.y()}")

        except Exception as e:
            logger.exception(
                f"Erro durante processamento : {e}"
            )
            self.log_new(
                f"⚠️ Erro ao salvar posição da janela: {e}"
            )

    def salvar_configuracoes(self):
        try:
            with open("config_ui.txt", "w", encoding="utf-8") as f:
                f.write(f"{self.combo_usuario.currentIndex()}\n")
                f.write(f"{self.combo_usuario_2.currentIndex()}\n")
                f.write(f"{self.combo_usuario_3.currentIndex()}\n")
                f.write(f"{self.combo_timeout.currentText()}\n")
                f.write(f"{self.combo_intervalo_reload.currentText()}\n")
                f.write(f"{self.combo_navegador.currentText()}\n")

        except Exception as e:
            self.log_new(f"⚠️ Erro ao salvar configurações: {e}")

    def carregar_configuracoes(self):

        try:

            if not os.path.exists("config_ui.txt"):
                return

            with open("config_ui.txt", "r", encoding="utf-8") as f:
                linhas = [x.strip() for x in f.readlines()]

            if len(linhas) >= 6:
                self.combo_usuario.setCurrentIndex(
                    int(linhas[0])
                )

                self.combo_usuario_2.setCurrentIndex(
                    int(linhas[1])
                )

                self.combo_usuario_3.setCurrentIndex(
                    int(linhas[2])
                )

                self.combo_timeout.setCurrentText(
                    linhas[3]
                )
                self.combo_intervalo_reload.setCurrentText(linhas[4])

                self.combo_navegador.setCurrentText(linhas[5])

                # força preencher usuário e senha
                self.on_usuario_selecionado(
                    self.combo_usuario.currentIndex()
                )

                self.on_usuario_selecionado_2(
                    self.combo_usuario_2.currentIndex()
                )

                self.on_usuario_selecionado_3(
                    self.combo_usuario_3.currentIndex()
                )

        except Exception as e:
            self.log_new(
                f"⚠️ Erro ao carregar configurações: {e}"
            )

    def closeEvent(self, event):

        # salva posição atual da janela
        self.salvar_posicao_janela()
        self.salvar_configuracoes()

        try:
            if hasattr(self, "selenium1"):
                self.selenium1.stop()

            if hasattr(self, "selenium2"):
                self.selenium2.stop()

            if hasattr(self, "selenium3"):
                self.selenium3.stop()

        except Exception:
            logger.exception(
                "Erro durante processamento"
            )
            pass

        event.accept()

    def toggle_monitor_abas(self):
        ativo = self.btn_monitor_abas.isChecked()

        self.btn_monitor_abas.setText(
            "🧠 Monitor abas: ON" if ativo else "🧠 Monitor abas: OFF"
        )
        self.log("🟢 Monitor ATIVADO" if ativo else "🔴 Monitor DESATIVADO")

        for attr in ("selenium1", "selenium2", "selenium3"):
            selenium = getattr(self, attr, None)
            if not selenium:
                continue
            if ativo:
                selenium.monitor_abas_ativo = True
                selenium.iniciar_monitor_abas()
            else:
                selenium.monitor_abas_ativo = False
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    w = MainApp()
    w.show()
    sys.exit(app.exec_())