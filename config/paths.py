import os
import sys
from pathlib import Path

def pasta_app():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent

BASE_DIR = pasta_app()

def resource_path(relative):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.abspath("."), relative)

FIREFOX_PROFILE_PATH = BASE_DIR / "ui" / "firefox_profile"
FIREFOX_PROFILE_PATH.mkdir(parents=True, exist_ok=True)

FIREFOX_BIN_PATHS = [
    r"C:\Program Files\Mozilla Firefox\firefox.exe",
    r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
]

PROFILE_PATH = BASE_DIR / "ui"/ "chrome_profile"

EXCEL_PROCESSOS_PATH = BASE_DIR / "processos.xlsx"

caminho = BASE_DIR / "solver_button.png"

DOWNLOAD_DIR = BASE_DIR / "pdfs"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
chrome_path = BASE_DIR / "chrome" / "chrome.exe"
driver_path = BASE_DIR / "chromedriver" / "chromedriver.exe"
from openpyxl import Workbook

if not EXCEL_PROCESSOS_PATH.exists():
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "Numero_Processo"
    wb.save(EXCEL_PROCESSOS_PATH)
