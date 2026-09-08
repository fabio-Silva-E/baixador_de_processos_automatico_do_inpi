import time

from selenium.common import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

from config.settings import WAIT_MEDIUM, WAIT_POPUP


def login_tres_abas(self):
    self.login_inpi(self.driver1, self.input_usuario, self.input_senha)
    self.garantir_login(self.driver1)

    self.login_inpi(self.driver2, self.input_usuario_2, self.input_senha_2)
    self.garantir_login(self.driver2)

    self.login_inpi(self.driver3, self.input_usuario_3, self.input_senha_3)
    self.garantir_login(self.driver3)

    self.log_new("✅ Login realizado nos tres navegadores")

#def login_inpi(self, driver, usuario_input, senha_input):
#    driver.get("https://busca.inpi.gov.br/pePI/")
#    time.sleep(3)
#
#    driver.find_element(By.NAME, "T_Login").clear()
#    driver.find_element(By.NAME, "T_Login").send_keys(usuario_input.text())
#
#    driver.find_element(By.NAME, "T_Senha").clear()
#    driver.find_element(By.NAME, "T_Senha").send_keys(senha_input.text())
#
#    driver.find_element(
#        By.XPATH,
#        "//input[@type='submit' and contains(@value,'Continuar')]"
#    ).click()

def login_inpi(self, driver, usuario_input, senha_input):
    driver.get("https://busca.inpi.gov.br/pePI/")

    # aguarda campo aparecer (até 30s) — seguro em máquinas lentas
    campo_login = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.NAME, "T_Login"))
    )
    campo_login.clear()
    campo_login.send_keys(usuario_input.text())

    campo_senha = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.NAME, "T_Senha"))
    )
    campo_senha.clear()
    campo_senha.send_keys(senha_input.text())

    WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//input[@type='submit' and contains(@value,'Continuar')]")
        )
    ).click()

def garantir_login(self, driver):
    self.log_new("LOGIN 1")
    self.log_new("GARANTIR LOGIN INICIO")

    self.log_new(driver)

    self.log_new(driver.session_id)

    self.log_new("ANTES DO FINDELEMENT")
    try:
        self.log_new("LOGIN 2")
        # 🔎 Já está na página correta?
        driver.find_element(By.NAME, "NumPedido")
        self.log_new("FINDELEMENT OK")
        self.log_new("✅ Usuário já está logado e na página correta.")
        return
    except:
        pass
    self.log_new("🔐 Usuário não está na página correta. Garantindo login...")
    # ======================
    # LOGIN
    # ======================
    try:
        # 🔧 FIX: a lógica antiga assumia "se não for driver1 nem driver2,
        # é driver3" — com o 4º worker isso identificava ERRADO o worker_id
        # de driver4 como sendo 3, fazendo o login usar o usuário/senha do
        # worker 3 no navegador do worker 4. Usa _worker_id_por_driver, que
        # já existe no app e cobre até 4 workers corretamente.
        worker_id = self._worker_id_por_driver(driver)
        if worker_id is None:
            raise Exception("Driver não corresponde a nenhum worker ativo")
        self.login_inpi(
            driver,
            self._usuario_atual(worker_id),
            self._senha_atual(worker_id)
        )
        self.log_new("LOGIN 3")
    except Exception as e:
        raise Exception(f"Falha no login: {e}")
    # ======================
    # AGUARDA PÁGINA PRINCIPAL
    # ======================
    WebDriverWait(driver, WAIT_MEDIUM).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    self.log_new("🔑 Login realizado. Acessando menu Marcas...")
    # ======================
    # CLICA NO MENU MARCAS
    # ======================
    try:
        menu_marcas = WebDriverWait(driver, WAIT_MEDIUM).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "area[href*='Pesquisa_num_processo.jsp']")
            )
        )
        # ⚠️ area precisa ser clicada via JS
        driver.execute_script("arguments[0].click();", menu_marcas)
    except TimeoutException:
        raise Exception("❌ Não foi possível localizar o menu Marcas")
    # ======================
    # AGUARDA CAMPO NumPedido
    # ======================
    try:
        WebDriverWait(driver, WAIT_MEDIUM).until(
            EC.presence_of_element_located((By.NAME, "NumPedido"))
        )
        self.log_new("✅ Página de pesquisa por processo carregada com sucesso.")
    except TimeoutException:
        raise Exception("❌ Campo NumPedido não apareceu após acessar Marcas")

def reiniciar_sessao_worker(self, worker_id):
    """
    🔧 FIX: reinicia o navegador (Selenium) de um worker quando a sessão
    morre (ex.: InvalidSessionIdException, chrome not reachable, janela
    fechada). Sem isso, o worker ficava retentando indefinidamente contra
    uma sessão já morta, sem nunca reabrir o navegador.
    """
    from core.selenium_controller import SeleniumController

    self.log_new(f"♻️ Worker {worker_id}: reiniciando sessão do navegador...")

    try:
        selenium_antigo = self._selenium_por_worker(worker_id)
        selenium_antigo.stop()
    except Exception as e:
        self.log_new(f"⚠️ Worker {worker_id}: erro ao parar sessão antiga: {e}")

    time.sleep(2)

    novo_selenium = SeleniumController()
    novo_selenium.worker_id = worker_id
    novo_driver = novo_selenium.start()
    novo_driver.get("https://busca.inpi.gov.br/pePI/")

    if worker_id == 1:
        self.selenium1 = novo_selenium
        self.driver1 = novo_driver
    elif worker_id == 2:
        self.selenium2 = novo_selenium
        self.driver2 = novo_driver
    elif worker_id == 3:
        self.selenium3 = novo_selenium
        self.driver3 = novo_driver
    elif worker_id == 4:
        # 🔧 FIX: faltava o worker 4 aqui — quando a sessão dele morria
        # por lentidão de rede (ou qualquer outro motivo) e o sistema
        # tentava reiniciar, um novo navegador até abria, mas nunca era
        # atribuído a self.selenium4/self.driver4. O worker 4 ficava
        # "perdido": o código continuava usando o driver ANTIGO (morto),
        # travado pra sempre, enquanto o navegador novo ficava órfão
        # aberto sem nunca ser usado.
        self.selenium4 = novo_selenium
        self.driver4 = novo_driver

    try:
        # 🔧 FIX: usa o atributo cacheado _monitor_abas_ligado (mesmo padrao
        # ja usado em iniciar_selenium/toggle_monitor_abas) em vez de ler
        # btn_monitor_abas.isChecked() direto — essa funcao roda dentro da
        # QThread do worker, e widgets do Qt nao sao thread-safe (causa
        # classica do crash 0xc0000409 no Qt5Core.dll confirmado no Event
        # Viewer).
        if getattr(self, "_monitor_abas_ligado", True):
            novo_selenium.monitor_abas_ativo = True
            novo_selenium.iniciar_monitor_abas()
    except Exception:
        pass

    self.log_new(f"✅ Worker {worker_id}: sessão reiniciada com sucesso")


def garantir_acesso_peticiones(self, driver):
    """
    Retorna True se o link de restricao foi encontrado e clicado (ou seja,
    uma popup de amplo acesso DEVE aparecer e liberar_acesso_peticiones
    precisa rodar). Retorna False se o processo ja tem acesso liberado e
    nenhuma popup vai aparecer — nesse caso o chamador deve PULAR
    liberar_acesso_peticiones em vez de esperar 20s por uma popup que
    nunca chega.
    """
    self.log_new("🔍 Verificando necessidade de amplo acesso às petições...")

    try:
        link_amplo = WebDriverWait(driver, WAIT_MEDIUM).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//a[contains(normalize-space(),'Clique aqui para ter acesso as petições')]"
            ))
        )
    except TimeoutException:
        # 🔧 FIX: link nao existe = acesso ja liberado, nenhuma popup vai
        # aparecer. Retorna False explicitamente em vez de deixar o
        # chamador achar que precisa esperar por uma popup.
        self.log_new("🔓 Nenhum bloqueio de petições detectado")
        return False

    self.log_new("🔐 Acesso restrito detectado. Solicitando liberação...")

    try:
        driver.execute_script(
            "arguments[0].scrollIntoView(true);",
            link_amplo
        )
        time.sleep(0.5)
        link_amplo.click()
        self.log_new("🪟 Link de amplo acesso clicado — popup deve abrir")
    except Exception as e:
        self.log_new(f"❌ Erro ao clicar no link de amplo acesso: {e}")
        raise

    # 🔧 FIX: o antigo check de titulo ("Finalidade do Acesso") rodava no
    # driver ainda apontando pra janela PRINCIPAL, mas a popup abre numa
    # janela NOVA — entao esse titulo nunca aparecia aqui de verdade, e
    # esse trecho sempre estourava o timeout e caia no "Nenhum bloqueio"
    # (mensagem enganosa, pois o link FOI clicado e a popup FOI aberta).
    # Quem realmente confere/usa a popup e liberar_acesso_peticiones, que
    # troca pra janela nova. Aqui so precisamos confirmar que clicamos.
    return True

def liberar_acesso_peticiones(self, driver):
    janela_principal = driver.current_window_handle

    # 🔧 FIX: esta função abre uma popup de verdade (nova janela) e precisa
    # de alguns segundos para marcar o checkbox e clicar em Enviar. Mas o
    # monitor de abas (SeleniumController.monitor, rodando a cada 0.5s)
    # fecha QUALQUER janela extra assim que detecta mais de uma aba —
    # inclusive essa popup de liberação — antes da interação terminar.
    # Isso fazia a popup "fechar antes da liberação". Bloqueamos o monitor
    # enquanto trabalhamos na popup, igual já é feito em
    # limpar_historico_downloads/limpar_historico_navegacao.
    try:
        # 🔧 FIX: mesmo problema do garantir_login — "driver4" caia no
        # else e era tratado como worker 3, fazendo o bloqueio de
        # fechamento de abas (bloquear_fechamento_abas) e a popup de
        # amplo acesso serem manipulados no SeleniumController ERRADO.
        worker_id = self._worker_id_por_driver(driver)
        selenium_ctrl = self._selenium_por_worker(worker_id) if worker_id else None
        if selenium_ctrl:
            selenium_ctrl.bloquear_fechamento_abas = True
    except Exception:
        selenium_ctrl = None

    try:
        self.log_new("🔍 Verificando popup de amplo acesso...")
        # 🔧 FIX v2: quem abre a popup de verdade e o clique em
        # garantir_acesso_peticiones, que roda ANTES desta funcao — ou seja,
        # a popup ja existe quando chegamos aqui. A versao anterior deste
        # fix comparava handles "antes vs depois" pra achar uma janela NOVA,
        # mas como a popup ja estava aberta antes mesmo de comecarmos a
        # contar, nenhuma janela "nova" surgia e o wait sempre estourava os
        # 20s por completo, mesmo com a popup renderizada corretamente na
        # tela (confirmado por screenshot). Agora identificamos a popup
        # pelo conteudo dela (titulo "Finalidade do Acesso"), nao por
        # timing de quando apareceu — funciona tanto se ela ja estava
        # aberta quanto se abrir durante a espera, e ainda ignora janelas
        # orfas de verdade (que nao vao ter esse titulo).
        def _popup_valida(d):
            for h in d.window_handles:
                if h == janela_principal:
                    continue
                try:
                    d.switch_to.window(h)
                    if "Finalidade do Acesso" in d.title:
                        return h
                except Exception:
                    continue
            return None

        janela_popup = WebDriverWait(driver, WAIT_POPUP).until(
            lambda d: _popup_valida(d)
        )
        driver.switch_to.window(janela_popup)
        self.log_new("🪟 Popup de amplo acesso detectado")
        # aguarda checkbox aparecer
        checkbox = WebDriverWait(driver, WAIT_POPUP).until(
            EC.element_to_be_clickable((By.ID, "aceite"))
        )
        checkbox.click()
        self.log_new("☑️ Checkbox de concordância marcado")
        # botão Enviar (input submit)
        botao_enviar = WebDriverWait(driver, WAIT_POPUP).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//input[@type='submit' and @name='Enviar']"
            ))
        )
        botao_enviar.click()
        self.log_new("📨 Formulário enviado")
        # aguarda popup fechar
        WebDriverWait(driver, WAIT_POPUP).until(
            lambda d: len(d.window_handles) == 1
        )
        # volta para janela principal
        driver.switch_to.window(janela_principal)
        self.log_new("✅ Acesso às petições liberado com sucesso")
    except TimeoutException:
        self.log_new("🔓 Nenhum popup de amplo acesso detectado")
        # 🔧 FIX: salva screenshot + HTML da(s) janela(s) extra(s) no momento
        # da falha, para diagnosticar POR QUE o checkbox/botao nao apareceu
        # a tempo (pagina travada, elemento com outro id, alerta bloqueando
        # etc). Sem isso estamos so adivinhando pelo log de texto.
        try:
            from pathlib import Path
            import datetime
            debug_dir = Path("debug_popup")
            debug_dir.mkdir(exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            for idx, janela in enumerate(driver.window_handles):
                if janela == janela_principal:
                    continue
                try:
                    driver.switch_to.window(janela)
                    driver.save_screenshot(str(debug_dir / f"popup_{ts}_{idx}.png"))
                    html = driver.page_source
                    (debug_dir / f"popup_{ts}_{idx}.html").write_text(html, encoding="utf-8")
                    self.log_new(f"📸 Debug salvo: popup_{ts}_{idx}.png/html (url={driver.current_url})")
                except Exception as e_dbg:
                    self.log_new(f"⚠️ Falha ao salvar debug da popup: {e_dbg}")
        except Exception:
            pass
        # 🔧 FIX: fecha qualquer janela extra que tenha ficado aberta (a
        # popup pode ter aberto mas nao renderizado o checkbox a tempo).
        # Sem isso, essa janela orfa continua aberta e "engana" a PROXIMA
        # chamada de liberar_acesso_peticiones, que a confunde com uma
        # popup nova valida e nunca acha o checkbox nela — um efeito
        # cascata que faz a falha se perpetuar nas tentativas seguintes.
        for janela in list(driver.window_handles):
            if janela != janela_principal:
                try:
                    driver.switch_to.window(janela)
                    driver.close()
                except Exception:
                    pass
        driver.switch_to.window(janela_principal)

        # 🔧 FIX: antes o codigo engolia essa falha e o chamador seguia como
        # se a liberacao tivesse funcionado ("peticões liberadas"), indo
        # direto pro clique do PDF sem acesso liberado de verdade — o que
        # bate com os crashes de chromedriver vistos logo depois no log.
        # Agora propagamos a falha para o worker tratar como erro e
        # repetir o processo, em vez de seguir cegamente.
        raise Exception("Popup de amplo acesso nao pode ser liberada (timeout)")

    finally:
        if selenium_ctrl is not None:
            selenium_ctrl.bloquear_fechamento_abas = False