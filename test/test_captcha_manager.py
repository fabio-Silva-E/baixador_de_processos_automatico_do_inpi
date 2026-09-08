from unittest.mock import MagicMock
from core.captcha_manager import detectar_worker_com_captcha, clicar_solver_button


def test_detectar_worker_por_modal():

    manager = MagicMock()

    manager._driver_locks = {
        1: MagicMock(),
        2: MagicMock(),
        3: MagicMock()
    }

    modal = MagicMock()
    modal.is_displayed.return_value = True

    driver = MagicMock()
    driver.find_element.return_value = modal

    manager.driver1 = driver
    manager.driver2 = None
    manager.driver3 = None

    worker = detectar_worker_com_captcha(manager)

    assert worker == 1


def test_detectar_worker_por_recaptcha():

    manager = MagicMock()

    manager._driver_locks = {
        1: MagicMock(),
        2: MagicMock(),
        3: MagicMock()
    }

    driver = MagicMock()

    driver.find_element.side_effect = [
        Exception(),
        MagicMock()
    ]

    manager.driver1 = driver

    worker = detectar_worker_com_captcha(manager)

    assert worker == 1
def test_detectar_worker_sem_captcha():

    manager = MagicMock()

    manager._driver_locks = {
        1: MagicMock(),
        2: MagicMock(),
        3: MagicMock()
    }

    driver = MagicMock()
    driver.find_element.side_effect = Exception()

    manager.driver1 = driver
    manager.driver2 = driver
    manager.driver3 = driver

    assert detectar_worker_com_captcha(manager) is None

import time

from core.captcha_manager import captcha_travado


def test_captcha_travado_true():

    manager = MagicMock()

    manager.captcha_inicio = {
        1: time.time() - 20
    }

    assert captcha_travado(
        manager,
        1,
        limite=10
    )

def test_captcha_travado_false():

    manager = MagicMock()

    manager.captcha_inicio = {
        1: time.time()
    }

    assert not captcha_travado(
        manager,
        1,
        limite=10
    )


def test_captcha_travado_sem_worker():

    manager = MagicMock()

    manager.captcha_inicio = {}

    assert not captcha_travado(
        manager,
        1
    )

from unittest.mock import MagicMock

from core.captcha_manager import (
    selenium_get_recaptcha_iframe
)


def test_iframe_por_src():

    iframe = MagicMock()

    iframe.get_attribute.side_effect = (
        lambda nome:
        "https://google.com/api2/anchor"
        if nome == "src"
        else ""
    )

    driver = MagicMock()

    driver.find_elements.return_value = [
        iframe
    ]

    resultado = selenium_get_recaptcha_iframe(
        MagicMock(),
        driver
    )

    assert resultado == iframe

def test_iframe_por_title():

    iframe = MagicMock()

    def attrs(nome):

        if nome == "src":
            return ""

        if nome == "title":
            return "reCAPTCHA"

        return ""

    iframe.get_attribute.side_effect = attrs

    driver = MagicMock()

    driver.find_elements.return_value = [
        iframe
    ]

    resultado = selenium_get_recaptcha_iframe(
        MagicMock(),
        driver
    )

    assert resultado == iframe

def test_iframe_nao_encontrado():

    iframe = MagicMock()

    iframe.get_attribute.return_value = ""

    driver = MagicMock()

    driver.find_elements.return_value = [
        iframe
    ]

    resultado = selenium_get_recaptcha_iframe(
        MagicMock(),
        driver
    )

    assert resultado is None

from unittest.mock import patch
from unittest.mock import MagicMock

from core.captcha_manager import (
    clicar_checkbox_recaptcha
)


@patch(
    "core.captcha_manager.WebDriverWait"
)
def test_checkbox_recaptcha_sucesso(
    wait_mock
):

    checkbox = MagicMock()

    wait_mock.return_value.until.return_value = (
        checkbox
    )

    manager = MagicMock()

    manager.selenium_get_recaptcha_iframe.return_value = (
        MagicMock()
    )

    driver = MagicMock()

    assert clicar_checkbox_recaptcha(
        manager,
        driver
    )

def test_checkbox_sem_iframe():

    manager = MagicMock()

    manager.selenium_get_recaptcha_iframe.return_value = None

    driver = MagicMock()

    assert not clicar_checkbox_recaptcha(
        manager,
        driver
    )

from unittest.mock import MagicMock

from core.captcha_manager import (
    verificar_popup_erro_inpi
)


def test_popup_inpi_detectado():

    manager = MagicMock()

    driver = MagicMock()

    driver.find_elements.return_value = [
        MagicMock()
    ]

    driver.find_element.return_value = (
        MagicMock()
    )

    assert verificar_popup_erro_inpi(
        manager,
        driver
    )

def test_popup_inpi_nao_detectado():

    manager = MagicMock()

    driver = MagicMock()

    driver.find_elements.return_value = []

    assert not verificar_popup_erro_inpi(
        manager,
        driver
    )

from unittest.mock import MagicMock
from unittest.mock import patch

from core.captcha_manager import (
    clicar_reload_duplo
)


@patch(
    "core.captcha_manager.pyautogui.locateCenterOnScreen"
)
def test_reload_encontrado(
    locate_mock
):

    pos = MagicMock()

    pos.x = 100
    pos.y = 200

    locate_mock.return_value = pos

    manager = MagicMock()

    manager.reload_img.exists.return_value = True

    assert clicar_reload_duplo(
        manager
    )

def test_reload_sem_imagem():

    manager = MagicMock()

    manager.reload_img.exists.return_value = False

    assert not clicar_reload_duplo(
        manager
    )

@patch(
    "core.captcha_manager.pyautogui.locateCenterOnScreen"
)
def test_solver_button_sucesso(
    locate_mock
):

    pos = MagicMock()

    pos.x = 10
    pos.y = 20

    locate_mock.return_value = pos

    manager = MagicMock()

    manager.pyautogui_lock = MagicMock()

    assert clicar_solver_button(
        manager
    )

@patch(
    "core.captcha_manager.pyautogui.locateCenterOnScreen"
)
def test_solver_button_nao_encontrado(
    locate_mock
):

    locate_mock.return_value = None

    manager = MagicMock()

    manager.pyautogui_lock = MagicMock()

    assert not clicar_solver_button(
        manager
    )