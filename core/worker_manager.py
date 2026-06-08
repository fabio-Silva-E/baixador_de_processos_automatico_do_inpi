import logging
import traceback
import threading
from PyQt5.QtCore import QThread, pyqtSignal, QTimer


class SeleniumWorker(QThread):
    worker_finished = pyqtSignal(int)

    error = pyqtSignal(int, str)

    def __init__(self, app, worker_id):
        super().__init__()
        self.app = app
        self.worker_id = worker_id

    def run(self):
        try:
            print(f"THREAD START {self.worker_id}")

            driver = {
                1: self.app.driver1,
                2: self.app.driver2,
                3: self.app.driver3
            }.get(self.worker_id)

            if driver is None:
                raise ValueError("Driver inválido")

            self.app.log(f"🚀 Worker {self.worker_id} iniciando")

            self.app.abrir_detalhe_processo(driver, self.worker_id)

            self.app.log(f"🏁 Worker {self.worker_id} finalizou")
            # ✅ worker_finished NÃO é emitido aqui —
            # abrir_detalhe_processo já chama _finalizar ou _repetir diretamente.
            # Emitir aqui causava corrida entre o retry e o finalizar.
        except Exception:
            import traceback
            print(traceback.format_exc())
            self.error.emit(self.worker_id, traceback.format_exc())


def _processar_proximo(self, worker_id):
    self.log_new(f"🟡 _processar_proximo chamado Worker {worker_id}")

    if self.processando.get(worker_id):
        self.log_new(f"⛔ Worker {worker_id} já está processando")
        return

    if worker_id == 1:
        fila = self.processos_1
    elif worker_id == 2:
        fila = self.processos_2
    elif worker_id == 3:
        fila = self.processos_3
    else:
        self.log_new(f"❌ Worker inválido: {worker_id}")
        return

    self.log_new(f"📦 Worker {worker_id} fila restante: {len(fila)}")

    if not fila:
        self.log(f"🏁 Worker {worker_id} finalizou fila")
        return

    self.processando[worker_id] = True

    numero = fila.popleft()

    self.numero_atual[worker_id] = numero

    self.tentativas_por_processo.setdefault(numero, 0)

    self.log_new(
        f"🚀 Worker {worker_id} iniciou processo {numero}"
    )

    if not hasattr(self, "_workers"):
        self._workers = {}

    worker = SeleniumWorker(self, worker_id)

    worker.worker_finished.connect(
        self._finalizar_processo_atual
    )

    worker.error.connect(self._erro_worker)

    self._workers[worker_id] = worker

    self.log_new(f"🧵 Worker thread START {worker_id}")

    worker.start()


def _erro_worker(self, worker_id, mensagem):

    self.log_new(
        f"💥 Worker {worker_id} erro"
    )

    self.log_new(mensagem)

    self.processando[worker_id] = False

    QTimer.singleShot(
        0,
        lambda wid=worker_id: self._processar_proximo(wid)
    )


def _finalizar_processo_atual(self, worker_id):

    try:

        self.log_new(
            f"🏁 FINALIZAR worker {worker_id} "
            f"thread={threading.current_thread().name}"
        )

        processo = self.numero_atual.get(worker_id)

        self.log_new(
            f"📌 Processo atual antes limpar: {processo}"
        )

        self.processando[worker_id] = False

        self.log_new(
            f"✅ processando[{worker_id}] = False"
        )

        self.numero_atual[worker_id] = None

        self.log_new(
            f"✅ numero_atual[{worker_id}] = None"
        )

        if hasattr(self, "_workers"):

            self.log_new(
                f"🗑 Removendo worker {worker_id}"
            )

            self._workers.pop(worker_id, None)

        self.log_new(
            f"🔄 Agendando próximo processo worker {worker_id}"
        )

        QTimer.singleShot(
            0,
            lambda wid=worker_id: self._processar_proximo(wid)
        )

        self.log_new(
            f"✅ QTimer.singleShot criado worker {worker_id}"
        )

    except Exception:

        erro = traceback.format_exc()

        logging.exception(
            f"💥 ERRO EM _finalizar_processo_atual "
            f"worker={worker_id}"
        )

        self.log_new(erro)
