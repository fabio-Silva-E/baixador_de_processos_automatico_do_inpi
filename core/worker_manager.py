import traceback

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
            self.worker_finished.emit(
                self.worker_id
            )
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
    self.processando[worker_id] = False
    QTimer.singleShot(
        0, lambda: self._processar_proximo(worker_id)
    )


def _finalizar_processo_atual(self, worker_id):
    self.log_new(f"✅ FINALIZAR worker {worker_id}")
    print(f"🏁 FINALIZANDO worker {worker_id}")
    self.log_new(
        f"📌 Processo atual antes limpar: "
        f"{self.numero_atual.get(worker_id)}"
    )

    self.processando[worker_id] = False

    self.numero_atual[worker_id] = None

    if hasattr(self, "_workers"):
        self._workers.pop(worker_id, None)

    self.processos_extraidos += 1

    self._atualizar_contador_ui()

    self.log_new(
        f"🔄 Agendando próximo processo worker {worker_id}"
    )

    QTimer.singleShot(
        0,
        lambda: self._processar_proximo(worker_id)
    )
