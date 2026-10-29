# -*- coding: utf-8 -*-
"""关于页。"""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.theme import APP_DIR
from core.widgets import LogoMark, SectionCard


class AboutPage(QWidget):
    title = "关于"
    subtitle = "版本、依赖、路径与快捷键"
    icon_name = "about"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget()
        page.setObjectName("Page")
        page.setMinimumHeight(560)
        scroll.setWidget(page)
        outer.addWidget(scroll)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 18, 22, 18)
        hero_layout.setSpacing(14)
        hero_layout.addWidget(LogoMark(48))
        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("嵌入式控制中心")
        title.setObjectName("HeroTitle")
        title.setStyleSheet("font-size:22px;")
        sub = QLabel("v1.0.0 · 模块化上位机框架")
        sub.setObjectName("HeroSub")
        titles.addWidget(title)
        titles.addWidget(sub)
        hero_layout.addLayout(titles)
        hero_layout.addStretch(1)
        open_btn = QPushButton("打开项目目录")
        open_btn.setObjectName("Primary")
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(APP_DIR)))
        )
        hero_layout.addWidget(open_btn)
        layout.addWidget(hero)

        modules = SectionCard("已加载模块", "通过 modules/registry.py 注册")
        module_text = QLabel(
            "● 2.4G 温湿度：SX1280 + HDC1080，自动识别 0x18 / 0x19，双 Y 轴曲线。\n"
            "● FOC 电机控制：DRV8320S 配置、D/Q/速度环 PID、4 通道波形、电机启停。\n"
            "● 每个模块使用独立串口连接，切换模块不会中断另一个模块的接收。"
        )
        module_text.setObjectName("Hint")
        module_text.setWordWrap(True)
        module_text.setStyleSheet("line-height: 160%;")
        modules.body.addWidget(module_text)
        layout.addWidget(modules)

        stack = SectionCard("技术栈与运行环境", "本机信息")
        env_text = QLabel(
            f"Python {platform.python_version()}　|　PySide6 6.11.1　|　"
            f"pyqtgraph 0.14.0　|　pyserial 3.5\n"
            f"系统：{platform.system()} {platform.release()}\n"
            f"配置：{APP_DIR / 'settings.ini'}\n"
            f"FOC 预设/PID：{APP_DIR / 'config'}"
        )
        env_text.setObjectName("Hint")
        env_text.setWordWrap(True)
        env_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        stack.body.addWidget(env_text)
        layout.addWidget(stack)

        shortcuts = SectionCard("快捷键", "仅当前模块生效")
        shortcut_text = QLabel(
            "Ctrl + B：收起 / 展开侧边栏\n"
            "2.4G：Ctrl + Enter 发送；Ctrl + O 打开/关闭串口\n"
            "FOC：Ctrl + O 打开/关闭串口；Ctrl + S 保存日志；F5 刷新从机；Alt + P 暂停波形"
        )
        shortcut_text.setObjectName("Hint")
        shortcut_text.setWordWrap(True)
        shortcut_text.setStyleSheet("line-height: 160%;")
        shortcuts.body.addWidget(shortcut_text)
        layout.addWidget(shortcuts)

        extend = SectionCard("如何新增一个模块", "面向后续扩展")
        extend_text = QLabel(
            "1. 在 modules/ 下新建一个包，实现 QWidget 页面；\n"
            "2. 页面提供 title / subtitle / icon_name，可选 on_shown / on_hidden / shutdown；\n"
            "3. 在 modules/registry.py 的 MODULE_SPECS 中增加一条记录；\n"
            "4. 侧边栏、总览卡片和页面栈会自动出现新模块。"
        )
        extend_text.setObjectName("Hint")
        extend_text.setWordWrap(True)
        extend_text.setStyleSheet("line-height: 160%;")
        extend.body.addWidget(extend_text)
        layout.addWidget(extend)
        layout.addStretch(1)
