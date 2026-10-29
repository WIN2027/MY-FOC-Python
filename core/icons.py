# -*- coding: utf-8 -*-
"""QPainter 绘制的线性图标，避免依赖外部图片资源。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from .theme import C

ICON_SIZE = 28


def _pen(color: str, width: float = 1.8) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def draw_icon(name: str, color: str = C.MUTED, size: int = 24) -> QPixmap:
    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(_pen(color))

    if name == "overview":
        painter.setBrush(Qt.NoBrush)
        for x, y in ((5, 5), (16, 5), (5, 16), (16, 16)):
            painter.drawRoundedRect(QRectF(x, y, 7, 7), 2, 2)

    elif name == "lora":
        painter.setBrush(Qt.NoBrush)
        for radius in (4.0, 8.0, 12.0):
            painter.drawArc(
                QRectF(14 - radius, 22 - radius, radius * 2, radius * 2),
                45 * 16,
                90 * 16,
            )
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(14, 22), 1.8, 1.8)

    elif name == "foc":
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(14, 14), 10, 10)
        painter.drawPolyline(
            [QPointF(7, 16), QPointF(10, 11), QPointF(14, 17), QPointF(18, 11), QPointF(21, 16)]
        )

    elif name == "about":
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(14, 14), 10, 10)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(14, 9), 1.4, 1.4)
        painter.setPen(_pen(color, 2.0))
        painter.drawLine(QPointF(14, 13), QPointF(14, 20))

    elif name in ("hardware", "settings"):
        painter.setPen(_pen(color, 1.8))
        for y, knob_x in ((8, 10), (14, 18), (20, 7)):
            painter.drawLine(QPointF(5, y), QPointF(23, y))
            painter.setBrush(QColor("#071226"))
            painter.drawEllipse(QPointF(knob_x, y), 2.4, 2.4)

    elif name == "pid":
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(QRectF(5, 6, 18, 18), 210 * 16, 240 * 16)
        painter.drawLine(QPointF(14, 15), QPointF(20, 9))
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(14, 15), 1.8, 1.8)

    elif name == "monitor":
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(QPointF(4, 23), QPointF(24, 23))
        painter.drawPolyline(
            [
                QPointF(5, 18),
                QPointF(9, 10),
                QPointF(13, 16),
                QPointF(17, 6),
                QPointF(21, 13),
                QPointF(24, 11),
            ]
        )

    elif name == "comm":
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(4, 6, 20, 16), 3, 3)
        painter.drawPolyline([QPointF(8, 11), QPointF(12, 14), QPointF(8, 17)])
        painter.drawLine(QPointF(14, 17), QPointF(20, 17))

    elif name in ("serial", "link"):
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(QPointF(5, 10), QPointF(23, 10))
        painter.drawLine(QPointF(5, 18), QPointF(23, 18))
        painter.drawPolyline([QPointF(9, 6), QPointF(5, 10), QPointF(9, 14)])
        painter.drawPolyline([QPointF(19, 14), QPointF(23, 18), QPointF(19, 22)])

    elif name in ("collapse_left", "expand_right"):
        direction = 1 if name == "collapse_left" else -1
        painter.drawPolyline(
            [
                QPointF(14 + 4 * direction, 7),
                QPointF(14 - 4 * direction, 14),
                QPointF(14 + 4 * direction, 21),
            ]
        )

    elif name in ("refresh", "sync"):
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(QRectF(6, 6, 16, 16), 40 * 16, 280 * 16)
        painter.drawPolyline([QPointF(20, 6), QPointF(22, 11), QPointF(17, 11)])

    elif name == "play":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon([QPointF(9, 6), QPointF(23, 14), QPointF(9, 22)])

    elif name == "stop":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(8, 8, 12, 12), 2, 2)

    elif name == "pause":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(8, 6, 4, 16), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(16, 6, 4, 16), 1.5, 1.5)

    elif name == "save":
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(5, 5, 18, 18), 2, 2)
        painter.drawRect(QRectF(9, 5, 8, 6))
        painter.drawRect(QRectF(9, 16, 10, 7))

    elif name == "export":
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(QPointF(14, 5), QPointF(14, 18))
        painter.drawPolyline([QPointF(9, 13), QPointF(14, 18), QPointF(19, 13)])
        painter.drawPolyline([QPointF(6, 20), QPointF(6, 23), QPointF(22, 23), QPointF(22, 20)])

    elif name == "measure":
        painter.setBrush(Qt.NoBrush)
        for x in (9, 19):
            painter.drawLine(QPointF(x, 5), QPointF(x, 23))
        painter.drawLine(QPointF(9, 14), QPointF(19, 14))
        painter.drawPolyline([QPointF(7, 8), QPointF(9, 6), QPointF(11, 8)])
        painter.drawPolyline([QPointF(17, 20), QPointF(19, 22), QPointF(21, 20)])

    elif name == "plus":
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(QPointF(14, 6), QPointF(14, 22))
        painter.drawLine(QPointF(6, 14), QPointF(22, 14))

    else:
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(14, 14), 9, 9)

    painter.end()
    if size != ICON_SIZE:
        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pixmap


def make_icon(name: str, color: str = C.MUTED, size: int = 24) -> QIcon:
    return QIcon(draw_icon(name, color, size))


def nav_icon(name: str, size: int = 22) -> QIcon:
    icon = QIcon()
    icon.addPixmap(draw_icon(name, C.MUTED, size), QIcon.Normal, QIcon.Off)
    icon.addPixmap(draw_icon(name, "#FFFFFF", size), QIcon.Normal, QIcon.On)
    icon.addPixmap(draw_icon(name, C.BLUE, size), QIcon.Active, QIcon.Off)
    icon.addPixmap(draw_icon(name, C.BLUE, size), QIcon.Active, QIcon.On)
    return icon


def app_icon() -> QIcon:
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    from PySide6.QtGui import QLinearGradient

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#4A8CFF"))
    gradient.setColorAt(1.0, QColor("#1D4ED8"))
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), 16, 16)
    pen = QPen(QColor(255, 255, 255, 235), 3.0)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    cx, cy = size / 2.0, size * 0.72
    for radius in (9.0, 17.0, 25.0):
        painter.drawArc(
            QRectF(cx - radius, cy - radius, radius * 2, radius * 2), 45 * 16, 90 * 16
        )
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 255, 255, 245))
    painter.drawEllipse(QPointF(cx, cy), 3.4, 3.4)
    painter.end()
    return QIcon(pixmap)
