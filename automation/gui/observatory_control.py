# ===============================================================================
#  observatory_control.py  -  Entry point.
#
#  Run:     python observatory_control.py
#  Package: pyinstaller --onefile --windowed observatory_control.py
#
#  All configuration is in config.py.
#  All styling is in styles.py.
#  Device addresses / timeouts are in config.DEVICE_CONFIGS.
# ===============================================================================

import traceback
from PySide6.QtCore import qInstallMessageHandler, QtMsgType

def qt_message_handler(mode, context, message):
    if 'killTimer' in message or 'cannot' in message.lower():
        print(f"\n=== QT WARNING: {message}")
        print("=== Python stack at this moment:")
        traceback.print_stack()
        print("===\n")
    else:
        print(message)

qInstallMessageHandler(qt_message_handler)


import sys
import os
from pathlib import Path

# Add the observatory package to path so all imports resolve
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

# BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# sys.path.insert(0, BASE_DIR)

# sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from ui.main_window import MainWindow
from config import ICON_PATH


def main():
    # High-DPI support (PySide6 handles this automatically on Qt6)
    # import ctypes

    # ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
    #     "observatory_control_t2"
    # )
    
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(ICON_PATH))
    app.setApplicationName("Observatory Control System")
    app.setOrganizationName("T2 Raptor")
    
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
