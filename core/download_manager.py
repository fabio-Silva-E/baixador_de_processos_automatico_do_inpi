import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QTimer, QDateTime

from config.paths import DOWNLOAD_DIR, BASE_DIR


def _renomear_pdf_para_processo(self, worker_id, caminho_pdf):
    print(f"📄 RENOMEANDO worker {worker_id}")
    print("DEBUG RENAME")
    print("worker:", worker_id)
    print("numero:", self.numero_atual.get(worker_id))
    print("caminho:", caminho_pdf)
    try:
        numero = self.numero_atual.get(worker_id)
        if not numero:
            self.log_new(
                f"⚠️ Worker {worker_id} — Processo atual não definido para renomear PDF."
            )
            return

        nome_seguro = "".join(c for c in str(numero) if c.isalnum())
        pasta_worker = Path(self.download_dirs[worker_id])
        pasta_worker.mkdir(parents=True, exist_ok=True)

        novo_nome = f"{nome_seguro}.pdf"
        novo_caminho = pasta_worker / novo_nome

        if novo_caminho.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            novo_caminho = pasta_worker / f"{nome_seguro}_{ts}.pdf"

        caminho_pdf = Path(caminho_pdf)
        shutil.move(str(caminho_pdf), str(novo_caminho))

        self.log_new(
            f"📄 Worker {worker_id} — PDF renomeado para: {novo_caminho.name}"
        )

        if novo_caminho.exists():
            self._registrar_processo_concluido(numero)

            # 🔥 FIX #2 — limpa entrada de tentativas para liberar memória
            self.tentativas_por_processo.pop(numero, None)

            # 🧹 Limpa o histórico de downloads do navegador para não acumular na barra
            try:
                self.log_new(f"🧹 Worker {worker_id} — limpando histórico de downloads...")
                selenium = self._selenium_por_worker(worker_id)
                selenium.limpar_historico_downloads()
                self.log_new(f"✅ Worker {worker_id} — histórico de downloads limpo com sucesso")
            except Exception as e:
                self.log_new(f"⚠️ Worker {worker_id} — Erro ao limpar histórico downloads: {e}")

            # 🧹 Limpa o histórico de navegação do worker para não acumular URLs visitadas
            try:
                self.log_new(f"🧹 Worker {worker_id} — limpando histórico de navegação...")
                selenium = self._selenium_por_worker(worker_id)
                selenium.limpar_historico_navegacao()
                self.log_new(f"✅ Worker {worker_id} — histórico de navegação limpo com sucesso")
            except Exception as e:
                self.log_new(f"⚠️ Worker {worker_id} — Erro ao limpar histórico de navegação: {e}")

        else:
            self.log_new(
                f"⚠️ Worker {worker_id} — PDF não encontrado após renomear, processo NÃO registrado."
            )

    except Exception as e:
        self.log_new(
            f"❌ Worker {worker_id} — Erro ao renomear PDF: {e}"
        )


def _pdf_baixado_com_sucesso(self, worker_id, caminho_final):
    caminho_pdf = os.path.abspath(caminho_final)
    self.log(f"📥 Worker {worker_id} — PDF salvo: {caminho_pdf}")
    QTimer.singleShot(
        0, lambda: self._finalizar_processo_atual(worker_id)
    )

def wait_for_download(self, worker_id, timeout=120):

    pasta = Path(self.download_dirs[worker_id])

    self.log_new(
        f"⏳ Worker {worker_id} aguardando download..."
    )

    inicio = time.time()

    arquivos_iniciais = {
        f.name for f in pasta.glob("*")
    }

    while time.time() - inicio < timeout:

        arquivos_pdf = list(pasta.glob("*.pdf"))

        for arquivo in arquivos_pdf:

            if arquivo.name in arquivos_iniciais:
                continue

            if arquivo.with_suffix(".crdownload").exists():
                continue

            tamanho1 = arquivo.stat().st_size

            time.sleep(1)

            tamanho2 = arquivo.stat().st_size

            if tamanho1 != tamanho2:
                continue

            self.log_new(
                f"✅ Worker {worker_id} download concluído: "
                f"{arquivo.name}"
            )

            return str(arquivo)

        time.sleep(1)

    self.log_new(
        f"⌛ Worker {worker_id} timeout download"
    )

    return None
