# ==============================================================================
#  styles.py  -  Qt Stylesheet strings.
#  All visual styling lives here.  config.py supplies the colour variables.
# ==============================================================================

from config import (
    COL_BG, COL_SURFACE, COL_PANEL, COL_BORDER, COL_BORDER_DIM,
    COL_ACCENT, COL_GREEN, COL_RED, COL_AMBER, COL_INACTIVE,
    COL_TEXT_PRI, COL_TEXT_SEC, COL_TEXT_DIM,
    FONT_DISPLAY, FONT_MONO, FONT_FALLBACK,
)
from PySide6.QtWidgets import QLabel

# -- Main application stylesheet -----------------------------------------------
APP_STYLESHEET = f"""

/* -- Global reset -------------------------------------------------- */
QWidget {{
    background-color: {COL_BG};
    color: {COL_TEXT_PRI};
    font-family: "{FONT_DISPLAY}", "{FONT_FALLBACK}";
    font-size: 10pt;
    border: none;
    outline: none;
}}

QWidget#container {{
    background-color: rgba(30, 30, 30, 230);
    border-radius: 8px;
}}

QLabel {{
    background: transparent;
    border: none;
    padding: 0px;
}}

QMainWindow {{
    background-color: #1e1e1e;
}}

QMainWindow, QDialog {{
    background-color: {COL_BG};
}}

/* -- Scrollbar - log console -------------------------------------- */
QScrollBar:vertical {{
    background: {COL_BG};
    width: 6px;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {COL_BORDER};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COL_TEXT_SEC};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* -- QTextEdit (log console) -------------------------------------- */
QTextEdit {{
    background-color: {COL_BG};
    color: {COL_TEXT_PRI};
    font-family: "{FONT_MONO}";
    font-size: 8pt;
    border: 1px solid {COL_BORDER};
    border-radius: 3px;
    padding: 6px 8px;
    selection-background-color: {COL_ACCENT}44;
}}

/* -- Tooltips ---------------------------------------------------- */
QToolTip {{
    background-color: {COL_SURFACE};
    color: {COL_TEXT_PRI};
    border: 1px solid {COL_ACCENT}66;
    padding: 4px 8px;
    font-size: 8pt;
}}

/* -- QCheckBox (Night modal) ------------------------------------ */
QCheckBox {{
    color: {COL_TEXT_PRI};
    font-family: "{FONT_DISPLAY}";
    font-size: 9pt;
    font-weight: 600;
    spacing: 8px;
    letter-spacing: 1px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {COL_BORDER};
    border-radius: 2px;
    background: {COL_PANEL};
}}
QCheckBox::indicator:checked {{
    background: {COL_ACCENT};
    border: 1px solid {COL_ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: {COL_ACCENT}88;
}}

"""
# border-color: {COL_ACCENT};

# -- Widget-level stylesheets (applied in code) ----------------------------------

def card_style(highlighted: bool = False) -> str:
    border = COL_ACCENT + "55" if highlighted else COL_ACCENT#"rgba(0, 229, 255, 0.5)"#COL_ACCENT + "95"#BORDER
    return f"""
        QFrame {{
            background-color: {COL_PANEL};
            border: 1px solid {border};
            border-radius: 4px;
        }}
        QFrame:hover {{
            border: 1px solid {COL_ACCENT}44;
        }}
    """


def icon_box_style() -> str:
    return f"""
        background-color: {COL_BG};
        border: none;
        border-top-left-radius: 4px;
        border-bottom-left-radius: 4px;
    """
#border-right: 1px solid {COL_BORDER};

def badge_style(colour: str) -> str:
    return f"""
        color: {colour};
        background-color: {colour}18;
        border: 1px solid {colour}44;
        border-radius: 2px;
        padding: 1px 7px;
        font-family: "{FONT_DISPLAY}";
        font-size: 8pt;
        font-weight: 700;
        letter-spacing: 1.5px;
    """


def label_style() -> str:
    return f"""
        QLabel {{
            color: {COL_TEXT_SEC};
            font-family: "{FONT_MONO}";
            font-size: 8pt;
            font-weight: 600;
            letter-spacing: 0.5px;
            min-width: 88px;
            background: transparent;
            border: none;
            padding: 0px;
        }}
    """


def value_style(colour: str = None) -> str:
    c = colour or COL_TEXT_PRI
    return f"""
        QLabel {{
            color: {c};
            font-family: "{FONT_MONO}";
            font-size: 10pt;
            font-weight: 500;
            background: transparent;
            border: none;
            padding: 0px;
        }}
    """


def action_button_style(danger: bool = False) -> str:
    border_c = COL_RED + "66" if danger else COL_BORDER
    text_c   = COL_RED       if danger else COL_TEXT_SEC
    hover_bg = COL_RED + "18" if danger else COL_ACCENT + "18"
    hover_c  = COL_RED       if danger else COL_ACCENT
    hover_border = COL_RED   if danger else COL_ACCENT
    return f"""
        QPushButton {{
            color: {text_c};
            background: transparent;
            border: 1px solid {border_c};
            border-radius: 2px;
            padding: 3px 10px;
            font-family: "{FONT_DISPLAY}";
            font-size: 8pt;
            font-weight: 700;
            letter-spacing: 1px;
        }}
        QPushButton:hover {{
            color: {hover_c};
            background: {hover_bg};
            border-color: {hover_border};
        }}
        QPushButton:pressed {{
            background: {hover_bg};
            padding: 4px 9px 2px 11px;
        }}
        QPushButton:disabled {{
            color: {COL_TEXT_DIM};
            border-color: {COL_BORDER_DIM};
            background: transparent;
        }}
    """


def nav_button_style(colour: str) -> str:
    """Connect All / Start Night / End Night top-bar buttons."""
    return f"""
        QPushButton {{
            color: {colour};
            background: transparent;
            border: 1px solid {colour}77;
            border-radius: 3px;
            border-color: {colour};
            padding: 7px 18px;
            font-family: "{FONT_DISPLAY}";
            font-size: 9pt;
            font-weight: 700;
            letter-spacing: 2px;
        }}
        QPushButton:hover {{
            background: {colour}18;
            border-color: {colour};
        }}
        QPushButton:pressed {{
            background: {colour}28;
        }}
        QPushButton:disabled {{
            color: {COL_TEXT_DIM};
            border-color: {COL_BORDER_DIM};
        }}
    """


def card_title_style() -> str:
    return f"""
        color: {COL_TEXT_SEC};
        font-family: "{FONT_DISPLAY}";
        font-size: 9pt;
        font-weight: 700;
        letter-spacing: 3px;
    """


def header_title_style() -> str:
    return f"""
        color: {COL_ACCENT};
        font-family: "{FONT_DISPLAY}";
        font-size: 20pt;
        font-weight: 700;
        letter-spacing: 4px;
    """


def header_sub_style() -> str:
    return f"""
        color: {COL_TEXT_SEC};
        font-family: "{FONT_DISPLAY}";
        font-size: 14pt;
        font-weight: 600;
        letter-spacing: 4px;
    """


def clock_main_style() -> str:
    return f"""
        color: {COL_TEXT_PRI};
        font-family: "{FONT_MONO}";
        font-size: 22pt;
        font-weight: 400;
        letter-spacing: 2px;
    """


def clock_sub_style() -> str:
    return f"""
        color: {COL_TEXT_SEC};
        font-family: "{FONT_MONO}";
        font-size: 11pt;
        font-weight: 400;
        letter-spacing: 2px;
    """


def divider_style(colour: str = None) -> str:
    c = colour or COL_BORDER
    return f"background: {c};"


def modal_style() -> str:
    return f"""
        QDialog {{
            background: {COL_SURFACE};
            border: 1px solid {COL_ACCENT}55;
            border-radius: 4px;
        }}
        QLabel {{
            background: transparent;
        }}
    """


def log_section_label_style() -> str:
    return f"""
        color: {COL_TEXT_SEC};
        font-family: "{FONT_DISPLAY}";
        font-size: 8pt;
        font-weight: 700;
        letter-spacing: 3px;
    """

def plain_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("border: none; background: transparent;")
    return lbl

