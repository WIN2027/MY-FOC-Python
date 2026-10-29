# -*- coding: utf-8 -*-
"""2.4G 温湿度双 Y 轴曲线组件。"""

from __future__ import annotations

import time
from bisect import bisect_left
from datetime import datetime

import pyqtgraph as pg
from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.theme import C
from core.widgets import ChartArea
from modules.lora.protocol import Sample


class LoraChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._chart_x: list[float] = []
        self._chart_temp: list[float] = []
        self._chart_hum: list[float] = []
        self._paused = False
        self._last_visible_count = 0
        self._temp_visible = True
        self._hum_visible = True

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        self.plot = pg.PlotWidget(
            axisItems={"bottom": pg.DateAxisItem(orientation="bottom")}
        )
        self.plot.setAntialiasing(True)
        self.plot.setBackground(None)
        self.plot.setMinimumHeight(168)
        self.plot.setMenuEnabled(False)
        plot_item = self.plot.getPlotItem()
        plot_item.hideButtons()
        plot_item.setMenuEnabled(False)
        plot_item.setMouseEnabled(x=False, y=False)
        plot_item.showGrid(x=True, y=True, alpha=0.13)

        left = plot_item.getAxis("left")
        left.setPen(pg.mkPen("#1B3558"))
        left.setTextPen(pg.mkPen(C.MUTED))
        left.setWidth(52)
        left.setStyle(tickFont=QFont("Bahnschrift", 9), tickLength=-4, tickTextOffset=6)
        left.setLabel("温度", units="℃", color=C.CYAN, **{"font-size": "9pt"})
        left.enableAutoSIPrefix(False)

        bottom = plot_item.getAxis("bottom")
        bottom.setPen(pg.mkPen("#1B3558"))
        bottom.setTextPen(pg.mkPen(C.MUTED))
        bottom.setStyle(tickFont=QFont("Bahnschrift", 9), tickLength=-4, tickTextOffset=6)
        bottom.setHeight(26)

        self.hum_view = pg.ViewBox()
        plot_item.showAxis("right")
        plot_item.scene().addItem(self.hum_view)
        right = plot_item.getAxis("right")
        right.linkToView(self.hum_view)
        right.setPen(pg.mkPen("#1B3558"))
        right.setTextPen(pg.mkPen(C.MUTED))
        right.setWidth(52)
        right.setStyle(tickFont=QFont("Bahnschrift", 9), tickLength=-4, tickTextOffset=6)
        right.setLabel("湿度", units="%RH", color=C.TEAL, **{"font-size": "9pt"})
        right.enableAutoSIPrefix(False)
        self.hum_view.setXLink(plot_item.getViewBox())
        self.hum_view.setMouseEnabled(False, False)
        self.hum_view.setMenuEnabled(False)
        plot_item.getViewBox().sigResized.connect(self._sync_hum_view)

        now = time.time()
        plot_item.getViewBox().setXRange(now - 300, now, padding=0)
        plot_item.getViewBox().setYRange(15, 35, padding=0)
        self.hum_view.setYRange(30, 80, padding=0)

        self.temp_glow = plot_item.plot(
            [], [], pen=pg.mkPen(QColor(56, 189, 248, 34), width=7)
        )
        self.temp_curve = plot_item.plot([], [], pen=pg.mkPen(C.CYAN, width=2))
        self.hum_glow = pg.PlotDataItem(pen=pg.mkPen(QColor(45, 212, 191, 34), width=7))
        self.hum_curve = pg.PlotDataItem(pen=pg.mkPen(C.TEAL, width=2))
        self.hum_view.addItem(self.hum_glow)
        self.hum_view.addItem(self.hum_curve)

        self.vline = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(QColor(59, 130, 246, 110), width=1, style=Qt.DashLine),
        )
        plot_item.addItem(self.vline, ignoreBounds=True)
        self.vline.hide()
        self.temp_dot = pg.ScatterPlotItem(
            size=9, brush=pg.mkBrush(C.CYAN), pen=pg.mkPen(C.BG, width=2)
        )
        plot_item.addItem(self.temp_dot, ignoreBounds=True)
        self.temp_dot.hide()
        self.hum_dot = pg.ScatterPlotItem(
            size=9, brush=pg.mkBrush(C.TEAL), pen=pg.mkPen(C.BG, width=2)
        )
        self.hum_view.addItem(self.hum_dot)
        self.hum_dot.hide()

        self.latest_temp_dot = pg.ScatterPlotItem(
            size=7, brush=pg.mkBrush(C.CYAN), pen=pg.mkPen(C.BG, width=2)
        )
        plot_item.addItem(self.latest_temp_dot, ignoreBounds=True)
        self.latest_temp_dot.hide()
        self.latest_hum_dot = pg.ScatterPlotItem(
            size=7, brush=pg.mkBrush(C.TEAL), pen=pg.mkPen(C.BG, width=2)
        )
        self.hum_view.addItem(self.latest_hum_dot)
        self.latest_hum_dot.hide()

        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.plot.viewport().installEventFilter(self)
        QTimer.singleShot(0, self._sync_hum_view)

        self.chart_area = ChartArea(self.plot)
        root.addWidget(self.chart_area, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(2, 0, 2, 0)
        self.hover_label = QLabel("提示：在曲线上移动鼠标查看数值")
        self.hover_label.setObjectName("Hint")
        self.stats_label = QLabel("采样 0 · 帧率 —")
        self.stats_label.setObjectName("Hint")
        self.stats_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        footer.addWidget(self.hover_label)
        footer.addStretch(1)
        footer.addWidget(self.stats_label)
        root.addLayout(footer)

    # ------------------------------------------------------------------
    def set_series_visible(self, temp_visible: bool, hum_visible: bool):
        self._temp_visible = bool(temp_visible)
        self._hum_visible = bool(hum_visible)
        self.temp_curve.setVisible(temp_visible)
        self.temp_glow.setVisible(temp_visible)
        self.hum_curve.setVisible(hum_visible)
        self.hum_glow.setVisible(hum_visible)
        self.latest_temp_dot.setVisible(temp_visible and bool(self._chart_x))
        self.latest_hum_dot.setVisible(hum_visible and bool(self._chart_x))
        self._hide_crosshair()

    def set_paused(self, paused: bool):
        self._paused = paused
        self._hide_crosshair()

    def set_stats_text(self, text: str):
        self.stats_label.setText(text)

    def set_hover_text(self, text: str):
        self.hover_label.setText(text)

    def set_empty(self, text: str, visible: bool):
        self.chart_area.set_empty(text, visible)

    def clear(self):
        self.temp_curve.setData([], [])
        self.temp_glow.setData([], [])
        self.hum_curve.setData([], [])
        self.hum_glow.setData([], [])
        self.latest_temp_dot.hide()
        self.latest_hum_dot.hide()
        self._chart_x = []
        self._chart_temp = []
        self._chart_hum = []
        self._hide_crosshair()

    def set_samples(self, samples, window_sec: int, rate_text: str = "—"):
        if self._paused:
            return
        if not samples:
            self.clear()
            return

        now = time.time()
        if window_sec and window_sec > 0:
            start = now - window_sec
            visible = [sample for sample in samples if sample.ts >= start]
        else:
            visible = list(samples)
            start = visible[0].ts

        if not visible:
            self.clear()
            end = max(now, start + 2.0)
            self.plot.getPlotItem().getViewBox().setXRange(start, end, padding=0)
            self.chart_area.set_empty("当前时间窗内无数据\n可切换更长的窗口", True)
            self.stats_label.setText(f"采样 {len(samples)} · 帧率 {rate_text}")
            return

        x = [sample.ts for sample in visible]
        temps = [sample.temp for sample in visible]
        hums = [sample.hum for sample in visible]
        self._chart_x = x
        self._chart_temp = temps
        self._chart_hum = hums

        self.temp_curve.setData(x, temps, connect="finite")
        self.temp_glow.setData(x, temps, connect="finite")
        self.hum_curve.setData(x, hums, connect="finite")
        self.hum_glow.setData(x, hums, connect="finite")
        self.latest_temp_dot.setData([x[-1]], [temps[-1]])
        self.latest_hum_dot.setData([x[-1]], [hums[-1]])
        self.latest_temp_dot.setVisible(self._temp_visible)
        self.latest_hum_dot.setVisible(self._hum_visible)

        end = max(now, x[-1]) + 2.0
        if end - start < 2.0:
            end = start + 2.0
        self.plot.getPlotItem().getViewBox().setXRange(start, end, padding=0)

        temp_min, temp_max = min(temps), max(temps)
        if temp_max - temp_min < 1.0:
            middle = (temp_max + temp_min) / 2.0
            temp_min, temp_max = middle - 1.0, middle + 1.0
        else:
            pad = max(0.4, (temp_max - temp_min) * 0.12)
            temp_min -= pad
            temp_max += pad
        self.plot.getPlotItem().getViewBox().setYRange(temp_min, temp_max, padding=0)

        hum_min, hum_max = min(hums), max(hums)
        if hum_max - hum_min < 8.0:
            middle = (hum_max + hum_min) / 2.0
            hum_min, hum_max = middle - 5.0, middle + 5.0
        else:
            pad = max(1.5, (hum_max - hum_min) * 0.12)
            hum_min -= pad
            hum_max += pad
        hum_min = max(0.0, hum_min)
        hum_max = min(100.0, hum_max)
        if hum_max - hum_min < 2.0:
            hum_max = min(100.0, hum_min + 2.0)
        self.hum_view.setYRange(hum_min, hum_max, padding=0)

        self.chart_area.set_empty("", False)
        self.stats_label.setText(f"采样 {len(samples)} · 帧率 {rate_text}")
        self._last_visible_count = len(visible)
        self._sync_hum_view()

    # ------------------------------------------------------------------
    def _sync_hum_view(self, *_):
        try:
            self.hum_view.setGeometry(
                self.plot.getPlotItem().getViewBox().sceneBoundingRect()
            )
            self.hum_view.linkedViewChanged(
                self.plot.getPlotItem().getViewBox(), self.hum_view.XAxis
            )
        except Exception:
            pass

    def _split_visible(self, cursor_x: float) -> tuple[int, int] | None:
        if not self._chart_x:
            return None
        index = bisect_left(self._chart_x, cursor_x)
        if index >= len(self._chart_x):
            index = len(self._chart_x) - 1
        if index > 0:
            before = abs(self._chart_x[index - 1] - cursor_x)
            after = abs(self._chart_x[index] - cursor_x)
            if before < after:
                index -= 1
        return index, 0

    def _on_mouse_moved(self, pos):
        if not self._chart_x:
            return
        view_box = self.plot.getPlotItem().getViewBox()
        if not view_box.sceneBoundingRect().contains(pos):
            return
        cursor_x = view_box.mapSceneToView(pos).x()
        result = self._split_visible(cursor_x)
        if result is None:
            return
        index, _ = result
        timestamp = self._chart_x[index]
        temp = self._chart_temp[index]
        hum = self._chart_hum[index]
        self.vline.setPos(timestamp)
        self.vline.show()
        if self.temp_curve.isVisible():
            self.temp_dot.setData([timestamp], [temp])
            self.temp_dot.show()
        else:
            self.temp_dot.hide()
        if self.hum_curve.isVisible():
            self.hum_dot.setData([timestamp], [hum])
            self.hum_dot.show()
        else:
            self.hum_dot.hide()
        self.hover_label.setText(
            f"{datetime.fromtimestamp(timestamp):%H:%M:%S}   "
            f"{temp:.2f} ℃   {hum:.2f} %RH"
        )

    def _hide_crosshair(self):
        self.vline.hide()
        self.temp_dot.hide()
        self.hum_dot.hide()
        if self._paused:
            self.hover_label.setText("曲线已暂停（数据仍在后台接收）")
        elif not self.temp_curve.isVisible() and not self.hum_curve.isVisible():
            self.hover_label.setText("两条曲线均已隐藏")
        else:
            self.hover_label.setText("提示：在曲线上移动鼠标查看数值")

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.plot.viewport() and event.type() == QEvent.Leave:
            self._hide_crosshair()
        return super().eventFilter(obj, event)

    def sizeHint(self):  # noqa: N802
        return QSize(760, 200)

    def minimumSizeHint(self):  # noqa: N802
        return QSize(420, 176)
