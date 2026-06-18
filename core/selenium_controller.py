import os
import time
import threading
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



from config.paths import PROFILE_PATH, DOWNLOAD_DIR
from config.settings import WAIT_MEDIUM


class SeleniumController:
    NAVEGADOR = "edge"
    def __init__(self):
        self.driver = None
        self.driver_lock = threading.RLock()
        # =========================
        # 🔥 MONITOR DE ABAS (FIX)
        # =========================
        self.monitor_abas_ativo = False
        self.monitor_abas_thread = None

        self.bloquear_fechamento_abas = False
        self.worker_id = None

    # ==================================================
    # 🧠 MONITOR DE ABAS (ON/OFF SEGURO)
    # ==================================================
    def iniciar_monitor_abas(self):
        # já rodando
        if self.monitor_abas_thread and self.monitor_abas_thread.is_alive():
            return

        self.monitor_abas_ativo = True

        def monitor():
            while self.monitor_abas_ativo:
                if not self.driver:
                    time.sleep(0.5)
                    continue
                try:
                    abas = self.driver.window_handles
                    if len(abas) > 1 and not self.bloquear_fechamento_abas:
                        self.fechar_abas_extras()
                except Exception as e:
                    print(f"[MONITOR ERROR] {e}")
                    break
                time.sleep(0.5)  # ← 500ms entre checagens

        # ← ESTAS DUAS LINHAS ESTAVAM FALTANDO:
        self.monitor_abas_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_abas_thread.start()

    def start(self):
        navegador = SeleniumController.NAVEGADOR
        worker_id = getattr(self, "worker_id", 1)

        # ← perfil separado por NAVEGADOR e worker
        profile_path = Path(PROFILE_PATH) / navegador / f"profile_{worker_id}"
        profile_path.mkdir(parents=True, exist_ok=True)

        download_dir = Path(DOWNLOAD_DIR) / f"worker_{worker_id}"
        download_dir.mkdir(parents=True, exist_ok=True)

        prefs = {
            "download.default_directory": str(download_dir.resolve()),
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
            "profile.password_manager_leak_detection": False,
            "download.open_pdf_in_system_reader": False,
            "download.extensions_to_open": "",
            "download.manager.showWhenStarting": False,
        }

        self._aguardar_rede_estavel()

        if navegador == "edge":
            from selenium.webdriver.edge.service import Service
            from selenium.webdriver.edge.options import Options
            options = Options()
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument("--profile-directory=Default")
            options.add_experimental_option("prefs", prefs)
            self._aplicar_flags_comuns(options)
            self.driver = webdriver.Edge(service=Service(), options=options)

        elif navegador == "chrome":
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            options = Options()
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument("--profile-directory=Default")
            options.add_experimental_option("prefs", prefs)
            self._aplicar_flags_comuns(options)
            self.driver = webdriver.Chrome(service=Service(), options=options)

        elif navegador == "brave":
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            brave_paths = [
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Users\fs271\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe",
            ]
            brave_bin = next((p for p in brave_paths if Path(p).exists()), None)
            if not brave_bin:
                raise RuntimeError("❌ Brave não encontrado.")
            options = Options()
            options.binary_location = brave_bin
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument("--profile-directory=Default")
            options.add_experimental_option("prefs", prefs)
            self._aplicar_flags_comuns(options)
            self.driver = webdriver.Chrome(service=Service(), options=options)

        elif navegador == "firefox":
            from selenium.webdriver.firefox.service import Service
            from selenium.webdriver.firefox.options import Options
            from webdriver_manager.firefox import GeckoDriverManager
            from config.paths import FIREFOX_BIN_PATHS
            firefox_bin = next((p for p in FIREFOX_BIN_PATHS if Path(p).exists()), None)
            if not firefox_bin:
                raise RuntimeError("❌ Firefox não encontrado.")
            # ← Firefox usa pasta própria separada dos outros
            firefox_profile = Path(PROFILE_PATH) / "firefox" / f"profile_{worker_id}"
            firefox_profile.mkdir(parents=True, exist_ok=True)
            options = Options()
            options.binary_location = firefox_bin
            options.add_argument("-profile")
            options.add_argument(str(firefox_profile))
            options.set_preference("browser.download.folderList", 2)
            options.set_preference("browser.download.dir", str(download_dir.resolve()))
            options.set_preference("browser.download.useDownloadDir", True)
            options.set_preference("browser.download.manager.showWhenStarting", False)
            options.set_preference("browser.download.manager.focusWhenStarting", False)
            options.set_preference("browser.helperApps.neverAsk.saveToDisk",
                                   "application/pdf,application/octet-stream")
            options.set_preference("pdfjs.disabled", True)
            options.set_preference("browser.helperApps.alwaysAsk.force", False)
            options.set_preference("browser.download.manager.alertOnEXEOpen", False)
            options.set_preference("browser.download.manager.closeWhenDone", True)
            options.set_preference("xpinstall.signatures.required", False)
            options.set_preference("browser.download.animateNotifications", False)
            options.set_preference("browser.download.panel.shown", False)
            self.driver = webdriver.Firefox(
                service=Service(GeckoDriverManager().install()),
                options=options
            )
            profile_path = firefox_profile  # ← atualiza para salvar corretamente abaixo

        else:
            raise ValueError(f"Navegador desconhecido: {navegador}")

        self.download_dir = download_dir
        self.profile_path = profile_path
        #self.iniciar_monitor_abas()
        self.driver.set_window_size(600, 720)
        return self.driver



    def _aplicar_flags_comuns(self, options):
        """Flags comuns a Edge, Chrome e Brave."""
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")

    # ==================================================
    # 🌐 REDE
    # ==================================================
    def _aguardar_rede_estavel(self, timeout=30):
        start = time.time()

        while time.time() - start < timeout:
            try:
                r = requests.get("https://www.google.com", timeout=5)
                if r.status_code == 200:
                    return
            except:
                pass

            time.sleep(3)

        raise RuntimeError("❌ Rede instável")

    # ==================================================
    # 🛑 STOP
    # ==================================================
    def stop(self):
        try:
            self.parar_monitor_abas()
            if self.driver:
                self.driver.quit()
        except:
            pass

    # ==================================================
    # 🔥 FECHAR ABAS EXTRAS
    # ==================================================
    def fechar_abas_extras(self):
        try:
            abas = self.driver.window_handles
            if len(abas) <= 1:
                return

            aba_principal = abas[0]

            for aba in abas[1:]:
                try:
                    self.driver.switch_to.window(aba)
                    url = self.driver.current_url
                    # ← não fecha aba de downloads — wait_for_download cuida disso
                    if "downloads" in url:
                        continue
                    self.driver.close()
                except Exception:
                    pass

            self.driver.switch_to.window(aba_principal)

        except Exception as e:
            print(f"Erro fechar abas: {e}")

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


    #def fechar_abas_extras(self):
    #
    #     try:
    #
    #         abas = self.driver.window_handles
    #
    #         if len(abas) <= 1:
    #             return
    #
    #         aba_principal = abas[0]
    #
    #         for aba in abas[1:]:
    #
    #             try:
    #                 self.driver.switch_to.window(aba)
    #                 self.driver.close()
    #
    #             except Exception:
    #                 pass
    #
    #         self.driver.switch_to.window(aba_principal)
    #
    #     except Exception as e:
    #
    #         print(f"Erro fechar abas: {e}")