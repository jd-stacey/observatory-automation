# ===============================================================================
#  ui/controls_bar.py  -  Top control bar.
#
#  Contains:  [CONNECT ALL]  ···spacer···  [START NIGHT]  [END NIGHT]
#
#  To change button labels / colours, edit the constants at the top.
#  To add a new top-bar button, copy one of the _make_nav_btn() calls.
# ===============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt

from config import COL_ACCENT, COL_GREEN, COL_RED, COL_AMBER
from styles import nav_button_style


class ControlsBar(QWidget):
    connect_all_requested = Signal()
    start_night_requested = Signal()
    end_night_requested   = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # -- Connect All -------------------------------------------------------
        self.connect_btn = self._make_nav_btn("\u002B   CONNECT ALL", COL_ACCENT)
        self.connect_btn.setObjectName("connectBtn")
        self.connect_btn.setStyleSheet(nav_button_style(COL_ACCENT) + 
                                       """QPushButton#connectBtn:hover {background-color: #006D73;}""")
        self.connect_btn.clicked.connect(self.connect_all_requested)
        layout.addWidget(self.connect_btn)

        layout.addStretch()

        # -- Start Night -------------------------------------------------------
        start_btn = self._make_nav_btn("\u263E   START NIGHT", COL_GREEN)
        start_btn.clicked.connect(self.start_night_requested)
        layout.addWidget(start_btn)

        # -- End Night -------------------------------------------------------
        end_btn = self._make_nav_btn("\u2600   END NIGHT", COL_RED)
        end_btn.clicked.connect(self.end_night_requested)
        layout.addWidget(end_btn)

    def _make_nav_btn(self, label: str, colour: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setStyleSheet(nav_button_style(colour))
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def set_connecting(self, connecting: bool):
        """Visual feedback while connection is in progress."""
        self.connect_btn.setText("CONNECTING..." if connecting else "\u002B   CONNECT ALL")
        self.connect_btn.setEnabled(not connecting)
        style_colour = COL_AMBER if connecting else COL_ACCENT
        self.connect_btn.setStyleSheet(nav_button_style(style_colour))
