# ui/app.py
import pyautogui
import os
import time
import sys
import tempfile
import shutil
import requests
import threading

from config.paths import DOWNLOAD_DIR
from config.settings import WAIT_MEDIUM, URL_INPI, URL_DESTINO
from core.selenium_controller import SeleniumController
from core.processo_manager import selecionar_processo, atualizar_lista_processos, abrir_detalhe_processo
print(requests.get("https://api.ipify.org").text)
from config.paths import PROFILE_PATH, BASE_DIR, EXCEL_PROCESSOS_PATH
from collections import deque
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime
from openpyxl import Workbook, load_workbook


from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLineEdit, QListWidget,
    QLabel, QMessageBox, QApplication, QProgressDialog, QTextEdit, QMessageBox, QComboBox
)
from PyQt5.QtCore import QTimer, QDateTime, QThread, pyqtSignal

# Selenium imports
from selenium import webdriver

from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, WebDriverException,
    ElementClickInterceptedException, UnexpectedAlertPresentException,
    NoAlertPresentException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
    clicar_imagem
)

class MainApp(QWidget):
    iniciar_monitor_captcha =iniciar_monitor_captcha
    _loop_monitor_captcha =_loop_monitor_captcha
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

        self.arquivo_concluidos = "processos_concluidos.txt"
        self.processos = []
        self.processos_concluidos = set()

        self.vpn = VPNManager()



        # 2️⃣ Criar UI PRIMEIRO
        self._criar_interface()
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

        # 🔌 CONECTA OS COMBOS AOS MÉTODOS
        self.combo_usuario.currentIndexChanged.connect(self.on_usuario_selecionado)
        self.combo_usuario_2.currentIndexChanged.connect(self.on_usuario_selecionado_2)
        self.combo_usuario_3.currentIndexChanged.connect(self.on_usuario_selecionado_3)

    def _criar_interface(self):
        self.setWindowTitle("INPI - vs(1.3)")
        self.setGeometry(50, 30, 700, 50)

        # 🔹 Layout principal
        self.layout = QHBoxLayout(self)

        # ==================================================
        # 🟦 COLUNA LOGIN
        # ==================================================
        coluna_login = QVBoxLayout()

        self.label_ip = QLabel("🌍 IP: ---")
        coluna_login.addWidget(self.label_ip)
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

        self.btn_parar = QPushButton("⏹ Parar")
        self.btn_parar.clicked.connect(self.parar_processamento)

        coluna_processos.addWidget(self.btn_buscar)
        coluna_processos.addWidget(self.btn_parar)

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

    def log_new(self, mensagem):

        pass

    def log(self, mensagem):
        self.log_signal.emit(mensagem)


    def iniciar_selenium(self):
        self.log("Iniciando 3 Chromes independentes...")

        try:
            # Fecha se já existir
            if hasattr(self, "driver1") and self.driver1:
                self.selenium1.stop()

            if hasattr(self, "driver2") and self.driver2:
                self.selenium2.stop()

            if hasattr(self, "driver3") and self.driver2:
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

            self.log_new("✅ Três Chromes iniciados com sucesso")

            self.iniciar_solver_auto()
            #self.iniciar_try_again_auto()
            self._ultimo_solver_click = 0
            self.iniciar_monitor_captcha()
        except Exception as e:
           QMessageBox.critical(self, "Erro", str(e))





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




    def closeEvent(self, event):
        try:
            if hasattr(self, "selenium1"):
                self.selenium1.stop()
            if hasattr(self, "selenium2"):
                self.selenium2.stop()
            if hasattr(self, "selenium3"):
                self.selenium3.stop()
        except:
            pass

        event.accept()


# Se você quer testar este arquivo standalone (sem main.py),
# comente a importação em main.py e execute este módulo diretamente.
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    w = MainApp()
    w.show()
    sys.exit(app.exec_())
