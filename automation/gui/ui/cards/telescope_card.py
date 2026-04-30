# ==============================================================================
#  ui/cards/telescope_card.py
#
#  To add/remove rows: add_info_row() calls below.
#  To add/remove buttons: add_button() calls below.
#  Row keys match what update() expects from drivers.TelescopeWrapper.get_info()
# ==============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config import COL_TEXT_PRI, COL_AMBER, status_colour, COL_ACCENT, COL_TEXT_SEC
from ui.device_card import DeviceCard
from ui.confirm import confirm
from ui.icons import draw_telescope_inactive, draw_telescope_active, draw_telescope, draw_telescope_connected, draw_telescope_connected2
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal
from styles import nav_button_style, plain_label


class TelescopeCard(DeviceCard):
    mirror_requested = Signal(str)
    def __init__(self, parent=None):
        super().__init__("telescope", "TELESCOPE", draw_telescope, draw_telescope_connected2, parent)
        
        # -- Info rows (order = display order) ------------------------------
        self.add_info_row("ra",     "RA")
        self.add_info_row("dec",    "DEC")
        self.add_info_row("alt",    "ALT")
        self.add_info_row("az",     "AZ")
        self.add_info_row("status", "STATUS")

        # -- Action buttons -------------------------------------------------
        # Remove a line here to hide that button.  Add one to add a new button.
        self._park_cb  = None   # set by main_window
        self._abort_cb = None

        self.add_button("park",  "PARK")
        self.add_button("mirror", "MIRR")
        self.add_button("abort", "ABORT", danger=True)
        
        self.button("mirror").clicked.connect(self._on_mirror_btn)

    def set_callbacks(self, park=None, abort=None, mirror=None):
        if park:
            self._park_cb = park
            self.button("park").clicked.connect(park)
        if abort:
            self._abort_cb = abort
            self.button("abort").clicked.connect(abort)
        if mirror:
            self.button("mirror").clicked.connect(mirror)

    def update_from_info(self, info: dict):
        """
        Called from the poll thread (via Qt signal) with the dict returned by
        drivers.TelescopeWrapper.get_info().
        """
        if not info.get("connected"):
            self.badge.set_status("OFFLINE", status_colour("OFFLINE"))
            self.enable_buttons(False)
            return

        # Status string
        if info.get("parked"):
            status = "PARKED"
        elif info.get("slewing"):
            status = "SLEWING"
        elif info.get("tracking"):
            status = "TRACKING"
        else:
            status = "ONLINE"

        self.badge.set_status(status, status_colour(status))
        self.set_connected(COL_ACCENT)

        # RA: decimal hours -> HH h MM m SS.S s
        ra = info.get("ra")
        if ra is not None:
            h   = int(ra)
            m   = int((ra - h) * 60)
            s   = ((ra - h) * 60 - m) * 60
            self.row("ra").set_value(f"{h:02d}h {m:02d}m {s:04.1f}s")
        else:
            self.row("ra").set_value("-")

        # Dec: decimal degrees - ±DD° MM' SS.S"
        dec = info.get("dec")
        if dec is not None:
            sign = "+" if dec >= 0 else "-"
            dec  = abs(dec)
            d    = int(dec)
            m    = int((dec - d) * 60)
            s    = ((dec - d) * 60 - m) * 60
            self.row("dec").set_value(f"{sign}{d:02d}° {m:02d}\' {s:04.1f}\"")
        else:
            self.row("dec").set_value("-")

        alt = info.get("alt")
        self.row("alt").set_value(f"{alt:.2f}°" if alt is not None else "-")

        az = info.get("az")
        self.row("az").set_value(f"{az:.2f}°" if az is not None else "-")

        self.row("status").set_value(status, status_colour(status))

        # Buttons
        self.enable_button("park",  not info.get("parked", False))
        self.enable_button("abort", True)
        self.enable_button("mirror", True)

    def _on_mirror_btn(self):
        dlg = MirrorDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            choice = dlg.choice()
            label = "photometry" if choice == "phot" else "spectroscopy"
            if confirm(self, "Tertiary Mirror", f"Switch tertiary mirror to {label.upper()} port?", danger=True):
                self.mirror_requested.emit(choice)
            
class MirrorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tertiary Mirror")
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setFixedWidth(240)
        self.setStyleSheet("background: #121821; color: #E6EDF3;")
        self._choice = None
        lo = QVBoxLayout(self)
        lo.setSpacing(10); lo.setContentsMargins(20, 18, 20, 18)
        # label = QLabel("Select tertiary mirror position:")
        # label.setStyleSheet("border: none; background: transparent;")
        lo.addWidget(plain_label("Select tertiary mirror position:"))
        # lo.addWidget(QLabel("Select tertiary mirror position:"))
        phot_btn = QPushButton("PHOTOMETRY")
        phot_btn.setStyleSheet(nav_button_style(COL_ACCENT) + 
                                       """QPushButton:hover {background-color: #006D73;}""")
        phot_btn.clicked.connect(lambda: self._select("phot"))
        lo.addWidget(phot_btn)
        spec_btn = QPushButton("SPECTROSCOPY")
        spec_btn.setStyleSheet(nav_button_style(COL_ACCENT) + 
                                       """QPushButton:hover {background-color: #006D73;}""")
        spec_btn.clicked.connect(lambda: self._select("spectro"))
        lo.addWidget(spec_btn)
        cancel = QPushButton("CANCEL")
        cancel.setStyleSheet(nav_button_style(COL_TEXT_SEC))
        cancel.clicked.connect(self.reject)
        lo.addWidget(cancel)

    def _select(self, choice: str):
        self._choice = choice
        self.accept()

    def choice(self) -> str:
        return self._choice