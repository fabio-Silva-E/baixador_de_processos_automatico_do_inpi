from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QMessageBox, QApplication
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from core.licenca import (
    get_machine_id,
    validar_licenca,
    salvar_licenca,
    licenca_valida,
    dias_restantes
)


class JanelaLicenca(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ativação — INPI Busca")
        self.setFixedSize(480, 280)
        self.setWindowFlags(
            Qt.Dialog |
            Qt.WindowTitleHint |
            Qt.CustomizeWindowHint
        )
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # título
        titulo = QLabel("🔐 Ativação necessária")
        titulo.setFont(QFont("Arial", 14, QFont.Bold))
        titulo.setAlignment(Qt.AlignCenter)
        layout.addWidget(titulo)

        # machine id
        layout.addWidget(QLabel("Seu ID de máquina (envie ao desenvolvedor):"))
        machine_id = get_machine_id()
        row_id = QHBoxLayout()
        self.entry_id = QLineEdit(machine_id)
        self.entry_id.setReadOnly(True)
        row_id.addWidget(self.entry_id)
        btn_copiar = QPushButton("Copiar")
        btn_copiar.setFixedWidth(70)
        btn_copiar.clicked.connect(self._copiar_id)
        row_id.addWidget(btn_copiar)
        layout.addLayout(row_id)

        # licença
        layout.addWidget(QLabel("Cole sua licença abaixo:"))
        self.entry_licenca = QLineEdit()
        self.entry_licenca.setPlaceholderText("xxxx|yyyy-mm-dd|zzzz")
        layout.addWidget(self.entry_licenca)

        # botões
        row_btn = QHBoxLayout()
        btn_ativar = QPushButton("✅ Ativar")
        btn_ativar.setFixedHeight(36)
        btn_ativar.setStyleSheet(
            "background-color: #2ecc71; color: white; font-weight: bold;"
        )
        btn_ativar.clicked.connect(self._ativar)
        row_btn.addWidget(btn_ativar)

        btn_sair = QPushButton("❌ Sair")
        btn_sair.setFixedHeight(36)
        btn_sair.clicked.connect(self.reject)
        row_btn.addWidget(btn_sair)
        layout.addLayout(row_btn)

    def _copiar_id(self):
        QApplication.clipboard().setText(self.entry_id.text())
        QMessageBox.information(self, "Copiado", "ID copiado para a área de transferência!")

    def _ativar(self):
        licenca = self.entry_licenca.text().strip()
        if validar_licenca(licenca):
            salvar_licenca(licenca)
            QMessageBox.information(self, "Sucesso", "✅ Licença ativada com sucesso!")
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Erro",
                "❌ Licença inválida ou expirada.\n"
                "Verifique o código e tente novamente."
            )


def verificar_ou_pedir_licenca() -> bool:
    """
    Retorna True se a licença for válida.
    Abre a janela de ativação caso contrário.
    """
    if licenca_valida():
        return True

    janela = JanelaLicenca()
    resultado = janela.exec_()
    return resultado == QDialog.Accepted
