import socket
import time

import requests
from selenium.common import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


def internet_disponivel(timeout=5):
    try:
        socket.create_connection(
            ("8.8.8.8", 53),
            timeout=2
        )
        return True
    except:
        return False


def aguardar_rede(timeout=600):

    inicio = time.time()

    while True:

        if internet_disponivel():
            return True

        if time.time() - inicio > timeout:
            return False

        time.sleep(10)


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


def wait_title(self, driver, titulo, timeout=30):

    try:
        WebDriverWait(driver, timeout).until(
            EC.title_contains(titulo)
        )

    except TimeoutException:

        if not internet_disponivel():

            self.log_new(
                "🌐 Internet caiu aguardando título."
            )

            if aguardar_rede():

                return WebDriverWait(
                    driver,
                    timeout
                ).until(
                    EC.title_contains(titulo)
                )

        raise

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