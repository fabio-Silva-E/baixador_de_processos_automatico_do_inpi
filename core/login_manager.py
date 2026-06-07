import time

from selenium.common import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

from config.settings import WAIT_MEDIUM
from core.network_utils import internet_disponivel, aguardar_rede, wait_element, wait_clickable

def login_tres_abas(self):
    self.login_inpi(self.driver1, self.input_usuario, self.input_senha)
    self.garantir_login(self.driver1)

    self.login_inpi(self.driver2, self.input_usuario_2, self.input_senha_2)
    self.garantir_login(self.driver2)

    self.login_inpi(self.driver3, self.input_usuario_3, self.input_senha_3)
    self.garantir_login(self.driver3)

    self.log_new("✅ Login realizado nos tres navegadores")

def login_inpi(self, driver, usuario_input, senha_input):
    if not internet_disponivel():

        self.log_new(
            "🌐 Sem internet antes do login."
        )

        if not aguardar_rede():
            raise Exception(
                "Internet indisponível."
            )

    driver.get("https://busca.inpi.gov.br/pePI/")

    time.sleep(3)

    driver.find_element(By.NAME, "T_Login").clear()
    driver.find_element(By.NAME, "T_Login").send_keys(usuario_input.text())

    driver.find_element(By.NAME, "T_Senha").clear()
    driver.find_element(By.NAME, "T_Senha").send_keys(senha_input.text())

    driver.find_element(
        By.XPATH,
        "//input[@type='submit' and contains(@value,'Continuar')]"
    ).click()

def garantir_login(self, driver):
    self.log_new("LOGIN 1")
    self.log_new("GARANTIR LOGIN INICIO")

    self.log_new(driver)

    self.log_new(driver.session_id)

    self.log_new("ANTES DO FINDELEMENT")
    self.log_new("LOGIN 2")

    try:
        wait_element(
            self,
            driver,
            (By.NAME, "NumPedido"),
            timeout=5
        )

        self.log_new("✅ Usuário já está logado.")
        return

    except TimeoutException:
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
    wait_element(
        self,
        driver,
        (By.TAG_NAME, "body"),
        timeout=WAIT_MEDIUM
    )
    self.log_new("🔑 Login realizado. Acessando menu Marcas...")
    # ======================
    # CLICA NO MENU MARCAS
    # ======================
    try:
        menu_marcas = wait_element(
            self,
            driver,
            (
                By.CSS_SELECTOR,
                "area[href*='Pesquisa_num_processo.jsp']"
            ),
            timeout=WAIT_MEDIUM
        )
        # ⚠️ area precisa ser clicada via JS
        driver.execute_script("arguments[0].click();", menu_marcas)
    except TimeoutException:

        if not internet_disponivel():

            self.log_new("🌐 Sem internet. Aguardando retorno...")

            if not aguardar_rede():
                raise Exception(
                    "Internet indisponível por muito tempo."
                )

            self.log_new("🌐 Internet restabelecida.")

            # tenta novamente localizar o elemento
            menu_marcas = wait_element(
                self,
                driver,
                (
                    By.CSS_SELECTOR,
                    "area[href*='Pesquisa_num_processo.jsp']"
                ),
                timeout=WAIT_MEDIUM
            )

            driver.execute_script(
                "arguments[0].click();",
                menu_marcas
            )

        else:
            raise Exception(
                "❌ Não foi possível localizar o menu Marcas"
            )
    # ======================
    # AGUARDA CAMPO NumPedido
    # ======================
    try:
        wait_element(
            self,
            driver,
            (By.NAME, "NumPedido"),
            timeout=WAIT_MEDIUM
        )
        self.log_new("✅ Página de pesquisa por processo carregada com sucesso.")
    except TimeoutException:

        if not internet_disponivel():

            self.log_new("🌐 Sem internet. Aguardando retorno...")

            if not aguardar_rede():
                raise Exception(
                    "Internet indisponível por muito tempo."
                )

            self.log_new("🌐 Internet restabelecida.")

            return self.garantir_login(driver)

        raise Exception("❌ Campo NumPedido não apareceu após acessar Marcas")

def garantir_acesso_peticiones(self, driver):

    try:
        self.log_new(
            "🔍 Verificando necessidade de amplo acesso às petições..."
        )

        link_amplo = wait_element(
            self,
            driver,
            (
                By.XPATH,
                "//a[contains(normalize-space(),'Clique aqui para ter acesso as petições')]"
            ),
            timeout=WAIT_MEDIUM
        )

        self.log_new(
            "🔐 Acesso restrito detectado. Solicitando liberação..."
        )

        driver.execute_script(
            "arguments[0].scrollIntoView(true);",
            link_amplo
        )

        time.sleep(0.5)

        # IMPORTANTE
        link_amplo.click()

        self.log_new(
            "🖱 Link de acesso clicado"
        )

        WebDriverWait(driver, WAIT_MEDIUM).until(
            EC.title_contains("Finalidade do Acesso")
        )

        self.log_new(
            "🪟 Modal de acesso aberto"
        )

        WebDriverWait(driver, WAIT_MEDIUM).until(
            EC.not_(
                EC.title_contains("Finalidade do Acesso")
            )
        )

        self.log_new(
            "✅ Acesso às petições liberado"
        )

    except TimeoutException:

        self.log_new(
            "🔓 Nenhum bloqueio de petições detectado"
        )

    except Exception as e:

        self.log_new(
            f"❌ Erro em garantir_acesso_peticiones: {e}"
        )

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
        checkbox = wait_clickable(
            self,
            driver,
            (By.ID, "aceite"),
            timeout=WAIT_MEDIUM
        )
        checkbox.click()
        self.log_new("☑️ Checkbox de concordância marcado")
        # botão Enviar (input submit)
        botao_enviar = wait_clickable(
            self,
            driver,
            (
                By.XPATH,
                "//input[@type='submit' and @name='Enviar']"
            ),
            timeout=WAIT_MEDIUM
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

