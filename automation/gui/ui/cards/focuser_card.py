import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QDialog, QLabel, QLineEdit, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator

from config import COL_TEXT_PRI, COL_ACCENT, COL_AMBER, COL_BORDER, COL_PANEL, COL_TEXT_SEC, COL_TEXT_DIM, status_colour, DEVICE_CONFIGS
from styles import action_button_style, nav_button_style, value_style, label_style, plain_label
from ui.device_card import DeviceCard
from ui.icons import draw_focuser, draw_focuser2
from ui.confirm import confirm


# ?? Filter position buttons ????????????????????????????????????????????????????

# FILTER_LABELS = {
#     "c":  "C",
#     "u":  "U",
#     "b":  "B",
#     "v":  "V",
#     "r":  "R",
#     "i":  "I",
#     "c2": "C2",
# }
SPECTRO_KEY = "spectro"


def _filter_btn_style(active: bool = False) -> str:
    border = COL_ACCENT if active else COL_BORDER
    colour = COL_ACCENT if active else COL_TEXT_SEC
    return f"""
        QPushButton {{
            color: {colour};
            background: transparent;
            border: 1px solid {border};
            border-radius: 2px;
            padding: 2px 4px;
            font-size: 7pt;
            font-weight: 700;
            letter-spacing: 0.5px;
            min-width: 26px;
            max-width: 36px;
        }}
        QPushButton:hover {{
            color: {COL_ACCENT};
            border-color: {COL_ACCENT};
            background: {COL_ACCENT}18;
        }}
        QPushButton:disabled {{
            color: {COL_TEXT_DIM};
            border-color: {COL_BORDER};
        }}
    """


# ?? Move-to dialog ?????????????????????????????????????????????????????????????

class MoveDialog(QDialog):
    """Simple dialog to enter a target focuser position."""

    def __init__(self, current_pos, limits: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Move Focuser")
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setFixedWidth(280)
        self.setStyleSheet(f"background: #121821; color: #E6EDF3;")

        lo = QVBoxLayout(self)
        lo.setSpacing(12)
        lo.setContentsMargins(20, 18, 20, 18)

        lo.addWidget(plain_label(f"Current position: {current_pos}"))

        lim_min = limits.get("min", 0)
        lim_max = limits.get("max", 30000)
        lo.addWidget(plain_label(f"Valid range: {lim_min} - {lim_max}"))

        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Enter target position")
        self._edit.setValidator(QIntValidator(lim_min, lim_max, self))
        self._edit.setStyleSheet(f"""
            QLineEdit {{
                background: {COL_PANEL};
                border: 1px solid {COL_BORDER};
                border-radius: 2px;
                padding: 5px 8px;
                color: #E6EDF3;
                font-family: Consolas;
                font-size: 11pt;
            }}
            QLineEdit:focus {{ border-color: {COL_ACCENT}; }}
        """)
        lo.addWidget(self._edit)

        btn_row = QHBoxLayout()
        cancel = QPushButton("CANCEL")
        cancel.setStyleSheet(nav_button_style("#8B949E"))
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        self._ok = QPushButton("MOVE")
        self._ok.setStyleSheet(nav_button_style(COL_ACCENT))
        self._ok.setEnabled(False)
        self._ok.clicked.connect(self.accept)
        self._ok.setDefault(True)
        btn_row.addWidget(self._ok)
        lo.addLayout(btn_row)

        self._edit.textChanged.connect(
            lambda t: self._ok.setEnabled(bool(t) and self._edit.hasAcceptableInput()))
        self._edit.returnPressed.connect(
            lambda: self.accept() if self._edit.hasAcceptableInput() else None)

    def position(self) -> int:
        return int(self._edit.text())


# ?? Focuser Card ???????????????????????????????????????????????????????????????

class FocuserCard(DeviceCard):

    move_requested = Signal(int)   # emitted with target position

    def __init__(self, parent=None):
        super().__init__("focuser", "FOCUSER", draw_focuser2, parent)

        # ?? Info rows ??????????????????????????????????????????????????????
        self.add_info_row("position", "POSITION")
        # self.add_info_row("moving",   "MOVING")
        # self.add_info_row("limits",   "LIMITS")

        # ?? Filter buttons block ???????????????????????????????????????????
        # Sits below the info rows inside the info column
        self._filter_btns: dict[str, QPushButton] = {}
        self._current_pos = None
        self._limits      = {}

        btn_grid_widget = QWidget()
        btn_grid_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(btn_grid_widget)
        grid.setContentsMargins(0, 6, 0, 0)
        # grid.setSpacing(3)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(3)
        grid.setAlignment(Qt.AlignHCenter)
        
        # Keys and Labels are drawn from DEVICE_CONFIGS from config.py (which draws from devices.yaml)
        # Buttons are disabled until update_from_info() fires with real positions.
        photom_cfg = DEVICE_CONFIGS["focuser"].get("photom_positions", {})
        spectro_cfg = DEVICE_CONFIGS["focuser"].get("spectro_position")
        
        # Build ordered list: photom keys first, then Sp if spectro exists
        all_keys = list(photom_cfg.keys())          # order from yaml
        if spectro_cfg is not None:
            all_keys.append(SPECTRO_KEY)

        for i, key in enumerate(all_keys):
            label = "SPEC" if key == SPECTRO_KEY else key.upper()
            btn = QPushButton(label)
            btn.setStyleSheet(_filter_btn_style())
            btn.setEnabled(False)
            pos_hint = spectro_cfg if key == SPECTRO_KEY else photom_cfg.get(key, "?")
            btn.setToolTip(f"Move to {label}: {pos_hint}")
            btn.clicked.connect(lambda checked, k=key: self._on_filter_btn(k))
            self._filter_btns[key] = btn
            grid.addWidget(btn, i // 4, i % 4)  # 2 rows of 4 buttons
            # grid.addWidget(btn, 0, i)   # all on row 0 = single line

        self._info_layout.addWidget(btn_grid_widget)

        # filter_keys = list(FILTER_LABELS.items())   # (yaml_key, label)
        # for i, (key, label) in enumerate(filter_keys):
        #     btn = QPushButton(label)
        #     btn.setStyleSheet(_filter_btn_style())
        #     btn.setEnabled(False)
        #     btn.setToolTip(f"Move to {label} focus position")
        #     btn.clicked.connect(lambda checked, k=key: self._on_filter_btn(k))
        #     self._filter_btns[key] = btn
        #     grid.addWidget(btn, i // 4, i % 4)

        # # Spectro button ? separate, full label
        # sp_btn = QPushButton("Sp")
        # sp_btn.setStyleSheet(_filter_btn_style())
        # sp_btn.setEnabled(False)
        # sp_btn.setToolTip("Move to spectroscopy focus position")
        # sp_btn.clicked.connect(lambda: self._on_filter_btn(SPECTRO_KEY))
        # self._filter_btns[SPECTRO_KEY] = sp_btn
        # # Place Sp after C2 (position 7 = row 1, col 3)
        # grid.addWidget(sp_btn, 1, 3)

        # self._info_layout.addWidget(btn_grid_widget)

        # ?? Side buttons ???????????????????????????????????????????????????
        self.add_button("move", "MOVE", self._on_move_btn)
        # self.add_button("halt", "HALT", None, danger=True)
        self.add_button("filter", "FILTER")
        self.button("filter").clicked.connect(self.open_filter_wheel)
        self.button("filter").setEnabled(True)

        # Store photom/spectro positions (populated on connect)
        self._photom_positions: dict = {}
        self._spectro_position: int | None = None

    def set_callbacks(self, move=None, halt=None):
        if move: self.button("move").clicked.connect(move)
        # if halt: self.button("halt").clicked.connect(halt)

    def open_filter_wheel(self):
        from filterwheel import FilterWheelWindow
        if not hasattr(self, '_fw_window') or not self._fw_window.isVisible():
            self._fw_window = FilterWheelWindow()
            self._fw_window.show()
        else:
            self._fw_window.raise_()
            self._fw_window.activateWindow()
    
    # ?? Filter button handler ??????????????????????????????????????????????

    def _on_filter_btn(self, key: str):
        if key == SPECTRO_KEY:
            pos = self._spectro_position
            label = "spectro"
        else:
            pos = self._photom_positions.get(key)
            label = f"{'spectro' if key == SPECTRO_KEY else key.upper()} filter"

        if pos is None:
            return

        if confirm(self, "Move Focuser",
                   f"Move focuser to {label} position?\n\nTarget: {pos}"):
            self.move_requested.emit(pos)

    # ?? Move button handler ????????????????????????????????????????????????

    def _on_move_btn(self):
        dlg = MoveDialog(self._current_pos or 0, self._limits, parent=self)
        if dlg.exec() == QDialog.Accepted:
            target = dlg.position()
            if confirm(self, "Move Focuser",
                       f"Move focuser to position {target}?"):
                self.move_requested.emit(target)

    # ?? Update from driver info ????????????????????????????????????????????

    def update_from_info(self, info: dict):
        if not info.get("connected"):
            self.badge.set_status("OFFLINE", status_colour("OFFLINE"))
            self.enable_buttons(False)
            for btn in self._filter_btns.values():
                btn.setEnabled(False)
            return

        pos     = info.get("position")
        moving  = info.get("is_moving", False)
        limits  = info.get("limits", {})
        safe    = info.get("position_safe", True)

        self._current_pos       = pos
        self._limits            = limits
        self._photom_positions  = info.get("photom_positions", {})
        self._spectro_position  = info.get("spectro_position")

        status = "MOVING" if moving else ("ONLINE" if safe else "WARN")
        self.badge.set_status(status, status_colour(status))
        self.set_connected(COL_ACCENT)

        self.row("position").set_value(
            str(pos) if pos is not None else "-",
            COL_AMBER if moving else None)
        # self.row("moving").set_value(
        #     "YES" if moving else "NO",
        #     COL_AMBER if moving else None)

        # lim_min = limits.get("min", "-")
        # lim_max = limits.get("max", "-")
        # self.row("limits").set_value(f"{lim_min} - {lim_max}")

        self.enable_button("move", not moving)
        self.enable_button("halt", moving)
        for btn in self._filter_btns.values():
            btn.setEnabled(not moving)