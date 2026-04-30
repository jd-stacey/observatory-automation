from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt


BTN_BASE = """
    QPushButton {
        min-width: 90px;
        min-height: 28px;
        padding: 4px 16px;
        border-radius: 3px;
        font-weight: 600;
        font-size: 9pt;
        letter-spacing: 1px;
        margin: 0px 6px;
    }
"""

CANCEL_STYLE = BTN_BASE + """
    QPushButton {
        color: #8B949E;
        background: transparent;
        border: 1px solid #26303A;
    }
    QPushButton:hover {
        color: #E6EDF3;
        border-color: #8B949E;
        background: #1C2530;
    }
"""

OK_STYLE = BTN_BASE + """
    QPushButton {
        color: #E6EDF3;
        background: transparent;
        border: 1px solid #26303A;
    }
    QPushButton:hover {
        color: #00E5FF;
        border-color: #00E5FF;
        background: #0D1F2A;
    }
"""

DANGER_STYLE = BTN_BASE + """
    QPushButton {
        color: #EF4444;
        background: transparent;
        border: 1px solid #EF444466;
    }
    QPushButton:hover {
        color: #EF4444;
        border-color: #EF4444;
        background: #2A1010;
    }
"""

def confirm(parent, title: str, message: str, danger: bool = False) -> bool:
    """
    Show a confirmation dialogue. Returns True if user clicks OK/Yes.
    danger=True tints the confirm button red.
    """
    
    dlg = QMessageBox(parent)
    dlg.setWindowTitle(f"Confirm: {title}")
    dlg.setText(message)
    dlg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
    dlg.setDefaultButton(QMessageBox.Cancel)  # default to Cancel for safety
    dlg.setIcon(QMessageBox.Warning if danger else QMessageBox.Question)
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
    
    dlg.button(QMessageBox.Cancel).setStyleSheet(CANCEL_STYLE)
    dlg.button(QMessageBox.Ok).setStyleSheet(DANGER_STYLE if danger else OK_STYLE)
    dlg.setStyleSheet("""QMessageBox QLabel {border: none; background: transparent;}""")
    # if danger:
    #     btn = dlg.button(QMessageBox.Ok)
    #     btn.setStyleSheet("color: #EF4444; font-weight: bold;")
    
    return dlg.exec() == QMessageBox.Ok
    