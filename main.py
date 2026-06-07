import sys
import logging
import threading
import traceback
import faulthandler

from PyQt5.QtWidgets import QApplication
from ui.app import MainApp
import psutil
import os

process = psutil.Process(os.getpid())

logging.info(
    f"RAM: {process.memory_info().rss / 1024 / 1024:.1f} MB"
)
# dump de falhas graves
arquivo = open("fatal_dump.log", "a", buffering=1)
faulthandler.enable(arquivo)

logging.basicConfig(
    filename="crash.log",
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s"
)

def excecao_global(tipo, valor, tb):

    erro = "".join(
        traceback.format_exception(
            tipo,
            valor,
            tb
        )
    )

    logging.critical(
        f"ERRO FATAL GLOBAL\n{erro}"
    )

sys.excepthook = excecao_global


def excecao_thread(args):

    erro = "".join(
        traceback.format_exception(
            args.exc_type,
            args.exc_value,
            args.exc_traceback
        )
    )

    logging.critical(
        f"ERRO FATAL THREAD: {args.thread.name}\n{erro}"
    )

threading.excepthook = excecao_thread


if __name__ == "__main__":

    try:

        app = QApplication(sys.argv)

        window = MainApp()
        window.show()

        codigo = app.exec_()

        logging.info(
            f"Aplicação encerrada. ExitCode={codigo}"
        )

        sys.exit(codigo)

    except Exception:

        logging.exception(
            "ERRO FATAL NO LOOP PRINCIPAL"
        )

        raise