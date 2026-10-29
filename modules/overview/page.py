# -*- coding: utf-8 -*-
"""控制中心总览页。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.icons import draw_icon
from core.theme import C
from core.widgets import LogoMark, SectionCard
from modules.registry import ModuleSpec


class ModuleCard(QFrame):
    open_requested = Signal(str)

    def __init__(self, spec: ModuleSpec, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.setObjectName("ModuleCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(206)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(19, 17, 19, 16)
        layout.setSpacing(9)

        head = QHBoxLayout()
        head.setSpacing(12)
        icon = QLabel()
        icon.setFixedSize(54, 54)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(
            "background-color:#0B2A4A; border:1px solid #1E4A7E; border-radius:13px;"
        )
        icon.setPixmap(draw_icon(spec.icon_name, C.BLUE, 30))
        head.addWidget(icon)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        name = QLabel(spec.name)
        name.setObjectName("ModuleTitle")
        subtitle = QLabel(spec.subtitle)
        subtitle.setObjectName("ModuleDesc")
        titles.addWidget(name)
        titles.addWidget(subtitle)
        head.addLayout(titles)
        head.addStretch(1)
        self.status_label = QLabel("串口未连接")
        self.status_label.setObjectName("Hint")
        head.addWidget(self.status_label, 0, Qt.AlignTop)
        layout.addLayout(head)

        desc = QLabel(spec.description)
        desc.setObjectName("ModuleDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        tags = QHBoxLayout()
        tags.setSpacing(5)
        for tag in spec.tags:
            label = QLabel(tag)
            label.setObjectName("Tag")
            tags.addWidget(label)
        tags.addStretch(1)
        layout.addLayout(tags)
        layout.addStretch(1)

        bottom = QHBoxLayout()
        self.enter_btn = QPushButton("进入模块  →")
        self.enter_btn.setObjectName("Primary")
        self.enter_btn.setCursor(Qt.PointingHandCursor)
        self.enter_btn.setFixedWidth(126)
        self.enter_btn.clicked.connect(lambda: self.open_requested.emit(self.spec.key))
        bottom.addWidget(self.enter_btn)
        bottom.addStretch(1)
        layout.addLayout(bottom)

    def set_connected(self, connected: bool):
        if connected:
            self.status_label.setText("● 串口已连接")
            self.status_label.setStyleSheet(
                f"color:{C.GREEN}; font-size:11px; font-weight:600;"
            )
        else:
            self.status_label.setText("串口未连接")
            self.status_label.setStyleSheet(f"color:{C.DIM}; font-size:11px;")

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self.spec.key)
        super().mouseReleaseEvent(event)


class OverviewPage(QWidget):
    open_module = Signal(str)

    def __init__(self, specs: tuple[ModuleSpec, ...], parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.specs = specs
        self.cards: dict[str, ModuleCard] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget()
        page.setObjectName("Page")
        page.setMinimumHeight(600)
        scroll.setWidget(page)
        outer.addWidget(scroll)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # ---- Hero ----
        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(18)
        hero_layout.addWidget(LogoMark(58))
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("嵌入式控制中心")
        title.setObjectName("HeroTitle")
        sub = QLabel("2.4G 温湿度 + FOC 电机控制，一个窗口完成调试、监控与参数管理。")
        sub.setObjectName("HeroSub")
        sub.setWordWrap(True)
        titles.addWidget(title)
        titles.addWidget(sub)
        hero_layout.addLayout(titles, 1)
        right = QVBoxLayout()
        right.setSpacing(5)
        badge = QLabel(f"{len(specs)} MODULES")
        badge.setObjectName("HeroBadge")
        badge.setAlignment(Qt.AlignCenter)
        hint = QLabel("独立串口 · 互不干扰")
        hint.setObjectName("Hint")
        hint.setAlignment(Qt.AlignCenter)
        right.addWidget(badge)
        right.addWidget(hint)
        hero_layout.addLayout(right)
        layout.addWidget(hero)

        # ---- 模块卡片 ----
        section = QHBoxLayout()
        section_title = QLabel("功能模块")
        section_title.setObjectName("CardTitle")
        section.addWidget(section_title)
        section.addStretch(1)
        section_hint = QLabel("选择左侧模块或点击下方卡片进入")
        section_hint.setObjectName("Hint")
        section.addWidget(section_hint)
        layout.addLayout(section)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for index, spec in enumerate(specs):
            card = ModuleCard(spec)
            card.open_requested.connect(self.open_module.emit)
            self.cards[spec.key] = card
            grid.addWidget(card, 0, index)
            grid.setColumnStretch(index, 1)
        self.cards = self.cards

        add_card = QFrame()
        add_card.setObjectName("AddCard")
        add_card.setMinimumHeight(206)
        add_layout = QVBoxLayout(add_card)
        add_layout.setContentsMargins(18, 18, 18, 18)
        add_layout.setSpacing(6)
        add_layout.addStretch(1)
        plus = QLabel()
        plus.setAlignment(Qt.AlignCenter)
        plus.setPixmap(draw_icon("plus", C.DIM, 30))
        add_layout.addWidget(plus)
        add_title = QLabel("扩展模块")
        add_title.setObjectName("AddTitle")
        add_title.setAlignment(Qt.AlignCenter)
        add_layout.addWidget(add_title)
        add_desc = QLabel("在 modules/ 下新增页面并注册即可")
        add_desc.setObjectName("AddDesc")
        add_desc.setAlignment(Qt.AlignCenter)
        add_desc.setWordWrap(True)
        add_layout.addWidget(add_desc)
        add_layout.addStretch(1)
        grid.addWidget(add_card, 0, len(specs))
        grid.setColumnStretch(len(specs), 1)
        layout.addLayout(grid)

        # ---- 底部说明 ----
        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        quick = SectionCard("快速开始", "三步进入调试")
        steps = QLabel(
            "1. 在左侧选择 2.4G 或 FOC 模块\n"
            "2. 在页面顶部选择串口并打开（默认 115200-8N1）\n"
            "3. 监控数据 / 调整参数；模块之间串口互不影响"
        )
        steps.setObjectName("Hint")
        steps.setWordWrap(True)
        steps.setStyleSheet("line-height: 160%;")
        quick.body.addWidget(steps)
        bottom.addWidget(quick, 1)

        design = SectionCard("设计说明", "为后续模块预留")
        design_text = QLabel(
            "· 公共主题、控件、串口线程集中在 core/\n"
            "· 每个功能一个独立模块，按注册表加入侧边栏\n"
            "· FOC 原有协议、遥测、PID、DRV 逻辑保持不变"
        )
        design_text.setObjectName("Hint")
        design_text.setWordWrap(True)
        design_text.setStyleSheet("line-height: 160%;")
        design.body.addWidget(design_text)
        bottom.addWidget(design, 1)
        layout.addLayout(bottom)
        layout.addStretch(1)

    def set_module_connected(self, key: str, connected: bool):
        card = self.cards.get(key)
        if card is not None:
            card.set_connected(connected)
