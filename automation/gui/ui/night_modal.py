# ===============================================================================
#  ui/night_modal.py  -  Start Night / End Night options dialog.
#
#  To add or remove options, edit START_OPTIONS / END_OPTIONS below.
#  Each entry is (config_key, display_label).
# ===============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from config import COL_GREEN, COL_RED, COL_SURFACE, COL_BORDER, COL_ACCENT, COL_TEXT_SEC
from styles import modal_style, nav_button_style, badge_style

# -- Edit these to change what appears in each modal -------------------------------
START_OPTIONS = [
    ("dome",    "Open dome"),
    ("motors",  "Enable telescope motors"),
    ("covers",  "Open covers"),
]

END_OPTIONS = [
    ("covers",  "Close covers"),
    ("park",    "Park telescope"),
    ("motors",  "Disable telescope motors"),
    ("dome",    "Close dome"),
]
# ===============================================================================


class NightModal(QDialog):
    """
    Modal dialog that collects user choices then calls on_confirm(mode, opts).
    mode = 'start' | 'end'
    opts = dict[key, bool]
    """

    def __init__(self, mode: str, on_confirm, parent=None):
        super().__init__(parent)
        self._mode       = mode
        self._on_confirm = on_confirm
        self._checks: dict[str, QCheckBox] = {}

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setStyleSheet(modal_style())
        self.setMinimumWidth(360)

        colour   = COL_GREEN if mode == "start" else COL_RED
        title    = "\u263E  START NIGHT" if mode == "start" else "\u2600  END NIGHT"
        desc     = ("Select operations to perform at session start:"
                    if mode == "start" else
                    "Select shutdown operations to perform:")
        options  = START_OPTIONS if mode == "start" else END_OPTIONS
        exec_lbl = "EXECUTE" if mode == "start" else "SHUTDOWN"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # -- Title -------------------------------------------------------------
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {colour}; font-size: 12pt; font-weight: 700;"
            f"letter-spacing: 2px;")
        layout.addWidget(title_lbl)

        # -- Accent rule under title -------------------------------------------
        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: {colour}44;")
        layout.addWidget(rule)

        # -- Description -------------------------------------------------------
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(f"color: {COL_TEXT_SEC}; font-size: 9pt;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # -- Checkboxes -------------------------------------------------------
        for key, label in options:
            cb = QCheckBox(label.upper())
            cb.setChecked(False)
            self._checks[key] = cb
            layout.addWidget(cb)

        layout.addSpacing(4)

        # -- Buttons row -----------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton("CANCEL")
        cancel.setStyleSheet(nav_button_style(COL_TEXT_SEC))
        cancel.clicked.connect(self.reject)
        cancel.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(cancel)

        execute = QPushButton(exec_lbl)
        execute.setStyleSheet(nav_button_style(colour))
        execute.clicked.connect(self._execute)
        execute.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(execute)

        layout.addLayout(btn_row)

    def _execute(self):
        opts = {key: cb.isChecked() for key, cb in self._checks.items()}
        self.accept()
        self._on_confirm(self._mode, opts)
