# ==============================================================================
#  ui/device_card.py  -  The reusable DeviceCard base widget.
#
#  Layout (left -> right):
#    -----------------------------------------------------
#    | Icon box |  Status badge + info rows   |  Buttons |
#    | (fixed W)|  (stretches)                | (fixed W)|
#    -----------------------------------------------------
#
#  All four cards share this base so their columns line up perfectly.
#  Subclasses add rows and buttons in their own __init__.
# ==============================================================================

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy,
    QFrame,
)
from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPen

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    COL_BG, COL_PANEL, COL_BORDER, COL_TEXT_SEC, COL_TEXT_DIM,
    COL_ACCENT, COL_GREEN, COL_RED, COL_AMBER, COL_INACTIVE,
    CARD_ICON_WIDTH, CARD_ICON_HEIGHT, CARD_MIN_HEIGHT, CARD_PADDING,
    LAMP_SIZE, LAMP_GAP, INFO_ROW_HEIGHT, INFO_ROW_SPACING,
    FONT_MONO, FONT_DISPLAY, COL_TEXT_PRI
)
from styles import (
    card_style, icon_box_style, badge_style, label_style,
    value_style, action_button_style, card_title_style,
)


# -- Lamp -----------------------------------------------------------------------

class Lamp(QWidget):
    """
    Small circular status indicator.  Click triggers reconnect signal.
    States: 'off' | 'connecting' | 'connected' | 'disconnected'
    """
    clicked = Signal()

    _COLOURS = {
        "connected":    COL_GREEN,
        "disconnected": COL_RED,
        "connecting":   COL_AMBER,
        "off":          COL_INACTIVE,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "off"
        self._pulse_bright = True
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(450)
        self._pulse_timer.timeout.connect(self._on_pulse)
        self.setFixedSize(LAMP_SIZE, LAMP_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to reconnect")
        # self._timer_id = None
        # self.setFixedSize(LAMP_SIZE, LAMP_SIZE)
        # self.setCursor(Qt.PointingHandCursor)
        # self.setToolTip("Click to reconnect")

    def _on_pulse(self):
        self._pulse_bright = not self._pulse_bright
        self.update()
    
    def set_state(self, state: str):
        self._state = state
        self._pulse_timer.stop()
        if state == "connecting":
            self._pulse_bright = True
            self._pulse_timer.start()
        self.update()
    
    # def set_state(self, state: str):
    #     self._state = state
    #     if self._timer_id is not None:
    #         self.killTimer(self._timer_id)
    #         self._timer_id = None
    #     if state == "connecting":
    #         self._pulse_bright = True
    #         self._timer_id = self.startTimer(450)
    #     self.update()

    # def timerEvent(self, event):
    #     self._pulse_bright = not self._pulse_bright
    #     self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        colour = self._COLOURS.get(self._state, COL_INACTIVE)
        if self._state == "connecting" and not self._pulse_bright:
            colour = COL_INACTIVE
        c = QColor(colour)
        if self._state != "off":
            glow = QColor(colour)
            glow.setAlpha(40)
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(0, 0, LAMP_SIZE, LAMP_SIZE)
        p.setPen(QPen(c.darker(120), 1))
        p.setBrush(c)
        m = 2
        p.drawEllipse(m, m, LAMP_SIZE - m * 2, LAMP_SIZE - m * 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


# -- Icon Canvas -----------------------------------------------------------------

class IconCanvas(QWidget):
    """Fixed-size widget that calls a draw_fn(painter, cx, cy, size, colour)."""

    def __init__(self, draw_fn_inactive, draw_fn_active=None, parent=None):
        super().__init__(parent)
        self._draw_inactive = draw_fn_inactive
        self._draw_active   = draw_fn_active or draw_fn_inactive
        self._colour     = COL_TEXT_DIM
        self._connected  = False
        self.setFixedSize(CARD_ICON_WIDTH, CARD_ICON_HEIGHT)

    def set_colour(self, colour, connected=False):
        self._colour    = colour
        self._connected = connected
        self.update()

    def paintEvent(self, event):
        p  = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx = self.width()  / 2
        cy = self.height() / 2
        sz = min(cx, cy) * 0.82
        fn = self._draw_active if self._connected else self._draw_inactive
        fn(p, cx, cy, sz, self._colour)
    
    # def __init__(self, draw_fn_inactive, drawparent=None):
    #     super().__init__(parent)
    #     self._draw_fn = draw_fn
    #     self._colour  = COL_TEXT_DIM
    #     self.setFixedSize(CARD_ICON_WIDTH, CARD_ICON_HEIGHT)

    # def set_colour(self, colour: str):
    #     self._colour = colour
    #     self.update()

    # def paintEvent(self, event):
    #     p = QPainter(self)
    #     p.setRenderHint(QPainter.Antialiasing)
    #     cx = self.width()  / 2
    #     cy = self.height() / 2
    #     sz = min(cx, cy) * 0.82
    #     self._draw_fn(p, cx, cy, sz, self._colour)


# -- Info Row ------------------------------------------------------------------

class InfoRow(QWidget):
    """A single label + value row inside the card's info section."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(INFO_ROW_HEIGHT)
        self.setStyleSheet(f"background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._label = QLabel(label.upper())
        self._label.setStyleSheet(label_style())
        self._label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._label.setContentsMargins(0, 0, 8, 0)

        self._value = QLabel("-") 
        self._value.setStyleSheet(value_style())
        self._value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(self._label)
        layout.addWidget(self._value, 1)

    def set_value(self, text: str, colour: str = None):
        """Update the value label.  colour overrides default text colour."""
        self._value.setText(str(text))
        self._value.setStyleSheet(value_style(colour))


# -- Status Badge -----------------------------------------------------------------

class StatusBadge(QLabel):
    def __init__(self, parent=None):
        super().__init__("OFFLINE", parent)
        self._update("OFFLINE", COL_TEXT_SEC)

    def set_status(self, text: str, colour: str):
        self._update(text.upper(), colour)

    def _update(self, text: str, colour: str):
        self.setText(text)
        self.setStyleSheet(badge_style(colour))
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)


# -- Action Button --------------------------------------------------------------

class ActionButton(QPushButton):
    def __init__(self, text: str, danger: bool = False, parent=None):
        super().__init__(text.upper(), parent)
        self._danger = danger
        self.setStyleSheet(action_button_style(danger))
        self.setFixedHeight(24)
        self.setCursor(Qt.PointingHandCursor)


# -- Device Card -------------------------------------------------------------------

class DeviceCard(QFrame):
    """
    Base card.  Subclasses call add_info_row() and add_button() in their
    __init__ to populate the middle and right sections.
    """
    reconnect_requested = Signal(str)   # emits device key e.g. "telescope"

    def __init__(self, device_key: str, title: str, draw_fn, draw_fn_active=None, parent=None):
        super().__init__(parent)
        self._device_key = device_key
        self._connected  = False
        self.setStyleSheet(card_style())
        self.setMinimumHeight(CARD_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # -- Root horizontal layout ----------------------------------------
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Icon column ----------------------------------------------------
        icon_col = QWidget()
        icon_col.setFixedWidth(CARD_ICON_WIDTH)
        icon_col.setStyleSheet(icon_box_style())
        icon_layout = QVBoxLayout(icon_col)
        icon_layout.setContentsMargins(0, 10, 0, 10)
        icon_layout.setSpacing(5)
        icon_layout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        
        self.icon = IconCanvas(draw_fn, draw_fn_active)
        # self.icon = IconCanvas(draw_fn)
        icon_layout.addWidget(self.icon, 0, Qt.AlignHCenter)

        lamp_row = QWidget()
        lamp_layout = QHBoxLayout(lamp_row)
        lamp_layout.setContentsMargins(0, 0, 0, 0)
        lamp_layout.setSpacing(LAMP_GAP)
        lamp_layout.setAlignment(Qt.AlignHCenter)
        self.lamp_a = Lamp()
        self.lamp_b = Lamp()
        self.lamp_a.clicked.connect(lambda: self.reconnect_requested.emit(device_key))
        self.lamp_b.clicked.connect(lambda: self.reconnect_requested.emit(device_key))
        lamp_layout.addWidget(self.lamp_a)
        lamp_layout.addWidget(self.lamp_b)
        icon_layout.addWidget(lamp_row, 0, Qt.AlignHCenter)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(card_title_style())
        title_lbl.setAlignment(Qt.AlignHCenter)
        title_lbl.setContentsMargins(4, 0, 4, 0)
        icon_layout.addWidget(title_lbl, 0, Qt.AlignHCenter)
        
        # icon_layout.addWidget(self.icon, 0, Qt.AlignHCenter)

        # title_lbl = QLabel(title)
        # title_lbl.setStyleSheet(card_title_style())
        # title_lbl.setAlignment(Qt.AlignHCenter)
        # title_lbl.setContentsMargins(4, 0, 4, 0)
        # icon_layout.addWidget(title_lbl, 0, Qt.AlignHCenter)

        # lamp_row = QWidget()
        # lamp_layout = QHBoxLayout(lamp_row)
        # lamp_layout.setContentsMargins(0, 0, 0, 0)
        # lamp_layout.setSpacing(LAMP_GAP)
        # lamp_layout.setAlignment(Qt.AlignHCenter)
        # self.lamp_a = Lamp()
        # self.lamp_b = Lamp()
        # self.lamp_a.clicked.connect(lambda: self.reconnect_requested.emit(device_key))
        # self.lamp_b.clicked.connect(lambda: self.reconnect_requested.emit(device_key))
        # lamp_layout.addWidget(self.lamp_a)
        # lamp_layout.addWidget(self.lamp_b)
        # icon_layout.addWidget(lamp_row, 0, Qt.AlignHCenter)

        root.addWidget(icon_col)

        # -- Info column ----------------------------------------------------
        info_col = QWidget()
        info_layout = QVBoxLayout(info_col)
        info_layout.setContentsMargins(CARD_PADDING, CARD_PADDING,
                                       CARD_PADDING // 2, CARD_PADDING)
        info_layout.setSpacing(INFO_ROW_SPACING)
        info_layout.setAlignment(Qt.AlignTop)

        self.badge = StatusBadge()
        info_layout.addWidget(self.badge)

        info_layout.addSpacing(3)

        # Subclasses add rows here via add_info_row()
        self._info_layout = info_layout
        self._rows: dict[str, InfoRow] = {}

        root.addWidget(info_col, 1)

        # -- Button column ----------------------------------------------------
        btn_col = QWidget()
        btn_col.setFixedWidth(82)
        btn_layout = QVBoxLayout(btn_col)
        btn_layout.setContentsMargins(0, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        btn_layout.setSpacing(4)
        btn_layout.setAlignment(Qt.AlignTop)
        self._btn_layout = btn_layout
        self._buttons: dict[str, ActionButton] = {}

        root.addWidget(btn_col)

    # -- Public helpers (called by subclasses) ---------------------------------

    def add_info_row(self, key: str, label: str) -> InfoRow:
        row = InfoRow(label)
        self._info_layout.addWidget(row)
        self._rows[key] = row
        return row

    def add_button(self, key: str, text: str,
                   callback=None, danger: bool = False) -> ActionButton:
        btn = ActionButton(text, danger=danger)
        btn.setEnabled(False)
        if callback:
            btn.clicked.connect(callback)
        self._btn_layout.addWidget(btn)
        self._buttons[key] = btn
        return btn

    def row(self, key: str) -> InfoRow:
        return self._rows[key]

    def button(self, key: str) -> ActionButton:
        return self._buttons[key]

    # -- Lamp state ------------------------------------------------------------

    def set_lamp(self, state):
        """Set both lamps to the same state."""
        self.lamp_a.set_state(state)
        self.lamp_b.set_state(state)
        connected = (state == "connected")
        dim_colour = COL_TEXT_DIM if state in ("off", "disconnected") else COL_TEXT_SEC
        self.icon.set_colour(COL_ACCENT if connected else dim_colour, connected=connected)
        
        # colour = COL_TEXT_DIM if state in ("off", "disconnected") else COL_TEXT_SEC if state == "connecting" else None
        # if colour:
        #     self.icon.set_colour(colour)

    def set_connected(self, colour: str):
        """Called when fully connected - set icon to bright colour."""
        self.icon.set_colour(colour, connected=True)

    # -- Enable/disable all action buttons ----------------------------------

    def enable_buttons(self, enabled: bool):
        for btn in self._buttons.values():
            btn.setEnabled(enabled)

    def enable_button(self, key: str, enabled: bool):
        if key in self._buttons:
            self._buttons[key].setEnabled(enabled)
