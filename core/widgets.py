# -*- coding: utf-8 -*-
"""跨模块复用的 UI 控件。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .icons import nav_icon
from .theme import C, q_rgba


class LogoMark(QWidget):
    def __init__(self, size: int = 46, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("#4A8CFF"))
        gradient.setColorAt(1.0, QColor("#1D4ED8"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(rect, self.width() * 0.28, self.width() * 0.28)

        pen = QPen(QColor(255, 255, 255, 232))
        pen.setWidthF(max(1.4, self.width() / 22.0))
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        cx, cy = self.width() / 2.0, self.height() * 0.72
        scale = self.width() / 46.0
        for radius in (7.0 * scale, 13.0 * scale, 19.0 * scale):
            painter.drawArc(
                QRectF(cx - radius, cy - radius, radius * 2, radius * 2), 45 * 16, 90 * 16
            )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 245))
        painter.drawEllipse(QPointF(cx, cy), 2.6 * scale, 2.6 * scale)
        painter.end()


class Sparkline(QWidget):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self._color = QColor(color)
        self._values: list[float] = []

    def set_values(self, values):
        self._values = list(values)[-72:]
        self.update()

    def paintEvent(self, event):  # noqa: N802
        if len(self._values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(1, 4, max(2, self.width() - 2), max(2, self.height() - 8))
        low = min(self._values)
        high = max(self._values)
        if high - low < 1e-9:
            high = low + 1.0
            low -= 1.0
        count = len(self._values)
        points = [
            QPointF(
                rect.left() + i * rect.width() / (count - 1),
                rect.bottom() - (value - low) / (high - low) * rect.height(),
            )
            for i, value in enumerate(self._values)
        ]
        line = QPainterPath()
        line.moveTo(points[0])
        for point in points[1:]:
            line.lineTo(point)
        fill = QPainterPath(line)
        fill.lineTo(points[-1].x(), rect.bottom())
        fill.lineTo(points[0].x(), rect.bottom())
        fill.closeSubpath()
        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        top = QColor(self._color)
        top.setAlpha(72)
        bottom = QColor(self._color)
        bottom.setAlpha(0)
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, bottom)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawPath(fill)
        pen = QPen(self._color, 1.8)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(line)
        painter.end()


class LevelBar(QWidget):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self._color = QColor(color)
        self._ratio = 0.0

    def set_ratio(self, ratio: float):
        self._ratio = max(0.0, min(1.0, ratio))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        height = 6.0
        top = (self.height() - height) / 2.0
        track = QRectF(0, top, self.width(), height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 18))
        painter.drawRoundedRect(track, 3, 3)
        if self._ratio > 0:
            width = max(6.0, self.width() * self._ratio)
            fill = QRectF(0, top, width, height)
            gradient = QLinearGradient(0, 0, self.width(), 0)
            start = QColor(self._color)
            start.setAlpha(150)
            gradient.setColorAt(0.0, start)
            gradient.setColorAt(1.0, self._color)
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(fill, 3, 3)
        painter.end()


class MetricCard(QFrame):
    def __init__(self, title: str, unit: str, accent: str, kind: str = "spark", parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setMinimumHeight(126)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.accent = accent
        root = QVBoxLayout(self)
        root.setContentsMargins(17, 13, 17, 12)
        root.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        marker = QFrame()
        marker.setFixedSize(18, 3)
        marker.setStyleSheet(f"background-color:{accent}; border-radius:1px;")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")
        self.badge = QLabel("")
        self.badge.setObjectName("MetricBadge")
        self.badge.setVisible(False)
        top.addWidget(marker)
        top.addWidget(self.title_label)
        top.addStretch(1)
        top.addWidget(self.badge)
        root.addLayout(top)

        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        self.value_label = QLabel("—")
        self.value_label.setObjectName("MetricValue")
        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("MetricUnit")
        value_row.addWidget(self.value_label)
        value_row.addWidget(self.unit_label, 0, Qt.AlignBottom)
        value_row.addStretch(1)
        root.addLayout(value_row)

        self.sub_label = QLabel("等待数据")
        self.sub_label.setObjectName("MetricSub")
        root.addWidget(self.sub_label)

        if kind == "spark":
            self.spark = Sparkline(accent)
            root.addWidget(self.spark)
            self.bar = None
        else:
            self.bar = LevelBar(accent)
            root.addSpacing(4)
            root.addWidget(self.bar)
            self.spark = None

    def set_value(self, text: str, sub: str | None = None, badge: str | None = None):
        self.value_label.setText(text)
        if sub is not None:
            self.sub_label.setText(sub)
        if badge is not None:
            self.badge.setText(badge)
            self.badge.setVisible(bool(badge))

    def set_ratio(self, ratio: float):
        if self.bar is not None:
            self.bar.set_ratio(ratio)

    def set_spark(self, values):
        if self.spark is not None:
            self.spark.set_values(values)


class SectionCard(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        titles.addWidget(self.title_label)
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("CardSub")
            titles.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None
        self.header.addLayout(titles)
        self.header.addStretch(1)
        root.addLayout(self.header)

        self.body = QVBoxLayout()
        self.body.setSpacing(9)
        root.addLayout(self.body, 1)


class ChartArea(QWidget):
    def __init__(self, plot: QWidget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(plot)
        self.empty_label = QLabel("串口未连接\n请选择串口并打开", self)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.empty_label.setStyleSheet(
            "color:#4F6688; font-size:13px; background:transparent;"
        )
        self.empty_label.setGeometry(self.rect())

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.empty_label.setGeometry(self.rect())
        self.empty_label.raise_()

    def sizeHint(self):  # noqa: N802
        return QSize(640, 220)

    def minimumSizeHint(self):  # noqa: N802
        return QSize(320, 190)

    def set_empty(self, text: str, visible: bool):
        self.empty_label.setText(text)
        self.empty_label.setVisible(visible)
        if visible:
            self.empty_label.raise_()


class StatTile(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatTile")
        self.setMinimumHeight(50)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(0)
        title_label = QLabel(title)
        title_label.setObjectName("StatTitle")
        self.value_label = QLabel("—")
        self.value_label.setObjectName("StatValue")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, text: str):
        self.value_label.setText(text)


class StatusPill(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("Pill")
        self.setAlignment(Qt.AlignCenter)
        self.set_muted(text)

    def set_state(self, text: str, color: str):
        self.setText(text)
        self.setStyleSheet(
            f"color:{color}; background-color:{q_rgba(color, 0.10)};"
            f"border:1px solid {q_rgba(color, 0.35)}; border-radius:10px;"
            "padding:4px 11px; font-size:12px;"
        )

    def set_muted(self, text: str):
        self.set_state(text, C.DIM)


class SegmentedTabs(QFrame):
    """模块内部的二级功能标签（硬件/PID/监测/通讯 或 数据/串口）。"""

    changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModuleTabs")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        self._group.idClicked.connect(self.changed.emit)

    def add_tab(self, text: str, icon_name: str = "") -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("ModuleTab")
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        if icon_name:
            button.setIcon(nav_icon(icon_name, 18))
            button.setIconSize(QSize(18, 18))
        index = len(self._buttons)
        self._group.addButton(button, index)
        self._buttons.append(button)
        self._layout.addWidget(button)
        if index == 0:
            button.setChecked(True)
        return button

    def add_stretch(self):
        self._layout.addStretch(1)

    def add_action(self, widget: QWidget):
        """在标签右侧添加一个操作控件（如协议说明按钮）。"""
        self._layout.addSpacing(6)
        self._layout.addWidget(widget)

    def set_current(self, index: int):
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def current_index(self) -> int:
        return max(0, self._group.checkedId())

    def buttons(self) -> list[QPushButton]:
        return list(self._buttons)
