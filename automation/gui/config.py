# ==============================================================================
#  config.py  -  Single source of truth.
#  Change anything here; it propagates everywhere automatically.
# ==============================================================================

# -- Taskbar icon path ---------------------------------------------------------

ICON_PATH = "C:/Users/asa/Documents/JS/automation/gui/img/newtel.ico"

# -- Colour palette ------------------------------------------------------------
# Background layers (darkest -> lightest)
COL_BG          = "#0B0F14"   # outermost window background
COL_SURFACE     = "#121821"   # modal / secondary surfaces
COL_PANEL       = "#171E2A"   # device card body
COL_ICON_BG     = "#0E1520"   # icon box inset background

# Borders
COL_BORDER      = "#26303A"   # default border
COL_BORDER_DIM  = "#1C252F"   # subtle inner borders

# Accent / semantic colours
COL_ACCENT      = "#00E5FF"   # cyan - primary highlight, Connect All, active lamps
COL_GREEN       = "#22C55E"   # connected, closed, parked, Start Night
COL_RED         = "#EF4444"   # disconnected, error, End Night, danger buttons
COL_AMBER       = "#F59E0B"   # warning, moving, connecting pulse
COL_INACTIVE    = "#2A313B"   # off-state lamp fill
COL_TEST        = "#00E5FF78"

# Text
COL_TEXT_PRI    = "#E6EDF3"   # primary readable text
COL_TEXT_SEC    = "#8B949E"   # secondary / labels
COL_TEXT_DIM    = "#4A5568"   # very muted - dimmed icons, placeholders

# - Status - colour mapping ----------------------------------------------------------
# Used by status_colour() helper in styles.py.
# Add new states here if your devices report them.
STATUS_COLOURS = {
    # Green - safe / nominal
    "CLOSED":       COL_GREEN,
    "PARKED":       COL_GREEN,
    "TRACKING":     COL_GREEN,
    "ONLINE":       COL_GREEN,
    "CONNECTED":    COL_GREEN,
    "STATIONARY":   COL_GREEN,
    # Amber - attention / in-motion
    "OPEN":         COL_AMBER,
    "OPENING":      COL_AMBER,
    "CLOSING":      COL_AMBER,
    "PARKING":      COL_AMBER,
    "MOVING":       COL_AMBER,
    "SLEWING":      COL_AMBER,
    "CONNECTING":   COL_AMBER,
    # Red - fault / offline
    "OFFLINE":      COL_RED,
    "FAILED":       COL_RED,
    "ERROR":        COL_RED,
    "NOT CONNECTED":COL_RED,
    # Grey - unknown / no data
    "UNKNOWN":      COL_TEXT_SEC,
    "-":            COL_TEXT_SEC,
}

def status_colour(state: str) -> str:
    """Return the hex colour for a given status string."""
    return STATUS_COLOURS.get(str(state).upper(), COL_TEXT_SEC)


# -- Typography --------------------------------------------------------------
# Qt will fall back through the list until it finds an installed font.
FONT_DISPLAY    = "Rajdhani"          # card titles, badges, buttons
FONT_MONO       = "Consolas"          # data values, log console
FONT_FALLBACK   = "Segoe UI"          # Windows system fallback

# Font sizes (pt)
FS_TITLE        = 20    # "RAPTOR / T2" header
FS_SUBTITLE     = 14    # "OBSERVATORY CONTROL SYSTEM"
FS_CLOCK_MAIN   = 22    # local time display
FS_CLOCK_SUB    = 11    # UTC time underneath
FS_CARD_TITLE   = 9     # device name below icon
FS_BADGE        = 8     # status badge text
FS_LABEL        = 8     # info row left-hand labels
FS_VALUE        = 10    # info row right-hand values
FS_BUTTON       = 8     # action button text
FS_LOG          = 8     # log console entries
FS_NAV_BTN      = 9     # Connect All / Start Night / End Night


# -- Layout / sizing --------------------------------------------------------------
CARD_ICON_WIDTH     = 112   # px - fixed width of the icon column in every card
CARD_ICON_HEIGHT    = 70    # px - fixed height of the icon canvas
CARD_MIN_HEIGHT     = 110   # px - minimum card height (keeps rows aligned)
CARD_PADDING        = 10    # px - inner padding of the info/button sections
CARD_SPACING        = 1     # px - vertical gap between cards
CARD_RADIUS         = 14     # px - border-radius of cards

LAMP_SIZE           = 15    # px - diameter of each status lamp circle
LAMP_GAP            = 5     # px - horizontal gap between the two lamps

INFO_ROW_HEIGHT     = 18    # px - fixed height of each label/value row
INFO_ROW_SPACING    = 2     # px - vertical gap between info rows

WINDOW_MIN_W        = 400
WINDOW_MIN_H        = 920

LOG_HEIGHT          = 120   # px - height of the log console at the bottom


# -- Polling intervals (milliseconds) --------------------------------------------
# Adjust these to trade off responsiveness vs. network load.
POLL_TELESCOPE_MS   = 3000
POLL_COVERS_MS      = 3000
POLL_DOME_MS        = 5000
POLL_ROTATOR_MS     = 5000
POLL_FOCUSER_MS     = 3000


# -- Device network configuration -------------------------------------------------
# These mirror devices.yaml.  Edit here, not in the driver wrappers.
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "devices.yaml"

with open(CONFIG_PATH, "r") as f:
    DEVICES_YAML = yaml.safe_load(f)

DEVICE_CONFIGS = {
    "telescope": {
        "address":       DEVICES_YAML["telescope"]["address"],
        "device_number": DEVICES_YAML["telescope"]["device_number"],
        "settle_time":   DEVICES_YAML["telescope"]["settle_time"],
    },
    "rotator": {
        "address":       DEVICES_YAML["rotator"]["address"],
        "device_number": DEVICES_YAML["rotator"]["device_number"],
        "settle_time":   DEVICES_YAML["rotator"]["settle_time"],
        "mechanical_limits": DEVICES_YAML["rotator"]["mechanical_limits"],
    },
    "cover": {
        "address":           DEVICES_YAML["cover"]["address"],
        "device_number":     DEVICES_YAML["cover"]["device_number"],
        "operation_timeout": DEVICES_YAML["cover"]["operation_timeout"],
        "settle_time":       DEVICES_YAML["cover"]["settle_time"],
    },
    "dome": {
        "host":             DEVICES_YAML["dome_t2"]["host"],
        "port":             DEVICES_YAML["dome_t2"]["port"],
        "dome_id":          DEVICES_YAML["dome_t2"]["dome_id"],
        "timeout_status":   DEVICES_YAML["dome_t2"]["timeout_status"],
        "timeout_abort":    DEVICES_YAML["dome_t2"]["timeout_abort"],
        "timeout_move":     DEVICES_YAML["dome_t2"]["timeout_move"],
        "timeout_command":  DEVICES_YAML["dome_t2"]["timeout_command"],
        "poll_interval":    DEVICES_YAML["dome_t2"]["poll_interval"],
        "max_retries":      DEVICES_YAML["dome_t2"]["max_retries"],
    },
    "focuser": {
        "address":           DEVICES_YAML["focuser"]["address"],
        "device_number":     DEVICES_YAML["focuser"]["device_number"],
        "photom_positions":   DEVICES_YAML["focuser"]["focus_positions"],
        "spectro_position":   DEVICES_YAML["focuser"]["spectro_focus_position"]["spectro"],
    },
}

# DEVICE_CONFIGS = {
#     "telescope": {
#         "address":       "127.0.0.1:11111",
#         "device_number": 0,
#         "settle_time":   2.0,
#     },
#     "rotator": {
#         "address":       "127.0.0.1:11112",
#         "device_number": 0,
#         "settle_time":   0.1,
#         "mechanical_limits": {"min_deg": 94.0, "max_deg": 320.0},
#     },
#     "cover": {
#         "address":          "127.0.0.1:11112",
#         "device_number":    0,
#         "operation_timeout": 30.0,
#         "settle_time":      15.0,
#     },
#     "dome": {
#         "host":             "192.168.249.27",
#         "port":             1880,
#         "dome_id":          "DOME",
#         "timeout_status":   2,
#         "timeout_abort":    20,
#         "timeout_move":     75,
#         "timeout_command":  5,
#         "poll_interval":    2.0,
#         "max_retries":      3,
#     },
# }


# -- Icon stroke widths ----------------------------------------------------------
ICON_LINE_WIDTH     = 2.0   # default QPen width for icon drawings
ICON_LINE_WIDTH_THIN = 1.2  # thin detail lines


# -- Log level colours -----------------------------------------------------------
LOG_COLOURS = {
    "SYS":   COL_TEXT_SEC,
    "INFO":  COL_ACCENT,
    "OK":    COL_GREEN,
    "WARN":  COL_AMBER,
    "ERROR": COL_RED,
}
