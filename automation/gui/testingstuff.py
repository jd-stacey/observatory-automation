from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QFont

app = QApplication()
label = QLabel("\u2600 \u263E \U0001F323 \U0001F50C \u002B \U0001F782")

font = QFont()
font.setPointSize(32)
label.setFont(font)
label.show()
app.exec()


# not working
# \u23FB \u23FC 