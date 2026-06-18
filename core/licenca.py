import uuid
import hashlib
import hmac
import os
from datetime import datetime
from pathlib import Path

# =========================
# CONFIG
# =========================

PASTA_APP = Path(os.getenv("LOCALAPPDATA")) / "InpiBusca"
PASTA_APP.mkdir(parents=True, exist_ok=True)

ARQUIVO_LICENCA = PASTA_APP / "sys.dat"

SEGREDO = "3f9a1b7e2c4d8f6a0e5b9c3d7f1a4e8b2c6f0d4a8e3b7c1f5a9d2e6b0c4f8a1"


# =========================
# MACHINE ID
# =========================

def get_machine_id() -> str:
    mac = uuid.getnode()
    return hashlib.sha256(str(mac).encode()).hexdigest()


# =========================
# VALIDAR LICENCA
# =========================

def validar_licenca(licenca: str) -> bool:
    try:
        partes = licenca.strip().split("|")
        if len(partes) != 3:
            return False

        machine_id_licenca, data_expiracao, assinatura_recebida = partes

        if machine_id_licenca != get_machine_id():
            return False

        dados = f"{machine_id_licenca}|{data_expiracao}"
        assinatura_correta = hmac.new(
            SEGREDO.encode(),
            dados.encode(),
            hashlib.sha256
        ).hexdigest()

        if assinatura_recebida != assinatura_correta:
            return False

        data_validade = datetime.strptime(data_expiracao, "%Y-%m-%d")
        if datetime.now() > data_validade:
            return False

        return True

    except Exception:
        return False


# =========================
# GERAR LICENCA (uso do desenvolvedor)
# =========================

def gerar_licenca(machine_id: str, data_expiracao: str) -> str:
    """
    Uso: gerar_licenca("abc123...", "2026-12-31")
    Retorna a string de licenca para enviar ao cliente.
    """
    dados = f"{machine_id}|{data_expiracao}"
    assinatura = hmac.new(
        SEGREDO.encode(),
        dados.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{machine_id}|{data_expiracao}|{assinatura}"


# =========================
# SALVAR / CARREGAR
# =========================

def salvar_licenca(licenca: str):
    with open(ARQUIVO_LICENCA, "w") as f:
        f.write(licenca.strip())


def carregar_licenca():
    if ARQUIVO_LICENCA.exists():
        with open(ARQUIVO_LICENCA, "r") as f:
            return f.read().strip()
    return None


# =========================
# VERIFICAR
# =========================

def licenca_valida() -> bool:
    licenca = carregar_licenca()
    return bool(licenca and validar_licenca(licenca))


def dias_restantes():
    licenca = carregar_licenca()
    if not licenca:
        return None
    try:
        _, data_expiracao, _ = licenca.split("|")
        data_validade = datetime.strptime(data_expiracao, "%Y-%m-%d")
        delta = data_validade - datetime.now()
        return max(0, delta.days)
    except Exception:
        return None
