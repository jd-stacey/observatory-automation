# ==============================================================================
#  ui/cards/dome_card.py
# ==============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config import COL_TEXT_PRI, status_colour, COL_ACCENT
from ui.device_card import DeviceCard
from ui.icons import draw_dome, draw_dome_active


class DomeCard(DeviceCard):

    def __init__(self, parent=None):
        super().__init__("dome", "DOME", draw_dome, draw_dome_active, parent)

        self.add_info_row("left",    "LEFT PANEL")
        self.add_info_row("right",   "RIGHT PANEL")
        self.add_info_row("overall", "OVERALL")

        self.add_button("open",  "OPEN")
        self.add_button("close", "CLOSE")
        self.add_button("abort", "ABORT", danger=True)

    def set_callbacks(self, open_cb=None, close_cb=None, abort_cb=None):
        if open_cb:  self.button("open").clicked.connect(open_cb)
        if close_cb: self.button("close").clicked.connect(close_cb)
        if abort_cb: self.button("abort").clicked.connect(abort_cb)

    def update_from_info(self, info: dict):
        if not info.get("connected"):
            self.badge.set_status("OFFLINE", status_colour("OFFLINE"))
            self.enable_buttons(False)
            return

        left    = str(info.get("left",  "UNKNOWN")).upper()
        right   = str(info.get("right", "UNKNOWN")).upper()
        closed  = info.get("closed", False)
        moving  = info.get("moving", False)

        if closed:
            overall = "CLOSED"
        elif moving:
            overall = "MOVING"
        elif info.get("is_open"):
            overall = "OPEN"
        else:
            overall = left if left == right else "PARTIAL"

        self.badge.set_status(overall, status_colour(overall))
        self.set_connected(COL_ACCENT)
        self.row("left").set_value(left,    status_colour(left))
        self.row("right").set_value(right,  status_colour(right))
        self.row("overall").set_value(overall, status_colour(overall))

        self.enable_button("open",  not moving and overall != "OPEN")
        self.enable_button("close", not moving and not closed)
        self.enable_button("abort", True)
