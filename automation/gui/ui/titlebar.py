# ??????????????????????????????????????????????????????????????????????????????
#  ui/titlebar.py  ?  Custom frameless window titlebar.
#
#  Replaces the Windows title bar entirely.  Provides:
#    - Drag to move window (click + drag anywhere on the bar)
#    - Minimise button
#    - Maximise / restore button
#    - Close button (with confirmation dialog)
#    - Integrated T2/ RAPTOR title + subtitle
#    - Live local + UTC clock (replacing the old HeaderWidget)
#
#  To change the close confirmation message: edit CLOSE_MSG below.
#  To change button sizes: edit BTN_SIZE.
#  To remove a button: delete the relevant _make_btn call in __init__.
# ??????????????????????????????????????????????????????????????????????????????

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore    import Qt, QTimer, QPoint, QSize
from PySide6.QtGui     import QPainter, QPen, QColor

from config import (
    COL_BG, COL_SURFACE, COL_BORDER, COL_ACCENT,
    COL_TEXT_PRI, COL_TEXT_SEC, COL_RED, COL_AMBER,
    FONT_DISPLAY, FONT_MONO,
)
from ui.confirm import confirm

# ?? Tunables ???????????????????????????????????????????????????????????????????
BTN_SIZE    = 32          # px ? square size of each window control button
BAR_HEIGHT  = 52          # px ? total titlebar height
CLOSE_MSG   = "Close Observatory Control?\n\nAll device connections will be disconnected."


# ?? Window control button ??????????????????????????????????????????????????????

class WinBtn(QPushButton):
    """
    A single frameless window control button.
    icon: 'min' | 'max' | 'restore' | 'close'
    """
    def __init__(self, icon: str, parent=None):
        super().__init__(parent)
        self._icon = icon
        self.setFixedSize(BTN_SIZE, BTN_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(self._base_style())
        self.setToolTip({
            "min":     "Minimise",
            "max":     "Maximise",
            "restore": "Restore",
            "close":   "Close",
        }.get(icon, ""))

    def _base_style(self) -> str:
        hover_bg = "#3A1010" if self._icon == "close" else "#1A2530"
        hover_c  = COL_RED   if self._icon == "close" else COL_ACCENT
        return f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 0px;
            }}
            QPushButton:hover {{
                background: {hover_bg};
            }}
            QPushButton:pressed {{
                background: {hover_bg};
                opacity: 0.8;
            }}
        """

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        is_hover = self.underMouse()
        colour   = COL_RED if (self._icon == "close" and is_hover) else \
                   COL_ACCENT if is_hover else COL_TEXT_SEC
        pen = QPen(QColor(colour), 1.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)

        cx, cy = self.width() / 2, self.height() / 2
        s = 5.5   # half-size of the icon shape

        if self._icon == "min":
            p.drawLine(QPoint(int(cx - s), int(cy + 3)),
                       QPoint(int(cx + s), int(cy + 3)))

        elif self._icon in ("max", "restore"):
            if self._icon == "max":
                p.drawRect(int(cx - s), int(cy - s), int(s * 2), int(s * 2))
            else:
                # Two overlapping squares (restore icon)
                offset = 2
                p.drawRect(int(cx - s + offset), int(cy - s),
                           int(s * 2 - offset), int(s * 2 - offset))
                pen2 = QPen(QColor(colour), 1.5)
                pen2.setCapStyle(Qt.RoundCap)
                p.setPen(pen2)
                p.drawLine(int(cx - s), int(cy - s + offset + 1),
                           int(cx - s), int(cy + s - offset))
                p.drawLine(int(cx - s), int(cy + s - offset),
                           int(cx + s - offset - 1), int(cy + s - offset))

        elif self._icon == "close":
            p.drawLine(QPoint(int(cx - s), int(cy - s)),
                       QPoint(int(cx + s), int(cy + s)))
            p.drawLine(QPoint(int(cx + s), int(cy - s)),
                       QPoint(int(cx - s), int(cy + s)))

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


# ?? Titlebar ???????????????????????????????????????????????????????????????????

class TitleBar(QWidget):
    """
    Custom titlebar widget.  Must be added as the FIRST widget in the
    main window's root layout.  Handles its own mouse drag for window moving.
    Pass the QMainWindow as `window` so it can call show/hide/close on it.
    """

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window      = window
        self._drag_pos    = None
        self._maximised   = False

        self.setFixedHeight(BAR_HEIGHT)
        self.setStyleSheet(f"background: {COL_BG};")

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 0, 4, 0)
        root.setSpacing(0)

        # ?? Left: title + subtitle ?????????????????????????????????????????
        left = QVBoxLayout()
        left.setSpacing(1)
        left.setAlignment(Qt.AlignVCenter)

        title = QLabel("T2 / RAPTOR")

        title.setStyleSheet(f"""
            color: {COL_ACCENT};
            font-family: "{FONT_DISPLAY}";
            font-size: 18pt;
            font-weight: 700;
            letter-spacing: 4px;
            background: transparent;
        """)
        left.addWidget(title)

        subtitle = QLabel("OBSERVATORY CONTROL SYSTEM")
        subtitle.setStyleSheet(f"""
            color: {COL_TEXT_SEC};
            font-family: "{FONT_DISPLAY}";
            font-size: 10pt;
            font-weight: 600;
            letter-spacing: 4px;
            background: transparent;
        """)
        left.addWidget(subtitle)
        root.addLayout(left)

        root.addStretch()

        # ?? Centre: clock ??????????????????????????????????????????????????
        clock_col = QVBoxLayout()
        clock_col.setSpacing(0)
        clock_col.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        self._local_lbl = QLabel()
        self._local_lbl.setStyleSheet(f"""
            color: {COL_TEXT_PRI};
            font-family: "{FONT_MONO}";
            font-size: 20pt;
            font-weight: 400;
            letter-spacing: 2px;
            background: transparent;
        """)
        self._local_lbl.setAlignment(Qt.AlignRight)
        clock_col.addWidget(self._local_lbl)

        self._utc_lbl = QLabel()
        self._utc_lbl.setStyleSheet(f"""
            color: {COL_TEXT_SEC};
            font-family: "{FONT_MONO}";
            font-size: 9pt;
            font-weight: 400;
            letter-spacing: 2px;
            background: transparent;
        """)
        self._utc_lbl.setAlignment(Qt.AlignRight)
        clock_col.addWidget(self._utc_lbl)

        root.addLayout(clock_col)
        root.addSpacing(16)

        # ?? Right: window control buttons ??????????????????????????????????
        # Subtle vertical separator before buttons
        sep = QWidget()
        sep.setFixedSize(1, BAR_HEIGHT - 16)
        sep.setStyleSheet(f"background: {COL_BORDER};")
        root.addWidget(sep, 0, Qt.AlignVCenter)
        root.addSpacing(4)

        self._min_btn     = WinBtn("min")
        self._max_btn     = WinBtn("max")
        self._close_btn   = WinBtn("close")

        self._min_btn.clicked.connect(self._on_minimise)
        self._max_btn.clicked.connect(self._on_maximise)
        self._close_btn.clicked.connect(self._on_close)
        for btn in (self._min_btn, self._max_btn, self._close_btn):
            root.addWidget(btn)

        # ?? Clock tick ?????????????????????????????????????????????????????
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick)
        self._clock.start(1000)
        self._tick()

    # ?? Clock ??????????????????????????????????????????????????????????????

    def _tick(self):
        self._local_lbl.setText(datetime.now().strftime("%H:%M:%S  QLD"))
        self._utc_lbl.setText(datetime.now(timezone.utc).strftime("%H:%M:%S  UTC"))

    # ?? Window controls ????????????????????????????????????????????????????

    def _on_minimise(self):
        self._window.showMinimized()

    def _on_maximise(self):
        if self._maximised:
            self._window.showNormal()
            self._max_btn._icon = "max"
            self._maximised = False
        else:
            self._window.showMaximized()
            self._max_btn._icon = "restore"
            self._maximised = True
        self._max_btn.update()

    def _on_close(self):
        if confirm(self._window, "Close Observatory Control", CLOSE_MSG, danger=True):
            self._window.close()

    # ?? Drag to move ???????????????????????????????????????????????????????

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() \
                             - self._window.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        """Double-click titlebar to maximise/restore."""
        if event.button() == Qt.LeftButton:
            self._on_maximise()

    # ?? Bottom accent line ?????????????????????????????????????????????????

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        # Thin cyan accent line along the bottom of the titlebar
        p.setPen(QPen(QColor(COL_ACCENT + "88"), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)