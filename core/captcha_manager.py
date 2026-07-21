
import pyautogui

import time


import requests
import threading

from config.settings import WAIT_MEDIUM, WAIT_SHORT, WAIT_LONG


from config.paths import  BASE_DIR

from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, WebDriverException,
    ElementClickInterceptedException, UnexpectedAlertPresentException,
    NoAlertPresentException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


import pyautogui

pyautogui.screenshot("tela.png")

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

            except:
                pass

        # 🔥 FIX #4 — era 2s, agora 5s para reduzir carga de CPU/rede
        time.sleep(5)

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

        # 🔥 FIX #5 — era 0.8s, agora 2s para reduzir capturas de tela contínuas
        time.sleep(2)


def parar_solver_auto(self):
    self._solver_ativo = False
    self.log_new("🛑 Solver automático parado")


def clicar_solver_button(self):
    img_path = BASE_DIR / "solver_button.png"

    if not img_path.exists():
        self.log_new("❌ solver_button.png não encontrado")
        return False

    try:
        pos = pyautogui.locateCenterOnScreen(
            str(img_path),
            confidence=0.78
        )

        if pos:
            pyautogui.moveTo(pos.x, pos.y, duration=0.3)
            pyautogui.click()
            self.log_new("🤖 Solver button clicado via PyAutoGUI")
            return True
        else:
            self.log_new("⚠️ Solver button não encontrado na tela")
            return False

    except:
        pass

def clicar_try_again(self, confidence=0.8):

    modal_path = BASE_DIR / "modal_try_again.png"
    botao_path = BASE_DIR / "botao_try_again.png"

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

    except:
        pass

def tratar_modal_captcha(self, driver, worker_id):

    # impede múltiplas threads no mesmo worker
    if self.captcha_estado.get(worker_id, False):
        self.log(f"[W{worker_id}] ⛔ captcha_estado=True — aguardando liberação...")
        t_wait = time.time()
        while self.captcha_estado.get(worker_id, False) and time.time() - t_wait < 5:
            time.sleep(0.2)
        if self.captcha_estado.get(worker_id, False):
            self.log(f"[W{worker_id}] ❌ não liberou em 5s — abortando")
            return None
        self.log(f"[W{worker_id}] ✅ liberado — prosseguindo")

    self.captcha_estado[worker_id] = True
    if not hasattr(self, "captcha_inicio"):
        self.captcha_inicio = {}
    if not hasattr(self, "captcha_reload_count"):
        self.captcha_reload_count = {}

    self.captcha_inicio[worker_id] = time.time()

    try:
        # ── 1) AGUARDA MODAL ──────────────────────────────────────────────
        self.log(f"[W{worker_id}] 🧩 aguardando modal... WAIT_LONG={WAIT_LONG}s")
        t0 = time.time()
        modal = None
        while time.time() - t0 < WAIT_LONG:
            try:
                modal = driver.find_element(By.CSS_SELECTOR, "#janelaModalCaptchaDownload")
                if modal.is_displayed():
                    self.log(f"[W{worker_id}] ✅ modal visível t={time.time() - t0:.1f}s")
                    break
            except NoSuchElementException:
                try:
                    g = driver.find_element(By.CSS_SELECTOR, ".g-recaptcha")
                    if g.is_displayed():
                        self.log(f"[W{worker_id}] ✅ g-recaptcha visível")
                        break
                except NoSuchElementException:
                    pass
            except Exception as e:
                self.log(f"[W{worker_id}] ❌ ERRO NO LOOP MODAL: {type(e).__name__}: {e}")
                break
            self.log(f"[W{worker_id}] loop t={time.time() - t0:.1f}s aguardando modal...")
            time.sleep(1)

        if modal:
            self.log("[captcha] modal visível")
        else:
            self.log("[captcha] modal não encontrado explicitamente — tentando detectar .g-recaptcha")

        # ── 2) CLICA CHECKBOX ─────────────────────────────────────────────
        iframe = self.selenium_get_recaptcha_iframe(driver)
        self.log(f"[W{worker_id}] iframe={'encontrado' if iframe else 'NÃO encontrado'}")

        if iframe:
            try:
                driver.switch_to.frame(iframe)
                try:
                    checkbox = WebDriverWait(driver, WAIT_SHORT).until(
                        EC.element_to_be_clickable((By.ID, "recaptcha-anchor"))
                    )
                    checkbox.click()
                    self.log_new("[captcha] checkbox clicado")
                except Exception:
                    self.log_new("[captcha] falha ao clicar checkbox")
                finally:
                    driver.switch_to.default_content()
            except Exception:
                self.log_new("[captcha] erro switch_to.frame")
        else:
            self.log_new("[captcha] iframe do recaptcha não encontrado")

        # ── 3) AGUARDA TOKEN ──────────────────────────────────────────────
        token = None
        timeout = self.obter_timeout()
        inicio = time.time()

        while time.time() - inicio < timeout:

            # 3a) TOKEN PRIMEIRO
            try:
                t_input = driver.find_element(By.ID, "recaptcha-token")
                val = t_input.get_attribute("value")
                if val and len(val) > 10:
                    token = val
                    break
            except NoSuchElementException:
                pass
            try:
                gr = driver.find_element(By.CSS_SELECTOR, "textarea.g-recaptcha-response")
                val2 = gr.get_attribute("value")
                if val2 and len(val2) > 10:
                    token = val2
                    break
            except NoSuchElementException:
                pass
            except Exception:
                pass

            # 3b) TRY AGAIN
            if self.captcha_retry.get(worker_id):
                self.log(f"🔄 Reiniciando captcha worker {worker_id}")
                self.captcha_retry[worker_id] = False
                self.captcha_estado[worker_id] = False
                return self.tratar_modal_captcha(driver, worker_id)

            # 3c) SESSÃO EXPIRADA
            if self.sessao_expirada(driver):
                self.log(f"[W{worker_id}] ⚠️ sessão expirada no loop token — abortando")
                try:
                    self.garantir_login(driver)
                    self.log(f"[W{worker_id}] ✅ login refeito")
                except Exception as e:
                    self.log(f"[W{worker_id}] ❌ falha relogin:")
                return None

            # 3d) CAPTCHA TRAVADO
            if self.captcha_travado(worker_id):
                self.log(f"🔥 ENTROU NO CAPTCHA TRAVADO W{worker_id}")
                self.captcha_reload_count[worker_id] = \
                    self.captcha_reload_count.get(worker_id, 0) + 1

                while self.captcha_travado(worker_id):
                    try:
                        t_input = driver.find_element(By.ID, "recaptcha-token")
                        val = t_input.get_attribute("value")
                        if val and len(val) > 10:
                            token = val
                            self.log(f"[W{worker_id}] ✅ token detectado antes do reload — saindo")
                            break
                    except NoSuchElementException:
                        pass
                    try:
                        gr = driver.find_element(By.CSS_SELECTOR, "textarea.g-recaptcha-response")
                        val2 = gr.get_attribute("value")
                        if val2 and len(val2) > 10:
                            token = val2
                            self.log(f"[W{worker_id}] ✅ token detectado antes do reload — saindo")
                            break
                    except NoSuchElementException:
                        pass

                    if token:
                        break

                    if self.sessao_expirada(driver):
                        self.log(f"[W{worker_id}] ⚠️ sessão expirou durante reload — abortando")
                        try:
                            self.garantir_login(driver)
                        except Exception:
                            pass
                        return None
                    ok = self.clicar_reload_duplo(driver, worker_id)
                    self.log(f"🔥 Reload clicado ok={ok} — aguardando 3s...")
                    self.captcha_inicio[worker_id] = time.time()
                    time.sleep(self.obter_intervalo_reload())
                    if self.captcha_retry.get(worker_id) or \
                            not self.captcha_estado.get(worker_id, False):
                        break

                self.captcha_inicio[worker_id] = time.time()
                continue

            time.sleep(1)

        # ── 4) PROCESSA TOKEN ─────────────────────────────────────────────
        if token:
            self.log(f"[captcha] token detectado (len={len(token)})")
            try:
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
            except Exception:
                self.log_new("Erro ao injetar token via JS")

            caminho_pdf = self.aguardar_botao_download(driver, worker_id)
            return caminho_pdf

        else:
            self.log(f"[W{worker_id}] ❌ token não detectado — timeout={timeout}s")
            return None

    except Exception as e:
        import traceback
        self.log(f"[W{worker_id}] 💥 ERRO GERAL captcha: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        return None

    finally:
        self.captcha_estado[worker_id] = False
        if hasattr(self, "captcha_inicio"):
            self.captcha_inicio.pop(worker_id, None)
        self.log(f"[W{worker_id}] finally executado")


def selenium_get_recaptcha_iframe(self, driver):
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for fr in iframes:
            src = fr.get_attribute("src") or ""
            if "api2/anchor" in src or "recaptcha" in src and "anchor" in src:
                return fr
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

def clicar_reload_duplo(self, driver, worker_id):
    """Clica no botão reload do reCAPTCHA via Selenium no iframe bframe."""
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        bframe = None
        for fr in iframes:
            src = fr.get_attribute("src") or ""
            if "bframe" in src or "api2/bframe" in src:
                bframe = fr
                break

        if not bframe:
            self.log(f"[W{worker_id}] ❌ reload: iframe bframe não encontrado (desafio ainda não abriu)")
            return False

        driver.switch_to.frame(bframe)
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "recaptcha-reload-button"))
            )
            driver.execute_script("arguments[0].click();", btn)
            driver.execute_script("arguments[0].click();", btn)
            self.log(f"[W{worker_id}] 🔄 Reload clicado via Selenium (bframe)")
            return True
        finally:
            driver.switch_to.default_content()

    except Exception as e:
        self.log_new(f"[W{worker_id}] ❌ reload erro: {type(e).__name__}: {e}")
        return False


def captcha_travado(self, worker_id, limite=8):

    inicio = self.captcha_inicio.get(worker_id)

    if inicio is None:
        return False

    decorrido = time.time() - inicio

    self.log(
        f"DEBUG W{worker_id}: {decorrido:.1f}s"
    )

    return decorrido > limite

def sessao_expirada(self, driver):

    try:

        erro = driver.find_element(
            By.ID,
            "msgErroCaptcha"
        )

        texto = erro.text.lower()

        return "sessão expirada" in texto or \
               "sess" in texto and "expirada" in texto

    except Exception:
        return False

def limpar_cache_navegador(self, driver):

    try:

        self.log_new("🧹 Limpando cache do Chrome...")

        driver.execute_cdp_cmd(
            "Network.clearBrowserCache",
            {}
        )

        driver.execute_cdp_cmd(
            "Network.clearBrowserCookies",
            {}
        )

        self.log_new("✅ Cache limpo")

        return True

    except Exception as e:

        self.log_new(
            f"❌ Erro limpar cache: {e}"
        )

        return False

def verificar_sessao_apos_download(self, driver, worker_id):
    if self.sessao_expirada(driver):
        self.log(f"⚠️ Worker {worker_id} — sessão expirada após clique no download")
        try:
            self.garantir_login(driver)
            self.log(f"✅ Worker {worker_id} — login refeito")
        except Exception as e:
            self.log(f"❌ Worker {worker_id} — falha relogin: {e}")
        return False
    return True

def aguardar_botao_download(self, driver, worker_id, timeout=60):
    self.log(f"[W{worker_id}] 🔘 aguardando botão download...")
    t0 = time.time()
    clicou = False

    while time.time() - t0 < timeout:

        if self.sessao_expirada(driver):
            self.log(f"[W{worker_id}] ⚠️ sessão expirada — abortando")
            try:
                self.garantir_login(driver)
                self.log(f"[W{worker_id}] ✅ login refeito")
            except Exception as e:
                self.log(f"[W{worker_id}] ❌ falha relogin: {e}")
            return None

        pasta = Path(self.download_dirs[worker_id])
        em_andamento = list(pasta.glob("*.crdownload"))
        if em_andamento:
            self.log(f"[W{worker_id}] ⏳ download em andamento — aguardando arquivo...")
            caminho_pdf = self.wait_for_download(worker_id)
            if caminho_pdf and Path(caminho_pdf).exists():
                self.log(f"✅ Worker {worker_id} PDF baixado")
                return str(caminho_pdf)
            sessao_ok = self.verificar_sessao_apos_download(driver, worker_id)
            if not sessao_ok:
                return None
            self.log(f"❌ Worker {worker_id} download timeout")
            return None

        if not clicou:
            try:
                btn = driver.find_element(By.ID, "captchaButton")
                visivel = btn.is_displayed()
                habilitado = btn.is_enabled()
                disabled_attr = btn.get_attribute("disabled")
                self.log(f"[W{worker_id}] 🔘 captchaButton visivel={visivel} habilitado={habilitado} disabled={disabled_attr} t={time.time()-t0:.1f}s")

                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", btn)
                self.log(f"[W{worker_id}] 🖱 botão download clicado t={time.time() - t0:.1f}s")
                clicou = True

                t_aguarda = time.time()
                while time.time() - t_aguarda < 5:
                    if list(pasta.glob("*.crdownload")):
                        self.log(f"[W{worker_id}] ✅ .crdownload detectado — download iniciado")
                        break
                    time.sleep(0.3)
                else:
                    self.log(f"[W{worker_id}] ⚠️ .crdownload não apareceu — tentando novamente t={time.time()-t0:.1f}s")
                    clicou = False
                    time.sleep(1)
                    continue

                self.log(f"⏳ Worker {worker_id} aguardando download...")
                caminho_pdf = self.wait_for_download(worker_id)
                if caminho_pdf and Path(caminho_pdf).exists():
                    self.log(f"✅ Worker {worker_id} PDF baixado")
                    return str(caminho_pdf)
                sessao_ok = self.verificar_sessao_apos_download(driver, worker_id)
                if not sessao_ok:
                    return None
                self.log(f"[W{worker_id}] 🔄 download não concluiu — tentando reclicaar")
                clicou = False
                continue

            except NoSuchElementException:
                self.log(f"[W{worker_id}] ⏳ #captchaButton não encontrado t={time.time()-t0:.1f}s")
                time.sleep(1)
                continue
            except Exception as e:
                self.log(f"[W{worker_id}] ❌ erro aguardar botão: {type(e).__name__}: {e}")
                time.sleep(1)
                continue
        else:
            time.sleep(0.5)

    self.log(f"[W{worker_id}] ❌ timeout {timeout}s aguardando botão download")
    return None
