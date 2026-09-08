"""
Gerador de Licenças

Uso:
1. Cole o Machine ID enviado pelo cliente.
2. Informe a data de validade.
3. Clique em "Gerar Licença".
4. Copie a licença gerada.
"""

import tkinter as tk
from tkinter import messagebox
from datetime import datetime

from core.licenca import gerar_licenca


def gerar():
    machine_id = entrada_id.get().strip()
    data_validade = entrada_data.get().strip()

    if not machine_id:
        messagebox.showwarning("Atenção", "Informe o Machine ID.")
        return

    if not data_validade:
        messagebox.showwarning("Atenção", "Informe a data de validade.")
        return

    try:
        datetime.strptime(data_validade, "%Y-%m-%d")
    except ValueError:
        messagebox.showerror(
            "Data inválida",
            "Use o formato:\nAAAA-MM-DD\n\nExemplo:\n2026-12-31"
        )
        return

    try:
        licenca = gerar_licenca(machine_id, data_validade)

        resultado.config(state="normal")
        resultado.delete("1.0", tk.END)
        resultado.insert(tk.END, licenca)
        resultado.config(state="disabled")

        lbl_status.config(
            text=f"✅ Validade: {data_validade}",
            fg="green"
        )

    except Exception as e:
        messagebox.showerror("Erro", str(e))


def copiar():
    texto = resultado.get("1.0", tk.END).strip()

    if not texto:
        return

    janela.clipboard_clear()
    janela.clipboard_append(texto)

    messagebox.showinfo("Copiado", "Licença copiada para a área de transferência.")


# ==========================
# Interface
# ==========================

janela = tk.Tk()
janela.title("🔐 Gerador de Licenças")
janela.geometry("720x430")
janela.resizable(False, False)

titulo = tk.Label(
    janela,
    text="GERADOR DE LICENÇAS",
    font=("Arial", 16, "bold"),
    fg="#0066CC"
)
titulo.pack(pady=15)

# Machine ID
tk.Label(
    janela,
    text="Machine ID do Cliente:",
    font=("Arial", 11)
).pack(anchor="w", padx=20)

entrada_id = tk.Entry(
    janela,
    width=95,
    font=("Consolas", 10)
)

entrada_id.pack(padx=20, pady=5)

# Data
tk.Label(
    janela,
    text="Data de validade (AAAA-MM-DD):",
    font=("Arial", 11)
).pack(anchor="w", padx=20, pady=(10, 0))

entrada_data = tk.Entry(
    janela,
    width=20,
    font=("Arial", 11)
)

entrada_data.pack(anchor="w", padx=20, pady=5)

entrada_data.insert(0, "2026-12-31")

# Botão Gerar
tk.Button(
    janela,
    text="🔑 Gerar Licença",
    command=gerar,
    bg="#0B8E2C",
    fg="white",
    font=("Arial", 11, "bold"),
    width=22,
    height=1
).pack(pady=15)

# Resultado
tk.Label(
    janela,
    text="Licença Gerada:",
    font=("Arial", 11)
).pack(anchor="w", padx=20)

resultado = tk.Text(
    janela,
    height=7,
    font=("Consolas", 10),
    wrap="word"
)

resultado.pack(
    padx=20,
    pady=5,
    fill="x"
)

resultado.config(state="disabled")

# Status
lbl_status = tk.Label(
    janela,
    text="",
    font=("Arial", 10, "bold")
)

lbl_status.pack(pady=5)

# Copiar
tk.Button(
    janela,
    text="📋 Copiar Licença",
    command=copiar,
    width=20,
    font=("Arial", 10)
).pack(pady=10)

janela.mainloop()