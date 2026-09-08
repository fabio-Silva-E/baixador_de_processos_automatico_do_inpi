import sys
import socket

# 🔧 FIX: trava de segurança global de rede. Sem isso, qualquer chamada de
# rede (Selenium/chromedriver, requests, etc.) que não defina seu próprio
# timeout fica bloqueada PARA SEMPRE se o outro lado parar de responder
# (foi a causa raiz confirmada dos travamentos do app: threads presas
# indefinidamente em socket.readinto aguardando o chromedriver). Isso
# precisa vir ANTES de qualquer import que crie sockets (ex.: ui.app ->
# selenium), pois alguns módulos leem socket.getdefaulttimeout() uma
# única vez, no momento do import.
socket.setdefaulttimeout(30)

# 🔧 FIX: declara o processo como DPI-aware pro Windows. Sem isso, em
# qualquer maquina com escala de tela != 100% (muito comum em notebooks
# novos, Windows costuma vir com 125%/150% por padrao), o Windows
# "virtualiza" a resolucao pro processo — as imagens de referencia do
# PyAutoGUI (solver_button.png, botao_try_again.png etc, capturadas a
# 100%) deixam de bater com o que a tela realmente mostra, e
# locateOnScreen() simplesmente nao encontra nada ("nenhuma acao").
# Precisa vir o mais cedo possivel, antes de qualquer screenshot ou
# janela ser criada.
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import logging
from logging.handlers import RotatingFileHandler
import threading
import traceback
import faulthandler

from PyQt5.QtWidgets import QApplication
from ui.app import MainApp
from ui.licenca_ui import verificar_ou_pedir_licenca
import psutil
import os

process = psutil.Process(os.getpid())

# 🔧 FIX: logging.basicConfig(filename="crash.log", ...) NUNCA fazia
# efeito — "from ui.app import MainApp" (linha acima) já dispara o
# logging.basicConfig() de utils/log_utils.py primeiro (configurando
# logs/app.log). Como só a PRIMEIRA chamada de basicConfig() no processo
# tem efeito, essa aqui era ignorada silenciosamente pelo Python — nunca
# existiu, de fato, um crash.log. Agora usamos um logger dedicado, com seu
# próprio handler (RotatingFileHandler, limitado a 5 MB x 3 arquivos),
# que funciona independente da ordem de import.
crash_logger = logging.getLogger("CRASH")
crash_logger.setLevel(logging.DEBUG)
_crash_handler = RotatingFileHandler(
    "crash.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8"
)
_crash_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(threadName)s | %(message)s")
)
crash_logger.addHandler(_crash_handler)

crash_logger.info(f"RAM: {process.memory_info().rss / 1024 / 1024:.1f} MB")

# 🔧 FIX: removido o faulthandler.enable(arquivo) mirando em
# "fatal_dump.log" que existia aqui. Só existe UM alvo de dump de crash
# fatal por processo — ui/app.py (MainApp.__init__) já chama
# faulthandler.enable() de novo, mirando em "faulthandler.log", e essa
# chamada (que roda DEPOIS, quando MainApp() é instanciado) sempre vencia
# e substituía esta. "fatal_dump.log" nunca recebia o dump de verdade.
# Mantém só faulthandler.log como único arquivo de crash fatal — já tem
# rotação por tamanho configurada em app.py.


def excecao_global(tipo, valor, tb):
    erro = "".join(traceback.format_exception(tipo, valor, tb))
    crash_logger.critical(f"ERRO FATAL GLOBAL\n{erro}")


sys.excepthook = excecao_global


def excecao_thread(args):
    erro = "".join(traceback.format_exception(
        args.exc_type, args.exc_value, args.exc_traceback
    ))
    crash_logger.critical(f"ERRO FATAL THREAD: {args.thread.name}\n{erro}")


threading.excepthook = excecao_thread


if __name__ == "__main__":

    try:

        app = QApplication(sys.argv)

        # ── VERIFICAÇÃO DE LICENÇA ────────────────────────────────
        if not verificar_ou_pedir_licenca():
            sys.exit(0)
        # ─────────────────────────────────────────────────────────

        window = MainApp()
        window.show()

        codigo = app.exec_()

        crash_logger.info(f"Aplicação encerrada. ExitCode={codigo}")

        sys.exit(codigo)

    except Exception:
        crash_logger.exception("ERRO FATAL NO LOOP PRINCIPAL")
        raise
