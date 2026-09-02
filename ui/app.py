import os
import subprocess
import threading
import time
import sys
import psutil
import os
from config.paths import BASE_DIR

# INSTÂNCIA ÚNICA + LIMPEZA DE PROCESSOS ÓRFÃOS (só Windows)
#
# Resolve dois problemas:
#   1) Fechar o programa pelo Gerenciador de Tarefas mata só o processo
#      principal — os Chromes/chromedriver que ele abriu ficam órfãos,
#      rodando pra sempre.
#   2) Reabrir o programa nessas condições cria uma SEGUNDA instância
#      inteira, empilhando programas e Chromes duplicados.
#
# Solução:
#   - Job Object do Windows: todo Chrome/chromedriver aberto por este
#     processo passa a "morrer junto" com ele, não importa como o
#     processo principal seja encerrado (fechamento normal, crash, ou
#     finalizado à força pelo Gerenciador de Tarefas).
#   - Mutex nomeado: impede abrir uma segunda janela do programa
#     enquanto já existe uma rodando.
#   - Limpeza na abertura: mata qualquer chromedriver.exe/chrome.exe
#     órfão de uma execução anterior a essa correção, identificado
#     pelo caminho do projeto aparecendo na linha de comando.
# =========================================================

def _configurar_job_object_matar_filhos():
    """Cria um Job Object do Windows e associa o processo atual a ele,
    com JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE — isso faz TODOS os processos
    filhos (chromedriver.exe, que por sua vez abre chrome.exe) serem
    finalizados automaticamente quando este processo morrer, de
    qualquer jeito."""
    import ctypes

    try:
        JobObjectExtendedLimitInformation = 9
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.windll.kernel32

        job = kernel32.CreateJobObjectW(None, None)

        if not job:
            print("⚠️ não consegui criar Job Object — limpeza automática de Chromes órfãos desativada")
            return None

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        kernel32.SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info)
        )

        processo_atual = kernel32.GetCurrentProcess()

        ok = kernel32.AssignProcessToJobObject(job, processo_atual)

        if not ok:
            print("⚠️ não consegui associar o processo ao Job Object")
            return None

        print("🔒 Job Object configurado — Chromes abertos por este programa serão fechados junto com ele, mesmo se finalizado à força.")

        return job

    except Exception as e:
        print(f"⚠️ erro configurando Job Object: {e}")
        return None


def _garantir_instancia_unica():
    """Cria um mutex nomeado do Windows — se já existir (outra instância
    do programa rodando), retorna False em vez de abrir uma segunda
    janela."""
    import ctypes

    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW(None, False, "SeleniumBase_InterfaceExtracao_Mutex")
        ERROR_ALREADY_EXISTS = 183
        return ctypes.GetLastError() != ERROR_ALREADY_EXISTS

    except Exception as e:
        print(f"⚠️ erro checando instância única: {e}")
        return True  # em caso de erro, deixa abrir normalmente


def _limpar_processos_orfaos():
    """Mata chromedriver.exe/chrome.exe órfãos de execuções anteriores a
    essa correção, identificados pelo caminho do projeto aparecendo na
    linha de comando (--user-data-dir apontando pra uma pasta
    perfil_chrome_* deste projeto)."""
    try:
        base = str(BASE_DIR).replace("'", "''")

        comando = (
            "Get-CimInstance Win32_Process -Filter "
            "\"Name='chromedriver.exe' or Name='chrome.exe'\" "
            "| Where-Object { $_.CommandLine -like '*" + base + "*' } "
            "| Select-Object -ExpandProperty ProcessId"
        )

        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-Command", comando],
            capture_output=True,
            text=True,
            timeout=15
        )

        pids = [p.strip() for p in resultado.stdout.splitlines() if p.strip().isdigit()]

        for pid in pids:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    capture_output=True,
                    timeout=5
                )
            except Exception:
                pass

        if pids:
            print(f"🧹 {len(pids)} processo(s) órfão(s) de execuções anteriores finalizado(s).")

    except Exception as e:
        print(f"⚠️ não consegui checar processos órfãos: {e}")


def _limpar_trava_webdriver_manager():
    """Remove qualquer arquivo de trava (.wdm-lock-*) do webdriver-manager
    que tenha ficado 'preso' de uma execução anterior morta à força —
    sem isso, TODA tentativa futura de abrir um Chrome trava pra sempre
    esperando essa trava liberar (erro 'Timed out waiting for
    webdriver-manager lock'). Como já garantimos instância única do
    programa antes de chegar aqui, não existe risco de apagar uma trava
    de uma instância legítima ainda rodando."""
    try:
        pasta_wdm = Path.home() / ".wdm"

        if not pasta_wdm.exists():
            return

        travas = list(pasta_wdm.glob(".wdm-lock-*"))

        for trava in travas:
            try:
                trava.unlink()
                print(f"🔓 Trava presa do webdriver-manager removida: {trava.name}")
            except Exception as e:
                print(f"⚠️ não consegui remover trava {trava.name}: {e}")

    except Exception as e:
        print(f"⚠️ não consegui checar travas do webdriver-manager: {e}")


from config.paths import DOWNLOAD_DIR
from config.settings import URL_INPI
from core.perfil_manager import resetar_todos_perfis
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
    liberar_acesso_peticiones,
    reiniciar_sessao_worker
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
    resetar_todos_perfis = resetar_todos_perfis
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
    ip_signal = pyqtSignal(str)
    selenium_pronto_signal = pyqtSignal(bool, str)
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
    reiniciar_sessao_worker = reiniciar_sessao_worker
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
                    4: threading.RLock(),
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
            3: False,
            4: False
        }
        self.captcha_retry = {
            1: False,
            2: False,
            3: False,
            4: False
        }

        self.log_signal.connect(self._log_ui)
        self.selenium_pronto_signal.connect(self._on_selenium_pronto)

        self.tentativas_por_processo = {}
        self.MAX_TENTATIVAS = 2

        # diretórios de download por worker
        self.download_dirs = {}

        # 1️⃣ Flags e dados
        self.parar_loop = False
        self.loop_ativo = False

        # 🔢 quantidade de workers/navegadores em paralelo (1 a 4) — 4
        # workers exige um 4º login (aba extra na coluna de login)
        self._qtd_workers = 3

        self.processando = {1: False, 2: False, 3: False, 4: False}

        self.numero_atual = {
            1: None,
            2: None,
            3: None,
            4: None
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
        for wid in (1, 2, 3, 4):
            pasta = Path(DOWNLOAD_DIR) / f"worker_{wid}"
            pasta.mkdir(parents=True, exist_ok=True)
            self.download_dirs[wid] = pasta
        self.carregar_usuarios_excel()

        for u in self.usuarios:
            self.combo_usuario.addItem(u["usuario"])
            self.combo_usuario_2.addItem(u["usuario"])
            self.combo_usuario_3.addItem(u["usuario"])
            self.combo_usuario_4.addItem(u["usuario"])

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

        self.combo_usuario_4.currentIndexChanged.connect(
            self.on_usuario_selecionado_4
        )

        # depois restaura
        self.carregar_configuracoes()
        # 🔌 CONECTA OS COMBOS AOS MÉTODOS
        self.combo_usuario.currentIndexChanged.connect(self.on_usuario_selecionado)
        self.combo_usuario_2.currentIndexChanged.connect(self.on_usuario_selecionado_2)
        self.combo_usuario_3.currentIndexChanged.connect(self.on_usuario_selecionado_3)
        self.combo_usuario_4.currentIndexChanged.connect(self.on_usuario_selecionado_4)

        # aplica a visibilidade correta do Login Aba 4 conforme a
        # quantidade de workers restaurada de config_ui.txt
        self._atualizar_visibilidade_worker4()

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

        self.btn_monitor_abas = QPushButton("🧠 Monitor abas: ON")
        self.btn_monitor_abas.setCheckable(True)
        self.btn_monitor_abas.setChecked(True)
        self._monitor_abas_ligado = True
        self.btn_monitor_abas.clicked.connect(self.toggle_monitor_abas)

        coluna_login.addWidget(self.btn_monitor_abas)


        # ===== dropdown de timeout =====
        coluna_login.addWidget(QLabel("Timeout Captcha (segundos)"))

        self.combo_timeout = QComboBox()
        self.combo_timeout.addItem("Selecione o timeout")
        self.combo_timeout.model().item(0).setEnabled(False)

        self.combo_timeout.addItems(["30", "60", "120", "180", "300"])
        self.combo_timeout.setCurrentText("120")
        self._timeout_captcha = 120
        self.combo_timeout.currentTextChanged.connect(self._on_timeout_mudou)

        coluna_login.addWidget(self.combo_timeout)

        coluna_login.addWidget(QLabel("⏱ Intervalo Reload (segundos)"))
        self.combo_intervalo_reload = QComboBox()
        self.combo_intervalo_reload.addItems(["1", "2", "3", "5", "8", "10"])
        self.combo_intervalo_reload.setCurrentText("3")
        self._intervalo_reload = 3
        self.combo_intervalo_reload.currentTextChanged.connect(self._on_intervalo_reload_mudou)
        coluna_login.addWidget(self.combo_intervalo_reload)

        # ===== QUANTIDADE DE WORKERS =====
        coluna_login.addWidget(QLabel("🧵 Quantidade de Workers"))
        self.combo_qtd_workers = QComboBox()
        self.combo_qtd_workers.addItems(["1", "2", "3", "4"])
        self.combo_qtd_workers.setCurrentText("3")
        self.combo_qtd_workers.currentTextChanged.connect(self._on_qtd_workers_mudou)
        coluna_login.addWidget(self.combo_qtd_workers)

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

        # ===== USUÁRIO 4 (só aparece com 4 workers selecionados) =====
        self.widget_login_4 = QWidget()
        layout_login_4 = QVBoxLayout(self.widget_login_4)
        layout_login_4.setContentsMargins(0, 0, 0, 0)

        layout_login_4.addWidget(QLabel("Login Aba 4"))
        self.combo_usuario_4 = QComboBox()
        self.combo_usuario_4.addItem("Selecione o usuário INPI")
        self.combo_usuario_4.model().item(0).setEnabled(False)

        self.input_usuario_4 = QLineEdit()
        self.input_senha_4 = QLineEdit()
        self.input_senha_4.setEchoMode(QLineEdit.Password)

        layout_login_4.addWidget(self.combo_usuario_4)
        layout_login_4.addWidget(self.input_usuario_4)
        layout_login_4.addWidget(self.input_senha_4)

        self.widget_login_4.setVisible(False)
        coluna_login.addWidget(self.widget_login_4)

        self.btn_iniciar = QPushButton("🌐 Abrir site INPI")
        self.btn_iniciar.clicked.connect(self.iniciar_selenium)
        coluna_login.addWidget(self.btn_iniciar)

        # 🧹 reseta cookies/cache/sessão de TODOS os perfis de navegador já
        # usados pelo programa (chrome, edge, brave — o que existir em
        # disco), preservando extensões instaladas manualmente (Modo
        # Desenvolvedor)
        self.btn_resetar_perfis_login = QPushButton("🧹 Resetar Perfis dos Navegadores")
        self.btn_resetar_perfis_login.clicked.connect(self.resetar_perfis_navegador)
        coluna_login.addWidget(self.btn_resetar_perfis_login)

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


        # 🔧 FIX: antes chamava resetar_perfis_chrome, uma função quebrada
        # (só olhava a pasta "chrome", passava o nome do PERFIL em vez do
        # nome do NAVEGADOR pra resetar_todos_perfis, usava tkinter.messagebox
        # num app Qt, e referenciava self.status que não existe nesta UI).
        # Agora os dois botões de reset usam a mesma função corrigida.
        self.btn_resetar_perfis_processos = QPushButton("🧹 Resetar Perfis dos Navegadores")
        self.btn_resetar_perfis_processos.clicked.connect(self.resetar_perfis_navegador)
        coluna_processos.addWidget(self.btn_resetar_perfis_processos)

        
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
        # 🔗 ADICIONA AO LAYOUT PRINCIPAL
        # ==================================================
        self.layout.addLayout(coluna_login, 2)
        self.layout.addLayout(coluna_processos, 2)
        self.layout.addLayout(coluna_logs, 3)

    def _log_ui(self, mensagem):
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.console_log.append(f"[{timestamp}] {mensagem}")

        # 🔥 FIX #1 — limita o log a 300 linhas para não travar a UI
        doc = self.console_log.document()
        while doc.blockCount() > 300:
            cursor = self.console_log.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

        self.console_log.ensureCursorVisible()
        self.label_status.setText(f"Status: {mensagem}")

    def _iniciar_monitor_ip(self):
        self.ip_signal.connect(self.label_ip.setText)
        self._ip_check_em_andamento = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.atualizar_ip)
        self.timer.start(5000)
        self.atualizar_ip()

    def atualizar_ip(self):
        # 🔧 FIX: `vpn.ip_atual()` faz uma requisicao de rede que, mesmo com
        # timeout=5 no requests, pode travar no handshake SSL (visto no
        # faulthandler.log preso por minutos em ssl.py do_handshake) --
        # problema conhecido do Windows quando a validacao de certificado
        # faz uma checagem de revogacao que ignora o timeout do socket.
        # Como essa funcao roda direto no QTimer da thread da UI, um unico
        # travamento congela a janela inteira. Rodando em thread separada,
        # mesmo que essa chamada trave, a UI continua respondendo.
        if self._ip_check_em_andamento:
            return
        self._ip_check_em_andamento = True

        def worker():
            try:
                ip = self.vpn.ip_atual()
            finally:
                self._ip_check_em_andamento = False
            self.ip_signal.emit(f"🌍 IP: {ip}")

        threading.Thread(target=worker, daemon=True).start()

    def trocar_navegador(self, texto):
        from core.selenium_controller import SeleniumController
        mapa = {
            "Edge": "edge",
            "Chrome": "chrome",
            "Brave": "brave",
        }
        SeleniumController.NAVEGADOR = mapa.get(texto, "edge")
        self.log(f"🌐 Navegador selecionado: {texto} — terá efeito ao reabrir os browsers")

    def obter_intervalo_reload(self) -> int:
        # 🔧 FIX: le um atributo Python simples, cacheado pela thread da UI,
        # em vez de chamar self.combo_intervalo_reload.currentText() direto
        # — essa funcao e chamada de dentro das threads de worker (fluxo de
        # captcha), e widgets do Qt nao sao thread-safe. Acesso concorrente
        # a um QComboBox de fora da thread da UI e a causa mais provavel do
        # crash confirmado no Event Viewer (0xc0000409 dentro do
        # Qt5Core.dll).
        return getattr(self, "_intervalo_reload", 3)

    def _on_intervalo_reload_mudou(self, texto):
        try:
            self._intervalo_reload = int(texto)
        except ValueError:
            self._intervalo_reload = 3

    def _on_qtd_workers_mudou(self, texto):
        try:
            self._qtd_workers = int(texto)
        except ValueError:
            self._qtd_workers = 3
        self._atualizar_visibilidade_worker4()

    def _atualizar_visibilidade_worker4(self):
        # 🔥 4 workers exige um 4º login — o bloco "Login Aba 4" só
        # aparece quando 4 workers estão selecionados
        if hasattr(self, "widget_login_4"):
            self.widget_login_4.setVisible(self._qtd_workers >= 4)

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

    def on_usuario_selecionado_4(self, index):
        if index <= 0:
            self.input_usuario_4.clear()
            self.input_senha_4.clear()
            return
        user = self.usuarios[index - 1]
        self.input_usuario_4.setText(user["usuario"])
        self.input_senha_4.setText(user["senha"])

    def on_usuario_selecionado(self, index):
        if index == 0:
            self.input_usuario.clear()
            self.input_senha.clear()
            return
        user = self.usuarios[index - 1]
        self.input_usuario.setText(user["usuario"])
        self.input_senha.setText(user["senha"])


    def parar_processamento(self):
        if not self.loop_ativo:
            return
        self.loop_ativo = False
        self.processando = {1: False, 2: False, 3: False, 4: False}
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
        workers_ativos = list(range(1, self._qtd_workers + 1))

        if not all(hasattr(self, f"driver{i}") for i in workers_ativos):
            self.ui_warning(
                "Chrome não iniciado",
                f"Abra os {len(workers_ativos)} Chrome(s) antes de iniciar a extração."
            )
            self.log_new("⚠️ Tentativa de iniciar lote sem Chromes abertos.")
            return

        if not self.processos:
            self.ui_warning("Aviso", "Nenhum processo carregado.")
            return

        self.loop_ativo = True
        self.lista_processos.setEnabled(False)

        self.processos_filas = {wid: deque() for wid in workers_ativos}

        for i, p in enumerate(self.processos):
            wid = workers_ativos[i % len(workers_ativos)]
            self.processos_filas[wid].append(p)

        self.total_processos = len(self.processos)
        self.processos_extraidos = 0
        self._atualizar_contador_ui()

        self.log_new(f"🚀 Iniciando processamento em lote ({len(workers_ativos)} Chrome(s))...")

        for wid in workers_ativos:
            self._processar_proximo(wid)

    def carregar_usuarios_excel(self):
        self.usuarios = []

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
        QTimer.singleShot(0, lambda: QMessageBox.warning(self, titulo, msg))

    def ui_error(self, titulo, msg):
        QTimer.singleShot(0, lambda: QMessageBox.critical(self, titulo, msg))

    def log(self, mensagem):
        logger.error(mensagem)
        self.log_signal.emit(mensagem)

    def log_new(self, mensagem):
        logger.error(mensagem)

    def iniciar_selenium(self):
        # 🔧 FIX: abrir os navegadores e navegar ate URL_INPI faz chamadas
        # de rede (driver.get) que, numa maquina com internet mais lenta,
        # podem travar por bastante tempo. Como esse metodo roda direto no
        # slot do clique do botao (thread da UI/Qt), um travamento aqui
        # congela a janela inteira — no faulthandler.log da maquina
        # secundaria a MainThread ficou presa exatamente nesse driver.get()
        # dentro de iniciar_selenium. Mesma causa raiz do bug ja corrigido
        # em atualizar_ip(): tirar a chamada de rede da thread da UI.
        if getattr(self, "_iniciando_selenium", False):
            return
        self._iniciando_selenium = True
        self.btn_iniciar.setEnabled(False)

        workers_ativos = list(range(1, self._qtd_workers + 1))
        self.log(f"Iniciando {len(workers_ativos)} Chrome(s) independente(s)...")

        def worker():
            try:
                # encerra qualquer sessão anterior (inclusive de uma
                # quantidade de workers diferente da atual)
                for wid in (1, 2, 3, 4):
                    selenium_antigo = getattr(self, f"selenium{wid}", None)
                    driver_antigo = getattr(self, f"driver{wid}", None)
                    if selenium_antigo and driver_antigo:
                        selenium_antigo.stop()

                time.sleep(3)

                seleniums_novos = []

                for wid in workers_ativos:
                    selenium_novo = SeleniumController()
                    selenium_novo.worker_id = wid
                    driver_novo = selenium_novo.start()
                    driver_novo.get(URL_INPI)

                    setattr(self, f"selenium{wid}", selenium_novo)
                    setattr(self, f"driver{wid}", driver_novo)
                    seleniums_novos.append(selenium_novo)

                if self._monitor_abas_ligado:
                    for selenium in seleniums_novos:
                        selenium.monitor_abas_ativo = True
                        selenium.iniciar_monitor_abas()

                self.log_new(f"✅ {len(workers_ativos)} Chrome(s) iniciado(s) com sucesso")

                self.iniciar_solver_auto()
                self._ultimo_solver_click = 0
                self.iniciar_monitor_captcha()

                self.selenium_pronto_signal.emit(True, "")

            except Exception as e:
                logger.exception("Erro durante processamento")
                self.selenium_pronto_signal.emit(False, str(e))

            finally:
                self._iniciando_selenium = False

        threading.Thread(target=worker, daemon=True).start()

    def _on_selenium_pronto(self, sucesso, erro):
        # roda na thread da UI (conectado via signal), seguro pra mexer em
        # widgets
        self.btn_iniciar.setEnabled(True)
        if not sucesso:
            QMessageBox.critical(self, "Erro", erro)

    def resetar_perfis_navegador(self):
        """
        Limpa cookies/cache/histórico/sessão de TODOS os perfis de
        navegador já usados pelo programa (profile_1, profile_2, ...),
        preservando extensões instaladas manualmente. Sempre reseta os
        perfis do Chrome (navegador usado por este usuário) e também os
        do navegador atualmente selecionado no combo, caso seja outro.
        """
        confirmar = QMessageBox.question(
            self,
            "Resetar perfis do Chrome",
            "Isso vai limpar cookies/cache/histórico/sessão de TODOS os "
            "perfis do Chrome usados pelo programa (profile_1, profile_2, "
            "etc.), preservando as extensões instaladas manualmente.\n\n"
            "⚠️ Feche todas as janelas do Chrome abertas pelo programa "
            "antes de continuar — com o navegador aberto, o reset pode "
            "falhar em alguns arquivos.\n\n"
            "Deseja continuar?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirmar != QMessageBox.Yes:
            return

        from core.perfil_manager import resetar_todos_perfis
        from config.paths import PROFILE_PATH

        # 🔧 FIX: varre TODAS as subpastas de navegador que já existirem em
        # disco (chrome, edge, brave, ...) em vez de supor só "chrome" + o
        # navegador selecionado no combo no momento — do jeito antigo,
        # perfis de um navegador usado no passado (mas não selecionado
        # agora) nunca eram limpos.
        if PROFILE_PATH.exists():
            navegadores = sorted(p.name for p in PROFILE_PATH.iterdir() if p.is_dir())
        else:
            navegadores = []

        resetados_total = []

        for navegador in navegadores:
            resetados = resetar_todos_perfis(navegador)
            for nome in resetados:
                identificador = f"{navegador}/{nome}"
                resetados_total.append(identificador)
                self.log_new(f"🧹 Perfil resetado: {identificador}")

        if not resetados_total:
            self.log_new("⚠️ Nenhum perfil encontrado para resetar")
            QMessageBox.information(
                self,
                "Resetar perfis",
                "Nenhum perfil encontrado (nenhum navegador foi aberto ainda pelo programa)."
            )
            return

        QMessageBox.information(
            self,
            "Concluído",
            f"{len(resetados_total)} perfil(is) resetado(s):\n" + "\n".join(resetados_total)
        )

    def _usuario_atual(self, worker_id):
        if worker_id == 1:
            return self.input_usuario
        elif worker_id == 2:
            return self.input_usuario_2
        elif worker_id == 3:
            return self.input_usuario_3
        elif worker_id == 4:
            return self.input_usuario_4
        return None

    def _senha_atual(self, worker_id):
        if worker_id == 1:
            return self.input_senha
        elif worker_id == 2:
            return self.input_senha_2
        elif worker_id == 3:
            return self.input_senha_3
        elif worker_id == 4:
            return self.input_senha_4
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
        elif worker_id == 4:
            return self.selenium4
        else:
            raise ValueError("Worker inválido")

    def _worker_id_por_driver(self, driver):
        for wid in range(1, self._qtd_workers + 1):
            if getattr(self, f"driver{wid}", None) is driver:
                return wid
        return None

    def obter_timeout(self) -> int:
        # 🔧 FIX: mesma razao do obter_intervalo_reload — le o atributo
        # cacheado em vez do widget, pra nao acessar QComboBox de fora da
        # thread da UI.
        return getattr(self, "_timeout_captcha", 120)

    def _on_timeout_mudou(self, texto):
        try:
            self._timeout_captcha = int(texto)
        except ValueError:
            pass

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
                logger.exception(f"Erro durante processamento  {e}")
                self.log_new(f"⚠️ Erro ao restaurar posição da janela: {e}")

    def salvar_posicao_janela(self):
        try:
            with open("window_pos.txt", "w") as f:
                f.write(f"{self.x()},{self.y()}")
        except Exception as e:
            logger.exception(f"Erro durante processamento : {e}")
            self.log_new(f"⚠️ Erro ao salvar posição da janela: {e}")

    def salvar_configuracoes(self):
        try:
            with open("config_ui.txt", "w", encoding="utf-8") as f:
                f.write(f"{self.combo_usuario.currentIndex()}\n")
                f.write(f"{self.combo_usuario_2.currentIndex()}\n")
                f.write(f"{self.combo_usuario_3.currentIndex()}\n")
                f.write(f"{self.combo_timeout.currentText()}\n")
                f.write(f"{self.combo_intervalo_reload.currentText()}\n")
                f.write(f"{self.combo_navegador.currentText()}\n")
                f.write(f"{self.combo_usuario_4.currentIndex()}\n")
                f.write(f"{self.combo_qtd_workers.currentText()}\n")
        except Exception as e:
            self.log_new(f"⚠️ Erro ao salvar configurações: {e}")

    def carregar_configuracoes(self):
        try:
            if not os.path.exists("config_ui.txt"):
                return
            with open("config_ui.txt", "r", encoding="utf-8") as f:
                linhas = [x.strip() for x in f.readlines()]
            if len(linhas) >= 6:
                self.combo_usuario.setCurrentIndex(int(linhas[0]))
                self.combo_usuario_2.setCurrentIndex(int(linhas[1]))
                self.combo_usuario_3.setCurrentIndex(int(linhas[2]))
                self.combo_timeout.setCurrentText(linhas[3])
                self.combo_intervalo_reload.setCurrentText(linhas[4])
                self.combo_navegador.setCurrentText(linhas[5])
                self.on_usuario_selecionado(self.combo_usuario.currentIndex())
                self.on_usuario_selecionado_2(self.combo_usuario_2.currentIndex())
                self.on_usuario_selecionado_3(self.combo_usuario_3.currentIndex())
            if len(linhas) >= 8:
                self.combo_usuario_4.setCurrentIndex(int(linhas[6]))
                self.combo_qtd_workers.setCurrentText(linhas[7])
                self.on_usuario_selecionado_4(self.combo_usuario_4.currentIndex())
        except Exception as e:
            self.log_new(f"⚠️ Erro ao carregar configurações: {e}")

    def closeEvent(self, event):
        self.salvar_posicao_janela()
        self.salvar_configuracoes()
        try:
            for wid in (1, 2, 3, 4):
                selenium = getattr(self, f"selenium{wid}", None)
                if selenium:
                    selenium.stop()
        except Exception:
            logger.exception("Erro durante processamento")
            pass
        event.accept()


    def toggle_monitor_abas(self):
        ativo = self.btn_monitor_abas.isChecked()
        self._monitor_abas_ligado = ativo
        self.btn_monitor_abas.setText(
            "🧠 Monitor abas: ON" if ativo else "🧠 Monitor abas: OFF"
        )
        self.log("🟢 Monitor ATIVADO" if ativo else "🔴 Monitor DESATIVADO")
        for attr in ("selenium1", "selenium2", "selenium3", "selenium4"):
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
