# ===============================================================================
#  ui/header.py  -  Title bar + clock.
#
#  Clock shows:
#    Local time  (large)     - edit FS_CLOCK_MAIN in config.py to resize
#    UTC underneath (smaller) - edit FS_CLOCK_SUB in config.py to resize
#
#  To swap which is larger / smaller, swap the font size assignments below.
#  To show only one timezone, delete the other QLabel and its timer update.
# ===============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import QTimer, Qt

from styles import header_title_style, header_sub_style, clock_main_style, clock_sub_style


class HeaderWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- Left: Observatory title -------------------------------------------
        left = QVBoxLayout()
        left.setSpacing(2)

        title = QLabel("T2 / RAPTOR")
        title.setStyleSheet(header_title_style())
        left.addWidget(title)

        subtitle = QLabel("OBSERVATORY CONTROL SYSTEM")
        subtitle.setStyleSheet(header_sub_style())
        left.addWidget(subtitle)

        layout.addLayout(left)
        layout.addStretch()

        # -- Right: Clock ----------------------------------------------------
        right = QVBoxLayout()
        right.setSpacing(0)
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._local_lbl = QLabel()
        self._local_lbl.setStyleSheet(clock_main_style())
        self._local_lbl.setAlignment(Qt.AlignRight)
        right.addWidget(self._local_lbl)

        self._utc_lbl = QLabel()
        self._utc_lbl.setStyleSheet(clock_sub_style())
        self._utc_lbl.setAlignment(Qt.AlignRight)
        right.addWidget(self._utc_lbl)

        layout.addLayout(right)

        # -- Tick every second ------------------------------------------------
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _tick(self):
        now_local = datetime.now()
        now_utc   = datetime.now(timezone.utc)

        # Local: HH:MM:SS  (24h - change strftime format here to customise)
        self._local_lbl.setText(now_local.strftime("%H:%M:%S  QLD"))

        # UTC: HH:MM:SS UTC  (smaller, underneath)
        self._utc_lbl.setText(now_utc.strftime("%H:%M:%S  UTC"))
