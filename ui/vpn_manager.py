import subprocess
import time
import os
import requests
import sys
import zipfile
import io
import random
OPENVPN_EXE = r"C:\Program Files\OpenVPN\bin\openvpn.exe"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VPN_DIR = os.path.join(BASE_DIR, "vpn")
class VPNManager:
    def __init__(self):
        self.process = None

    def ip_atual(self):
        try:
            return requests.get("https://api.ipify.org", timeout=5).text
        except:
            return "Indisponível"

    def _aguardar_rede_estavel(self, timeout=40):
        self.log_new("⏳ Aguardando rede estabilizar...")
        inicio = time.time()

        while time.time() - inicio < timeout:
            try:
                r = requests.get("https://www.google.com", timeout=5)
                if r.status_code == 200:
                    self.log_new("✅ Rede estabilizada")
                    return
            except:
                pass
            time.sleep(2)

        raise RuntimeError("❌ Rede não estabilizou após VPN")





