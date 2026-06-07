
import os
import time

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, WebDriverException,
    ElementClickInterceptedException, UnexpectedAlertPresentException,
    NoAlertPresentException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config.paths import PROFILE_PATH, DOWNLOAD_DIR
from config.settings import WAIT_MEDIUM


class SeleniumController:
    def __init__(self):
        self.driver = None



    def start(self):
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options

        chrome_options = Options()

        worker_id = getattr(self, "worker_id", 1)

        # 📁 PERFIL ÚNICO POR WORKER
        profile_path = os.path.join(PROFILE_PATH, f"profile_{worker_id}")
        os.makedirs(profile_path, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={profile_path}")

        # 📁 DOWNLOAD ÚNICO POR WORKER
        download_dir = os.path.join(DOWNLOAD_DIR, f"worker_{worker_id}")
        os.makedirs(download_dir, exist_ok=True)

        prefs = {
            "download.default_directory": os.path.abspath(download_dir),
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Flags que você já usa
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-features=PasswordLeakDetection")
        chrome_options.add_argument("--disable-save-password-bubble")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
        chrome_options.add_argument("--verbose")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")

        service = Service()
        service.start_timeout = 60

        self._aguardar_rede_estavel()

        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_window_size(600, 720)

            # 🔥 guarda para uso futuro (downloads, logs, etc)
            self.download_dir = download_dir

            return self.driver
        except Exception as e:
            raise RuntimeError(f"Erro ao iniciar ChromeDriver: {e}")

    def _aguardar_rede_estavel(self, timeout=30):
        inicio = time.time()

        while time.time() - inicio < timeout:
            try:
                r = requests.get("https://www.google.com", timeout=5)
                if r.status_code == 200:
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(3)  # Aguardar mais tempo
        raise RuntimeError("❌ A rede não estabilizou após a troca de VPN.")

    def stop(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass

    def wait_for_element(self, by, value, timeout=WAIT_MEDIUM):
        return WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((by, value)))

    def wait_for_clickable(self, by, value, timeout=WAIT_MEDIUM):
        return WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((by, value)))

    def safe_click(self, by, value, timeout=WAIT_MEDIUM):
        try:
            el = self.wait_for_clickable(by, value, timeout=timeout)
            el.click()
            return True
        except Exception as e:
            print(f"[selenium] safe_click falhou ({by},{value}): {e}")
            return False

    def element_exists(self, by, value):
        try:
            self.driver.find_element(by, value)
            return True
        except NoSuchElementException:
            return False

    def get_iframe_by_src_contains(self, partial_src):
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        for fr in iframes:
            try:
                src = fr.get_attribute("src") or ""
                if partial_src in src:
                    return fr
            except Exception:
                continue
        return None

    def popup_erro_download_visivel(self):
        try:
            popup = self.driver.find_element(
                By.XPATH,
                "//div[contains(text(),'Erro') or contains(text(),'erro')]"
            )
            return popup.is_displayed()
        except:
            return False

    def _arquivo_estavel(self, caminho, tentativas=5, intervalo=0.5):
        """
        Só considera estável se o tamanho NÃO mudar por várias verificações seguidas
        """
        try:
            tamanhos_iguais = 0
            tamanho_anterior = -1

            for _ in range(tentativas):
                tamanho = os.path.getsize(caminho)

                if tamanho == tamanho_anterior:
                    tamanhos_iguais += 1
                else:
                    tamanhos_iguais = 0  # reset se mudou

                tamanho_anterior = tamanho

                # 🔥 só aceita se ficou estável por várias vezes
                if tamanhos_iguais >= 2:
                    return True

                time.sleep(intervalo)

        except FileNotFoundError:
            return False

        return False


