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

import logging
import threading
import traceback
import faulthandler

from PyQt5.QtWidgets import QApplication
from ui.app import MainApp
from ui.licenca_ui import verificar_ou_pedir_licenca
import psutil
import os

process = psutil.Process(os.getpid())

logging.basicConfig(
    filename="crash.log",
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s"
)

logging.info(f"RAM: {process.memory_info().rss / 1024 / 1024:.1f} MB")

arquivo = open("fatal_dump.log", "a", buffering=1)
faulthandler.enable(arquivo)


def excecao_global(tipo, valor, tb):
    erro = "".join(traceback.format_exception(tipo, valor, tb))
    logging.critical(f"ERRO FATAL GLOBAL\n{erro}")


sys.excepthook = excecao_global


def excecao_thread(args):
    erro = "".join(traceback.format_exception(
        args.exc_type, args.exc_value, args.exc_traceback
    ))
    logging.critical(f"ERRO FATAL THREAD: {args.thread.name}\n{erro}")


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

        logging.info(f"Aplicação encerrada. ExitCode={codigo}")

        sys.exit(codigo)

    except Exception:
        logging.exception("ERRO FATAL NO LOOP PRINCIPAL")
        raise
