# ==============================================================================
#  ui/cards/covers_card.py
# ==============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config import COL_TEXT_PRI, status_colour, COL_ACCENT
from ui.device_card import DeviceCard
from ui.icons import draw_covers


class CoversCard(DeviceCard):

    def __init__(self, parent=None):
        super().__init__("cover", "COVERS", draw_covers, parent)

        self.add_info_row("state",  "COVER STATE")
        self.add_info_row("moving", "MOVING")

        self.add_button("open",  "OPEN")
        self.add_button("close", "CLOSE")

    def set_callbacks(self, open_cb=None, close_cb=None):
        if open_cb:
            self.button("open").clicked.connect(open_cb)
        if close_cb:
            self.button("close").clicked.connect(close_cb)

    def update_from_info(self, info: dict):
        if not info.get("connected"):
            self.badge.set_status("OFFLINE", status_colour("OFFLINE"))
            self.enable_buttons(False)
            return

        state  = str(info.get("cover_state", "UNKNOWN")).upper()
        moving = state in ("OPENING", "CLOSING", "MOVING")

        self.badge.set_status(state, status_colour(state))
        self.set_connected(COL_ACCENT)
        self.row("state").set_value(state, status_colour(state))
        self.row("moving").set_value("YES" if moving else "NO",
                                     status_colour("MOVING") if moving else None)

        self.enable_button("open",  not moving and state != "OPEN")
        self.enable_button("close", not moving and state != "CLOSED")
