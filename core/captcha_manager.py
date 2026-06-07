import logging
import traceback

import pyautogui

import time

from pyautogui import ImageNotFoundException
import requests
import threading

from config.settings import WAIT_MEDIUM, WAIT_SHORT, WAIT_LONG


from config.paths import  BASE_DIR

from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def iniciar_monitor_captcha(self):

    if getattr(self, "_monitor_captcha_ativo", False):
        return

    self._monitor_captcha_ativo = True

    threading.Thread(
        target=self._loop_monitor_captcha,
        daemon=True
    ).start()


def _loop_monitor_captcha(self):

    while self._monitor_captcha_ativo:

        for worker_id in (1, 2, 3):

            driver = getattr(
                self,
                f"driver{worker_id}",
                None
            )

            if not driver:
                continue

            try:

                modal = driver.find_element(
                    By.ID,
                    "janelaModalCaptchaDownload"
                )

                if modal.is_displayed():

                    self.log_new(
                        f"🧩 Captcha ativo worker {worker_id}"
                    )



            except NoSuchElementException:

                pass


            except WebDriverException as e:

                self.log_new(

                    f"Worker {worker_id} perdeu conexão real: {e}"

                )

        time.sleep(2)

def iniciar_solver_auto(self):
    if getattr(self, "_solver_ativo", False):
        return

    self._solver_ativo = True

    self._solver_thread = threading.Thread(
        target=self._loop_solver_button,
        daemon=True
    )
    self._solver_thread.start()



def detectar_worker_com_captcha(self):
    for wid in (1, 2, 3):
        lock = self._driver_locks[wid]
        driver = getattr(self, f"driver{wid}", None)

        if not driver:
            continue

        with lock:
            try:
                modal = driver.find_element(By.ID, "janelaModalCaptchaDownload")
                if modal.is_displayed():
                    return wid
            except:
                pass

            try:
                driver.find_element(By.CSS_SELECTOR, ".g-recaptcha")
                return wid
            except:
                pass

    return None


def _loop_solver_button(self):
    self._ultimo_solver_click = 0

    while self._solver_ativo:

        try:
            agora = time.time()

            # 🔹 Loop do Solver Button
            if agora - self._ultimo_solver_click > 1:
                if self.clicar_solver_button():
                    self._ultimo_solver_click = agora

            # 🔹 Loop do Try Again
            if self.clicar_try_again():
                self.log_new("🔄 Try Again clicado")

        except Exception as e:
            print(f"⚠️ Solver loop erro: {e}")

        time.sleep(0.8)


def parar_solver_auto(self):
    self._solver_ativo = False
    self.log_new("🛑 Solver automático parado")


def clicar_solver_button(self):

    #img_path = BASE_DIR / "solver_button.png"
    #
    #if not img_path.exists():
    #    self.log_new("❌ solver_button.png não encontrado")
    #    return False

    try:

        with self.pyautogui_lock:

            pos = pyautogui.locateCenterOnScreen(
                str(self.solver_img),
                confidence=0.78
            )

        if pos:

            with self.pyautogui_lock:
                pyautogui.moveTo(
                    pos.x,
                    pos.y,
                    duration=0.3
                )

                pyautogui.click()

            self.log_new(
                "🤖 Solver button clicado via PyAutoGUI"
            )

            return True

        return False

    except Exception as e:

        self.log_new(
            f"Erro PyAutoGUI: {e}"
        )

        return False

def clicar_try_again(self, confidence=0.8):

    modal_path = self.modal_try_again_img
    botao_path = self.botao_try_again_img

    if not modal_path.exists() or not botao_path.exists():
        return False

    try:

        modal = pyautogui.locateOnScreen(
            str(modal_path),
            confidence=confidence
        )

        if not modal:
            return False

        botao = pyautogui.locateCenterOnScreen(
            str(botao_path),
            confidence=confidence,
            region=modal
        )

        if botao:

            pyautogui.moveTo(botao.x, botao.y, duration=0.2)
            pyautogui.click()

            self.log("🔄 Botão Try Again clicado!")

            # 🔥 libera novamente os workers
            for wid in (1, 2, 3):
                self.captcha_retry[wid] = True

            return True

        return False

    except Exception as e:
        self.log_new(repr(e))
        return False

def tratar_modal_captcha(self, driver, worker_id):
    """
    Fluxo:
    - aguarda modal #janelaModalCaptchaDownload visível (ou .g-recaptcha)
    - tenta clicar checkbox do reCAPTCHA (dentro do iframe)
    - aguarda que o token apareça (no DOM: g-recaptcha-response ou input #recaptcha-token)
    - quando token presente, clica botão #captchaButton (Download)
    - aguarda download terminar e processa PDF
    """
    # impede múltiplas threads no mesmo worker
    if self.captcha_estado.get(worker_id, False):
        return None

    self.captcha_estado[worker_id] = True
    if not hasattr(self, "captcha_inicio"):
        self.captcha_inicio = {}

    self.captcha_inicio[worker_id] = time.time()
    try:
        self.log(f"[W{worker_id}] 🧩 aguardando modal...")
        # espera até o modal aparecer (ou timeout)
        t0 = time.time()
        modal = None
        while time.time() - t0 < WAIT_LONG:
            try:
                modal = driver.find_element(By.CSS_SELECTOR, "#janelaModalCaptchaDownload")
                if modal.is_displayed():
                    break
            except NoSuchElementException:
                # fallback: procurar .g-recaptcha direto
                try:
                    g = driver.find_element(By.CSS_SELECTOR, ".g-recaptcha")
                    if g.is_displayed():
                        break
                except NoSuchElementException:
                    pass
            time.sleep(1)
        if not modal:
            self.log_new("[captcha] modal não encontrado explicitamente — tentando detectar .g-recaptcha")
        else:
            self.log_new("[captcha] modal visível")
        # tenta clicar a checkbox do reCAPTCHA (iframe com src contendo 'anchor')
        iframe = self.selenium_get_recaptcha_iframe(driver)
        if iframe:
            try:
                driver.switch_to.frame(iframe)
                # checkbox id recaptcha-anchor
                try:
                    checkbox = WebDriverWait(driver, WAIT_SHORT).until(
                        EC.element_to_be_clickable((By.ID, "recaptcha-anchor"))
                    )
                    #checkbox.click()
                    try:
                        driver.execute_script(
                            "arguments[0].click();",
                            checkbox
                        )
                    except Exception:

                        checkbox = driver.find_element(
                            By.ID,
                            "recaptcha-anchor"
                        )

                        driver.execute_script(
                            "arguments[0].click();",
                            checkbox
                        )
                    self.log_new("[captcha] checkbox clicado")
                except Exception:
                    self.log_new(traceback.format_exc())
                finally:
                    driver.switch_to.default_content()
            except Exception as e:
                    self.log_new(
                        f"[captcha] erro switch_to.frame: {e}"
                    )
        else:
            self.log_new("[captcha] iframe do recaptcha não encontrado")
            self.log_new("[captcha] iframe não encontrado — aguardando novamente")
        #
        # Se você usa Buster: a extensão pode interagir com o desafio automaticamente.
        # Aqui aguardamos o token aparecer no DOM (g-recaptcha-response ou input#recaptcha-token)
        self.log_new("[captcha] aguardando token resolver (sem timeout)...")
        token = None

        if not hasattr(self, "ultimo_reload"):
            self.ultimo_reload = {}

        inicio_token = time.time()

        while time.time() - inicio_token < 90:

            ultimo = self.ultimo_reload.get(
                worker_id,
                0
            )

            # captcha travado
            if (
                    self.captcha_travado(worker_id, limite=10)
                    and time.time() - ultimo > 30
            ):
                self.log(
                    f"⏱️ Captcha travado no worker {worker_id}"
                )

                self.clicar_reload_duplo()

                self.log(
                    f"🔄 Reload executado worker {worker_id}"
                )

                self.ultimo_reload[worker_id] = time.time()

                self.captcha_inicio[worker_id] = time.time()

            # Try Again
            if self.captcha_retry.get(worker_id):

                self.captcha_retry[worker_id] = False

                self.captcha_inicio[worker_id] = time.time()

                token = None

                self.log(
                    f"🔄 Aguardando modal novamente worker {worker_id}"
                )

                try:

                    WebDriverWait(
                        driver,
                        30
                    ).until(
                        EC.visibility_of_element_located(
                            (
                                By.ID,
                                "janelaModalCaptchaDownload"
                            )
                        )
                    )

                    self.log(
                        f"✅ Modal reapareceu worker {worker_id}"
                    )

                    self.clicar_checkbox_recaptcha(driver)

                except Exception as e:

                    self.log(
                        f"❌ Modal não reapareceu: {e}"
                    )

                continue

            # recaptcha-token
            try:

                token_input = driver.find_element(
                    By.ID,
                    "recaptcha-token"
                )

                val = token_input.get_attribute(
                    "value"
                )

                if val and len(val) > 10:
                    token = val

                    self.log(
                        f"✅ Token encontrado worker {worker_id}"
                    )

                    break

            except NoSuchElementException:
                pass

            # g-recaptcha-response
            try:

                gr = driver.find_element(
                    By.CSS_SELECTOR,
                    "textarea.g-recaptcha-response"
                )

                val2 = gr.get_attribute(
                    "value"
                )

                if val2 and len(val2) > 10:
                    token = val2

                    self.log(
                        f"✅ Token encontrado worker {worker_id}"
                    )

                    break

            except NoSuchElementException:
                pass

            except WebDriverException as e:

                self.log(
                    f"❌ Worker {worker_id} perdeu driver: {e}"
                )

                return None

            time.sleep(1)
        if token:
            self.log_new(f"[captcha] token detectado (len={len(token)})")
            # injeta token em possíveis campos e aciona o botão download
            try:
                # tentar preencher g-recaptcha-response via JS (algumas páginas aceitam)
                script_set = """
                (function(t){
                    var ga = document.querySelector('textarea.g-recaptcha-response');
                    if(ga){ ga.value = t; ga.style.display='block'; }
                    var ri = document.getElementById('recaptcha-token');
                    if(ri) ri.value = t;
                    return true;
                })(arguments[0]);
                """
                driver.execute_script(script_set, token)
            except Exception as e:
                self.log_new(
                    f"Erro ao injetar token via JS: {e}"
                )
            # clica no botão #captchaButton (Download)
            try:
                btn = WebDriverWait(driver, WAIT_MEDIUM).until(
                    EC.element_to_be_clickable((By.ID, "captchaButton"))
                )
                btn.click()

                for _ in range(20):

                    if verificar_popup_erro_inpi(self, driver):
                        self.log(
                            f"❌ Worker {worker_id} recebeu erro do INPI"
                        )
                        return None

                    time.sleep(0.5)

                caminho_pdf = self.wait_for_download(
                    worker_id,
                    driver
                )

                # 🔥 LOOP DE ESPERA EXTRA
                timeout_pdf = time.time() + 120

                while time.time() < timeout_pdf:

                    if caminho_pdf:

                        caminho_pdf = Path(caminho_pdf)

                        if caminho_pdf.exists():
                            self.log(
                                f"✅ Worker {worker_id} PDF baixado"
                            )

                            return str(caminho_pdf)

                    time.sleep(1)

                    caminho_pdf = self.wait_for_download(worker_id, driver)

                self.log(
                    f"❌ Worker {worker_id} download timeout"
                )

                return None
            except Exception as e:
                self.log_new(f"[captcha] falha ao clicar #captchaButton: {e}")
        else:
            self.log_new("[captcha] token não detectado — talvez Buster não resolveu automaticamente.")
            self.log_new("[captcha] nenhum PDF detectado no diretório de download (timeout).")
    except Exception as e:
        self.log_new(f"[W{worker_id}] erro captcha: {e}")
    finally:

        self.captcha_estado[worker_id] = False

        if hasattr(self, "captcha_inicio"):
            self.captcha_inicio.pop(worker_id, None)

        self.log_new("[captcha] finalizado")

def selenium_get_recaptcha_iframe(self, driver):
    # procura iframe que contém 'anchor' (checkbox) ou 'api2/anchor'
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for fr in iframes:
            src = fr.get_attribute("src") or ""
            if "api2/anchor" in src or "recaptcha" in src and "anchor" in src:
                return fr
        # fallback: iframe title containing "reCAPTCHA"
        for fr in iframes:
            title = fr.get_attribute("title") or ""
            if "reCAPTCHA" in title or "recaptcha" in title.lower():
                return fr
    except Exception:
        pass
    return None

def clicar_imagem(
        self,
        timeout=15,
        confidence=0.85,
        clicar=True,
        delay=0.5
):
    """
    Localiza uma imagem PNG na tela e opcionalmente clica nela.
    :param nome_imagem: Nome do arquivo PNG (ex: 'captcha_checkbox.png')
    :param timeout: Tempo máximo de espera (segundos)
    :param confidence: Precisão da imagem (0.7 a 0.95)
    :param clicar: Se True, clica no centro da imagem
    :param delay: Delay após clicar
    :return: (x, y) ou None
    """
    caminho = BASE_DIR / "solver_button.png"
    if not caminho.exists():
        raise FileNotFoundError(f"Imagem não encontrada: {caminho}")
    inicio = time.time()
    while time.time() - inicio < timeout:
        pos = pyautogui.locateCenterOnScreen(
            str(caminho),
            confidence=confidence
        )
        if pos:
            if clicar:
                pyautogui.moveTo(pos.x, pos.y, duration=0.2)
                pyautogui.click()
                time.sleep(delay)
            return pos
        time.sleep(0.3)
    self.log_new(f"⚠️ Imagem não encontrada na tela: {caminho}")
    return None

def clicar_reload_duplo(self, confidence=0.85):
    caminho = self.reload_img

    self.log(f"🔍 Procurando reload: {caminho}")

    if not caminho.exists():
        self.log("❌ reload_button.png não encontrado")
        return False

    try:

        pos = pyautogui.locateCenterOnScreen(
            str(caminho),
            confidence=confidence
        )

        if not pos:
            self.log("❌ Reload não encontrado na tela")
            return False

        self.log(
            f"✅ Reload encontrado em X={pos.x} Y={pos.y}"
        )

        pyautogui.moveTo(
            pos.x,
            pos.y,
            duration=0.2
        )

        pyautogui.doubleClick(
            pos.x,
            pos.y,
            interval=0.3
        )

        self.log("🔄 Reload clicado 2x")

        return True

    except Exception as e:

        #self.log(
        #    f"❌ Erro reload: {e}"
        #)

        return False

def captcha_travado(self, worker_id, limite=10):

    inicio = self.captcha_inicio.get(worker_id)

    if inicio is None:
        return False

    return (time.time() - inicio) > limite


def excecao_thread(args):

    logging.critical(
        f"ERRO FATAL THREAD: {args.thread.name}",
        exc_info=(
            args.exc_type,
            args.exc_value,
            args.exc_traceback
        )
    )

threading.excepthook = excecao_thread

def clicar_checkbox_recaptcha(self, driver):

    iframe = self.selenium_get_recaptcha_iframe(driver)

    if not iframe:
        self.log_new("❌ iframe recaptcha não encontrado")
        return False

    try:

        driver.switch_to.default_content()

        driver.switch_to.frame(iframe)

        checkbox = WebDriverWait(
            driver,
            WAIT_SHORT
        ).until(
            EC.element_to_be_clickable(
                (By.ID, "recaptcha-anchor")
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            checkbox
        )

        self.log_new("✅ Checkbox recaptcha clicado")

        return True

    except Exception as e:

        self.log_new(
            f"Erro clicar checkbox: {e}"
        )

        return False

    finally:

        driver.switch_to.default_content()

def verificar_popup_erro_inpi(self, driver):

    try:

        elementos = driver.find_elements(
            By.XPATH,
            "//*[contains(text(),'Erro inesperado ao gerar PDF')]"
        )

        if elementos:

            self.log_new(
                "❌ Popup HTML do INPI detectado"
            )

            try:

                botao_ok = driver.find_element(
                    By.XPATH,
                    "//button[contains(., 'OK')]"
                )

                botao_ok.click()

            except Exception:
                pass

            return True

    except Exception:
        pass

    return False