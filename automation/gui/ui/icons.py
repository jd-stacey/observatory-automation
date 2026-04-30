# ===============================================================================
#  ui/icons.py  -  All device icon drawing functions.
#
#  Each function receives a QPainter already begun on the target widget,
#  plus (cx, cy) centre point, size hint, and colour.
#  To tweak an icon: find its function, adjust coordinates.
# ===============================================================================

import math
import random
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QPixmap
from PySide6.QtCore import Qt, QPointF, QRectF, QByteArray
from PySide6.QtSvg import QSvgRenderer

from config import (
    COL_TEXT_PRI, COL_TEXT_DIM, COL_ACCENT,
    ICON_LINE_WIDTH, ICON_LINE_WIDTH_THIN,
)

def _setup_icon(painter, cx, cy, size):
    painter.save()
    painter.translate(cx, cy)
    painter.scale(size / 60.0, size / 60.0)
    
def _finish_icon(painter):
    painter.restore()


def _pen(painter: QPainter, colour: str, width: float = ICON_LINE_WIDTH,
         style=Qt.SolidLine):
    p = QPen(QColor(colour), width, style)
    p.setCapStyle(Qt.RoundCap)
    p.setJoinStyle(Qt.RoundJoin)
    painter.setPen(p)
    painter.setBrush(Qt.NoBrush)

def draw_telescope_inactive2(painter, cx, cy, size, colour):
    _setup_icon(painter, cx, cy, size)

    scope = f'''<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="auto" viewBox="0 0 287 247" version="1.1">

	<path d="M 132.083 9.116 C 103.130 13.014, 71.630 32.620, 55.858 56.562 C 42.695 76.542, 37.109 94.113, 36.487 117.500 L 36.140 130.500 36.970 119.500 C 38.018 105.602, 39.438 97.573, 42.613 87.598 C 54.747 49.474, 86.386 21.130, 126.500 12.449 C 137.073 10.161, 159.667 10.106, 169.698 12.345 C 204.770 20.170, 232.855 42.063, 247.968 73.358 C 254.717 87.336, 258.118 101.563, 258.995 119.500 L 259.680 133.500 259.840 121.381 C 260.024 107.419, 258.333 96.253, 254.178 84 C 241.609 46.932, 209.482 18.379, 171.500 10.521 C 161.633 8.480, 142.007 7.780, 132.083 9.116 M 157 23.748 C 157 24.853, 155.879 26.057, 154.250 26.701 C 151.616 27.741, 151.599 27.792, 153.844 27.894 C 155.291 27.959, 156.387 28.765, 156.710 30 C 157.324 32.348, 159 32.690, 159 30.468 C 159 29.625, 160.005 28.564, 161.234 28.109 L 163.467 27.283 161.234 26.574 C 160.005 26.184, 159 25.247, 159 24.492 C 159 23.736, 158.550 22.840, 158 22.500 C 157.450 22.160, 157 22.722, 157 23.748 M 121 24.059 C 121 24.641, 121.450 24.840, 122 24.500 C 122.550 24.160, 123 23.684, 123 23.441 C 123 23.198, 122.550 23, 122 23 C 121.450 23, 121 23.477, 121 24.059 M 89.500 41 C 89.160 41.550, 89.359 42, 89.941 42 C 90.523 42, 91 41.550, 91 41 C 91 40.450, 90.802 40, 90.559 40 C 90.316 40, 89.840 40.450, 89.500 41 M 160 42.059 C 160 42.641, 160.450 42.840, 161 42.500 C 161.550 42.160, 162 41.684, 162 41.441 C 162 41.198, 161.550 41, 161 41 C 160.450 41, 160 41.477, 160 42.059 M 218 45 C 218 45.550, 218.477 46, 219.059 46 C 219.641 46, 219.840 45.550, 219.500 45 C 219.160 44.450, 218.684 44, 218.441 44 C 218.198 44, 218 44.450, 218 45 M 135 48 C 135 48.550, 135.450 49, 136 49 C 136.550 49, 137 48.550, 137 48 C 137 47.450, 136.550 47, 136 47 C 135.450 47, 135 47.450, 135 48 M 105 53 C 105 53.550, 105.477 54, 106.059 54 C 106.641 54, 106.840 53.550, 106.500 53 C 106.160 52.450, 105.684 52, 105.441 52 C 105.198 52, 105 52.450, 105 53 M 193 53 C 193 53.550, 193.477 54, 194.059 54 C 194.641 54, 194.840 53.550, 194.500 53 C 194.160 52.450, 193.684 52, 193.441 52 C 193.198 52, 193 52.450, 193 53 M 176 55 C 176 55.550, 176.450 56, 177 56 C 177.550 56, 178 55.550, 178 55 C 178 54.450, 177.550 54, 177 54 C 176.450 54, 176 54.450, 176 55 M 72.500 59 C 72.840 59.550, 73.316 60, 73.559 60 C 73.802 60, 74 59.550, 74 59 C 74 58.450, 73.523 58, 72.941 58 C 72.359 58, 72.160 58.450, 72.500 59 M 208 61 C 208 61.550, 208.477 62, 209.059 62 C 209.641 62, 209.840 61.550, 209.500 61 C 209.160 60.450, 208.684 60, 208.441 60 C 208.198 60, 208 60.450, 208 61 M 144 62 C 144 62.550, 144.477 63, 145.059 63 C 145.641 63, 145.840 62.550, 145.500 62 C 145.160 61.450, 144.684 61, 144.441 61 C 144.198 61, 144 61.450, 144 62 M 162.750 74.810 C 152.258 80.219, 145.992 84.016, 145.979 84.973 C 145.965 85.950, 137.816 90.638, 123.332 98 C 110.888 104.325, 100.516 110.207, 100.283 111.071 C 100.051 111.935, 94.942 115.068, 88.931 118.034 C 77.467 123.691, 77.728 123.385, 79.744 128.750 C 80.003 129.438, 79.539 130, 78.714 130 C 77.889 130, 76.966 129.354, 76.664 128.566 C 76.214 127.394, 75.554 127.342, 73.057 128.285 C 71.375 128.919, 70 130.028, 70 130.749 C 70 132.316, 74.847 144.144, 75.978 145.335 C 77.197 146.620, 83.023 143.224, 82.397 141.593 C 81.405 139.006, 83.982 138.867, 85.156 141.444 C 85.797 142.850, 86.649 144, 87.050 144 C 87.451 144, 92.888 142.238, 99.133 140.084 C 106.764 137.453, 110.707 136.525, 111.158 137.256 C 111.612 137.991, 115.092 137.239, 121.885 134.940 C 131.616 131.646, 131.985 131.597, 133.317 133.419 C 134.488 135.021, 135.154 135.142, 137.770 134.230 C 141.436 132.952, 142 133.813, 142 140.687 C 142 144.698, 140.150 148.453, 125.658 173.855 C 116.670 189.610, 107.862 205.088, 106.085 208.250 L 102.853 214 96.677 214.128 C 51.521 215.061, 71.373 215.640, 148.500 215.639 C 226.622 215.638, 243.405 215.138, 199.500 214.122 L 193.500 213.983 186.507 201.741 C 156.518 149.243, 153.986 144.497, 154.550 141.850 C 154.981 139.830, 154.388 138.373, 152.057 135.718 C 148.215 131.342, 148.198 129.475, 151.990 128.153 C 154.076 127.426, 154.801 126.645, 154.388 125.569 C 153.585 123.475, 158.795 121.410, 161.170 122.882 C 162.443 123.671, 167.065 122.443, 180.643 117.708 L 198.447 111.500 199.438 107 C 201.217 98.920, 200.670 87.997, 198.254 83.387 C 195.932 78.956, 186.664 70, 184.400 70 C 183.639 70, 182.455 69.100, 181.768 68 C 181.081 66.900, 180.290 66.039, 180.009 66.087 C 179.729 66.136, 171.963 70.061, 162.750 74.810 M 238.500 69 C 238.160 69.550, 238.359 70, 238.941 70 C 239.523 70, 240 69.550, 240 69 C 240 68.450, 239.802 68, 239.559 68 C 239.316 68, 238.840 68.450, 238.500 69 M 121 70.941 C 121 72.333, 120.352 73, 119 73 C 117.900 73, 117 73.450, 117 74 C 117 74.550, 117.869 75, 118.930 75 C 120.135 75, 121.027 75.847, 121.303 77.250 L 121.746 79.500 122.466 77.342 C 122.861 76.156, 124.156 74.861, 125.342 74.466 L 127.500 73.746 125.250 73.303 C 124.013 73.060, 123 72.244, 123 71.489 C 123 70.735, 122.550 69.840, 122 69.500 C 121.450 69.160, 121 69.809, 121 70.941 M 177.169 70.297 C 176.367 71.263, 178.188 76.623, 184.296 91.282 C 188.808 102.110, 192.725 110.969, 193 110.969 C 193.275 110.969, 194.140 110.564, 194.922 110.069 C 196.084 109.334, 194.803 105.498, 187.922 89.096 C 183.290 78.055, 179.218 69.017, 178.872 69.011 C 178.527 69.005, 177.761 69.584, 177.169 70.297 M 163.750 76.780 C 158.938 79.349, 155 81.970, 155 82.605 C 155 83.949, 168.852 117.153, 169.858 118.217 C 170.696 119.106, 189.279 112.663, 189.724 111.329 C 190.128 110.117, 174.033 71.980, 173.148 72.054 C 172.792 72.084, 168.563 74.210, 163.750 76.780 M 187.659 82.747 C 190.154 88.661, 193.115 95.862, 194.237 98.750 C 195.359 101.638, 196.609 104, 197.014 104 C 197.888 104, 199 98.911, 199 94.913 C 199 87.449, 192.220 76.653, 185.311 73.116 C 183.339 72.106, 183.573 73.064, 187.659 82.747 M 73.040 75.667 C 73.013 77.121, 72.099 78.134, 70.258 78.747 L 67.515 79.662 70.258 80.350 C 72.191 80.835, 73.019 81.696, 73.063 83.269 L 73.127 85.500 74.040 83.226 C 74.542 81.976, 75.976 80.542, 77.226 80.040 C 78.902 79.367, 79.048 79.110, 77.782 79.063 C 76.837 79.029, 75.393 77.763, 74.572 76.250 C 73.212 73.744, 73.077 73.692, 73.040 75.667 M 136 79.059 C 136 79.641, 136.450 79.840, 137 79.500 C 137.550 79.160, 138 78.684, 138 78.441 C 138 78.198, 137.550 78, 137 78 C 136.450 78, 136 78.477, 136 79.059 M 219.500 80 C 219.160 80.550, 219.359 81, 219.941 81 C 220.523 81, 221 80.550, 221 80 C 221 79.450, 220.802 79, 220.559 79 C 220.316 79, 219.840 79.450, 219.500 80 M 149.752 84.250 C 148.282 85.377, 148.753 86.977, 154.534 100.500 C 158.061 108.750, 161.385 116.737, 161.921 118.250 C 162.887 120.975, 164.482 121.652, 166.595 120.235 C 167.328 119.743, 165.175 113.463, 160.095 101.272 C 155.918 91.247, 152.249 83.034, 151.941 83.022 C 151.634 83.010, 150.649 83.563, 149.752 84.250 M 233.116 84.275 C 233.052 85.251, 231.762 86.569, 230.250 87.203 C 227.606 88.313, 227.587 88.372, 229.748 88.748 C 231.182 88.997, 232.247 90.110, 232.686 91.819 L 233.376 94.500 233.975 92.036 C 234.339 90.536, 235.536 89.320, 237.036 88.927 L 239.500 88.281 236.834 87.197 C 235.368 86.601, 233.958 85.301, 233.700 84.307 C 233.261 82.611, 233.225 82.609, 233.116 84.275 M 118 89 C 118 89.550, 118.450 90, 119 90 C 119.550 90, 120 89.550, 120 89 C 120 88.450, 119.550 88, 119 88 C 118.450 88, 118 88.450, 118 89 M 127.029 98.457 C 116.870 103.609, 108.413 108.261, 108.235 108.794 C 107.954 109.637, 109.871 114.645, 116.430 130.211 L 117.994 133.922 138.747 126.809 C 150.161 122.897, 159.636 119.591, 159.803 119.462 C 160.493 118.928, 147.417 89.055, 146.500 89.071 C 145.950 89.081, 137.188 93.304, 127.029 98.457 M 51 101 C 51 101.550, 51.450 102, 52 102 C 52.550 102, 53 101.550, 53 101 C 53 100.450, 52.550 100, 52 100 C 51.450 100, 51 100.450, 51 101 M 88 107 C 88 107.550, 88.477 108, 89.059 108 C 89.641 108, 89.840 107.550, 89.500 107 C 89.160 106.450, 88.684 106, 88.441 106 C 88.198 106, 88 106.450, 88 107 M 244.500 108 C 244.160 108.550, 244.359 109, 244.941 109 C 245.523 109, 246 108.550, 246 108 C 246 107.450, 245.802 107, 245.559 107 C 245.316 107, 244.840 107.450, 244.500 108 M 103.278 111.956 C 103.559 113.031, 105.749 118.646, 108.145 124.433 C 111.330 132.128, 112.974 134.961, 114.263 134.977 C 115.912 134.999, 115.925 134.755, 114.469 131.250 C 107.253 113.882, 105.367 110, 104.149 110 C 103.270 110, 102.953 110.711, 103.278 111.956 M 90.500 119.654 C 85.550 122.172, 81.330 124.387, 81.122 124.577 C 80.316 125.313, 87.292 141, 88.425 141 C 89.380 141, 102.865 136.706, 108.720 134.538 C 110.298 133.953, 102.797 115.592, 100.855 115.288 C 100.110 115.171, 95.450 117.136, 90.500 119.654 M 58 119 C 58 119.550, 58.450 120, 59 120 C 59.550 120, 60 119.550, 60 119 C 60 118.450, 59.550 118, 59 118 C 58.450 118, 58 118.450, 58 119 M 211.500 125 C 211.160 125.550, 211.359 126, 211.941 126 C 212.523 126, 213 125.550, 213 125 C 213 124.450, 212.802 124, 212.559 124 C 212.316 124, 211.840 124.450, 211.500 125 M 142.250 127.662 C 137.840 129.186, 135 130.722, 135 131.583 C 135 133.375, 134.246 133.554, 143.316 129.611 C 155.456 124.334, 154.889 123.296, 142.250 127.662 M 184.500 128 C 184.840 128.550, 185.316 129, 185.559 129 C 185.802 129, 186 128.550, 186 128 C 186 127.450, 185.523 127, 184.941 127 C 184.359 127, 184.160 127.450, 184.500 128 M 236.063 129.275 C 236.029 130.251, 234.762 131.569, 233.250 132.203 C 230.660 133.290, 230.627 133.379, 232.687 133.740 C 233.981 133.966, 235.239 135.218, 235.768 136.804 L 236.662 139.485 237.350 136.742 C 237.728 135.234, 238.705 134, 239.519 134 C 240.334 134, 241 133.550, 241 133 C 241 132.450, 240.310 132, 239.468 132 C 238.625 132, 237.529 130.988, 237.031 129.750 C 236.323 127.989, 236.113 127.885, 236.063 129.275 M 73.293 130.706 C 72.435 131.013, 72.806 132.764, 74.577 136.769 C 77.484 143.343, 77.737 143.671, 78.943 142.433 C 79.492 141.870, 78.976 139.438, 77.639 136.296 C 75.107 130.344, 74.932 130.119, 73.293 130.706 M 143.446 132.087 C 143.077 132.685, 143.200 133.600, 143.720 134.120 C 145.074 135.474, 147.978 134.105, 147.330 132.417 C 146.686 130.740, 144.399 130.545, 143.446 132.087 M 37.158 134 C 37.158 135.375, 37.385 135.938, 37.662 135.250 C 37.940 134.563, 37.940 133.438, 37.662 132.750 C 37.385 132.063, 37.158 132.625, 37.158 134 M 79.473 134.748 C 80.327 138.150, 80.774 138.626, 81.984 137.416 C 83.337 136.063, 82.055 132, 80.275 132 C 79.147 132, 78.951 132.671, 79.473 134.748 M 258.079 136.583 C 258.127 137.748, 258.364 137.985, 258.683 137.188 C 258.972 136.466, 258.936 135.603, 258.604 135.271 C 258.272 134.939, 258.036 135.529, 258.079 136.583 M 145.200 137.200 C 143.555 138.845, 143.691 142.499, 145.452 143.960 C 147.400 145.577, 149.962 144.951, 151.617 142.454 C 154.203 138.552, 148.510 133.890, 145.200 137.200 M 145.384 138.442 C 144.446 140.885, 145.428 143.459, 147.445 143.847 C 150.088 144.356, 152.227 141.293, 150.926 138.862 C 149.746 136.658, 146.173 136.387, 145.384 138.442 M 140.755 151.728 C 124.328 179.895, 105.854 213.187, 106.367 213.701 C 106.715 214.049, 107.173 214.146, 107.383 213.917 C 109.608 211.500, 145.650 146.902, 144.999 146.499 C 144.516 146.201, 142.606 148.554, 140.755 151.728 M 151 147.007 C 151 147.737, 186.766 211.291, 188.619 213.854 C 188.760 214.049, 189.300 214.049, 189.820 213.854 C 190.339 213.659, 184.739 202.925, 177.376 190 C 170.012 177.075, 161.403 161.893, 158.244 156.263 C 152.976 146.875, 151 144.350, 151 147.007 M 147 181 C 147 202.333, 147.354 214, 148 214 C 148.646 214, 149 202.333, 149 181 C 149 159.667, 148.646 148, 148 148 C 147.354 148, 147 159.667, 147 181 M 127.401 183.585 L 110.302 213.500 127.293 213.774 C 136.639 213.925, 144.453 213.881, 144.658 213.676 C 144.863 213.471, 144.911 199.886, 144.765 183.486 L 144.500 153.670 127.401 183.585 M 151 183.800 L 151 214 168.535 214 L 186.070 214 184.873 211.750 C 181.154 204.764, 152.678 155.346, 151.913 154.550 C 151.362 153.976, 151 165.561, 151 183.800 M 84.500 225 C 86.150 225.420, 114.500 225.763, 147.500 225.763 C 180.500 225.763, 208.850 225.420, 210.500 225 C 212.150 224.580, 183.800 224.237, 147.500 224.237 C 111.200 224.237, 82.850 224.580, 84.500 225 M 123.500 235.038 C 131.356 236.013, 165.956 236.016, 173 235.042 C 176.255 234.592, 166.051 234.284, 148 234.288 C 129.909 234.292, 119.941 234.597, 123.500 235.038" stroke="none" fill="black" fill-rule="evenodd"/>

</svg>'''

    renderer = QSvgRenderer(QByteArray(scope.encode("utf-8")))

    scale = 5 

    w = int(size * scale)
    h = int(size * scale)

    pixmap = QPixmap(w, h)
    pixmap.fill(Qt.transparent)

    p = QPainter(pixmap)
    renderer.render(p)
    p.end()

    # optional tint so it matches your system colour
    p = QPainter(pixmap)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(pixmap.rect(), colour)
    p.end()

    # center it in your icon system
    painter.drawPixmap(
        int(-w / 2),
        int(-h / 2),
        pixmap
    )

    _finish_icon(painter)


def draw_telescope_inactive(painter, cx, cy, size, colour):
    _setup_icon(painter, cx, cy, size)
    _pen(painter, colour, ICON_LINE_WIDTH)
    # Tube (left ? right, flat)
    painter.drawRoundedRect(QRectF(-50, -10, 90, 20), 6, 6)
    # Objective (right)
    painter.drawEllipse(QPointF(40, 0), 8, 12)
    # Eyepiece (left)
    painter.drawRect(QRectF(-62, -6, 12, 12))
    # Finder scope
    _pen(painter, colour, ICON_LINE_WIDTH_THIN)
    painter.drawRoundedRect(QRectF(-20, -18, 40, 6), 3, 3)
    # Mount
    _pen(painter, colour, ICON_LINE_WIDTH)
    painter.drawRoundedRect(QRectF(-12, 14, 24, 14), 3, 3)
    # Tripod
    painter.drawLine(QPointF(0, 28), QPointF(0, 55))
    painter.drawLine(QPointF(0, 50), QPointF(-30, 75))
    painter.drawLine(QPointF(0, 50), QPointF(30, 75))
    painter.drawLine(QPointF(0, 50), QPointF(0, 78))
    _pen(painter, colour, ICON_LINE_WIDTH_THIN)
    painter.drawLine(QPointF(-22, 70), QPointF(22, 70))
    _finish_icon(painter)
def draw_telescope_inactive(painter, cx, cy, size, colour):
    """Horizontal scope, objective RIGHT ? disconnected/inactive state."""
    _pen(painter, colour, ICON_LINE_WIDTH)
    # mirror everything by using negative x offsets
    # Main tube
    painter.drawRoundedRect(QRectF(cx - 38, cy - 16, 110, 32), 8, 8)
    # Objective housing (right end)
    painter.drawEllipse(QPointF(cx + 72, cy), 6, 19)
    _pen(painter, colour, ICON_LINE_WIDTH_THIN)
    painter.drawEllipse(QPointF(cx + 72, cy), 3, 13)
    # Eyepiece (left end)
    painter.drawRect(QRectF(cx - 56, cy - 8, 18, 16))
    painter.drawRect(QRectF(cx - 62, cy - 5, 6, 10))
    # Focuser knob
    painter.drawRect(QRectF(cx - 22, cy - 26, 14, 10))
    painter.drawLine(QPointF(cx - 15, cy - 16), QPointF(cx - 15, cy - 10))
    # Finder scope
    painter.drawRoundedRect(QRectF(cx + 4, cy - 30, 46, 8), 3, 3)
    painter.drawLine(QPointF(cx + 10, cy - 22), QPointF(cx + 8,  cy - 16))
    painter.drawLine(QPointF(cx + 42, cy - 22), QPointF(cx + 40, cy - 16))
    # Fork mount
    _pen(painter, colour, ICON_LINE_WIDTH)
    painter.drawRoundedRect(QRectF(cx - 14, cy + 16, 28, 16), 3, 3)
    painter.drawEllipse(QPointF(cx, cy + 38), 20, 7)
    # Column + legs
    painter.drawLine(QPointF(cx, cy + 45), QPointF(cx, cy + 72))
    painter.drawLine(QPointF(cx, cy + 68), QPointF(cx - 38, cy + 95))
    painter.drawLine(QPointF(cx, cy + 68), QPointF(cx + 38, cy + 95))
    painter.drawLine(QPointF(cx, cy + 68), QPointF(cx,      cy + 96))
    _pen(painter, colour, ICON_LINE_WIDTH_THIN)
    painter.drawLine(QPointF(cx - 26, cy + 86), QPointF(cx + 26, cy + 86))

def draw_telescope_active(painter, cx, cy, size, colour):
    import random
    random.seed(4)
    _setup_icon(painter, cx, cy, size)
    star = QColor("#F5D20B")
    # --- stars (upper half of icon space)
    stars = []
    for _ in range(20):
        x = random.randint(-80, 80)
        y = random.randint(-100, -20)
        r = random.choice([1.2, 1.5, 1.8, 2.2])
        stars.append((x, y, r))

    # stars = [
    #     (-30, -60, 2.0),
    #     (40, -70, 1.4),
    #     (-10, -85, 1.8),
    #     (55, -40, 1.2),
    #     (-50, -50, 1.6),
    # ]
    for x, y, r in stars:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(star.red(), star.green(), star.blue(), 60))
        painter.drawEllipse(QPointF(x, y), r * 2.5, r * 2.5)
        painter.setBrush(star)
        painter.drawEllipse(QPointF(x, y), r, r)
    # --- telescope rotated upward
    painter.save()
    painter.rotate(-38)
    _pen(painter, colour, ICON_LINE_WIDTH)
    painter.drawRoundedRect(QRectF(-50, -10, 90, 20), 6, 6)
    painter.drawEllipse(QPointF(40, 0), 8, 12)
    _pen(painter, colour, ICON_LINE_WIDTH_THIN)
    painter.drawRect(QRectF(-62, -6, 12, 12))
    painter.drawRoundedRect(QRectF(-20, -18, 40, 6), 3, 3)
    painter.restore()
    # mount unchanged (ground reference)
    _pen(painter, colour, ICON_LINE_WIDTH)
    painter.drawRoundedRect(QRectF(-12, 14, 24, 14), 3, 3)
    painter.drawLine(QPointF(0, 28), QPointF(0, 55))
    painter.drawLine(QPointF(0, 50), QPointF(-30, 75))
    painter.drawLine(QPointF(0, 50), QPointF(30, 75))
    painter.drawLine(QPointF(0, 50), QPointF(0, 78))
    _finish_icon(painter)

# def draw_telescope_active(painter, cx, cy, size, colour):
#     """Scope angled ~38° objective upper-right, amber stars ? connected state."""
#     star_c = "#F59E0B"

#     # Stars
#     stars = [
#         (cx + 65, cy - 95, 2.0, True),
#         (cx - 20, cy - 105, 1.4, False),
#         (cx - 65, cy - 82, 2.5, True),
#         (cx + 30, cy - 112, 1.2, False),
#         (cx - 48, cy - 108, 1.6, False),
#         (cx + 80, cy - 68,  1.3, False),
#     ]
#     for sx, sy, sr, spikes in stars:
#         painter.setPen(Qt.NoPen)
#         painter.setBrush(QColor(star_c + "33"))
#         painter.drawEllipse(QPointF(sx, sy), sr * 2.2, sr * 2.2)
#         painter.setBrush(QColor(star_c))
#         painter.drawEllipse(QPointF(sx, sy), sr, sr)
#         painter.setBrush(Qt.NoBrush)
#         if spikes:
#             _pen(painter, star_c, 1.2)
#             sp = sr * 3.5
#             painter.drawLine(QPointF(sx, sy - sp), QPointF(sx, sy - sr - 1))
#             painter.drawLine(QPointF(sx, sy + sr + 1), QPointF(sx, sy + sp))
#             painter.drawLine(QPointF(sx - sp, sy), QPointF(sx - sr - 1, sy))
#             painter.drawLine(QPointF(sx + sr + 1, sy), QPointF(sx + sp, sy))

#     # Rotated scope - save/translate/scale(-1)/rotate/draw/restore
#     painter.save()
#     painter.translate(cx, cy)
#     painter.scale(-1, 1)
#     painter.rotate(38)
#     _pen(painter, colour, ICON_LINE_WIDTH)
#     painter.drawRoundedRect(QRectF(-72, -16, 110, 32), 8, 8)
#     painter.drawEllipse(QPointF(-72, 0), 6, 19)
#     _pen(painter, colour, ICON_LINE_WIDTH_THIN)
#     painter.drawEllipse(QPointF(-72, 0), 3, 13)
#     painter.drawRect(QRectF(38, -8, 18, 16))
#     painter.drawRect(QRectF(56, -5, 6, 10))
#     painter.drawRect(QRectF(8, -26, 14, 10))
#     painter.drawLine(QPointF(15, -16), QPointF(15, -10))
#     painter.drawRoundedRect(QRectF(-50, -30, 46, 8), 3, 3)
#     painter.drawLine(QPointF(-44, -22), QPointF(-40, -16))
#     painter.drawLine(QPointF(-12, -22), QPointF(-10, -16))
#     painter.restore()

#     # Mount - upright
#     _pen(painter, colour, ICON_LINE_WIDTH)
#     painter.drawRoundedRect(QRectF(cx - 14, cy + 12, 28, 16), 3, 3)
#     painter.drawEllipse(QPointF(cx, cy + 34), 20, 7)
#     painter.drawLine(QPointF(cx, cy + 41), QPointF(cx, cy + 68))
#     painter.drawLine(QPointF(cx, cy + 64), QPointF(cx - 38, cy + 90))
#     painter.drawLine(QPointF(cx, cy + 64), QPointF(cx + 38, cy + 90))
#     painter.drawLine(QPointF(cx, cy + 64), QPointF(cx,      cy + 91))
#     _pen(painter, colour, ICON_LINE_WIDTH_THIN)
#     painter.drawLine(QPointF(cx - 26, cy + 82), QPointF(cx + 26, cy + 82))

def draw_telescope(painter: QPainter, cx: float, cy: float,
                   size: float, colour: str):
    """
    Line-art refractor telescope icon.
    cx, cy = centre. size = radius hint (~40 px).
    """
    s = size
    lw = ICON_LINE_WIDTH

    _pen(painter, colour, lw)

    # Pivot point (ball joint centre) ? anchor everything from here
    px = cx + s * 0.05
    py = cy + s * 0.10

    # ?? TRIPOD ????????????????????????????????????????????????????????????????
    foot_y = py + s * 0.90
    painter.drawLine(QPointF(px, py + s * 0.16), QPointF(px - s * 0.55, foot_y))  # left
    painter.drawLine(QPointF(px, py + s * 0.16), QPointF(px,             foot_y))  # centre
    painter.drawLine(QPointF(px, py + s * 0.16), QPointF(px + s * 0.55, foot_y))  # right

    # ?? PIVOT BALL ????????????????????????????????????????????????????????????
    painter.drawEllipse(QPointF(px, py), s * 0.10, s * 0.10)

    # ?? OPTICAL ASSEMBLY (rotated -30 deg around pivot) ???????????????????????
    painter.save()
    painter.translate(px, py - s * 0.22)   # shift origin up to tube centre-line
    painter.rotate(0)

    # Main tube
    tw, th = s * 1.34, s * 0.41
    tx, ty = -s * 0.43, -th / 2
    painter.drawRect(QRectF(tx, ty, tw, th))

    # Detail line inside main tube
    painter.drawLine(
        QPointF(tx + tw * 0.22, ty + th * 0.26),
        QPointF(tx + tw * 0.59, ty + th * 0.26),
    )

    # Middle collar (step-down)
    cw, ch = s * 0.30, s * 0.31
    cx2 = tx - cw
    painter.drawRect(QRectF(cx2, -ch / 2, cw, ch))

    # Objective end cap (leftmost)
    ew, eh = s * 0.26, s * 0.24
    ex = cx2 - ew
    painter.drawRect(QRectF(ex, -eh / 2, ew, eh))

    # Eyepiece cap (rightmost)
    epw, eph = s * 0.18, s * 0.31
    epx = tx + tw
    painter.drawRect(QRectF(epx, -eph / 2, epw, eph))

    painter.restore()

def draw_telescope_connected(painter: QPainter, cx: float, cy: float,
                   size: float, colour: str):
    """
    Line-art refractor telescope icon.
    cx, cy = centre. size = radius hint (~40 px).
    """
    s = size
    lw = ICON_LINE_WIDTH

    _pen(painter, colour, lw)

    # Pivot point (ball joint centre) ? anchor everything from here
    px = cx + s * 0.05
    py = cy + s * 0.10

    # ?? TRIPOD ????????????????????????????????????????????????????????????????
    foot_y = py + s * 0.90
    painter.drawLine(QPointF(px, py + s * 0.16), QPointF(px - s * 0.55, foot_y))  # left
    painter.drawLine(QPointF(px, py + s * 0.16), QPointF(px,             foot_y))  # centre
    painter.drawLine(QPointF(px, py + s * 0.16), QPointF(px + s * 0.55, foot_y))  # right

    # ?? PIVOT BALL ????????????????????????????????????????????????????????????
    painter.drawEllipse(QPointF(px, py), s * 0.10, s * 0.10)

    # ?? OPTICAL ASSEMBLY (rotated -30 deg around pivot) ???????????????????????
    painter.save()
    painter.translate(px, py - s * 0.22)   # shift origin up to tube centre-line
    painter.rotate(-30)

    # Main tube
    tw, th = s * 1.34, s * 0.41
    tx, ty = -s * 0.43, -th / 2
    painter.drawRect(QRectF(tx, ty, tw, th))

    # Detail line inside main tube
    painter.drawLine(
        QPointF(tx + tw * 0.22, ty + th * 0.26),
        QPointF(tx + tw * 0.59, ty + th * 0.26),
    )

    # Middle collar (step-down)
    cw, ch = s * 0.30, s * 0.31
    cx2 = tx - cw
    painter.drawRect(QRectF(cx2, -ch / 2, cw, ch))

    # Objective end cap (leftmost)
    ew, eh = s * 0.26, s * 0.24
    ex = cx2 - ew
    painter.drawRect(QRectF(ex, -eh / 2, ew, eh))

    # Eyepiece cap (rightmost)
    epw, eph = s * 0.18, s * 0.31
    epx = tx + tw
    painter.drawRect(QRectF(epx, -eph / 2, epw, eph))

    painter.restore()

def draw_telescope_connected2(painter: QPainter, cx: float, cy: float,
                              size: float, colour: str):
    """
    Line-art refractor telescope icon with decorative stars.
    cx, cy = centre. size = radius hint (~40 px).
    """
    s = size
    lw = ICON_LINE_WIDTH

    # ?? STAR PARAMETERS (easy to tweak) ??????????????????????????????????????
    STAR_COLOUR     = QColor(210, 190, 100)   # muted yellow ? adjust RGB freely
    STAR_LINE_WIDTH = max(1.0, lw * 0.35)     # stroke thickness of each ellipse
    STAR_LONG_R     = s * 0.14               # long-axis radius of each ellipse
    STAR_SHORT_R    = s * 0.03              # short-axis radius (thinness)

    # (x_offset, y_offset, scale) ? positions relative to cx,cy; scale shrinks/grows individual stars
    STAR_POSITIONS = [
    (-0.95,  -0.20, 0.75),   # left low
    (-0.80,  -0.75, 1.00),   # left mid
    (-0.55,  -1.10, 0.55),   # top left
    (-0.45,  -0.40, 0.62),   # top left
    (-0.15,  -1.05, 0.70),   # upper left centre
    (-0.12,  -0.72, 0.85),   # upper left centre
    ( 0.28,  -0.90, 0.85),   # upper right centre
    ( 0.52,  -1.10, 0.60),   # top right
    ( 0.85,  -1.10, 0.90),   # right mid
    ( 0.48,   0.10, 0.70),   # right low
    ( 0.85,  -0.10, 0.90),   # right low
    # ( 1.00,  -0.95, 0.65),   # right low
]

    # Draw stars
    star_pen = QPen(STAR_COLOUR)
    star_pen.setWidthF(STAR_LINE_WIDTH)
    star_pen.setCapStyle(Qt.RoundCap)
    painter.setPen(star_pen)
    painter.setBrush(QBrush(STAR_COLOUR))

    for (ox, oy, sc) in STAR_POSITIONS:
        scx = cx + ox * s
        scy = cy + oy * s
        jitter = 0.15
        lr  = STAR_LONG_R  * sc * (1.0 + random.uniform(-jitter, jitter))
        sr  = STAR_SHORT_R * sc * (1.0 + random.uniform(-jitter, jitter))
        # Horizontal ellipse
        painter.drawEllipse(QPointF(scx, scy), lr, sr)
        # Vertical ellipse (same centre, axes swapped)
        painter.drawEllipse(QPointF(scx, scy), sr, lr)

    # ?? TELESCOPE ?????????????????????????????????????????????????????????????
    _pen(painter, colour, lw)

    px = cx + s * 0.05
    py = cy + s * 0.10

    # Tripod
    foot_y = py + s * 0.90
    painter.drawLine(QPointF(px, py + s * 0.16), QPointF(px - s * 0.55, foot_y))
    painter.drawLine(QPointF(px, py + s * 0.16), QPointF(px,             foot_y))
    painter.drawLine(QPointF(px, py + s * 0.16), QPointF(px + s * 0.55, foot_y))

    # Pivot ball
    painter.drawEllipse(QPointF(px, py), s * 0.10, s * 0.10)

    # Optical assembly
    painter.save()
    painter.translate(px, py - s * 0.22)
    painter.rotate(-30)

    tw, th = s * 1.34, s * 0.41
    tx, ty = -s * 0.43, -th / 2
    painter.drawRect(QRectF(tx, ty, tw, th))

    painter.drawLine(
        QPointF(tx + tw * 0.22, ty + th * 0.26),
        QPointF(tx + tw * 0.59, ty + th * 0.26),
    )

    cw, ch = s * 0.30, s * 0.31
    cx2 = tx - cw
    painter.drawRect(QRectF(cx2, -ch / 2, cw, ch))

    ew, eh = s * 0.26, s * 0.24
    ex = cx2 - ew
    painter.drawRect(QRectF(ex, -eh / 2, ew, eh))

    epw, eph = s * 0.18, s * 0.31
    epx = tx + tw
    painter.drawRect(QRectF(epx, -eph / 2, epw, eph))

    painter.restore()


def draw_covers(painter: QPainter, cx: float, cy: float,
                size: float, colour: str):
    """
    Two-panel aperture cover (front view of the telescope lens cap).
    """
    _pen(painter, colour, ICON_LINE_WIDTH)
    r = size * 0.72

    # Outer ring
    painter.drawEllipse(QPointF(cx, cy), r, r)

    # Left half panel
    left_path = QPainterPath()
    left_path.moveTo(cx, cy - r)
    left_path.arcTo(QRectF(cx - r, cy - r, r * 2, r * 2), 90, 180)
    left_path.closeSubpath()
    _pen(painter, colour, ICON_LINE_WIDTH)
    painter.drawPath(left_path)

    # Right half panel
    right_path = QPainterPath()
    right_path.moveTo(cx, cy - r)
    right_path.arcTo(QRectF(cx - r, cy - r, r * 2, r * 2), 90, -180)
    right_path.closeSubpath()
    painter.drawPath(right_path)

    # Centre divider line
    painter.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))

    # Hinge centre dot
    painter.setBrush(QColor(colour))
    painter.drawEllipse(QPointF(cx, cy), 3, 3)
    painter.setBrush(Qt.NoBrush)

    # Side brackets (L + R)
    _pen(painter, colour, ICON_LINE_WIDTH_THIN)
    bracket_len = r * 0.28
    for side in (-1, 1):
        bx = cx + side * (r + r * 0.22)
        painter.drawLine(QPointF(bx, cy - bracket_len),
                         QPointF(bx, cy + bracket_len))
        painter.drawLine(QPointF(bx - side * 4, cy - bracket_len),
                         QPointF(bx + side * 4, cy - bracket_len))
        painter.drawLine(QPointF(bx - side * 4, cy + bracket_len),
                         QPointF(bx + side * 4, cy + bracket_len))


def draw_dome(painter: QPainter, cx: float, cy: float,
              size: float, colour: str):
    """
    Observatory dome - hemisphere on a rectangular building.
    """
    s = size
    _pen(painter, colour, ICON_LINE_WIDTH)

    # Dome hemisphere
    dome_r  = s * 0.68
    dome_y  = cy + s * 0.05
    painter.drawArc(
        QRectF(cx - dome_r, dome_y - dome_r, dome_r * 2, dome_r * 2),
        0, 180 * 16   # Qt arcs use 1/16th degree
    )

    # Wall rectangle
    wall_w = dome_r * 2
    wall_h = s * 0.30
    wall_x = cx - wall_w * 0.5
    wall_y = dome_y
    painter.drawRect(QRectF(wall_x, wall_y, wall_w, wall_h))

    # Slit opening in dome
    _pen(painter, colour, ICON_LINE_WIDTH_THIN)
    slit_w = dome_r * 0.30
    painter.drawArc(
        QRectF(cx - dome_r, dome_y - dome_r, dome_r * 2, dome_r * 2),
        70 * 16, 40 * 16
    )
    painter.drawLine(QPointF(cx - slit_w * 0.5, dome_y - dome_r * 0.98),
                     QPointF(cx - slit_w * 0.5, dome_y))
    painter.drawLine(QPointF(cx + slit_w * 0.5, dome_y - dome_r * 0.98),
                     QPointF(cx + slit_w * 0.5, dome_y))

    # Sliding door panel line in wall
    painter.drawLine(QPointF(cx, wall_y), QPointF(cx, wall_y + wall_h))

    # Base plinth
    _pen(painter, colour, ICON_LINE_WIDTH)
    plinth_w = wall_w + s * 0.12
    painter.drawLine(QPointF(cx - plinth_w * 0.5, wall_y + wall_h),
                     QPointF(cx + plinth_w * 0.5, wall_y + wall_h))


def draw_dome_active(painter: QPainter, cx: float, cy: float,
              size: float, colour: str):
    """
    Observatory dome - hemisphere on a rectangular building.
    """
    s = size
    _pen(painter, colour, ICON_LINE_WIDTH)

    # Dome hemisphere
    dome_r  = s * 0.68
    dome_y  = cy + s * 0.05
    painter.drawArc(
        QRectF(cx - dome_r, dome_y - dome_r, dome_r * 2, dome_r * 2),
        0, 180 * 16   # Qt arcs use 1/16th degree
    )

    # Wall rectangle
    wall_w = dome_r * 2
    wall_h = s * 0.30
    wall_x = cx - wall_w * 0.5
    wall_y = dome_y
    painter.drawRect(QRectF(wall_x, wall_y, wall_w, wall_h))

    # Slit opening in dome
    _pen(painter, colour, ICON_LINE_WIDTH_THIN)
    slit_w = dome_r * 0.30
    painter.drawArc(
        QRectF(cx - dome_r, dome_y - dome_r, dome_r * 2, dome_r * 2),
        70 * 16, 40 * 16
    )
    painter.drawLine(QPointF(cx - slit_w * 0.5, dome_y - dome_r * 0.98),
                     QPointF(cx - slit_w * 0.5, dome_y))
    painter.drawLine(QPointF(cx + slit_w * 0.5, dome_y - dome_r * 0.98),
                     QPointF(cx + slit_w * 0.5, dome_y))

    # Sliding door panel line in wall
    painter.drawLine(QPointF(cx, wall_y), QPointF(cx, wall_y + wall_h))

    # Base plinth
    _pen(painter, colour, ICON_LINE_WIDTH)
    plinth_w = wall_w + s * 0.12
    painter.drawLine(QPointF(cx - plinth_w * 0.5, wall_y + wall_h),
                     QPointF(cx + plinth_w * 0.5, wall_y + wall_h))
    
    # ?? STAR PARAMETERS (easy to tweak) ??????????????????????????????????????
    STAR_COLOUR     = QColor(210, 190, 100)   # muted yellow ? adjust RGB freely
    STAR_LINE_WIDTH = max(1.0, ICON_LINE_WIDTH * 0.35)     # stroke thickness of each ellipse
    STAR_LONG_R     = s * 0.14               # long-axis radius of each ellipse
    STAR_SHORT_R    = s * 0.03              # short-axis radius (thinness)

    # (x_offset, y_offset, scale) ? positions relative to cx,cy; scale shrinks/grows individual stars
    STAR_POSITIONS = [
    (-0.95, -0.45, 0.53),
    (-0.90, -1.05, 0.85),
    (-0.77, -0.75, 0.95),
    # (-0.70, -0.65, 0.55),
    (-0.50, -1.00, 0.77),
    (-0.30, -0.92, 0.50),
    (-0.10, -0.98, 0.82),
    # (-0.00, -0.83, 0.88),   
    ( 0.10, -1.15, 0.55),
    ( 0.30, -1.00, 0.48),
    ( 0.55, -0.93, 0.92),
    ( 0.80, -0.60, 0.55),
    ( 0.85, -0.40, 0.50),
    ( 0.85, -1.05, 1.06),
]

    # Draw stars
    star_pen = QPen(STAR_COLOUR)
    star_pen.setWidthF(STAR_LINE_WIDTH)
    star_pen.setCapStyle(Qt.RoundCap)
    painter.setPen(star_pen)
    painter.setBrush(QBrush(STAR_COLOUR))

    for (ox, oy, sc) in STAR_POSITIONS:
        scx = cx + ox * s
        scy = cy + oy * s
        jitter = 0.15
        lr  = STAR_LONG_R  * sc * (1.0 + random.uniform(-jitter, jitter))
        sr  = STAR_SHORT_R * sc * (1.0 + random.uniform(-jitter, jitter))
        # lr  = STAR_LONG_R  * sc
        # sr  = STAR_SHORT_R * sc
        # Horizontal ellipse
        painter.drawEllipse(QPointF(scx, scy), lr, sr)
        # Vertical ellipse (same centre, axes swapped)
        painter.drawEllipse(QPointF(scx, scy), sr, lr)
    
    # Moon
    
    # MOON_R = s * 0.12
    # moon_x = cx - 0.65 * s
    # moon_y = cy - 0.85 * s

    # # soft glow layers
    # for i, alpha in enumerate([40, 25, 15]):
    #     glow_color = QColor(255, 255, 255, alpha)
    #     painter.setBrush(glow_color)
    #     painter.setPen(Qt.NoPen)
    #     painter.drawEllipse(QPointF(moon_x, moon_y), MOON_R * (1.4 + i*0.2), MOON_R * (1.4 + i*0.2))

    # # core moon
    # painter.setBrush(QColor(255, 255, 255))
    # painter.drawEllipse(QPointF(moon_x, moon_y), MOON_R, MOON_R)

def draw_rotator(painter: QPainter, cx: float, cy: float,
                 size: float, colour: str):
    """
    Rotator - concentric rings with directional rotation arrows.
    Arrows draw in accent colour when connected, dimmed otherwise.
    """
    s   = size
    _pen(painter, colour, ICON_LINE_WIDTH)

    # Outer ring
    painter.drawEllipse(QPointF(cx, cy), s * 0.70, s * 0.70)

    # Middle ring
    painter.drawEllipse(QPointF(cx, cy), s * 0.42, s * 0.42)

    # Inner dot
    painter.setBrush(QColor(colour))
    painter.drawEllipse(QPointF(cx, cy), s * 0.12, s * 0.12)
    painter.setBrush(Qt.NoBrush)

    # Rotation arrows - use accent if connected, dim otherwise
    arrow_colour = COL_ACCENT if colour != COL_TEXT_DIM else COL_TEXT_DIM
    _pen(painter, arrow_colour, ICON_LINE_WIDTH)

    arc_r = s * 0.92
    # Left arc (counter-clockwise sweep on left side)
    painter.drawArc(
        QRectF(cx - arc_r, cy - arc_r * 0.55, arc_r, arc_r * 1.1),
        200 * 16, 120 * 16
    )
    # Left arrowhead
    ax, ay = cx - arc_r * 0.92, cy - arc_r * 0.22
    _draw_arrowhead(painter, arrow_colour, ax, ay, angle_deg=330)

    # Right arc (clockwise sweep on right side)
    painter.drawArc(
        QRectF(cx, cy - arc_r * 0.55, arc_r, arc_r * 1.1),
        -20 * 16, 120 * 16  # sweep from -20 -> +100 (right side, upward)
    )
    # Right arrowhead
    bx, by = cx + arc_r * 0.92, cy + arc_r * 0.22
    _draw_arrowhead(painter, arrow_colour, bx, by, angle_deg=150)

def draw_rotator2(painter, cx, cy, size, colour):
    _setup_icon(painter, cx, cy, size)

    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))

    scale = 1.6  # ?? adjust this exactly the same way

    w = int(size * scale)
    h = int(size * scale)

    pixmap = QPixmap(w, h)
    pixmap.fill(Qt.transparent)

    p = QPainter(pixmap)
    renderer.render(p)
    p.end()

    # tint to match your icon system
    p = QPainter(pixmap)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(pixmap.rect(), colour)
    p.end()

    painter.drawPixmap(
        int(-w / 2),
        int(-h / 2),
        pixmap
    )

    _finish_icon(painter)

def draw_rotator3(painter, cx, cy, size, colour):
    _setup_icon(painter, cx, cy, size)

    rotator_icon = f"""<svg width="300" height="300" viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
  <g transform="translate(150,150)" fill="{colour}">
    <g id="arrow">
      <!-- Band -->
      <path d="
        M 0 -110
        A 110 110 0 0 1 95 -30
        L 85 -30
        A 85 85 0 0 0 0 -85
        Z
      "/>
      <!-- Arrowhead -->
      <path d="
        M 58 -30
        L 120 -30
        L 98 0
        Z
      "/>
    </g>
    <use href="#arrow" transform="rotate(120)"/>
    <use href="#arrow" transform="rotate(240)"/>
  </g>
</svg>
"""
    renderer = QSvgRenderer(QByteArray(rotator_icon.encode("utf-8")))
    scale = 4.5 
    # draw centered
    rect = QRectF(
        -size * scale / 2,
        -size * scale / 2,
        size * scale,
        size * scale
    )

    renderer.render(painter, rect)
    _finish_icon(painter)


def _draw_arrowhead(painter: QPainter, colour: str,
                    x: float, y: float, angle_deg: float, size: float = 5.5):
    """Draw a small filled arrowhead at (x,y) pointing in angle_deg direction."""
    angle = math.radians(angle_deg)
    tip   = QPointF(x, y)
    left  = QPointF(x - size * math.cos(angle - math.radians(30)),
                    y - size * math.sin(angle - math.radians(30)))
    right = QPointF(x - size * math.cos(angle + math.radians(30)),
                    y - size * math.sin(angle + math.radians(30)))
    path  = QPainterPath()
    path.moveTo(tip)
    path.lineTo(left)
    path.lineTo(right)
    path.closeSubpath()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(colour))
    painter.drawPath(path)
    painter.setBrush(Qt.NoBrush)



def draw_focuser(painter, cx, cy, size, colour):
    """Crayford focuser - drawtube sliding in a housing."""
    _pen(painter, colour, ICON_LINE_WIDTH)
    s = size

    # Main housing body (wide rectangle)
    painter.drawRoundedRect(QRectF(cx - s*0.55, cy - s*0.28, s*1.1, s*0.56), 4, 4)

    # Drawtube sliding out the right side
    painter.drawRoundedRect(QRectF(cx + s*0.22, cy - s*0.16, s*0.52, s*0.32), 3, 3)

    # Drawtube end cap
    _pen(painter, colour, ICON_LINE_WIDTH_THIN)
    painter.drawLine(QPointF(cx + s*0.74, cy - s*0.16),
                     QPointF(cx + s*0.74, cy + s*0.16))

    # Focuser knob on top of housing
    painter.drawRect(QRectF(cx - s*0.12, cy - s*0.42, s*0.24, s*0.14))
    painter.drawLine(QPointF(cx, cy - s*0.42), QPointF(cx, cy - s*0.28))

    # Second knob (fine adjust) ? slightly right
    painter.drawRect(QRectF(cx + s*0.18, cy - s*0.42, s*0.18, s*0.14))

    # Locking screw on housing side
    painter.drawEllipse(QPointF(cx - s*0.28, cy + s*0.28), s*0.06, s*0.06)
    painter.drawEllipse(QPointF(cx + s*0.10, cy + s*0.28), s*0.06, s*0.06)

    # Centre crosshair on drawtube end (eyepiece side)
    _pen(painter, colour, ICON_LINE_WIDTH_THIN)
    painter.drawLine(QPointF(cx + s*0.60, cy - s*0.10),
                     QPointF(cx + s*0.60, cy + s*0.10))
    painter.drawLine(QPointF(cx + s*0.50, cy),
                     QPointF(cx + s*0.70, cy))
    
def draw_focuser2(painter, cx, cy, size, colour):
    """Focuser icon - corner brackets + crosshair (replaces old diagram)."""
    _pen(painter, colour, ICON_LINE_WIDTH)
    s = size

    scale = 1.4
    half = (s * scale) / 2
    m = 0.20 * s * scale
    cross = 0.15 * s * scale
    
    # half = s / 2
    # m = 0.20 * s   # corner length
    # cross = 0.15 * s

    left   = cx - half
    right  = cx + half
    top    = cy - half
    bottom = cy + half

    # --- Corner brackets ---

    # Top-left
    painter.drawLine(QPointF(left, top), QPointF(left + m, top))
    painter.drawLine(QPointF(left, top), QPointF(left, top + m))

    # Top-right
    painter.drawLine(QPointF(right, top), QPointF(right - m, top))
    painter.drawLine(QPointF(right, top), QPointF(right, top + m))

    # Bottom-left
    painter.drawLine(QPointF(left, bottom), QPointF(left + m, bottom))
    painter.drawLine(QPointF(left, bottom), QPointF(left, bottom - m))

    # Bottom-right
    painter.drawLine(QPointF(right, bottom), QPointF(right - m, bottom))
    painter.drawLine(QPointF(right, bottom), QPointF(right, bottom - m))

    # --- Center crosshair ---
    painter.drawLine(QPointF(cx - cross, cy), QPointF(cx + cross, cy))
    painter.drawLine(QPointF(cx, cy - cross), QPointF(cx, cy + cross))