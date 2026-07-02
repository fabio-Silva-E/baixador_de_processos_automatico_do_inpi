import time

from selenium.common import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

from config.settings import WAIT_MEDIUM


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
        worker_id = (
            1 if driver == self.driver1 else
            2 if driver == self.driver2 else
            3
        )
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

def garantir_acesso_peticiones(self, driver):

    try:
        self.log_new("🔍 Verificando necessidade de amplo acesso às petições...")

        link_amplo = WebDriverWait(driver, WAIT_MEDIUM).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//a[contains(normalize-space(),'Clique aqui para ter acesso as petições')]"
            ))
        )

        self.log_new("🔐 Acesso restrito detectado. Solicitando liberação...")

        driver.execute_script(
            "arguments[0].scrollIntoView(true);",
            link_amplo
        )

        time.sleep(0.5)

        link_amplo.click()

        # aguarda popup/modal
        WebDriverWait(driver, WAIT_MEDIUM).until(
            EC.title_contains("Finalidade do Acesso")
        )

        self.log_new("🪟 Modal de acesso aberto")

        # espera voltar
        WebDriverWait(driver, WAIT_MEDIUM).until(
            EC.not_(EC.title_contains("Finalidade do Acesso"))
        )

        self.log_new("✅ Acesso às petições liberado")

    except TimeoutException:
        self.log_new("🔓 Nenhum bloqueio de petições detectado")

    except Exception as e:
        self.log_new(f"❌ Erro em garantir_acesso_peticiones")
        raise

def liberar_acesso_peticiones(self, driver):
    janela_principal = driver.current_window_handle
    try:
        self.log_new("🔍 Verificando popup de amplo acesso...")
        # aguarda abrir nova janela (popup)
        WebDriverWait(driver, WAIT_MEDIUM).until(
            lambda d: len(d.window_handles) > 1
        )
        # muda para o popup
        for janela in driver.window_handles:
            if janela != janela_principal:
                driver.switch_to.window(janela)
                break
        self.log_new("🪟 Popup de amplo acesso detectado")
        # aguarda checkbox aparecer
        checkbox = WebDriverWait(driver, WAIT_MEDIUM).until(
            EC.element_to_be_clickable((By.ID, "aceite"))
        )
        checkbox.click()
        self.log_new("☑️ Checkbox de concordância marcado")
        # botão Enviar (input submit)
        botao_enviar = WebDriverWait(driver, WAIT_MEDIUM).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//input[@type='submit' and @name='Enviar']"
            ))
        )
        botao_enviar.click()
        self.log_new("📨 Formulário enviado")
        # aguarda popup fechar
        WebDriverWait(driver, WAIT_MEDIUM).until(
            lambda d: len(d.window_handles) == 1
        )
        # volta para janela principal
        driver.switch_to.window(janela_principal)
        self.log_new("✅ Acesso às petições liberado com sucesso")
    except TimeoutException:
        self.log_new("🔓 Nenhum popup de amplo acesso detectado")
        driver.switch_to.window(janela_principal)