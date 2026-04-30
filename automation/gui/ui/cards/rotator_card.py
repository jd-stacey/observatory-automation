# ==============================================================================
#  ui/cards/rotator_card.py
#
#  Rotator has no action buttons by design - read-only status display.
#  To add a HALT button, uncomment the add_button block and set_callbacks.
# ==============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config import COL_TEXT_PRI, COL_ACCENT, status_colour, DEVICE_CONFIGS
from ui.device_card import DeviceCard
from ui.icons import draw_rotator, draw_rotator2, draw_rotator3
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PySide6.QtGui import QDoubleValidator
from PySide6.QtCore import Qt, Signal, QLocale
from ui.confirm import confirm
from styles import nav_button_style, plain_label

class RotatorMoveDialog(QDialog):
    def __init__(self, current_pos, limits: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Move Rotator")
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setFixedWidth(260)
        self.setStyleSheet("background: #121821; color: #E6EDF3;")
        lo = QVBoxLayout(self)
        lo.setSpacing(10); lo.setContentsMargins(20, 18, 20, 18)
        lo.addWidget(plain_label(f"Current position: {current_pos:.2f}°" if current_pos is not None else "Current position: ?"))
        # lo.addWidget(QLabel(f"Current position: {current_pos:.2f}°" if current_pos is not None else "Current position: ?"))
        lim_min = limits.get("min", 0)
        lim_max = limits.get("max", 360)
        lo.addWidget(plain_label(f"Valid range: {lim_min}° - {lim_max}°"))
        # lo.addWidget(QLabel(f"Valid range: {lim_min}° - {lim_max}°"))
        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Enter target degrees")
        v = QDoubleValidator(limits.get("min", 0), limits.get("max", 360), 2, self)
        v.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self._edit.setValidator(v)
        # self._edit.setValidator(QDoubleValidator(lim_min, lim_max, 2, self))
        self._edit.setStyleSheet(f"""
            QLineEdit {{
                background: #171E2A; border: 1px solid #26303A;
                border-radius: 2px; padding: 5px 8px;
                color: #E6EDF3; font-family: Consolas; font-size: 11pt;
            }}
            QLineEdit:focus {{ border-color: #00E5FF; }}
        """)
        lo.addWidget(self._edit)
        btn_row = QHBoxLayout()
        cancel = QPushButton("CANCEL")
        cancel.setStyleSheet(nav_button_style("#8B949E"))
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        self._ok = QPushButton("MOVE")
        self._ok.setStyleSheet(nav_button_style("#00E5FF"))
        self._ok.setEnabled(False)
        self._ok.setDefault(True)
        self._ok.clicked.connect(self.accept)
        btn_row.addWidget(self._ok)
        lo.addLayout(btn_row)
        self._edit.textChanged.connect(
            lambda t: self._ok.setEnabled(bool(t) and self._edit.hasAcceptableInput()))
        self._edit.returnPressed.connect(
            lambda: self.accept() if self._edit.hasAcceptableInput() else None)

    def position(self) -> float:
        return float(self._edit.text())


class RotatorCard(DeviceCard):
    move_requested = Signal(float)
    def __init__(self, parent=None):
        super().__init__("rotator", "ROTATOR", draw_rotator3, parent)
        
        self.add_info_row("position", "POSITION")
        self.add_info_row("moving",   "MOVING")
        self.add_info_row("limits",   "MECH LIMITS")
        self._current_pos = None

        # No action buttons for rotator.
        # Uncomment below to add a HALT button:
        # self.add_button("halt", "HALT", danger=True)
        self.add_button("move", "MOVE", self._on_move_btn)

        # Pre-populate mechanical limits from config (static, not from driver)
        lim = DEVICE_CONFIGS["rotator"].get("mechanical_limits", {})
        self._limits = {"min": lim.get("min_deg", 0), "max": lim.get("max_deg", 360)}
        if lim:
            lim_str = f"{lim.get('min_deg', '?')}° - {lim.get('max_deg', '?')}°"
        else:
            lim_str = "N/A"
        self.row("limits").set_value(lim_str)

    # def set_callbacks(self, halt_cb=None):
    #     if halt_cb:
    #         self.button("halt").clicked.connect(halt_cb)

    def update_from_info(self, info: dict):
        if not info.get("connected"):
            self.badge.set_status("OFFLINE", status_colour("OFFLINE"))
            return

        pos    = info.get("position_deg")
        self._current_pos = pos
        moving = info.get("moving", False)

        self.badge.set_status("ONLINE", status_colour("ONLINE"))
        self.set_connected(COL_ACCENT)   # rotator uses accent colour when connected

        self.row("position").set_value(
            f"{pos:.2f}°" if pos is not None else "-")
        self.row("moving").set_value(
            "YES" if moving else "NO",
            status_colour("MOVING") if moving else None)
        self.enable_button("move", not info.get("moving", False))
    
    def _on_move_btn(self):
        dlg = RotatorMoveDialog(self._current_pos, self._limits, parent=self)
        if dlg.exec() == QDialog.Accepted:
            target = dlg.position()
            if confirm(self, "Move Rotator", f"Move rotator to {target:.2f}°?"):
                self.move_requested.emit(target)
