from pathlib import Path

from selenium.common import NoSuchElementException, UnexpectedAlertPresentException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
import time
from PyQt5.QtCore import QTimer
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from openpyxl import Workbook, load_workbook
from config.paths import EXCEL_PROCESSOS_PATH
from config.settings import WAIT_MEDIUM, URL_DESTINO
from core.network_utils import aguardar_rede, internet_disponivel



def wait_clickable(self, driver, locator, timeout=30):

    try:
        return WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )

    except TimeoutException:

        if not internet_disponivel():

            self.log_new(
                "🌐 Internet caiu durante espera."
            )

            if aguardar_rede():

                return WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable(locator)
                )

        raise

def wait_element(self, driver, locator, timeout=30):

    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )

    except TimeoutException:

        if not internet_disponivel():

            self.log_new(
                "🌐 Timeout causado por falta de internet."
            )

            if aguardar_rede():
                return WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located(locator)
                )

        raise

def tentar_clicar_botao_pdf(
    self,
    driver,
    worker_id,
    numero
):

    try:

        self.log_new(
            f"📄 Worker {worker_id} procurando PDF"
        )

        elemento = self.wait_clickable(
            driver,
            (
                By.XPATH,
                "//div[@id='389' or @id='394']/ancestor::tr//img[contains(@class,'salvaDocumento')]"
            ),
            timeout=20
        )



        if not elemento:

            self.log_new(
                f"❌ Worker {worker_id} PDF não encontrado"
            )

            return None

        elemento.click()

        self.log_new(
            f"🖱 Worker {worker_id} clicou PDF"
        )

        self.wait_element(
            driver,
            (By.ID, "janelaModalCaptchaDownload")
        )

        self.log_new(
            f"🧩 Worker {worker_id} captcha aberto"
        )

        return self.tratar_modal_captcha(
            driver,
            worker_id
        )

    except Exception as e:

        self.log_new(
            f"❌ Worker {worker_id} erro PDF: {e}"
        )

        return None

def selecionar_processo(self, item):
    if self.processando:
        return  # ignora clique durante processamento em lote
    numero = item.text()
    self.entry_processo.setText(numero)
    self.log(f"📌 Processo selecionado: {numero}")
def _registrar_processo_concluido(self, numero):
    if not numero:
        self.log_new(
            "⚠️ Tentativa de registrar processo concluído inválido."
        )
        return

    with open(
        self.arquivo_concluidos,
        "a",
        encoding="utf-8"
    ) as f:
        f.write(str(numero) + "\n")

    self.processos_concluidos.add(numero)
def _registrar_processo_descartado(self, numero):

    if not numero:
        self.log_new(
            "⚠️ Tentativa de registrar processo descartado inválido."
        )
        return

    with open(
        self.arquivo_descartados,
        "a",
        encoding="utf-8"
    ) as f:
        f.write(str(numero) + "\n")

    if not hasattr(self, "processos_descartados"):
        self.processos_descartados = set()

    self.processos_descartados.add(numero)

    self.log_new(
        f"🚫 Processo descartado registrado: {numero}"
    )


def atualizar_lista_processos(self):
    self.lista_processos.clear()
    self.processos = []
    try:
        if not EXCEL_PROCESSOS_PATH.exists():
            raise FileNotFoundError(
                f"Arquivo não encontrado: {EXCEL_PROCESSOS_PATH}"
            )
        wb = load_workbook(EXCEL_PROCESSOS_PATH, data_only=True)
        ws = wb.active
        header = ws["A1"].value
        if header != "Numero_Processo":
        #if header != "processo":
            raise ValueError(
                "A coluna A deve se chamar 'Numero_Processo'"
            )
        vistos = set()
        for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
            if not row or not row[0]:
                continue
            numero = str(row[0]).strip()
            # ignora duplicados e concluídos
            if numero in vistos or numero in self.processos_concluidos:
                continue
            vistos.add(numero)
            self.processos.append(numero)
            self.lista_processos.addItem(numero)
        self.total_processos = len(self.processos)
        self._atualizar_contador_ui()
        self.log(f"📄 {len(self.processos)} processos carregados do Excel.")
    except Exception as e:
        self.ui_error(
            "Erro Excel",
            f"Falha ao carregar processos do Excel"
        )
        self.log_new(f"Falha ao carregar processos do Excel")


#def possui_servico_389_ou_394(self, driver):
#    """
#    Retorna:
#    (True, None) → pode processar
#    (False, motivo) → deve pular e registrar descartado
#    """
#
#    try:
#        elementos = driver.find_elements(
#            By.XPATH,
#            "//a[normalize-space()]"
#        )
#
#        servicos_encontrados = {
#            el.text.strip() for el in elementos if el.text.strip()
#        }
#
#        self.log(f"📄 Serviços encontrados:")
#
#        bloqueio = {
#            "161", "304", "414", "530",
#            "301", "303", "305",
#            "401", "507"
#        }
#
#        intersecao = servicos_encontrados.intersection(bloqueio)
#
#        if intersecao:
#            motivo = f"bloqueio_servico_{','.join(intersecao)}"
#            self.log_new(f"⏭️ BLOQUEADO: {motivo}")
#            return False, motivo
#
#        if "389" in servicos_encontrados or "394" in servicos_encontrados:
#            self.log("📄 Serviço 389/394 detectado")
#            return True, None
#
#        return False, "sem_servico_relevante"
#
#    except NoSuchElementException:
#        return False, "servico_nao_encontrado"

def possui_servico_389_ou_394(self, driver):

    elementos = driver.find_elements(
        By.XPATH,
        "//a[normalize-space()='389' or normalize-space()='394']"
    )

    if elementos:
        self.log("📄 Serviço 389 ou 394 detectado")
        return True

    self.log_new("📄 Serviço 389/394 NÃO encontrado")
    return False

def _repetir_processo_atual(self, worker_id, motivo):

    numero = self.numero_atual[worker_id]

    self.log_new(
        f"🔁 REPEAT worker {worker_id} "
        f"processo {numero}"
    )

    self.log_new(f"📌 Motivo retry: {motivo}")

    self.tentativas_por_processo.setdefault(numero, 0)

    self.tentativas_por_processo[numero] += 1

    self.log_new(
        f"📌 Tentativa atual: "
        f"{self.tentativas_por_processo[numero]}"
    )

    if self.tentativas_por_processo[numero] >= self.MAX_TENTATIVAS:

        self.log_new(
            f"❌ Processo {numero} excedeu tentativas"
        )

        self.numero_atual[worker_id] = None

        self.processando[worker_id] = False

        self.log_new(
            f"🔄 Chamando próximo worker {worker_id}"
        )

        QTimer.singleShot(
            0,
            lambda: self._processar_proximo(worker_id)
        )

        return

    self.numero_atual[worker_id] = None

    self.processando[worker_id] = False

    self.log_new(
        f"⏳ Worker {worker_id} aguardará 3s antes retry"
    )

    QTimer.singleShot(
        3000,
        lambda: self._processar_proximo(worker_id)
    )

def abrir_detalhe_processo(self, driver, worker_id):
    try:

        numero = self.numero_atual.get(worker_id)

        if not numero:
            self.log_new(f"❌ Worker {worker_id} sem número")
            return

        self.log_new(
            f"🚀 PIPELINE START worker {worker_id} | {numero}"
        )

        # ==========================================
        # LOGIN
        # ==========================================
        self.garantir_login(driver)

        # ==========================================
        # PESQUISA
        # ==========================================
        try:
            driver.get(URL_DESTINO)

        except Exception:

            if not aguardar_rede():
                raise Exception(
                    "Internet indisponível."
                )

            driver.get(URL_DESTINO)

        campo = self.wait_element(
            driver,
            (By.NAME, "NumPedido"),
            timeout=30
        )

        campo.clear()
        campo.send_keys(numero)
        campo.submit()

        # detalhe
        link = self.wait_clickable(
            driver,
            (
                By.CSS_SELECTOR,
                "a[href*='detail']"
            ),
            timeout=20
        )

        driver.execute_script(
            "arguments[0].click();",
            link
        )

        self.wait_element(
            driver,
            (By.TAG_NAME, "body"),
            timeout=20
        )

        time.sleep(2)

        # serviço
        ok = self.possui_servico_389_ou_394(driver)

        if not ok:

            # 🚀 sempre conclui
            self._registrar_processo_concluido(numero)
            self.processos_extraidos += 1
            self._atualizar_contador_ui()
            # 🚫 se for bloqueio, também registra descartado
            #if motivo and "bloqueio" in motivo:
            #    self._registrar_processo_descartado(numero)
            #self._finalizar_processo_atual(worker_id)
            return
        # ==========================================
        # PETIÇÕES
        # ==========================================
        self.log(
            f"📂 Worker {worker_id} liberando petições"
        )

        self.garantir_acesso_peticiones(driver)

        self.liberar_acesso_peticiones(driver)

        self.log(
            f"✅ Worker {worker_id} petições liberadas"
        )

        time.sleep(2)
        # pdf
        caminho_pdf = self._fluxo_pdf(
            driver,
            worker_id,
            numero
        )
        self.log_new(
            f"DEBUG caminho_pdf={caminho_pdf}"
        )
        if not caminho_pdf:
            raise Exception("PDF não baixado")

        self.log_new(
            f"DEBUG iniciando rename {caminho_pdf}"
        )

        # renomear
        novo_pdf = self._renomear_pdf_para_processo(
            worker_id,
            caminho_pdf
        )

        self.log_new(
            f"✅ PDF final: {novo_pdf}"
        )

        # ✅ Só registra como concluído se o rename foi bem-sucedido
        if novo_pdf:
            self._registrar_processo_concluido(numero)
        else:
            self.log_new(
                f"⚠️ Worker {worker_id} — rename falhou, processo {numero} NÃO registrado."
            )
            raise Exception("Falha ao renomear PDF")
        self.log_new(
            f"DEBUG registrando concluído {numero}"
        )
        self.processos_extraidos += 1
        self._atualizar_contador_ui()
        # finalizar
        #self._finalizar_processo_atual(worker_id)
        return
    except Exception as e:

        import traceback

        self.log_new(traceback.format_exc())

        if not internet_disponivel():

            self.log_new(

                "🌐 Internet caiu durante processamento."

            )

            if aguardar_rede():
                self.log_new(
                    "🌐 Internet voltou."
                )

        self._repetir_processo_atual(
            worker_id,
            str(e)
        )
from pathlib import Path
import time

def _fluxo_pdf(self, driver, worker_id, numero):

    self.log(
        f"📥 Worker {worker_id} iniciando fluxo PDF"
    )

    caminho_pdf = self.tentar_clicar_botao_pdf(
        driver,
        worker_id,
        numero
    )

    self.log(
        f"📥 Worker {worker_id} retorno captcha: {caminho_pdf}"
    )

    if not caminho_pdf:

        self.log(
            f"❌ Worker {worker_id} PDF não encontrado"
        )

        return None

    caminho_pdf = Path(caminho_pdf)

    self.log(
        f"📄 Worker {worker_id} verificando arquivo: {caminho_pdf}"
    )

    # aguarda até 60 segundos pelo download
    for tentativa in range(60):

        if caminho_pdf.exists():

            self.log(
                f"✅ Worker {worker_id} arquivo encontrado após {tentativa}s"
            )

            break

        time.sleep(1)

    else:

        self.log(
            f"❌ Worker {worker_id} arquivo inexistente: {caminho_pdf}"
        )

        return None

    # Chrome ainda pode estar escrevendo
    crdownload = Path(str(caminho_pdf) + ".crdownload")

    for tentativa in range(30):

        if not crdownload.exists():
            break

        self.log(
            f"⏳ Worker {worker_id} aguardando fim download..."
        )

        time.sleep(1)

    self.log(
        f"✅ Worker {worker_id} PDF OK"
    )
    self.log_new(
        f"DEBUG PDF FINAL: {caminho_pdf}"
    )
    return caminho_pdf

