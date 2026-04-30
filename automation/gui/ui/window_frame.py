# ui/window_frame.py

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QWidget
from PySide6.QtCore    import Qt, QEvent
from PySide6.QtGui     import QPainter, QPen, QColor

from config import COL_ACCENT, COL_TEXT_PRI, COL_TEXT_SEC, COL_GREEN, COL_TEXT_DIM

class WindowFrame(QWidget):
    """
    Transparent overlay that paints corner bracket decorations
    on the window edges. Mouse-transparent so it doesn't interfere
    with any existing drag/resize/click handling.
    """
    CORNER_LEN   = 600    # px ? length of each bracket arm
    CORNER_WIDTH = 3     # px ? line weight
    COLOUR       = COL_TEXT_DIM #COL_ACCENT
    OPACITY      = 1  # 0.0?1.0

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Fill entire parent always
        parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.Resize:
            self.resize(obj.size())
        return False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        c = QColor(self.COLOUR)
        c.setAlphaF(self.OPACITY)
        p.setPen(QPen(c, self.CORNER_WIDTH))
        # Use these 2 lines for full border
        p.setPen(QPen(QColor(self.COLOUR), self.CORNER_WIDTH))
        p.drawRect(self.rect().adjusted(1, 1, -2, -2))
        
        # Use these for corners instead/as well
        # L = self.CORNER_LEN
        # gap = 0
        # w, h = self.width() - 1, self.height() - 1
        # L2 = int(L*1)
        # # Top-left
        # p.drawLine(gap, 0, L, 0);  p.drawLine(0, gap, 0, L)
        # # Top-right
        # p.drawLine(w, 0, w-L, 0); p.drawLine(w, 0, w, L)
        # # Bottom-left
        # p.drawLine(0, h, L, h);   p.drawLine(0, h, 0, h-L)
        # # Bottom-right
        # p.drawLine(w, h, w-L2, h); p.drawLine(w, h, w, h-L2)
        
        