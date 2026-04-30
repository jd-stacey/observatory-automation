# ===============================================================================
#  ui/log_console.py  -  Coloured log console at the bottom of the window.
#
#  Log level colours are set in config.LOG_COLOURS.
#  Font and size: config.FONT_MONO / FS_LOG.
#  Height: config.LOG_HEIGHT.
# ===============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton
from PySide6.QtGui import QTextCursor, QColor
from PySide6.QtCore import Qt

from config import COL_TEXT_SEC, COL_TEXT_DIM, LOG_COLOURS, LOG_HEIGHT
from styles import log_section_label_style, nav_button_style, COL_RED


class LogConsole(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # -- Header row --------------------------------------------------------
        hdr = QHBoxLayout()
        lbl = QLabel("SYSTEM LOG")
        lbl.setStyleSheet(log_section_label_style())
        hdr.addWidget(lbl)
        hdr.addStretch()

        clear_btn = QPushButton("CLEAR")
        clear_btn.setStyleSheet(nav_button_style(COL_TEXT_SEC))
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self.clear)
        clear_btn.setCursor(Qt.PointingHandCursor)
        hdr.addWidget(clear_btn)
        layout.addLayout(hdr)

        # -- Text area --------------------------------------------------------
        self._edit = QTextEdit()
        self._edit.setReadOnly(True)
        self._edit.setFixedHeight(LOG_HEIGHT)
        layout.addWidget(self._edit)

    def log(self, level: str, message: str):
        """Append a coloured log entry.  Thread-safe via Qt signal scheduling."""
        ts    = datetime.now().strftime("%H:%M:%S")
        # ts    = datetime.now(timezone.utc).strftime("%H:%M:%S") # if pref system log to show UTC time
        col   = LOG_COLOURS.get(level, COL_TEXT_SEC)
        dim   = COL_TEXT_DIM

        cursor = self._edit.textCursor()
        cursor.movePosition(QTextCursor.End)

        def _append(text: str, colour: str):
            fmt = cursor.charFormat()
            fmt.setForeground(QColor(colour))
            cursor.setCharFormat(fmt)
            cursor.insertText(text)

        _append(f"{ts}  ", dim)
        _append(f"[{level:<4s}]  ", col)
        _append(message + "\n", "#C9D1D9")   # near-white body text

        self._edit.setTextCursor(cursor)
        self._edit.ensureCursorVisible()

    def clear(self):
        self._edit.clear()
