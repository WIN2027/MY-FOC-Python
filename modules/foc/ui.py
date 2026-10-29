# -*- coding: utf-8 -*-
"""FOC 模块 UI 构建（逻辑由 logic.py mixin 提供）。"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.theme import C
from core.widgets import SectionCard, SegmentedTabs, StatusPill

from .protocol import (
    CURVE_COLORS,
    DEADTIME_OPTIONS,
    DEFAULT_DRV_CONFIG,
    IDRIVEN_OPTIONS,
    IDRIVEP_OPTIONS,
    OCP_DEGLITCH_OPTIONS,
    OCP_MODES,
    PWM_MODES,
    RETRY_OPTIONS,
    TDRIVE_OPTIONS,
    VDS_LEVELS,
)


class LimitedTextEdit(QTextEdit):
    def __init__(self, max_blocks=5000, parent=None):
        super().__init__(parent)
        self._max_blocks = max_blocks
        self.setUndoRedoEnabled(False)
        # 交给 QTextDocument 的环形缓冲裁剪，避免每次 append 手工移动光标。
        self.document().setMaximumBlockCount(max_blocks)


class FocPlotWidget(pg.PlotWidget):
    """限制默认 sizeHint，避免 QScrollArea 被 pyqtgraph 的 480px 默认高度撑开。"""

    def sizeHint(self):  # noqa: N802
        return QSize(420, 135)

    def minimumSizeHint(self):  # noqa: N802
        return QSize(220, 100)


def _wrap_scroll(widget: QWidget, min_height: int) -> QScrollArea:
    widget.setMinimumHeight(min_height)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    scroll.viewport().setAutoFillBackground(False)
    return scroll


def _bar_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("BarLabel")
    return label


def _small_button(text: str, icon: str = "") -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("Chip")
    button.setCursor(Qt.PointingHandCursor)
    return button


def _inline_panel(title: str) -> tuple[QFrame, QHBoxLayout]:
    """带左侧标题的单行卡片，标题与内容共用一行。"""
    panel = QFrame()
    panel.setObjectName("Card")
    panel.setFixedHeight(56)
    row = QHBoxLayout(panel)
    row.setContentsMargins(16, 12, 16, 12)
    row.setSpacing(6)
    label = QLabel(title)
    label.setObjectName("CardTitle")
    label.setFixedWidth(64)
    row.addWidget(label)
    row.addSpacing(8)
    return panel, row


def build_foc_ui(page):
    """构建 FOC 页面骨架，所有控件挂到 page 上，供 logic mixin 使用。"""

    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(12)

    page.tabs = SegmentedTabs()
    page.tabs.add_tab("硬件配置", "hardware")
    page.tabs.add_tab("PID 调参", "pid")
    page.tabs.add_tab("运行监测", "monitor")
    page.tabs.add_tab("通讯信息", "comm")
    page.tabs.add_stretch()
    badge = QLabel("DRV8320S · FOC")
    badge.setObjectName("Hint")
    page.tabs.add_action(badge)
    page.nav_buttons = page.tabs.buttons()
    page.tabs.changed.connect(page.switch_tab)
    root.addWidget(page.tabs)

    root.addWidget(build_serial_bar(page))

    page.stacked_widget = QWidget()
    page.stack_layout = QVBoxLayout(page.stacked_widget)
    page.stack_layout.setContentsMargins(0, 0, 0, 0)
    page.stack_layout.setSpacing(0)

    from PySide6.QtWidgets import QStackedWidget

    page.stack = QStackedWidget()
    page.page_hardware = build_hardware_page(page)
    page.page_pid = build_pid_page(page)
    page.page_monitor = build_monitor_page(page)
    page.page_comm = build_comm_page(page)
    page.stack.addWidget(_wrap_scroll(page.page_hardware, 500))
    page.stack.addWidget(_wrap_scroll(page.page_pid, 500))
    page.stack.addWidget(page.page_monitor)
    page.stack.addWidget(_wrap_scroll(page.page_comm, 400))
    page.stack_layout.addWidget(page.stack)
    root.addWidget(page.stacked_widget, 1)

    page.tabs.set_current(0)
    page.stack.setCurrentIndex(0)


def build_serial_bar(page) -> QFrame:
    bar = QFrame()
    bar.setObjectName("SerialBar")
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(14, 8, 12, 8)
    layout.setSpacing(6)

    layout.addWidget(_bar_label("串口"))
    page.port_combo = QComboBox()
    page.port_combo.setMinimumWidth(140)
    page.port_combo.setMaximumWidth(210)
    page.port_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    page.port_combo.setMinimumContentsLength(10)
    layout.addWidget(page.port_combo)

    page.refresh_btn = QPushButton("刷新")
    page.refresh_btn.setObjectName("Ghost")
    page.refresh_btn.setToolTip("重新扫描串口")
    page.refresh_btn.clicked.connect(page.refresh_ports)
    layout.addWidget(page.refresh_btn)

    layout.addSpacing(3)
    layout.addWidget(_bar_label("波特率"))
    page.baud_combo = QComboBox()
    page.baud_combo.addItems(
        ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
    )
    page.baud_combo.setCurrentText("115200")
    page.baud_combo.setFixedWidth(94)
    layout.addWidget(page.baud_combo)

    layout.addWidget(_bar_label("数据位"))
    page.data_combo = QComboBox()
    page.data_combo.addItems(["5", "6", "7", "8"])
    page.data_combo.setCurrentText("8")
    page.data_combo.setFixedWidth(58)
    layout.addWidget(page.data_combo)

    layout.addWidget(_bar_label("停止位"))
    page.stop_combo = QComboBox()
    page.stop_combo.addItems(["1", "1.5", "2"])
    page.stop_combo.setCurrentText("1")
    page.stop_combo.setFixedWidth(60)
    layout.addWidget(page.stop_combo)

    layout.addWidget(_bar_label("校验位"))
    page.parity_combo = QComboBox()
    page.parity_combo.addItems(["无", "奇", "偶"])
    page.parity_combo.setFixedWidth(62)
    layout.addWidget(page.parity_combo)

    page.serial_assistant_btn = QPushButton("串口助手")
    page.serial_assistant_btn.setObjectName("Chip")
    page.serial_assistant_btn.setCheckable(True)
    page.serial_assistant_btn.setCursor(Qt.PointingHandCursor)
    page.serial_assistant_btn.toggled.connect(page.toggle_serial_assistant)
    layout.addSpacing(4)
    layout.addWidget(page.serial_assistant_btn)

    layout.addStretch(1)
    layout.addSpacing(4)

    page.motor_state_label = QLabel("空闲")
    page.motor_state_label.setAlignment(Qt.AlignCenter)
    page.motor_state_label.setMinimumWidth(64)
    layout.addWidget(page.motor_state_label)

    page.status_label = StatusPill("未连接")
    layout.addWidget(page.status_label)

    page.open_btn = QPushButton("打开串口")
    page.open_btn.setObjectName("Primary")
    page.open_btn.setCursor(Qt.PointingHandCursor)
    page.open_btn.setFixedWidth(100)
    page.open_btn.clicked.connect(page.toggle_serial)
    layout.addWidget(page.open_btn)

    page.serial_controls = [
        page.port_combo,
        page.refresh_btn,
        page.baud_combo,
        page.data_combo,
        page.stop_combo,
        page.parity_combo,
    ]
    return bar


# ======================================================================
# 硬件配置
# ======================================================================
def build_hardware_page(page) -> QWidget:
    page_widget = QWidget()
    page_widget.setObjectName("Page")
    layout = QVBoxLayout(page_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    card = SectionCard(
        "DRV8320S 驱动配置",
        "16 项寄存器参数 · 读取 / 写入 / 自动回读校验",
    )
    page.slave_indicator = QLabel("● 从机离线")
    page.slave_indicator.setStyleSheet(
        f"color:{C.DIM}; font-weight:600; font-size:12px; padding-right:4px;"
    )
    page.refresh_slave_btn = _small_button("刷新从机")
    page.read_drv_btn = _small_button("读取 DRV")
    page.write_drv_btn = _small_button("写入 DRV")
    page.clear_fault_btn = _small_button("清除故障")
    page.refresh_slave_btn.clicked.connect(page.check_slave)
    page.read_drv_btn.clicked.connect(page.request_drv_config)
    page.write_drv_btn.clicked.connect(page.write_drv_config)
    page.clear_fault_btn.clicked.connect(page.clear_drv_faults)
    card.header.addWidget(page.slave_indicator)
    card.header.addWidget(page.refresh_slave_btn)
    card.header.addWidget(page.read_drv_btn)
    card.header.addWidget(page.write_drv_btn)
    card.header.addWidget(page.clear_fault_btn)

    params = [
        ("PWM 模式", "pwm_mode", PWM_MODES, DEFAULT_DRV_CONFIG["pwm_mode"]),
        ("死区时间", "dead_time", DEADTIME_OPTIONS, DEFAULT_DRV_CONFIG["dead_time"]),
        ("TDRIVE 时间", "tdrive", TDRIVE_OPTIONS, DEFAULT_DRV_CONFIG["tdrive"]),
        ("VDS 阈值", "vds_level", VDS_LEVELS, DEFAULT_DRV_CONFIG["vds_level"]),
        ("高侧源电流", "idrive_hs_source", IDRIVEP_OPTIONS, DEFAULT_DRV_CONFIG["idrive_hs_source"]),
        ("高侧灌电流", "idrive_hs_sink", IDRIVEN_OPTIONS, DEFAULT_DRV_CONFIG["idrive_hs_sink"]),
        ("低侧源电流", "idrive_ls_source", IDRIVEP_OPTIONS, DEFAULT_DRV_CONFIG["idrive_ls_source"]),
        ("低侧灌电流", "idrive_ls_sink", IDRIVEN_OPTIONS, DEFAULT_DRV_CONFIG["idrive_ls_sink"]),
        ("OCP 模式", "ocp_mode", OCP_MODES, DEFAULT_DRV_CONFIG["ocp_mode"]),
        ("OCP 消隐时间", "ocp_deglitch", OCP_DEGLITCH_OPTIONS, DEFAULT_DRV_CONFIG["ocp_deglitch"]),
        ("自动重试时间", "retry_mode", RETRY_OPTIONS, DEFAULT_DRV_CONFIG["retry_mode"]),
        ("电荷泵欠压保护", "cpuv_enabled", {0: "禁用", 1: "使能"}, DEFAULT_DRV_CONFIG["cpuv_enabled"]),
        ("栅极故障检测", "gdf_enabled", {0: "禁用", 1: "使能"}, DEFAULT_DRV_CONFIG["gdf_enabled"]),
        ("过热警告报告", "otw_report", {0: "仅寄存器", 1: "触发 nFAULT"}, DEFAULT_DRV_CONFIG["otw_report"]),
        ("FAULT1 寄存器", "fault1", None, None),
        ("FAULT2 寄存器", "fault2", None, None),
    ]

    grid_widget = QWidget()
    grid = QGridLayout(grid_widget)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(9)
    grid.setVerticalSpacing(9)
    for column in range(4):
        grid.setColumnStretch(column, 1)

    for index, (label_text, key, options, default_val) in enumerate(params):
        row, column = divmod(index, 4)
        card_frame = QFrame()
        card_frame.setObjectName("ParamCard")
        card_frame.setFixedHeight(82)
        card_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        box = QVBoxLayout(card_frame)
        box.setContentsMargins(10, 7, 10, 7)
        box.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("ParamLabel")
        box.addWidget(label)
        if options:
            combo = QComboBox()
            combo.addItems(list(options.values()))
            if default_val is not None:
                combo.setCurrentText(options[default_val])
            combo.setFixedHeight(30)
            page.drv_widgets[key] = (combo, options)
            box.addWidget(combo)
        else:
            entry = QLineEdit()
            entry.setReadOnly(True)
            entry.setPlaceholderText("—")
            entry.setFixedHeight(30)
            page.drv_widgets[key] = (entry, None)
            box.addWidget(entry)
        grid.addWidget(card_frame, row, column)

    card.body.addWidget(grid_widget)
    hint = QLabel("读取/写入需先打开串口；写入后约 300 ms 自动回读并比对配置。")
    hint.setObjectName("Hint")
    card.body.addWidget(hint)
    layout.addWidget(card)
    layout.addStretch(1)
    return page_widget


# ======================================================================
# PID 调参
# ======================================================================
def build_pid_page(page) -> QWidget:
    page_widget = QWidget()
    page_widget.setObjectName("Page")
    layout = QVBoxLayout(page_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    preset_card = SectionCard("参数预设", "保存 / 加载整套 D、Q、速度环参数")
    page.preset_combo = QComboBox()
    page.preset_combo.setFixedWidth(220)
    preset_save = _small_button("保存为预设")
    preset_load = _small_button("加载预设")
    preset_delete = _small_button("删除预设")
    preset_save.clicked.connect(page._on_preset_save)
    preset_load.clicked.connect(page._on_preset_load)
    preset_delete.clicked.connect(page._on_preset_delete)
    preset_row = QHBoxLayout()
    preset_row.setSpacing(7)
    preset_label = QLabel("预设")
    preset_label.setObjectName("KvKey")
    preset_row.addWidget(preset_label)
    preset_row.addWidget(page.preset_combo)
    preset_row.addWidget(preset_save)
    preset_row.addWidget(preset_load)
    preset_row.addWidget(preset_delete)
    preset_row.addStretch(1)
    page.send_all_pid_btn = _small_button("下发全部 PI")
    page.send_all_pid_btn.setToolTip("先发 0x02（D/Q 四参数），确认后发 0x03（速度环）")
    page.send_all_pid_btn.clicked.connect(page.send_all_pid)
    preset_row.addWidget(page.send_all_pid_btn)
    preset_card.body.addLayout(preset_row)
    layout.addWidget(preset_card)

    cards = QHBoxLayout()
    cards.setSpacing(10)
    curr_kp = [("0~0.1", 0, 0.1), ("0.1~0.2", 0.1, 0.2), ("0.2~0.3", 0.2, 0.3)]
    curr_ki = [("0~200", 0, 200), ("200~400", 200, 400), ("400~600", 400, 600)]
    spd_kp = [("0~0.02", 0, 0.02), ("0.02~0.04", 0.02, 0.04), ("0.04~0.06", 0.04, 0.06)]
    spd_ki = [("0~0.5", 0, 0.5), ("0.5~1.0", 0.5, 1.0), ("1.0~1.5", 1.0, 1.5)]
    spd_kd = [("0~0.02", 0, 0.02), ("0.02~0.04", 0.02, 0.04), ("0.04~0.06", 0.04, 0.06)]

    cards.addWidget(
        build_pid_card(page, "d", "D 轴电流环", [("Kp", curr_kp), ("Ki", curr_ki)], C.CYAN),
        1,
    )
    cards.addWidget(
        build_pid_card(page, "q", "Q 轴电流环", [("Kp", curr_kp), ("Ki", curr_ki)], C.TEAL),
        1,
    )
    cards.addWidget(
        build_pid_card(
            page, "speed", "速度环", [("Kp", spd_kp), ("Ki", spd_ki), ("Kd", spd_kd)], C.VIOLET
        ),
        1,
    )
    cards.addWidget(build_motor_params_card(page), 1)
    layout.addLayout(cards)
    layout.addStretch(1)
    return page_widget


def build_motor_params_card(page) -> QFrame:
    card = QFrame()
    card.setObjectName("PidCard")
    box = QVBoxLayout(card)
    box.setContentsMargins(12, 12, 12, 12)
    box.setSpacing(7)

    head = QHBoxLayout()
    head.setSpacing(6)
    titles = QVBoxLayout()
    titles.setSpacing(0)
    title = QLabel("电机参数")
    title.setObjectName("CardTitle")
    subtitle = QLabel("0x0B / 0x0C · 掉电恢复默认")
    subtitle.setObjectName("CardSub")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    head.addLayout(titles)
    head.addStretch(1)
    page.read_motor_btn = _small_button("读取")
    page.write_motor_btn = _small_button("写入")
    page.read_motor_btn.clicked.connect(page.read_motor_params)
    page.write_motor_btn.clicked.connect(page.write_motor_params)
    head.addWidget(page.read_motor_btn)
    head.addWidget(page.write_motor_btn)
    box.addLayout(head)

    marker = QFrame()
    marker.setFixedHeight(2)
    marker.setStyleSheet(f"background-color:{C.AMBER}; border-radius:1px;")
    box.addWidget(marker)

    grid = QGridLayout()
    grid.setHorizontalSpacing(5)
    grid.setVerticalSpacing(5)
    page.motor_spins = {}

    def add_spin(row, key, text, spin):
        label = QLabel(text)
        label.setObjectName("KvKey")
        spin.setFixedHeight(28)
        spin.setFixedWidth(128)
        spin.setKeyboardTracking(False)
        grid.addWidget(label, row, 0)
        grid.addWidget(spin, row, 1)
        page.motor_spins[key] = spin

    r = QDoubleSpinBox()
    r.setRange(0.001, 100.0)
    r.setDecimals(6)
    r.setSingleStep(0.001)
    r.setSuffix(" Ω")
    add_spin(0, "R", "R", r)

    ld = QDoubleSpinBox()
    ld.setRange(0.000001, 1.0)
    ld.setDecimals(8)
    ld.setSingleStep(0.000001)
    ld.setSuffix(" H")
    add_spin(1, "Ld", "Ld", ld)

    lq = QDoubleSpinBox()
    lq.setRange(0.000001, 1.0)
    lq.setDecimals(8)
    lq.setSingleStep(0.000001)
    lq.setSuffix(" H")
    add_spin(2, "Lq", "Lq", lq)

    flux = QDoubleSpinBox()
    flux.setRange(0.00001, 10.0)
    flux.setDecimals(8)
    flux.setSingleStep(0.0001)
    flux.setSuffix(" Wb")
    add_spin(3, "flux_link", "磁链", flux)

    poles = QSpinBox()
    poles.setRange(1, 255)
    add_spin(4, "pole_pairs", "极对数", poles)

    r.setValue(0.055)
    ld.setValue(0.000020)
    lq.setValue(0.000020)
    flux.setValue(0.0012)
    poles.setValue(7)
    box.addLayout(grid)

    hint = QLabel("仅 IDLE/FAULT 可写；Lq 当前只保存/回读。")
    hint.setObjectName("Hint")
    hint.setWordWrap(True)
    box.addWidget(hint)
    box.addStretch(1)
    return card


def build_pid_card(page, axis_key: str, title: str, params, accent: str) -> QFrame:
    card = QFrame()
    card.setObjectName("PidCard")
    box = QVBoxLayout(card)
    box.setContentsMargins(12, 12, 12, 12)
    box.setSpacing(9)

    head = QHBoxLayout()
    titles = QVBoxLayout()
    titles.setSpacing(0)
    title_label = QLabel(title)
    title_label.setObjectName("CardTitle")
    subtitle = QLabel("电流环 PI" if axis_key != "speed" else "速度环 PID")
    subtitle.setObjectName("CardSub")
    titles.addWidget(title_label)
    titles.addWidget(subtitle)
    head.addLayout(titles)
    head.addStretch(1)
    save_btn = _small_button("保存")
    save_btn.clicked.connect(lambda: page.save_pid_config(axis_key))
    head.addWidget(save_btn)
    box.addLayout(head)

    marker = QFrame()
    marker.setFixedHeight(2)
    marker.setStyleSheet(f"background-color:{accent}; border-radius:1px;")
    box.addWidget(marker)

    if axis_key not in page.pid_sliders:
        page.pid_sliders[axis_key] = {}
        page.pid_btn_groups[axis_key] = {}

    for param_key, ranges in params:
        group = QFrame()
        group.setObjectName("PidGroup")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(9, 7, 9, 7)
        group_layout.setSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(5)
        btn_group = QButtonGroup(page)
        btn_group.setExclusive(True)
        for label, min_val, max_val in ranges:
            button = QPushButton(label)
            button.setObjectName("RangeChip")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.min_val = min_val
            button.max_val = max_val
            btn_group.addButton(button)
            btn_row.addWidget(button)
        btn_group.buttons()[0].setChecked(True)
        group_layout.addLayout(btn_row)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(7)
        name = QLabel(param_key)
        name.setFixedWidth(24)
        name.setStyleSheet(f"color:{C.TEXT}; font-weight:600;")
        slider_row.addWidget(name)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 10000)
        slider.setValue(5000)
        slider.setMinimumHeight(24)
        slider_row.addWidget(slider, 1)
        spin = QDoubleSpinBox()
        spin.setDecimals(5)
        spin.setRange(0, 1e9)
        spin.setSingleStep(0.001)
        spin.setFixedWidth(108)
        spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin.setKeyboardTracking(False)
        slider_row.addWidget(spin)
        group_layout.addLayout(slider_row)
        box.addWidget(group)

        page.pid_sliders[axis_key][param_key] = slider
        page.pid_btn_groups[axis_key][param_key] = btn_group
        slider._spin = spin

        def on_range_changed(bg=btn_group, s=slider, sp=spin):
            min_val, max_val = page._get_range(bg)
            sp.blockSignals(True)
            sp.setRange(min_val, max_val)
            sp.setSingleStep(max((max_val - min_val) / 1000.0, 1e-6))
            s.setValue(5000)
            sp.setValue(min_val + 0.5 * (max_val - min_val))
            sp.blockSignals(False)

        for button in btn_group.buttons():
            button.clicked.connect(
                lambda checked, bg=btn_group, s=slider, sp=spin: on_range_changed(bg, s, sp)
                if checked
                else None
            )

        def on_slider(val, bg=btn_group, sp=spin):
            min_val, max_val = page._get_range(bg)
            real = min_val + (val / 10000.0) * (max_val - min_val)
            sp.blockSignals(True)
            sp.setValue(real)
            sp.blockSignals(False)

        def on_spin(val, bg=btn_group, s=slider):
            min_val, max_val = page._get_range(bg)
            if max_val - min_val < 1e-12:
                return
            pos = int(((val - min_val) / (max_val - min_val)) * 10000.0)
            pos = max(0, min(10000, pos))
            s.blockSignals(True)
            s.setValue(pos)
            s.blockSignals(False)

        slider.valueChanged.connect(lambda v, bg=btn_group, sp=spin: on_slider(v, bg, sp))
        spin.valueChanged.connect(lambda v, bg=btn_group, s=slider: on_spin(v, bg, s))
        on_range_changed(btn_group, slider, spin)

    footer = QLabel("滑块与数值联动；切换范围会重置到区间中点。")
    footer.setObjectName("Hint")
    footer.setWordWrap(True)
    box.addWidget(footer)
    box.addStretch(1)
    return card


# ======================================================================
# 运行监测
# ======================================================================
def build_monitor_page(page) -> QWidget:
    page_widget = QWidget()
    page_widget.setObjectName("Page")
    layout = QVBoxLayout(page_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    header = QHBoxLayout()
    header.setSpacing(8)
    titles = QVBoxLayout()
    titles.setSpacing(1)
    title = QLabel("运行监测")
    title.setObjectName("CardTitle")
    subtitle = QLabel("4 通道实时波形 · 遥测掩码 · 电机控制")
    subtitle.setObjectName("CardSub")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    header.addLayout(titles)
    header.addStretch(1)

    page.func_switch_btn = _small_button("电机控制")
    page.pause_btn = _small_button("暂停波形")
    page.auto_range_btn = _small_button("自动缩放:开")
    page.auto_range_btn.setToolTip("开启后自动适配量程；切换通道或重新开启会再次适配")
    page.export_btn = _small_button("导出 CSV")
    page.debug_btn = _small_button("调试")

    page.func_switch_btn.clicked.connect(page.toggle_monitor_mode)
    page.pause_btn.clicked.connect(page.toggle_pause)
    page.auto_range_btn.clicked.connect(page.toggle_auto_range)
    page.export_btn.clicked.connect(page.export_waveforms_csv)
    page.debug_btn.clicked.connect(page.toggle_debug_mode)
    for button in (
        page.func_switch_btn,
        page.pause_btn,
        page.auto_range_btn,
        page.export_btn,
        page.debug_btn,
    ):
        header.addWidget(button)
    layout.addLayout(header)

    # ---- 遥测通道：标题与胶囊同一行 ----
    page.telemetry_panel, chips_row = _inline_panel("遥测通道")

    page.adc1_btn = make_telemetry_chip(page, chips_row, "ADC1 源码", 0, "adc1")
    page.adc2_btn = make_telemetry_chip(page, chips_row, "ADC2 源码", 1, "adc2")
    page.calc_cycle_btn = make_telemetry_chip(page, chips_row, "计算周期", 8, "calc")
    page.speed_btn = make_telemetry_chip(page, chips_row, "转速", 7, "speed")
    page.three_phase_btn = make_telemetry_chip(page, chips_row, "三相电流", -1, "three")
    page.id_btn = make_telemetry_chip(page, chips_row, "D 轴电流", 5, "id")
    page.iq_btn = make_telemetry_chip(page, chips_row, "Q 轴电流", 6, "iq")
    page.bemf_btn = make_telemetry_chip(page, chips_row, "反电动势", 12, "bemf")
    page.pwm_btn = make_telemetry_chip(page, chips_row, "三相占空比", 9, "pwm")
    page.dpi_btn = make_telemetry_chip(page, chips_row, "D 轴 PI", 10, "dpi")
    page.qpi_btn = make_telemetry_chip(page, chips_row, "Q 轴 PI", 11, "qpi")
    chips_row.addStretch(1)
    layout.addWidget(page.telemetry_panel)

    # ---- 电机控制：标题与控件同一行 ----
    page.control_panel, control_row = _inline_panel("电机控制")
    page.align_btn = _small_button("转子对齐")
    page.start_btn = _small_button("启动")
    page.stop_btn = _small_button("停止")
    page.start_btn.setToolTip("启动电机")
    page.stop_btn.setToolTip("停止电机")
    for button in (page.align_btn, page.start_btn, page.stop_btn):
        button.setFixedHeight(32)
    page.align_btn.clicked.connect(page.run_rotor_alignment)
    page.start_btn.clicked.connect(page.run_motor_start)
    page.stop_btn.clicked.connect(page.run_motor_stop)
    control_row.addWidget(page.align_btn)
    control_row.addWidget(page.start_btn)
    control_row.addWidget(page.stop_btn)
    control_row.addSpacing(8)

    page.speed_slider_capsule = QFrame()
    page.speed_slider_capsule.setObjectName("SpeedCapsule")
    page.speed_slider_capsule.setFixedHeight(32)
    page.speed_slider_capsule.setMinimumWidth(200)
    page.speed_slider_capsule.setStyleSheet(
        "QFrame#SpeedCapsule { background:#081528; border:1px solid #1D3B63;"
        " border-radius:16px; }"
    )
    capsule_layout = QHBoxLayout(page.speed_slider_capsule)
    capsule_layout.setContentsMargins(12, 0, 12, 0)
    capsule_layout.setSpacing(8)
    page.speed_min_label = QLabel("RPM")
    page.speed_min_label.setObjectName("Hint")
    page.speed_min_label.setFixedWidth(28)
    page.speed_slider = QSlider(Qt.Horizontal)
    page.speed_slider.setRange(0, 3500)
    page.speed_slider.setValue(1500)
    page.speed_slider.setFixedHeight(24)
    page.speed_slider.setMinimumWidth(120)
    capsule_layout.addWidget(page.speed_min_label)
    capsule_layout.addWidget(page.speed_slider, 1)

    page.speed_spinbox = QSpinBox()
    page.speed_spinbox.setRange(0, 7000)
    page.speed_spinbox.setValue(1500)
    page.speed_spinbox.setSuffix(" RPM")
    page.speed_spinbox.setFixedWidth(136)
    page.speed_spinbox.setFixedHeight(32)
    page.speed_spinbox.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    page.speed_slider.valueChanged.connect(page.speed_spinbox.setValue)
    page.speed_spinbox.valueChanged.connect(page.speed_slider.setValue)

    interval_label = QLabel("下发间隔")
    interval_label.setObjectName("Hint")
    page.speed_interval_spin = QSpinBox()
    page.speed_interval_spin.setRange(50, 5000)
    page.speed_interval_spin.setSingleStep(10)
    page.speed_interval_spin.setValue(250)
    page.speed_interval_spin.setSuffix(" ms")
    page.speed_interval_spin.setFixedWidth(108)
    page.speed_interval_spin.setFixedHeight(32)
    page.speed_interval_spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    page.speed_interval_spin.setToolTip("运行中按此间隔周期重发目标转速 0x01")
    page.speed_interval_spin.valueChanged.connect(page.on_speed_interval_changed)

    control_row.addWidget(page.speed_slider_capsule, 1)
    control_row.addWidget(page.speed_spinbox)
    control_row.addWidget(interval_label)
    control_row.addWidget(page.speed_interval_spin)
    layout.addWidget(page.control_panel)

    # ---- 波形 + 右栏 ----
    main_row = QHBoxLayout()
    main_row.setSpacing(10)

    grid_widget = QWidget()
    grid = QGridLayout(grid_widget)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(8)
    page.plot_widgets = [None, None, None, None]
    page.select_btns = []
    page.area_curves = [[], [], [], []]
    page.area_config = [None, None, None, None]
    for index in range(4):
        card = build_waveform_card(page, index)
        grid.addWidget(card, index // 2, index % 2)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    grid.setRowStretch(0, 1)
    grid.setRowStretch(1, 1)
    main_row.addWidget(grid_widget, 1)

    rail = QWidget()
    rail.setFixedWidth(224)
    rail_layout = QVBoxLayout(rail)
    rail_layout.setContentsMargins(0, 0, 0, 0)
    rail_layout.setSpacing(10)

    range_card = SectionCard("转速范围", "仅电机控制模式可用")
    page.range_btn_min = QPushButton("0 ~ 3500 RPM")
    page.range_btn_max = QPushButton("0 ~ 7000 RPM")
    page.range_btn_min.setObjectName("RangeChip")
    page.range_btn_max.setObjectName("RangeChip")
    page.range_btn_min.setCursor(Qt.PointingHandCursor)
    page.range_btn_max.setCursor(Qt.PointingHandCursor)
    page.range_btn_min.clicked.connect(page.select_range_min)
    page.range_btn_max.clicked.connect(page.select_range_max)
    page.range_btn_min.setEnabled(False)
    page.range_btn_max.setEnabled(False)
    range_card.body.addWidget(page.range_btn_min)
    range_card.body.addWidget(page.range_btn_max)
    rail_layout.addWidget(range_card)

    rail_layout.addWidget(build_startup_card(page))
    rail_layout.addStretch(1)
    main_row.addWidget(rail)
    layout.addLayout(main_row, 1)

    page.update_sub_nav(2)
    return page_widget


def build_startup_card(page) -> SectionCard:
    card = SectionCard("启动参数", "0x08 / 0x0A · 掉电恢复默认")
    grid = QGridLayout()
    grid.setHorizontalSpacing(6)
    grid.setVerticalSpacing(5)

    def add_row(row, text, widget):
        label = QLabel(text)
        label.setObjectName("KvKey")
        grid.addWidget(label, row, 0)
        widget.setFixedHeight(28)
        widget.setFixedWidth(102)
        grid.addWidget(widget, row, 1)
        return widget

    align_current = QDoubleSpinBox()
    align_current.setRange(0.1, 5.0)
    align_current.setDecimals(2)
    align_current.setSingleStep(0.1)
    align_current.setSuffix(" A")
    add_row(0, "对齐电流", align_current)

    align_time = QSpinBox()
    align_time.setRange(10, 10000)
    align_time.setSingleStep(10)
    align_time.setSuffix(" ms")
    add_row(1, "对齐时间", align_time)

    openloop_current = QDoubleSpinBox()
    openloop_current.setRange(0.1, 5.0)
    openloop_current.setDecimals(2)
    openloop_current.setSingleStep(0.1)
    openloop_current.setSuffix(" A")
    add_row(2, "强拖电流", openloop_current)

    openloop_time = QSpinBox()
    openloop_time.setRange(100, 30000)
    openloop_time.setSingleStep(100)
    openloop_time.setSuffix(" ms")
    add_row(3, "强拖时间", openloop_time)

    openloop_freq = QDoubleSpinBox()
    openloop_freq.setRange(60.0, 500.0)
    openloop_freq.setDecimals(1)
    openloop_freq.setSingleStep(1.0)
    openloop_freq.setSuffix(" Hz")
    add_row(4, "强拖频率", openloop_freq)

    # 协议默认值，读取成功后由 0x0A 覆盖。
    align_current.setValue(1.0)
    align_time.setValue(1000)
    openloop_current.setValue(1.5)
    openloop_time.setValue(3000)
    openloop_freq.setValue(120.0)
    page.startup_spins = {
        "align_current": align_current,
        "align_time": align_time,
        "openloop_current": openloop_current,
        "openloop_time": openloop_time,
        "openloop_freq": openloop_freq,
    }
    card.body.addLayout(grid)

    row = QHBoxLayout()
    row.setSpacing(6)
    page.read_startup_btn = _small_button("读取")
    page.write_startup_btn = _small_button("写入")
    page.read_startup_btn.clicked.connect(page.read_startup_config)
    page.write_startup_btn.clicked.connect(page.write_startup_config)
    row.addWidget(page.read_startup_btn)
    row.addWidget(page.write_startup_btn)
    row.addStretch(1)
    card.body.addLayout(row)
    return card


def make_telemetry_chip(page, chips_row, text, bit, key):
    button = QPushButton(text)
    button.setObjectName("TelemetryChip")
    button.setCursor(Qt.PointingHandCursor)
    button.setFixedHeight(32)
    button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    button.ensurePolished()
    button.setMinimumWidth(button.sizeHint().width())
    chips_row.addWidget(button)
    if key == "adc1":
        button.clicked.connect(lambda: page.toggle_single_telemetry(0, button))
    elif key == "adc2":
        button.clicked.connect(lambda: page.toggle_single_telemetry(1, button))
    elif key == "three":
        button.clicked.connect(page.toggle_three_phase_telemetry)
    elif key == "dpi":
        button.clicked.connect(page.toggle_dpi_mode)
    elif key == "qpi":
        button.clicked.connect(page.toggle_qpi_mode)
    else:
        button.clicked.connect(lambda: page.toggle_single_telemetry(bit, button))
    return button


def build_waveform_card(page, index: int) -> QFrame:
    card = QFrame()
    card.setObjectName("WaveformCard")
    card.setMinimumHeight(176)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(7, 6, 7, 6)
    layout.setSpacing(4)

    head = QHBoxLayout()
    head.setSpacing(6)
    title = QLabel(f"波形 {index + 1}")
    title.setObjectName("CardSub")
    head.addWidget(title)
    head.addStretch(1)
    channel_btn = QPushButton("—")
    channel_btn.setObjectName("ChannelBtn")
    channel_btn.setCursor(Qt.PointingHandCursor)
    channel_btn.setMinimumWidth(104)
    channel_btn.clicked.connect(lambda: page.show_selection_popup(index))
    head.addWidget(channel_btn)
    page.select_btns.append(channel_btn)
    layout.addLayout(head)

    plot = FocPlotWidget(background=None)
    plot.setAntialiasing(True)
    plot.setMinimumHeight(110)
    plot.setMenuEnabled(False)
    plot.showGrid(x=True, y=True, alpha=0.18)
    plot.setLabel("left", "值")
    plot.setLabel("bottom", "时间", units="s")
    axis_style = {"color": C.MUTED, "font-size": "9pt"}
    plot.getPlotItem().getAxis("left").setTextPen(pg.mkPen(**axis_style))
    plot.getPlotItem().getAxis("bottom").setTextPen(pg.mkPen(**axis_style))
    plot.getPlotItem().getAxis("left").setPen(pg.mkPen("#1B3558"))
    plot.getPlotItem().getAxis("bottom").setPen(pg.mkPen("#1B3558"))
    # 不在每次 setData 时自动缩放，由 update_waveforms 限频调用 autoRange。
    plot.disableAutoRange()
    page.plot_widgets[index] = plot
    layout.addWidget(plot, 1)
    return card


# ======================================================================
# 通讯信息
# ======================================================================
def build_comm_page(page) -> QWidget:
    page_widget = QWidget()
    page_widget.setObjectName("Page")
    layout = QVBoxLayout(page_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    card = SectionCard("通信日志", "FOC 协议帧 / 参数变更 / 错误")
    page.log_filter = QComboBox()
    page.log_filter.addItems(["全部", "仅Tx", "仅Rx", "仅错误", "仅参数"])
    page.log_filter.setFixedWidth(100)
    page.log_filter.currentTextChanged.connect(page._rebuild_log)
    page.clear_log_btn = _small_button("清空日志")
    page.save_log_btn = _small_button("保存日志")
    page.clear_log_btn.clicked.connect(page.clear_log)
    page.save_log_btn.clicked.connect(page.save_log)
    card.header.addWidget(page.log_filter)
    card.header.addWidget(page.clear_log_btn)
    card.header.addWidget(page.save_log_btn)

    page.log_area = LimitedTextEdit(max_blocks=5000)
    page.log_area.setReadOnly(True)
    page.log_area.setObjectName("FocLog")
    page.log_area.setFont(QFont("Consolas", 9))
    card.body.addWidget(page.log_area, 1)

    page.assistant_send_row = QWidget()
    send_layout = QHBoxLayout(page.assistant_send_row)
    send_layout.setContentsMargins(0, 0, 0, 0)
    send_layout.setSpacing(7)
    page.assistant_hex_chk = QCheckBox("HEX 发送")
    page.assistant_input = QLineEdit()
    page.assistant_input.setPlaceholderText(
        "输入要发送的数据，按回车发送…（HEX 示例：5A 01 02 03）"
    )
    page.assistant_input.returnPressed.connect(page.assistant_send)
    assistant_send = QPushButton("发送")
    assistant_send.setObjectName("Primary")
    assistant_send.clicked.connect(page.assistant_send)
    send_layout.addWidget(page.assistant_hex_chk)
    send_layout.addWidget(page.assistant_input, 1)
    send_layout.addWidget(assistant_send)
    page.assistant_send_row.hide()
    card.body.addWidget(page.assistant_send_row)

    hint = QLabel(
        "串口助手模式下数据只透传、不解析 FOC 协议；关闭助手模式后恢复正常帧解析。"
    )
    hint.setObjectName("Hint")
    card.body.addWidget(hint)
    layout.addWidget(card, 1)
    return page_widget
