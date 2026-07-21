import os
import time
import threading
import json
import websocket
import requests as http_requests
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
        self._remote_debug_port = None
        self.monitor_abas_ativo = False
        self.monitor_abas_thread = None
        self.bloquear_fechamento_abas = False
        self.worker_id = None

    def iniciar_monitor_abas(self):
        if self.monitor_abas_thread and self.monitor_abas_thread.is_alive():
            return
        self.monitor_abas_ativo = True
        def monitor():
            while self.monitor_abas_ativo:
                if not self.driver:
                    time.sleep(0.5)
                    continue
                # enquanto bloqueado (ex: liberar_acesso_peticiones em andamento),
                # nem sequer consulta window_handles: essa chamada compete pelo
                # unico slot do connection pool do driver com o WebDriverWait
                # que esta rodando naquele momento, podendo fazer o wait estourar
                # o timeout por disputa de conexao, nao por lentidao real
                if self.bloquear_fechamento_abas:
                    time.sleep(0.5)
                    continue
                try:
                    abas = self.driver.window_handles
                    if len(abas) > 1:
                        self.fechar_abas_extras()
                except Exception as e:
                    print(f"[MONITOR ERROR] {e}")
                    break
                time.sleep(0.5)
        self.monitor_abas_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_abas_thread.start()

    def start(self):
        navegador = SeleniumController.NAVEGADOR
        worker_id = getattr(self, "worker_id", 1)

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
            "download.show_download_insights": False,
            "browser.download.animateNotifications": False,
            "download.shelf.enabled": False,
            "download.show_download_in_shelf": False,
        }

        debug_port = 9200 + worker_id
        self._remote_debug_port = debug_port

        self._aguardar_rede_estavel()

        if navegador == "edge":
            from selenium.webdriver.edge.service import Service
            from selenium.webdriver.edge.options import Options
            options = Options()
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument("--profile-directory=Default")
            options.add_argument(f"--remote-debugging-port={debug_port}")
            options.add_experimental_option("prefs", prefs)
            self._aplicar_flags_comuns(options)
            self.service = Service()
            self.driver = webdriver.Edge(service=self.service, options=options)

        elif navegador == "chrome":
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            options = Options()
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument("--profile-directory=Default")
            options.add_argument(f"--remote-debugging-port={debug_port}")
            options.add_experimental_option("prefs", prefs)
            self._aplicar_flags_comuns(options)
            self.service = Service()
            self.driver = webdriver.Chrome(service=self.service, options=options)

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
            options.add_argument(f"--remote-debugging-port={debug_port}")
            options.add_experimental_option("prefs", prefs)
            self._aplicar_flags_comuns(options)
            self.service = Service()
            self.driver = webdriver.Chrome(service=self.service, options=options)

        elif navegador == "firefox":
            from selenium.webdriver.firefox.service import Service
            from selenium.webdriver.firefox.options import Options
            from webdriver_manager.firefox import GeckoDriverManager
            from config.paths import FIREFOX_BIN_PATHS
            firefox_bin = next((p for p in FIREFOX_BIN_PATHS if Path(p).exists()), None)
            if not firefox_bin:
                raise RuntimeError("❌ Firefox não encontrado.")
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
            profile_path = firefox_profile

        else:
            raise ValueError(f"Navegador desconhecido: {navegador}")

        self.download_dir = download_dir
        self.profile_path = profile_path
        self.driver.set_window_size(600, 720)

        # 🔧 FIX: sem timeout no cliente HTTP do Selenium, uma chamada travada
        # ao chromedriver (socket que nunca recebe resposta) bloqueia a
        # thread do worker para sempre — mesmo dentro de um WebDriverWait
        # com timeout definido, porque o relógio do wait nunca chega a ser
        # checado enquanto a chamada HTTP subjacente não retorna. Definindo
        # um timeout aqui, hangs silenciosos viram exceções de verdade,
        # permitindo que o retry e o reinicio_sessao_worker entrem em ação.
        try:
            # 🔧 FIX v2: `command_executor.set_timeout()` é um classmethod do
            # Selenium que mexe num atributo de CLASSE compartilhado entre
            # TODAS as conexões (RemoteConnection._client_config). Como os
            # workers sobem seus navegadores quase ao mesmo tempo, isso cria
            # uma condição de corrida: o timeout de um worker podia
            # sobrescrever/perder efeito no de outro, deixando alguns
            # drivers sem timeout nenhum (bloqueio infinito, que foi
            # exatamente o travamento observado). Aqui setamos o timeout
            # direto no objeto de config DESSA instância, sem depender do
            # estado de classe compartilhado.
            self.driver.command_executor._client_config.timeout = 30

            # 🔧 FIX v3: o RemoteConnection cria seu urllib3.PoolManager com
            # maxsize=1 por padrão (uma unica conexao HTTP por driver). A
            # thread de monitor_abas (poll a cada 0.5s em window_handles) e o
            # proprio worker fazem chamadas concorrentes nesse MESMO driver,
            # entao com so 1 conexao elas ficam descartando/reabrindo conexao
            # o tempo todo ("Connection pool is full, discarding connection"),
            # o que sob qualquer pico de carga pode fazer um WebDriverWait
            # estourar por disputa de conexao, nao por lentidao real da
            # pagina. Recriamos o pool com mais slots para essa instância.
            import urllib3
            self.driver.command_executor._conn = urllib3.PoolManager(
                timeout=self.driver.command_executor._client_config.timeout,
                maxsize=10,
                block=False,
            )
        except Exception as e:
            print(f"[selenium] não foi possível definir timeout/pool do command_executor: {e}")

        return self.driver

    def _aplicar_flags_comuns(self, options):
        """Flags comuns a Edge, Chrome e Brave."""
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-features=DownloadBubble,DownloadBubbleV2,DownloadShelf")
        options.add_argument("--disable-download-notification")
        options.add_argument("--remote-allow-origins=*")

    # ==================================================
    # 🧹 LIMPAR HISTÓRICO DE DOWNLOADS via chrome://downloads
    # ==================================================
    def limpar_historico_downloads(self):
        """
        Abre chrome://downloads em nova aba, executa clear via shadow DOM e fecha.
        """
        aba_atual = None
        nova_aba = None
        try:
            self.bloquear_fechamento_abas = True  # impede monitor de fechar a nova aba
            aba_atual = self.driver.current_window_handle
            abas_antes = set(self.driver.window_handles)

            # abre nova aba vazia
            self.driver.execute_script("window.open('');")

            # aguarda a nova aba aparecer (até 3s)
            prazo = time.time() + 3
            while time.time() < prazo:
                abas_agora = set(self.driver.window_handles)
                novas = abas_agora - abas_antes
                if novas:
                    nova_aba = novas.pop()
                    break
                time.sleep(0.1)

            if not nova_aba:
                print("[limpar_downloads] nova aba não apareceu")
                return

            self.driver.switch_to.window(nova_aba)
            self.driver.get("chrome://downloads/")
            time.sleep(1.0)  # aguarda o DOM de chrome://downloads carregar

            resultado = self.driver.execute_script("""
                try {
                    const mgr = document.querySelector('downloads-manager');
                    if (!mgr) return 'no-manager';
                    const root = mgr.shadowRoot;
                    if (!root) return 'no-shadow';

                    // tenta método direto
                    if (typeof mgr.clearAll === 'function') { mgr.clearAll(); return 'clearAll-direct'; }

                    // procura toolbar e botão clear dentro do shadow DOM aninhado
                    function findClearBtn(el) {
                        if (!el) return null;
                        const sr = el.shadowRoot || el;
                        const btn = sr.querySelector('#clearAll') || sr.querySelector('[id*=clear]');
                        if (btn) return btn;
                        for (const child of sr.querySelectorAll('*')) {
                            const found = findClearBtn(child);
                            if (found) return found;
                        }
                        return null;
                    }

                    // abre o menu "mais ações" primeiro
                    const toolbar = root.querySelector('#toolbar') || root.querySelector('downloads-toolbar');
                    if (toolbar) {
                        const troot = toolbar.shadowRoot || toolbar;
                        const moreBtn = troot.querySelector('#moreActionsButton') ||
                                        troot.querySelector('cr-icon-button');
                        if (moreBtn) moreBtn.click();
                    }
                    return 'menu-opened';
                } catch(e) { return 'err1:' + e.toString(); }
            """)
            time.sleep(0.4)

            resultado2 = self.driver.execute_script("""
                try {
                    const mgr = document.querySelector('downloads-manager');
                    if (!mgr) return 'no-manager';

                    function findAndClick(el) {
                        if (!el) return false;
                        const sr = el.shadowRoot || el;
                        const candidates = sr.querySelectorAll('button, cr-button, [role=menuitem], paper-item');
                        for (const btn of candidates) {
                            const txt = (btn.textContent || '').toLowerCase().trim();
                            if (txt.includes('clear') || txt.includes('limpar') || btn.id.includes('clear')) {
                                btn.click();
                                return 'clicked:' + (btn.id || txt);
                            }
                        }
                        // recursivo em shadow roots
                        for (const child of sr.querySelectorAll('*')) {
                            if (child.shadowRoot) {
                                const res = findAndClick(child);
                                if (res) return res;
                            }
                        }
                        return null;
                    }

                    const res = findAndClick(mgr);
                    return res || 'not-found';
                } catch(e) { return 'err2:' + e.toString(); }
            """)

            print(f"[limpar_downloads] {resultado} / {resultado2}")
            time.sleep(0.3)

        except Exception as e:
            print(f"[limpar_downloads] erro: {e}")

        finally:
            self.bloquear_fechamento_abas = False
            try:
                # fecha a aba de downloads se ainda existir
                handles = self.driver.window_handles
                if nova_aba and nova_aba in handles:
                    self.driver.switch_to.window(nova_aba)
                    self.driver.close()
                # volta para a aba original
                handles = self.driver.window_handles
                if aba_atual and aba_atual in handles:
                    self.driver.switch_to.window(aba_atual)
                elif handles:
                    self.driver.switch_to.window(handles[0])
            except Exception as fe:
                print(f"[limpar_downloads] finally erro: {fe}")

    # ==================================================
    # 🧹 LIMPAR HISTÓRICO DE NAVEGAÇÃO via chrome://settings/clearBrowserData
    # ==================================================
    def limpar_historico_navegacao(self):
        """
        Abre chrome://settings/clearBrowserData em nova aba, tenta ajustar o
        período para 'Todo o período' e confirma a limpeza do histórico de
        navegação (mesmo padrão de limpar_historico_downloads).
        """
        aba_atual = None
        nova_aba = None
        try:
            self.bloquear_fechamento_abas = True  # impede monitor de fechar a nova aba
            aba_atual = self.driver.current_window_handle
            abas_antes = set(self.driver.window_handles)

            # abre nova aba vazia
            self.driver.execute_script("window.open('');")

            # aguarda a nova aba aparecer (até 3s)
            prazo = time.time() + 3
            while time.time() < prazo:
                abas_agora = set(self.driver.window_handles)
                novas = abas_agora - abas_antes
                if novas:
                    nova_aba = novas.pop()
                    break
                time.sleep(0.1)

            if not nova_aba:
                print("[limpar_historico] nova aba não apareceu")
                return

            self.driver.switch_to.window(nova_aba)
            self.driver.get("chrome://settings/clearBrowserData")
            time.sleep(1.2)  # aguarda o diálogo de limpeza carregar

            # tenta selecionar "Todo o período" / "All time" no seletor de intervalo
            resultado1 = self.driver.execute_script("""
                try {
                    function deepQueryAll(root, sel) {
                        let out = [];
                        try { out = out.concat(Array.from(root.querySelectorAll(sel))); } catch(e) {}
                        const all = root.querySelectorAll('*');
                        for (const el of all) {
                            if (el.shadowRoot) out = out.concat(deepQueryAll(el.shadowRoot, sel));
                        }
                        return out;
                    }
                    const selects = deepQueryAll(document, 'select');
                    for (const sel of selects) {
                        if (sel.id && sel.id.toLowerCase().includes('clearfrom')) {
                            const opts = Array.from(sel.options).map(o => o.textContent.toLowerCase());
                            const idx = opts.findIndex(t => t.includes('todo') || t.includes('all time'));
                            if (idx >= 0) {
                                sel.selectedIndex = idx;
                                sel.dispatchEvent(new Event('change', {bubbles:true}));
                                return 'periodo-ajustado:' + opts[idx];
                            }
                        }
                    }
                    return 'seletor-nao-encontrado';
                } catch(e) { return 'err1:' + e.toString(); }
            """)
            time.sleep(0.3)

            # clica no botão de confirmar limpeza ("Limpar dados" / "Clear data")
            resultado2 = self.driver.execute_script("""
                try {
                    function deepQueryAll(root, sel) {
                        let out = [];
                        try { out = out.concat(Array.from(root.querySelectorAll(sel))); } catch(e) {}
                        const all = root.querySelectorAll('*');
                        for (const el of all) {
                            if (el.shadowRoot) out = out.concat(deepQueryAll(el.shadowRoot, sel));
                        }
                        return out;
                    }
                    const candidatos = deepQueryAll(document, 'cr-button, button');
                    for (const btn of candidatos) {
                        const txt = (btn.textContent || '').toLowerCase().trim();
                        const id = (btn.id || '').toLowerCase();
                        if (id.includes('clearbrowsingdataconfirm') ||
                            txt.includes('limpar dados') || txt.includes('clear data')) {
                            btn.click();
                            return 'clicado:' + (btn.id || txt);
                        }
                    }
                    return 'botao-nao-encontrado';
                } catch(e) { return 'err2:' + e.toString(); }
            """)

            print(f"[limpar_historico] {resultado1} / {resultado2}")
            time.sleep(1.5)  # aguarda a limpeza concluir antes de fechar a aba

        except Exception as e:
            print(f"[limpar_historico] erro: {e}")

        finally:
            self.bloquear_fechamento_abas = False
            try:
                # fecha a aba de configurações se ainda existir
                handles = self.driver.window_handles
                if nova_aba and nova_aba in handles:
                    self.driver.switch_to.window(nova_aba)
                    self.driver.close()
                # volta para a aba original
                handles = self.driver.window_handles
                if aba_atual and aba_atual in handles:
                    self.driver.switch_to.window(aba_atual)
                elif handles:
                    self.driver.switch_to.window(handles[0])
            except Exception as fe:
                print(f"[limpar_historico] finally erro: {fe}")

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
        self.parar_monitor_abas()

        # 🔧 FIX: driver.quit() manda um comando HTTP pro chromedriver e
        # espera resposta — se o chromedriver ja tiver crashado/travado
        # (exatamente os stack traces nativos vistos no app.log), essa
        # chamada pode travar por muito tempo ou falhar, e o antigo
        # `except: pass` engolia isso silenciosamente sem garantir que o
        # processo terminasse. Rodar num thread com timeout evita travar
        # a reinicializacao da sessao esperando um quit() que nunca volta.
        if self.driver:
            t = threading.Thread(target=self.driver.quit, daemon=True)
            t.start()
            t.join(timeout=10)

        # 🔧 FIX: mesmo que o quit() acima tenha travado/falhado, garante
        # que o processo do chromedriver/msedgedriver E o navegador filho
        # sejam mortos de verdade pelo PID. Sem isso, cada crash+reinicio
        # de sessao deixava um processo zumbi rodando (consumindo RAM),
        # que se acumula ao longo de uma execucao longa ate a maquina
        # ficar sem memoria — mais grave em maquinas mais fracas, batendo
        # com o programa "fechando sozinho" na secundaria.
        try:
            import psutil
            service = getattr(self, "service", None)
            proc = getattr(service, "process", None)
            if proc and proc.pid:
                try:
                    p = psutil.Process(proc.pid)
                    for child in p.children(recursive=True):
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
        except Exception as e:
            print(f"[selenium] erro ao forcar encerramento do processo: {e}")

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
        try:
            tamanhos_iguais = 0
            tamanho_anterior = -1
            for _ in range(tentativas):
                tamanho = os.path.getsize(caminho)
                if tamanho == tamanho_anterior:
                    tamanhos_iguais += 1
                else:
                    tamanhos_iguais = 0
                tamanho_anterior = tamanho
                if tamanhos_iguais >= 2:
                    return True
                time.sleep(intervalo)
        except FileNotFoundError:
            return False
        return False
