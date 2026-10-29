# -*- coding: utf-8 -*-
"""2.4G LoRa 温湿度模块页面。"""

from __future__ import annotations

import csv
import html
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.protocol import Frame, build_frame
from core.serial_worker import SerialWorker
from core.settings import AppSettings
from core.theme import APP_DIR, C, q_rgba
from core.widgets import (
    LevelBar,
    MetricCard,
    SectionCard,
    SegmentedTabs,
    StatTile,
    StatusPill,
)
from modules.lora.chart import LoraChart
from modules.lora.protocol import (
    CMD_ACK,
    CMD_ERR_CMD,
    CMD_ERR_CRC,
    CMD_LOCAL,
    CMD_NAMES,
    CMD_REMOTE,
    CMD_STACK_OVERFLOW,
    CMD_SX_FAIL,
    SOURCE_NAMES,
    Sample,
    decode_local,
    decode_remote,
    hdc_status_text,
    rx_status_text,
    sx_status_text,
)


def fmt_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / 1024 / 1024:.2f} MB"


def fmt_time(ts: float | None = None, with_ms: bool = False) -> str:
    pattern = "%H:%M:%S.%f" if with_ms else "%H:%M:%S"
    text = datetime.fromtimestamp(ts if ts is not None else time.time()).strftime(pattern)
    return text[:-3] if with_ms else text


class LoraPage(QWidget):
    title = "2.4G 温湿度"
    subtitle = "SX1280 + HDC1080 · 实时曲线、链路质量与串口助手"
    icon_name = "lora"

    connection_changed = Signal(bool)
    MAX_TABLE_ROWS = 3

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("Page")
        self.worker: SerialWorker | None = None
        self.samples: deque[Sample] = deque(maxlen=20000)
        self.temp_history: deque[float] = deque(maxlen=60)
        self.hum_history: deque[float] = deque(maxlen=60)
        self.current_source: str | None = None
        self.last_seq: int | None = None
        self.lost_frames = 0
        self.valid_samples = 0
        self.total_frames = 0
        self.count_18 = 0
        self.count_19 = 0
        self.crc_errors = 0
        self.alert_count = 0
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.valid_times: deque[float] = deque(maxlen=30)
        self.last_valid_ts: float | None = None
        self.last_frame_ts: float | None = None
        self.chart_window_sec = 300
        self.chart_paused = False
        self.log_paused = False
        self._banner_kind: str | None = None
        self._visible = False
        self._built_frame: bytes | None = None
        self._last_export_dir = str(APP_DIR)

        self._build_ui()
        self.refresh_ports()
        self._restore_settings()
        self._apply_connection_state("off")
        self._set_source_pill(None)
        self._setup_timers()
        self._setup_shortcuts()
        self._update_frame_preview()
        self._tick_clock()
        self._refresh_counters()
        self._log_line("2.4G 模块已就绪，等待串口连接。", "info")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.tabs = SegmentedTabs()
        self.tabs.add_tab("数据监控", "monitor")
        self.tabs.add_tab("串口通信", "comm")
        self.tabs.add_stretch()
        self.help_btn = QPushButton("协议说明")
        self.help_btn.setObjectName("Ghost")
        self.help_btn.setCursor(Qt.PointingHandCursor)
        self.help_btn.clicked.connect(self.show_protocol_dialog)
        self.tabs.add_action(self.help_btn)
        self.tabs.changed.connect(self.switch_page)
        root.addWidget(self.tabs)

        root.addWidget(self._build_serial_bar())

        self.pages = QStackedWidget()
        self.monitor_page = self._build_monitor_page()
        self.monitor_page.setMinimumHeight(580)
        self.monitor_scroll = self._wrap_scroll(self.monitor_page)
        self.serial_page = self._build_serial_page()
        self.serial_page.setMinimumHeight(580)
        self.serial_scroll = self._wrap_scroll(self.serial_page)
        self.pages.addWidget(self.monitor_scroll)
        self.pages.addWidget(self.serial_scroll)
        root.addWidget(self.pages, 1)

    def _wrap_scroll(self, page: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    def switch_page(self, index: int):
        index = max(0, min(1, int(index)))
        self.pages.setCurrentIndex(index)
        self.tabs.set_current(index)
        self.settings.set("lora/tab", index)
        if self._visible:
            if index == 0:
                self.chart_timer.start()
                self._update_chart()
            else:
                self.chart_timer.stop()

    def on_shown(self):
        self._visible = True
        self.stats_timer.start()
        self.clock_timer.start()
        if self.pages.currentIndex() == 0:
            self.chart_timer.start()
        self._tick_clock()
        self._refresh_counters()
        self._update_chart()

    def on_hidden(self):
        self._visible = False
        self.chart_timer.stop()
        self.clock_timer.stop()
        self.stats_timer.stop()

    @property
    def is_connected(self) -> bool:
        return self.worker is not None

    def _build_serial_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("SerialBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 8, 12, 8)
        layout.setSpacing(6)

        def bar_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("BarLabel")
            return label

        layout.addWidget(bar_label("串口"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(140)
        self.port_combo.setMaximumWidth(210)
        self.port_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.port_combo.setMinimumContentsLength(10)
        layout.addWidget(self.port_combo)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setObjectName("Ghost")
        self.refresh_btn.setToolTip("重新扫描串口")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        layout.addWidget(self.refresh_btn)

        layout.addSpacing(3)
        layout.addWidget(bar_label("波特率"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(
            ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
        )
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setFixedWidth(94)
        layout.addWidget(self.baud_combo)

        layout.addWidget(bar_label("数据位"))
        self.data_combo = QComboBox()
        self.data_combo.addItems(["5", "6", "7", "8"])
        self.data_combo.setCurrentText("8")
        self.data_combo.setFixedWidth(58)
        layout.addWidget(self.data_combo)

        layout.addWidget(bar_label("停止位"))
        self.stop_combo = QComboBox()
        self.stop_combo.addItems(["1", "1.5", "2"])
        self.stop_combo.setCurrentText("1")
        self.stop_combo.setFixedWidth(60)
        layout.addWidget(self.stop_combo)

        layout.addWidget(bar_label("校验位"))
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["无", "奇", "偶"])
        self.parity_combo.setFixedWidth(62)
        layout.addWidget(self.parity_combo)

        layout.addStretch(1)
        self.serial_summary = QLabel("RX 0 B · TX 0 B")
        self.serial_summary.setObjectName("Hint")
        self.serial_summary.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.serial_summary)
        layout.addSpacing(4)

        self.status_label = StatusPill("未连接")
        layout.addWidget(self.status_label)

        self.open_btn = QPushButton("打开串口")
        self.open_btn.setObjectName("Primary")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.setFixedWidth(104)
        self.open_btn.clicked.connect(self.toggle_serial)
        layout.addWidget(self.open_btn)

        self.serial_controls = [
            self.port_combo,
            self.refresh_btn,
            self.baud_combo,
            self.data_combo,
            self.stop_combo,
            self.parity_combo,
        ]
        return bar

    def _build_monitor_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._build_alert_banner())

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.card_temp = MetricCard("温度", "℃", C.CYAN, "spark")
        self.card_hum = MetricCard("湿度", "%RH", C.TEAL, "spark")
        self.card_rssi = MetricCard("信号强度", "dBm", C.VIOLET, "bar")
        self.card_loss = MetricCard("丢包率", "%", C.AMBER, "bar")
        for card in (self.card_temp, self.card_hum, self.card_rssi, self.card_loss):
            metrics.addWidget(card, 1)
        layout.addLayout(metrics)

        middle = QHBoxLayout()
        middle.setSpacing(12)
        middle.addWidget(self._build_chart_card(), 1)
        middle.addWidget(self._build_link_card())
        layout.addLayout(middle, 1)

        layout.addWidget(self._build_recent_card())
        return page

    def _build_alert_banner(self) -> QFrame:
        self.alert_frame = QFrame()
        self.alert_frame.setObjectName("Alert")
        self.alert_frame.setVisible(False)
        layout = QHBoxLayout(self.alert_frame)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(10)
        self.alert_icon = QLabel("!")
        self.alert_icon.setObjectName("AlertIcon")
        self.alert_icon.setFixedSize(22, 22)
        self.alert_icon.setAlignment(Qt.AlignCenter)
        self.alert_text = QLabel("")
        self.alert_text.setObjectName("AlertText")
        self.alert_text.setWordWrap(True)
        self.alert_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        close_btn = QPushButton("×")
        close_btn.setObjectName("Ghost")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.hide_alert)
        layout.addWidget(self.alert_icon)
        layout.addWidget(self.alert_text, 1)
        layout.addWidget(close_btn)
        return self.alert_frame

    def _build_chart_card(self) -> SectionCard:
        card = SectionCard("温湿度实时曲线", "温度 ℃ · 湿度 %RH")
        card.setMinimumHeight(280)
        self.chart_card = card

        self.temp_chip = QPushButton("● 温度")
        self.temp_chip.setObjectName("Chip")
        self.temp_chip.setProperty("caption", "temp")
        self.temp_chip.setCheckable(True)
        self.temp_chip.setChecked(True)
        self.temp_chip.setCursor(Qt.PointingHandCursor)
        self.temp_chip.clicked.connect(self._on_series_toggle)

        self.hum_chip = QPushButton("● 湿度")
        self.hum_chip.setObjectName("Chip")
        self.hum_chip.setProperty("caption", "hum")
        self.hum_chip.setCheckable(True)
        self.hum_chip.setChecked(True)
        self.hum_chip.setCursor(Qt.PointingHandCursor)
        self.hum_chip.clicked.connect(self._on_series_toggle)

        self.window_combo = QComboBox()
        self.window_combo.setFixedWidth(100)
        for text, seconds in (
            ("1 分钟", 60),
            ("5 分钟", 300),
            ("10 分钟", 600),
            ("30 分钟", 1800),
            ("全部", 0),
        ):
            self.window_combo.addItem(text, seconds)
        self.window_combo.setCurrentIndex(1)
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setObjectName("Chip")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.toggled.connect(self.toggle_chart_pause)

        self.export_btn = QPushButton("导出 CSV")
        self.export_btn.setObjectName("Ghost")
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.clicked.connect(self.export_csv)

        card.header.addWidget(self.temp_chip)
        card.header.addWidget(self.hum_chip)
        card.header.addSpacing(4)
        card.header.addWidget(self.window_combo)
        card.header.addWidget(self.pause_btn)
        card.header.addWidget(self.export_btn)

        card.body.setSpacing(0)
        self.chart = LoraChart()
        card.body.addWidget(self.chart, 1)
        return card

    def _build_link_card(self) -> SectionCard:
        card = SectionCard("链路质量", "RSSI / SNR / 丢包")
        card.setFixedWidth(330)
        card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        body = card.body
        body.setSpacing(7)

        self.rssi_value, self.rssi_bar = self._add_meter(body, "信号强度 RSSI", C.VIOLET)
        self.snr_value, self.snr_bar = self._add_meter(body, "信噪比 SNR", C.CYAN)
        self.loss_value, self.loss_bar = self._add_meter(body, "丢包率", C.AMBER)

        line = QFrame()
        line.setObjectName("HLine")
        body.addWidget(line)
        body.addSpacing(2)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self.rate_value = self._add_kv_row(grid, 0, "帧率")
        self.source_value = self._add_kv_row(grid, 1, "数据源")
        self.last_update_value = self._add_kv_row(grid, 2, "最后更新")
        self.source_value.setWordWrap(True)
        body.addLayout(grid)
        body.addStretch(1)
        return card

    def _add_meter(self, body: QVBoxLayout, title: str, color: str):
        row = QHBoxLayout()
        row.setSpacing(8)
        key = QLabel(title)
        key.setObjectName("KvKey")
        value = QLabel("—")
        value.setObjectName("KvVal")
        value.setMinimumWidth(72)
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(key)
        row.addStretch(1)
        row.addWidget(value)
        body.addLayout(row)
        bar = LevelBar(color)
        body.addWidget(bar)
        return value, bar

    def _add_kv_row(self, grid: QGridLayout, row: int, title: str) -> QLabel:
        key = QLabel(title)
        key.setObjectName("KvKey")
        value = QLabel("—")
        value.setObjectName("KvVal")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(key, row, 0)
        grid.addWidget(value, row, 1)
        grid.setColumnStretch(1, 1)
        return value

    def _build_recent_card(self) -> SectionCard:
        card = SectionCard("最近数据")
        card.setFixedHeight(161)
        self.recent_table = QTableWidget(0, 8)
        self.recent_table.setHorizontalHeaderLabels(
            ["时间", "来源", "温度 ℃", "湿度 %RH", "RSSI dBm", "SNR dB", "序号", "状态"]
        )
        self.recent_table.setShowGrid(False)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.verticalHeader().setDefaultSectionSize(21)
        self.recent_table.horizontalHeader().setHighlightSections(False)
        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recent_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.recent_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recent_table.setFocusPolicy(Qt.NoFocus)
        self.recent_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.recent_table.setFixedHeight(94)
        card.body.addWidget(self.recent_table)
        return card

    def _build_serial_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(self._build_log_card(), 1)
        left.addWidget(self._build_send_card())
        layout.addLayout(left, 1)

        right = QWidget()
        right.setFixedWidth(330)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(self._build_stats_card())
        right_layout.addWidget(self._build_frame_card())
        right_layout.addStretch(1)
        layout.addWidget(right)
        return page

    def _build_log_card(self) -> SectionCard:
        card = SectionCard("接收日志", "原始字节 + 协议帧解析")
        self.hex_chk = QCheckBox("HEX 显示")
        self.hex_chk.setChecked(True)
        self.ts_chk = QCheckBox("时间戳")
        self.ts_chk.setChecked(True)
        self.autoscroll_chk = QCheckBox("自动滚动")
        self.autoscroll_chk.setChecked(True)
        self.log_pause_btn = QPushButton("暂停")
        self.log_pause_btn.setObjectName("Chip")
        self.log_pause_btn.setCheckable(True)
        self.log_pause_btn.toggled.connect(self.toggle_log_pause)
        self.log_clear_btn = QPushButton("清空")
        self.log_clear_btn.setObjectName("Ghost")
        self.log_clear_btn.clicked.connect(self.clear_log)
        self.log_save_btn = QPushButton("保存")
        self.log_save_btn.setObjectName("Ghost")
        self.log_save_btn.clicked.connect(self.save_log)

        card.header.addWidget(self.hex_chk)
        card.header.addWidget(self.ts_chk)
        card.header.addWidget(self.autoscroll_chk)
        card.header.addSpacing(4)
        card.header.addWidget(self.log_pause_btn)
        card.header.addWidget(self.log_clear_btn)
        card.header.addWidget(self.log_save_btn)

        self.rx_log = QPlainTextEdit()
        self.rx_log.setReadOnly(True)
        self.rx_log.setUndoRedoEnabled(False)
        self.rx_log.setFont(QFont("Consolas", 9))
        self.rx_log.document().setMaximumBlockCount(4000)
        self.rx_log.setMinimumHeight(220)
        card.body.addWidget(self.rx_log, 1)

        footer = QHBoxLayout()
        self.log_summary = QLabel("RX 0 B · TX 0 B · 0 帧")
        self.log_summary.setObjectName("Hint")
        hint = QLabel("Ctrl+Enter 发送 · 最多保留 4000 行")
        hint.setObjectName("Hint")
        footer.addWidget(self.log_summary)
        footer.addStretch(1)
        footer.addWidget(hint)
        card.body.addLayout(footer)
        return card

    def _build_send_card(self) -> SectionCard:
        card = SectionCard("发送")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.tx_mode = QComboBox()
        self.tx_mode.addItems(["ASCII", "HEX"])
        self.tx_mode.setFixedWidth(84)
        self.tx_mode.currentIndexChanged.connect(self._on_tx_mode_changed)
        self.tx_ending = QComboBox()
        self.tx_ending.addItems(["无换行", "CRLF (\\r\\n)", "LF (\\n)", "CR (\\r)"])
        self.tx_ending.setFixedWidth(120)
        self.periodic_chk = QCheckBox("周期发送")
        self.periodic_chk.toggled.connect(self.toggle_periodic_send)
        self.periodic_spin = QSpinBox()
        self.periodic_spin.setRange(100, 60000)
        self.periodic_spin.setValue(1000)
        self.periodic_spin.setSuffix(" ms")
        self.periodic_spin.setFixedWidth(96)
        self.periodic_spin.valueChanged.connect(self._on_periodic_interval)
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("Primary")
        self.send_btn.setFixedWidth(82)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(lambda: self.send_current_text(silent=False))

        row.addWidget(self.tx_mode)
        row.addWidget(self.tx_ending)
        row.addStretch(1)
        row.addWidget(self.periodic_chk)
        row.addWidget(self.periodic_spin)
        row.addWidget(self.send_btn)
        card.body.addLayout(row)

        self.tx_input = QPlainTextEdit()
        self.tx_input.setFixedHeight(58)
        self.tx_input.setPlaceholderText("输入要发送的内容，HEX 模式示例：5A 19 0B 00 ...")
        self.tx_input.setTabChangesFocus(True)
        card.body.addWidget(self.tx_input)
        return card

    def _build_stats_card(self) -> SectionCard:
        card = SectionCard("通信统计", "本次连接累计")
        reset_btn = QPushButton("重置")
        reset_btn.setObjectName("Ghost")
        reset_btn.clicked.connect(self.reset_stats)
        card.header.addWidget(reset_btn)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self.stat_tiles: dict[str, StatTile] = {}
        specs = [
            ("rx", "接收字节"),
            ("tx", "发送字节"),
            ("valid", "有效帧"),
            ("remote", "0x19 帧"),
            ("local", "0x18 帧"),
            ("crc", "CRC 错误"),
            ("alert", "告警帧"),
            ("rate", "帧率"),
        ]
        for index, (key, title) in enumerate(specs):
            tile = StatTile(title)
            self.stat_tiles[key] = tile
            grid.addWidget(tile, index // 2, index % 2)
        card.body.addLayout(grid)
        return card

    def _build_frame_card(self) -> SectionCard:
        card = SectionCard("协议帧构造", "CRC8 自动计算")
        row = QHBoxLayout()
        row.setSpacing(7)
        cmd_key = QLabel("CMD")
        cmd_key.setObjectName("KvKey")
        self.cmd_input = QLineEdit("19")
        self.cmd_input.setFixedWidth(58)
        self.cmd_input.setMaxLength(4)
        self.cmd_input.setPlaceholderText("19")
        data_key = QLabel("DATA")
        data_key.setObjectName("KvKey")
        self.data_input = QLineEdit()
        self.data_input.setPlaceholderText("00 00 00 ...")
        row.addWidget(cmd_key)
        row.addWidget(self.cmd_input)
        row.addWidget(data_key)
        row.addWidget(self.data_input, 1)
        card.body.addLayout(row)

        self.frame_preview = QLabel("—")
        self.frame_preview.setObjectName("FramePreview")
        self.frame_preview.setWordWrap(True)
        self.frame_preview.setMinimumHeight(42)
        self.frame_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card.body.addWidget(self.frame_preview)

        bottom = QHBoxLayout()
        self.frame_crc = QLabel("CRC8 = —")
        self.frame_crc.setObjectName("Hint")
        self.frame_send_btn = QPushButton("发送该帧")
        self.frame_send_btn.setObjectName("Primary")
        self.frame_send_btn.clicked.connect(self.send_built_frame)
        bottom.addWidget(self.frame_crc)
        bottom.addStretch(1)
        bottom.addWidget(self.frame_send_btn)
        card.body.addLayout(bottom)

        note = QLabel("固件当前只主动上报，未注册上位机下行命令；此构造器用于链路与协议自测。")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        card.body.addWidget(note)

        self.cmd_input.textChanged.connect(self._schedule_frame_preview)
        self.data_input.textChanged.connect(self._schedule_frame_preview)
        return card

    # ------------------------------------------------------------------
    # 定时器 / 快捷键 / 设置
    # ------------------------------------------------------------------
    def _setup_timers(self):
        self.chart_timer = QTimer(self)
        self.chart_timer.setInterval(200)
        self.chart_timer.timeout.connect(self._update_chart)

        self.stats_timer = QTimer(self)
        self.stats_timer.setInterval(500)
        self.stats_timer.timeout.connect(self._refresh_counters)

        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._tick_clock)

        self.periodic_timer = QTimer(self)
        self.periodic_timer.timeout.connect(lambda: self.send_current_text(silent=True))

        self.alert_timer = QTimer(self)
        self.alert_timer.setSingleShot(True)
        self.alert_timer.timeout.connect(self.hide_alert)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(140)
        self.preview_timer.timeout.connect(self._update_frame_preview)

    def _setup_shortcuts(self):
        for sequence, handler in (
            ("Ctrl+Return", lambda: self.send_current_text(silent=False)),
            ("Ctrl+Enter", lambda: self.send_current_text(silent=False)),
            ("Ctrl+O", self.toggle_serial),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)

    def _restore_settings(self):
        port = self.settings.get("lora/port", "")
        if port:
            index = self.port_combo.findData(port)
            if index < 0:
                index = self.port_combo.findText(str(port))
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        baud = self.settings.get("lora/baud", "115200")
        if self.baud_combo.findText(str(baud)) >= 0:
            self.baud_combo.setCurrentText(str(baud))
        window = self.settings.get("lora/window", 300)
        try:
            index = self.window_combo.findData(int(window))
            if index >= 0:
                self.window_combo.setCurrentIndex(index)
                self.chart_window_sec = int(window)
        except Exception:
            pass
        self.hex_chk.setChecked(self.settings.get("lora/log_hex", True, bool))
        self.ts_chk.setChecked(self.settings.get("lora/log_ts", True, bool))
        self.autoscroll_chk.setChecked(self.settings.get("lora/log_autoscroll", True, bool))
        self._last_export_dir = self.settings.get("lora/export_dir", str(APP_DIR))
        tab = self.settings.get("lora/tab", 0)
        try:
            tab = int(tab)
        except Exception:
            tab = 0
        self.switch_page(tab)

    def save_settings(self):
        self.settings.set("lora/tab", self.pages.currentIndex())
        port = self.port_combo.currentData() or self.port_combo.currentText()
        if port:
            self.settings.set("lora/port", port)
        self.settings.set("lora/baud", self.baud_combo.currentText())
        self.settings.set("lora/window", self.window_combo.currentData())
        self.settings.set("lora/log_hex", self.hex_chk.isChecked())
        self.settings.set("lora/log_ts", self.ts_chk.isChecked())
        self.settings.set("lora/log_autoscroll", self.autoscroll_chk.isChecked())
        self.settings.set("lora/export_dir", self._last_export_dir)

    # ------------------------------------------------------------------
    # 串口
    # ------------------------------------------------------------------
    def refresh_ports(self, *_):
        if self.worker is not None:
            return
        current = self.port_combo.currentData()
        try:
            import serial.tools.list_ports

            ports = sorted(serial.tools.list_ports.comports(), key=lambda p: p.device)
        except Exception:
            ports = []
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        for port in ports:
            description = (port.description or "").strip()
            self.port_combo.addItem(port.device, port.device)
            if description and description.lower() not in ("n/a", "none"):
                self.port_combo.setItemData(
                    self.port_combo.count() - 1, description, Qt.ToolTipRole
                )
        if not ports:
            self.port_combo.addItem("未检测到串口", None)
        else:
            index = self.port_combo.findData(current) if current else -1
            self.port_combo.setCurrentIndex(index if index >= 0 else 0)
        self.port_combo.blockSignals(False)

    def _serial_desc(self) -> str:
        parity = {"无": "N", "奇": "O", "偶": "E"}.get(
            self.parity_combo.currentText(), "N"
        )
        stop = self.stop_combo.currentText()
        if stop.endswith(".0"):
            stop = stop[:-2]
        return f"{self.baud_combo.currentText()} {self.data_combo.currentText()}{parity}{stop}"

    def toggle_serial(self, *_):
        if self.worker is not None:
            self.close_serial()
        else:
            self.open_serial()

    def open_serial(self):
        import serial

        if self.worker is not None:
            return
        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "提示", "未检测到可用串口。\n请检查 USB 连接后点击“刷新”。")
            return
        try:
            baud = int(self.baud_combo.currentText())
            bytesize = int(self.data_combo.currentText())
            stopbits = float(self.stop_combo.currentText())
        except ValueError:
            QMessageBox.warning(self, "提示", "串口参数格式不正确。")
            return
        parity = {
            "无": serial.PARITY_NONE,
            "奇": serial.PARITY_ODD,
            "偶": serial.PARITY_EVEN,
        }.get(self.parity_combo.currentText(), serial.PARITY_NONE)

        worker = SerialWorker(str(port), baud, bytesize, stopbits, parity, self)
        self.worker = worker
        worker.opened.connect(self._on_serial_opened)
        worker.closed.connect(self._on_serial_closed)
        worker.error_occurred.connect(self._on_serial_error)
        worker.raw_data.connect(self._on_raw_data)
        worker.frames_received.connect(self._on_frames)
        worker.crc_error.connect(self._on_crc_error)
        self._apply_connection_state("opening")
        self._log_line(f"正在打开串口 {port}（{self._serial_desc()}）…", "info")
        worker.start()

    def _on_serial_opened(self, success: bool, message: str):
        worker = self.worker
        if worker is None:
            return
        port = str(self.port_combo.currentData() or "")
        if success:
            self._apply_connection_state("on")
            self._log_line(f"串口 {port} 已打开（{self._serial_desc()}）。", "ok")
            self.connection_changed.emit(True)
            if not self.samples:
                self.chart.set_empty(self._empty_text(), True)
        else:
            self.worker = None
            worker.wait(400)
            self._apply_connection_state("error")
            self._log_line(f"打开串口失败：{message}", "error")
            QMessageBox.critical(self, "打开串口失败", f"无法打开 {port or '串口'}：\n{message}")
            if not self.samples:
                self.chart.set_empty(self._empty_text(), True)

    def _on_serial_closed(self):
        worker = self.worker
        if worker is None:
            return
        self.worker = None
        worker.wait(400)
        self._stop_periodic_send()
        self._apply_connection_state("off")
        self._log_line("串口连接已关闭。", "info")
        self.connection_changed.emit(False)
        if self._banner_kind == "data":
            self.hide_alert()
        if not self.samples:
            self.chart.set_empty(self._empty_text(), True)

    def _on_serial_error(self, message: str):
        self._log_line(f"串口异常：{message}", "error")
        self.show_alert(f"串口异常：{message}", "error", 8000)

    def close_serial(self):
        worker = self.worker
        if worker is None:
            return
        self.worker = None
        self._stop_periodic_send()
        self._apply_connection_state("off")
        self._log_line("正在关闭串口…", "info")
        worker.stop()
        worker.deleteLater()
        self._log_line("串口已关闭。", "info")
        self.connection_changed.emit(False)
        if not self.samples:
            self.chart.set_empty(self._empty_text(), True)

    def _apply_connection_state(self, state: str):
        connected = state == "on"
        opening = state == "opening"
        for widget in self.serial_controls:
            widget.setEnabled(not connected and not opening)
        self.open_btn.setEnabled(not opening)
        self.open_btn.setText("关闭串口" if connected else ("打开中…" if opening else "打开串口"))
        if connected:
            self.status_label.set_state("已连接", C.GREEN)
        elif opening:
            self.status_label.set_state("打开中…", C.AMBER)
        elif state == "error":
            self.status_label.set_state("打开失败", C.RED)
        else:
            self.status_label.set_state("未连接", C.RED)

    def _stop_periodic_send(self):
        self.periodic_timer.stop()
        self._set_periodic_check(False)

    def _set_periodic_check(self, checked: bool):
        if self.periodic_chk.isChecked() == checked:
            return
        self.periodic_chk.blockSignals(True)
        self.periodic_chk.setChecked(checked)
        self.periodic_chk.blockSignals(False)

    def _on_periodic_interval(self, value: int):
        if self.periodic_timer.isActive():
            self.periodic_timer.setInterval(value)

    def toggle_periodic_send(self, checked: bool):
        if not checked:
            self.periodic_timer.stop()
            if self.worker is not None:
                self._log_line("周期发送已停止。", "info")
            return
        if self.worker is None:
            self._set_periodic_check(False)
            QMessageBox.warning(self, "提示", "请先打开串口。")
            return
        if self._compose_tx_bytes(show_error=True) is None:
            self._set_periodic_check(False)
            return
        self.periodic_timer.start(self.periodic_spin.value())
        self._log_line(f"周期发送已开启（{self.periodic_spin.value()} ms）。", "info")

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------
    def _on_raw_data(self, data: bytes):
        self.rx_bytes += len(data)
        if not self.log_paused:
            self._append_raw(data)

    def _on_frames(self, frames):
        now = time.time()
        for frame in frames:
            self.total_frames += 1
            self._ingest_frame(frame, now)

    def _on_crc_error(self, bad_frame: bytes):
        self.crc_errors += 1
        if self.crc_errors == 1 or self.crc_errors % 20 == 0:
            preview = " ".join(f"{byte:02X}" for byte in bad_frame[:48])
            if len(bad_frame) > 48:
                preview += " …"
            self._log_line(f"CRC8 校验失败（累计 {self.crc_errors} 次）：{preview}", "error")
        if self.crc_errors == 1:
            self.show_alert("检测到 CRC 校验失败，请检查波特率、接线或信号干扰。", "warn", 6000)

    def _ingest_frame(self, frame: Frame, ts: float | None = None):
        ts = time.time() if ts is None else ts
        cmd = frame.cmd
        payload = frame.payload

        if cmd == CMD_REMOTE:
            self.count_19 += 1
            if len(payload) != 11:
                self._log_frame(frame, f"0x19 长度异常：{len(payload)} 字节（应为 11）", "warn")
                self.show_alert("0x19 帧长度异常，请核对固件版本。", "warn", 0)
                return
            telemetry = decode_remote(payload)
            self._register_source("RX")
            self._update_radio_quality(telemetry.rssi, telemetry.snr)
            if telemetry.status != 0:
                self._log_frame(
                    frame, f"0x19 接收端 收包异常 status={telemetry.status}", "warn"
                )
                self.show_alert(
                    f"收包异常：{rx_status_text(telemetry.status)}（{telemetry.status}）",
                    "warn",
                    0,
                )
                return
            if telemetry.remote_status != 0:
                self._log_frame(
                    frame,
                    f"0x19 接收端 remote_status={telemetry.remote_status}",
                    "warn",
                )
                self.show_alert(
                    f"发射端测量失败：{hdc_status_text(telemetry.remote_status)}"
                    f"（{telemetry.remote_status}）",
                    "warn",
                    0,
                )
                return
            self._log_frame(
                frame,
                f"0x19 接收端  温 {telemetry.temp:.2f}℃  湿 {telemetry.hum:.2f}%RH  "
                f"RSSI {telemetry.rssi} dBm  SNR {telemetry.snr} dB  SEQ {telemetry.seq}",
                "frame",
            )
            self._add_sample(
                ts,
                telemetry.temp,
                telemetry.hum,
                telemetry.rssi,
                telemetry.snr,
                telemetry.seq,
                "RX",
            )
            if self._banner_kind == "data":
                self.hide_alert()

        elif cmd == CMD_LOCAL:
            self.count_18 += 1
            if len(payload) != 7:
                self._log_frame(frame, f"0x18 长度异常：{len(payload)} 字节（应为 7）", "warn")
                self.show_alert("0x18 帧长度异常，请核对固件版本。", "warn", 0)
                return
            telemetry = decode_local(payload)
            self._register_source("TX")
            self._update_radio_quality(None, None)
            if telemetry.status != 0:
                self._log_frame(frame, f"0x18 发射端 status={telemetry.status}", "warn")
                self.show_alert(
                    f"HDC1080 测量失败：{hdc_status_text(telemetry.status)}"
                    f"（{telemetry.status}）",
                    "warn",
                    0,
                )
                return
            self._log_frame(
                frame,
                f"0x18 发射端  温 {telemetry.temp:.2f}℃  湿 {telemetry.hum:.2f}%RH  "
                f"SEQ {telemetry.seq}",
                "frame",
            )
            self._add_sample(
                ts, telemetry.temp, telemetry.hum, None, None, telemetry.seq, "TX"
            )
            if self._banner_kind == "data":
                self.hide_alert()

        elif cmd == CMD_STACK_OVERFLOW:
            self.alert_count += 1
            name = payload.decode("ascii", "replace")
            self._log_frame(frame, f"0xE0 任务栈溢出：{name}", "error")
            self.show_alert(f"检测到 FreeRTOS 任务栈溢出：{name}", "error", 15000)

        elif cmd == CMD_SX_FAIL:
            self.alert_count += 1
            if payload:
                code = payload[0] - 256 if payload[0] >= 128 else payload[0]
                detail = f"{sx_status_text(code)}（{code}）"
            else:
                detail = "无返回码"
            self._log_frame(frame, f"0xE1 SX1280 初始化失败：{detail}", "error")
            self.show_alert(f"SX1280 初始化失败：{detail}", "error", 15000)

        elif cmd in (CMD_ACK, CMD_ERR_CRC, CMD_ERR_CMD):
            self._log_frame(frame, f"0x{cmd:02X} 设备应答：{CMD_NAMES[cmd]}", "info")

        else:
            data_text = payload.hex(" ").upper()
            if len(data_text) > 90:
                data_text = data_text[:90] + " …"
            self._log_frame(
                frame,
                f"0x{cmd:02X} 未知命令  LEN={len(payload)}  DATA={data_text}",
                "warn",
            )

    def _register_source(self, source: str):
        if self.current_source == source:
            return
        previous = self.current_source
        self.current_source = source
        cmd = CMD_REMOTE if source == "RX" else CMD_LOCAL
        self.source_value.setText(f"{SOURCE_NAMES[source]} · 0x{cmd:02X}")
        self._set_source_pill(source)
        if previous is not None:
            self.samples.clear()
            self.temp_history.clear()
            self.hum_history.clear()
            self.recent_table.setRowCount(0)
            self.lost_frames = 0
            self.valid_samples = 0
            self.valid_times.clear()
            self.last_seq = None
            self.last_valid_ts = None
            self.chart.clear()
            self.chart.set_empty("等待数据…", True)
            self.card_temp.set_value("—", "等待数据", badge="")
            self.card_hum.set_value("—", "等待数据", badge="")
            self.card_temp.set_spark([])
            self.card_hum.set_spark([])
            self.card_loss.set_value("0.0", "接收 0 帧 · CRC 错 0", badge="")
            self.card_loss.set_ratio(0)
            self.loss_value.setText("0.00 %")
            self.loss_bar.set_ratio(0)
            self.rate_value.setText("—")
            self.last_update_value.setText("—")
            self.chart.set_stats_text("采样 0 · 帧率 —")
            self._log_line(
                f"数据源切换为 {SOURCE_NAMES[source]}，曲线与丢包统计已重置。", "warn"
            )

    def _track_seq(self, seq: int):
        if self.last_seq is not None:
            delta = (seq - self.last_seq) & 0xFFFF
            if 1 < delta <= 600:
                self.lost_frames += delta - 1
        self.last_seq = seq

    def _loss_percent(self) -> float:
        total = self.lost_frames + self.valid_samples
        return self.lost_frames / total * 100.0 if total else 0.0

    def _update_radio_quality(self, rssi: int | None, snr: int | None):
        if rssi is None:
            self.card_rssi.set_value("—", "本机遥测无无线质量", badge="")
            self.card_rssi.set_ratio(0)
            self.rssi_value.setText("—")
            self.snr_value.setText("—")
            self.rssi_bar.set_ratio(0)
            self.snr_bar.set_ratio(0)
            return
        rssi_ratio = max(0.0, min(1.0, (rssi + 100) / 70.0))
        snr_value = 0 if snr is None else snr
        self.card_rssi.set_value(str(rssi), f"SNR {snr_value} dB · 0x19", badge="无线")
        self.card_rssi.set_ratio(rssi_ratio)
        self.rssi_value.setText(f"{rssi} dBm")
        self.rssi_bar.set_ratio(rssi_ratio)
        self.snr_value.setText(f"{snr_value} dB")
        self.snr_bar.set_ratio(max(0.0, min(1.0, snr_value / 15.0)))

    def _add_sample(self, ts, temp, hum, rssi, snr, seq, source):
        self._track_seq(seq)
        self.valid_samples += 1
        self.valid_times.append(ts)
        self.last_valid_ts = ts
        self.last_update_value.setText("刚刚")
        sample = Sample(ts, temp, hum, rssi, snr, seq, source)
        self.samples.append(sample)
        self.temp_history.append(temp)
        self.hum_history.append(hum)

        badge = "0x19" if source == "RX" else "0x18"
        source_name = SOURCE_NAMES[source]
        sub = f"{source_name} · 序号 {seq} · {fmt_time(ts)}"
        self.card_temp.set_value(f"{temp:.2f}", sub, badge)
        self.card_hum.set_value(f"{hum:.2f}", sub, badge)
        self.card_temp.set_spark(self.temp_history)
        self.card_hum.set_spark(self.hum_history)

        loss = self._loss_percent()
        self.card_loss.set_value(
            f"{loss:.1f}", f"接收 {self.valid_samples} 帧 · CRC 错 {self.crc_errors}", ""
        )
        self.card_loss.set_ratio(min(1.0, loss / 5.0))
        self.loss_value.setText(f"{loss:.2f} %")
        self.loss_bar.set_ratio(min(1.0, loss / 5.0))

        self._insert_recent(sample)
        self._update_rate()
        self._update_chart()

    def _insert_recent(self, sample: Sample):
        table = self.recent_table
        table.insertRow(0)
        values = [
            fmt_time(sample.ts),
            SOURCE_NAMES[sample.source],
            f"{sample.temp:.2f}",
            f"{sample.hum:.2f}",
            "—" if sample.rssi is None else str(sample.rssi),
            "—" if sample.snr is None else str(sample.snr),
            str(sample.seq),
            "正常",
        ]
        for column, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            if column == 2:
                item.setForeground(QColor(C.CYAN))
            elif column == 3:
                item.setForeground(QColor(C.TEAL))
            elif column == 7:
                item.setForeground(QColor(C.GREEN))
            table.setItem(0, column, item)
        while table.rowCount() > self.MAX_TABLE_ROWS:
            table.removeRow(table.rowCount() - 1)

    # ------------------------------------------------------------------
    # 曲线 / 统计
    # ------------------------------------------------------------------
    def _empty_text(self) -> str:
        if self.worker is None:
            return "串口未连接\n请选择串口并打开"
        return "已连接，等待设备数据…"

    def _update_chart(self):
        if not self._visible or self.chart_paused:
            return
        if not self.samples:
            self.chart.clear()
            self.chart.set_empty(self._empty_text(), True)
            self.chart.set_stats_text("采样 0 · 帧率 —")
            return
        self.chart.set_samples(
            list(self.samples), self.chart_window_sec, self._rate_text()
        )

    def _on_series_toggle(self, *_):
        self.chart.set_series_visible(
            self.temp_chip.isChecked(), self.hum_chip.isChecked()
        )

    def _on_window_changed(self, _index: int):
        self.chart_window_sec = int(self.window_combo.currentData() or 0)
        self.settings.set("lora/window", self.chart_window_sec)
        self._update_chart()

    def toggle_chart_pause(self, checked: bool):
        self.chart_paused = bool(checked)
        self.pause_btn.setText("继续" if checked else "暂停")
        self.chart.set_paused(checked)
        if not checked:
            self._update_chart()

    def _rate_text(self) -> str:
        if len(self.valid_times) >= 2 and self.last_valid_ts is not None:
            if time.time() - self.last_valid_ts <= 5:
                span = self.valid_times[-1] - self.valid_times[0]
                if span > 0:
                    return f"{(len(self.valid_times) - 1) / span:.2f} Hz"
        return "—"

    def _update_rate(self):
        text = self._rate_text()
        self.rate_value.setText(text)
        self.stat_tiles["rate"].set_value(text)
        self.chart.set_stats_text(f"采样 {len(self.samples)} · 帧率 {text}")

    def _refresh_counters(self):
        rx_text = fmt_bytes(self.rx_bytes)
        tx_text = fmt_bytes(self.tx_bytes)
        self.serial_summary.setText(f"RX {rx_text} · TX {tx_text}")
        self.log_summary.setText(f"RX {rx_text} · TX {tx_text} · {self.total_frames} 帧")
        tiles = self.stat_tiles
        tiles["rx"].set_value(rx_text)
        tiles["tx"].set_value(tx_text)
        tiles["valid"].set_value(str(self.valid_samples))
        tiles["remote"].set_value(str(self.count_19))
        tiles["local"].set_value(str(self.count_18))
        tiles["crc"].set_value(str(self.crc_errors))
        tiles["alert"].set_value(str(self.alert_count))
        tiles["rate"].set_value(self._rate_text())

    def _tick_clock(self):
        if self.last_valid_ts is None:
            self.last_update_value.setText("—")
            return
        age = time.time() - self.last_valid_ts
        if age < 1.5:
            text = "刚刚"
        elif age < 60:
            text = f"{age:.0f} 秒前"
        else:
            text = fmt_time(self.last_valid_ts)
        self.last_update_value.setText(text)
        if age > 5:
            self.rate_value.setText("—")
            self.stat_tiles["rate"].set_value("—")
            self.chart.set_stats_text(f"采样 {len(self.samples)} · 数据超时")
        else:
            self._update_rate()

    def reset_stats(self, *_):
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.total_frames = 0
        self.count_18 = 0
        self.count_19 = 0
        self.crc_errors = 0
        self.alert_count = 0
        self.lost_frames = 0
        self.valid_samples = 0
        self.valid_times.clear()
        self.last_seq = None
        self.card_loss.set_value("0.0", "接收 0 帧 · CRC 错 0", "")
        self.card_loss.set_ratio(0)
        self.loss_value.setText("0.00 %")
        self.loss_bar.set_ratio(0)
        self._refresh_counters()
        self._update_rate()
        self._log_line("通信统计已重置（曲线数据保留）。", "info")

    def export_csv(self, *_):
        if not self.samples:
            QMessageBox.information(self, "提示", "当前没有可导出的数据。")
            return
        default = str(
            Path(self._last_export_dir) / f"lora_th_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "导出温湿度数据", default, "CSV 文件 (*.csv);;所有文件 (*.*)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    ["时间", "时间戳", "来源", "温度(℃)", "湿度(%RH)", "RSSI(dBm)", "SNR(dB)", "序号"]
                )
                for sample in self.samples:
                    writer.writerow(
                        [
                            fmt_time(sample.ts),
                            datetime.fromtimestamp(sample.ts).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                            SOURCE_NAMES[sample.source],
                            f"{sample.temp:.2f}",
                            f"{sample.hum:.2f}",
                            "" if sample.rssi is None else sample.rssi,
                            "" if sample.snr is None else sample.snr,
                            sample.seq,
                        ]
                    )
        except OSError as exc:
            QMessageBox.critical(self, "导出失败", f"写入文件失败：\n{exc}")
            return
        self._last_export_dir = str(Path(path).parent)
        self._log_line(f"已导出 {len(self.samples)} 条数据：{path}", "ok")
        QMessageBox.information(self, "导出完成", f"已导出 {len(self.samples)} 条数据到：\n{path}")

    # ------------------------------------------------------------------
    # 日志 / 发送
    # ------------------------------------------------------------------
    def _ts_prefix(self) -> str:
        return f"[{fmt_time(with_ms=True)}] " if self.ts_chk.isChecked() else ""

    def _append_html(self, text: str):
        scrollbar = self.rx_log.verticalScrollBar()
        if self.autoscroll_chk.isChecked():
            self.rx_log.appendHtml(text)
            scrollbar.setValue(scrollbar.maximum())
        else:
            value = scrollbar.value()
            self.rx_log.appendHtml(text)
            scrollbar.setValue(value)

    def _append_raw(self, data: bytes):
        prefix = self._ts_prefix()
        shown = data[:512]
        if self.hex_chk.isChecked():
            text = " ".join(f"{byte:02X}" for byte in shown)
        else:
            text = shown.decode("utf-8", "replace")
            text = "".join(
                char if char.isprintable() or char in "\r\n\t" else "·" for char in text
            )
            text = text.replace("\r", "␍").replace("\n", "␊").replace("\t", " ")
        if len(data) > len(shown):
            text += f" … (+{len(data) - len(shown)} B)"
        self._append_html(
            f'<span style="color:#6E86A8;">{prefix}RX  {html.escape(text)}</span>'
        )

    def _log_line(self, text: str, level: str = "info"):
        colors = {"info": C.MUTED, "ok": C.GREEN, "warn": C.AMBER, "error": C.RED}
        safe = html.escape(text).replace("\n", "<br>")
        self._append_html(
            f'<span style="color:#5E7699;">{self._ts_prefix()}</span>'
            f'<span style="color:{colors.get(level, C.MUTED)};">{safe}</span>'
        )

    def _log_frame(self, frame: Frame, summary: str, color: str):
        if self.log_paused:
            return
        colors = {"frame": "#8FC7FF", "info": C.MUTED, "warn": C.AMBER, "error": C.RED}
        self._append_html(
            f'<span style="color:#5E7699;">{self._ts_prefix()}</span>'
            f'<span style="color:{colors.get(color, color)};">{html.escape(summary)}</span>'
        )

    def toggle_log_pause(self, checked: bool):
        self.log_paused = bool(checked)
        self.log_pause_btn.setText("继续" if checked else "暂停")
        if checked:
            self._log_line("日志显示已暂停（串口仍在接收，统计继续更新）。", "warn")
        else:
            self._log_line("日志显示已继续。", "info")

    def clear_log(self, *_):
        self.rx_log.clear()
        self._log_line("接收日志已清空。", "info")

    def save_log(self, *_):
        default = str(
            Path(self._last_export_dir) / f"lora_serial_{datetime.now():%Y%m%d_%H%M%S}.txt"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "保存串口日志", default, "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if not path:
            return
        try:
            Path(path).write_text(self.rx_log.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", f"写入文件失败：\n{exc}")
            return
        self._last_export_dir = str(Path(path).parent)
        self._log_line(f"串口日志已保存：{path}", "ok")

    @staticmethod
    def _parse_hex(text: str) -> bytes:
        cleaned = (
            text.replace("0x", "").replace("0X", "").replace(",", " ").replace(";", " ")
        )
        compact = "".join(cleaned.split())
        if not compact:
            return b""
        if len(compact) % 2 != 0:
            raise ValueError("HEX 字符个数必须为偶数。")
        if any(char not in "0123456789abcdefABCDEF" for char in compact):
            raise ValueError("包含非十六进制字符。")
        return bytes.fromhex(compact)

    @staticmethod
    def _parse_hex_byte(text: str) -> int:
        cleaned = text.strip().replace("0x", "").replace("0X", "")
        if not cleaned:
            raise ValueError("CMD 不能为空。")
        if len(cleaned) > 2:
            raise ValueError("CMD 只能为 1 个字节。")
        if any(char not in "0123456789abcdefABCDEF" for char in cleaned):
            raise ValueError("CMD 必须为十六进制。")
        return int(cleaned, 16)

    def _compose_tx_bytes(self, show_error: bool) -> bytes | None:
        raw = self.tx_input.toPlainText()
        if not raw.strip():
            if show_error:
                QMessageBox.warning(self, "提示", "发送内容为空。")
            return None
        if self.tx_mode.currentIndex() == 1:
            try:
                return self._parse_hex(raw)
            except ValueError as exc:
                if show_error:
                    QMessageBox.warning(self, "HEX 格式错误", str(exc))
                return None
        endings = (b"", b"\r\n", b"\n", b"\r")
        index = max(0, min(len(endings) - 1, self.tx_ending.currentIndex()))
        return raw.encode("utf-8") + endings[index]

    def _log_tx_data(self, data: bytes, force_hex: bool = False):
        prefix = self._ts_prefix()
        shown = data[:512]
        if force_hex or self.tx_mode.currentIndex() == 1:
            text = " ".join(f"{byte:02X}" for byte in shown)
        else:
            text = shown.decode("utf-8", "replace")
            text = "".join(
                char if char.isprintable() or char in "\r\n\t" else "·" for char in text
            )
            text = text.replace("\r", "␍").replace("\n", "␊").replace("\t", " ")
        if len(data) > len(shown):
            text += f" … (+{len(data) - len(shown)} B)"
        self._append_html(
            f'<span style="color:#B49CFF;">{prefix}TX  {html.escape(text)}</span>'
        )

    def send_current_text(self, silent: bool = False) -> bool:
        if self.worker is None:
            if not silent:
                QMessageBox.warning(self, "提示", "请先打开串口。")
            else:
                self._stop_periodic_send()
            return False
        data = self._compose_tx_bytes(show_error=not silent)
        if data is None:
            if silent:
                self._stop_periodic_send()
            return False
        if self.worker.write(data):
            self.tx_bytes += len(data)
            self._log_tx_data(data)
            return True
        if not silent:
            QMessageBox.warning(self, "发送失败", "串口写入失败，请检查连接。")
        else:
            self._stop_periodic_send()
            self._log_line("周期发送失败，已自动停止。", "error")
        return False

    def _on_tx_mode_changed(self, index: int):
        hex_mode = index == 1
        self.tx_ending.setEnabled(not hex_mode)
        self.tx_input.setPlaceholderText(
            "HEX 模式示例：5A 19 0B 00 00 BF 01 A3 0B 59 0D F0 FF 0E 15"
            if hex_mode
            else "输入要发送的文本…"
        )

    # ------------------------------------------------------------------
    # 协议帧构造
    # ------------------------------------------------------------------
    def _schedule_frame_preview(self, *_):
        self.preview_timer.start()

    def _update_frame_preview(self):
        try:
            cmd = self._parse_hex_byte(self.cmd_input.text())
            data_text = self.data_input.text()
            data = self._parse_hex(data_text) if data_text.strip() else b""
            frame = build_frame(cmd, data)
        except ValueError as exc:
            self._built_frame = None
            self.frame_preview.setText(f"输入无效：{exc}")
            self.frame_crc.setText("CRC8 = —")
            return
        self._built_frame = frame
        hex_text = " ".join(f"{byte:02X}" for byte in frame)
        if len(hex_text) > 280:
            hex_text = hex_text[:280] + " …"
        self.frame_preview.setText(hex_text)
        self.frame_crc.setText(f"CRC8 = 0x{frame[-1]:02X} · 共 {len(frame)} B")

    def send_built_frame(self, *_):
        if self.worker is None:
            QMessageBox.warning(self, "提示", "请先打开串口。")
            return
        self._update_frame_preview()
        frame = self._built_frame
        if not frame:
            QMessageBox.warning(self, "帧无效", "请先修正 CMD / DATA 输入。")
            return
        if self.worker.write(frame):
            self.tx_bytes += len(frame)
            self._log_tx_data(frame, force_hex=True)
            self._log_line(f"已发送协议帧（{len(frame)} B）。", "ok")
        else:
            QMessageBox.warning(self, "发送失败", "串口写入失败，请检查连接。")

    # ------------------------------------------------------------------
    # 告警 / 状态
    # ------------------------------------------------------------------
    def _set_source_pill(self, source: str | None):
        if source == "RX":
            text, color = "接收端 · 0x19", C.CYAN
        elif source == "TX":
            text, color = "发射端 · 0x18", C.BLUE
        else:
            text, color = "等待数据", C.MUTED
        subtitle = self.chart_card.subtitle_label
        if subtitle is not None:
            subtitle.setText(f"温度 ℃ · 湿度 %RH · {text}")
            subtitle.setStyleSheet(f"color:{color}; font-size:11px;")

    def show_alert(self, text: str, level: str = "warn", timeout: int = 0):
        colors = {
            "warn": (C.AMBER, q_rgba(C.AMBER, 0.10)),
            "error": (C.RED, q_rgba(C.RED, 0.10)),
            "info": (C.BLUE, q_rgba(C.BLUE, 0.12)),
        }
        color, background = colors.get(level, colors["warn"])
        self.alert_frame.setStyleSheet(
            f"QFrame#Alert {{ background-color:{background};"
            f"border:1px solid {q_rgba(color, 0.38)}; border-radius:9px; }}"
        )
        self.alert_icon.setStyleSheet(
            f"color:{color}; background-color:{q_rgba(color, 0.16)};"
            "border-radius:9px; font-weight:700;"
        )
        self.alert_text.setStyleSheet(f"color:{color};")
        self.alert_text.setText(text)
        self._banner_kind = "data" if timeout == 0 else "event"
        self.alert_frame.setVisible(True)
        if timeout > 0:
            self.alert_timer.start(timeout)
        else:
            self.alert_timer.stop()

    def hide_alert(self, *_):
        self.alert_timer.stop()
        self.alert_frame.setVisible(False)
        self._banner_kind = None

    # ------------------------------------------------------------------
    def shutdown(self):
        self.save_settings()
        self.chart_timer.stop()
        self.stats_timer.stop()
        self.clock_timer.stop()
        self.periodic_timer.stop()
        self.alert_timer.stop()
        if self.worker is not None:
            worker = self.worker
            self.worker = None
            worker.stop()

    def show_protocol_dialog(self, *_):
        dialog = QDialog(self)
        dialog.setWindowTitle("2.4G LoRa 通信协议说明")
        dialog.resize(820, 680)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(protocol_html())
        layout.addWidget(browser, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("Primary")
        close_btn.setFixedWidth(88)
        close_btn.clicked.connect(dialog.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)
        dialog.exec()


def protocol_html() -> str:
    return """
<html><head><meta charset="utf-8">
<style>
body { color:#C9D9F0; font-family:'Microsoft YaHei UI','Microsoft YaHei'; font-size:13px; }
h1 { color:#F3F8FF; font-size:20px; }
h2 { color:#4A8CFF; font-size:15px; margin-top:20px; }
p { line-height:150%; }
pre { background-color:#081528; border:1px solid #1E3D66; padding:10px; color:#9CCBFF; font-family:Consolas; }
table { border-collapse:collapse; }
td, th { border:1px solid #1E3D66; padding:5px 9px; }
th { background-color:#0A1830; color:#8FA6C8; }
.muted { color:#7C93B4; }
.hl { color:#38BDF8; }
.warn { color:#FBBF24; }
</style></head><body>
<h1>2.4G LoRa 串口通信协议</h1>
<p class="muted">STM32F411 + SX1280 + HDC1080　|　控制中心 v1.0.0</p>
<h2>1. 物理层</h2>
<table>
<tr><th>参数</th><th>值</th></tr>
<tr><td>波特率</td><td class="hl">115200</td></tr>
<tr><td>数据位 / 校验 / 停止位</td><td>8 / None / 1</td></tr>
<tr><td>多字节字节序</td><td>小端（Little-Endian）</td></tr>
</table>
<h2>2. 帧结构</h2>
<pre>+------+------+------+---------------+------+
| 0x5A | CMD  | LEN  |  DATA x LEN   | CRC8 |
+------+------+------+---------------+------+
  帧头   命令   长度     净荷（LEN 字节）   校验</pre>
<p>整帧长度 = 4 + LEN。CRC8 校验范围 = <b>CMD + LEN + DATA</b>，不含帧头 0x5A 与 CRC 自身。</p>
<h2>3. CRC8</h2>
<table>
<tr><th>项目</th><th>值</th></tr>
<tr><td>多项式</td><td>0x07</td></tr>
<tr><td>初值</td><td>0xFF</td></tr>
<tr><td>输入 / 输出反转</td><td>否 / 否</td></tr>
<tr><td>结果异或</td><td>0x00</td></tr>
</table>
<h2>4. 命令码</h2>
<table>
<tr><th>CMD</th><th>名称</th><th>LEN</th><th>说明</th></tr>
<tr><td>0x18</td><td>本地遥测</td><td>7</td><td>发射端本地温湿度</td></tr>
<tr><td class="hl">0x19</td><td>空中接收上报</td><td>11</td><td>远端温湿度 + RSSI/SNR</td></tr>
<tr><td>0xE0</td><td>栈溢出告警</td><td>N</td><td>净荷为任务名 ASCII</td></tr>
<tr><td>0xE1</td><td>SX1280 初始化失败</td><td>1</td><td>净荷为返回码</td></tr>
<tr><td>0x80 / 0x81 / 0x82</td><td>模块保留应答</td><td>0</td><td>当前固件未使用</td></tr>
</table>
<h2>5. 0x19 字段</h2>
<table>
<tr><th>偏移</th><th>字段</th><th>类型</th><th>换算 / 说明</th></tr>
<tr><td>0</td><td>status</td><td>int8</td><td>0=正常；-8=长度错；-4=包头错</td></tr>
<tr><td>1</td><td>remote_status</td><td>int8</td><td>发射端 HDC1080 状态</td></tr>
<tr><td>2–3</td><td>remote_seq</td><td>uint16</td><td>帧序号</td></tr>
<tr><td>4–5</td><td>remote_temp</td><td>int16</td><td>÷100 → ℃</td></tr>
<tr><td>6–7</td><td>remote_hum</td><td>uint16</td><td>÷100 → %RH</td></tr>
<tr><td>8–9</td><td>rssi</td><td>int16</td><td>dBm，负值</td></tr>
<tr><td>10</td><td>snr</td><td>int8</td><td>dB</td></tr>
</table>
<h2>6. 真实抓包</h2>
<pre>5A 19 0B 00 00 BF 01 A3 0B 59 0D F0 FF 0E 15</pre>
<p>温度 0x0BA3 = 2979 → <span class="hl">29.79 ℃</span>；湿度 0x0D59 = 3417 → <span class="hl">34.17 %RH</span>；
RSSI 0xFFF0 = -16 dBm；SNR 0x0E = 14 dB；SEQ 447。</p>
<p class="warn">固件当前只主动上报，不解析上位机下行命令；串口页的发送/周期发送/帧构造器仅用于链路自测。</p>
</body></html>
"""
