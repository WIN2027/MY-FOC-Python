# -*- coding: utf-8 -*-
"""可收起的应用侧边栏。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .icons import make_icon, nav_icon
from .theme import C
from .widgets import LogoMark


class Sidebar(QFrame):
    item_selected = Signal(str)
    collapsed_changed = Signal(bool)

    EXPANDED_WIDTH = 226
    COLLAPSED_WIDTH = 72

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._collapsed = False
        self._items: dict[str, QPushButton] = {}
        self._texts: dict[str, str] = {}
        self._sections: list[QLabel] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(12, 16, 12, 12)
        self._root.setSpacing(2)

        self._header = QHBoxLayout()
        self._header.setSpacing(10)
        self._logo = LogoMark(38)
        self._header.addWidget(self._logo)
        self._brand_box = QVBoxLayout()
        self._brand_box.setSpacing(0)
        self._brand_title = QLabel("控制中心")
        self._brand_title.setObjectName("BrandTitle")
        self._brand_sub = QLabel("CONTROL CENTER")
        self._brand_sub.setObjectName("BrandSub")
        self._brand_box.addWidget(self._brand_title)
        self._brand_box.addWidget(self._brand_sub)
        self._header.addLayout(self._brand_box)
        self._header.addStretch(1)
        self._root.addLayout(self._header)
        self._root.addSpacing(24)

        self._nav_layout = QVBoxLayout()
        self._nav_layout.setSpacing(2)
        self._root.addLayout(self._nav_layout)
        self._root.addStretch(1)

        self._bottom_card = QFrame()
        self._bottom_card.setObjectName("SideCard")
        card_layout = QVBoxLayout(self._bottom_card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(2)
        card_title = QLabel("独立模块 · 独立串口")
        card_title.setObjectName("Hint")
        card_sub = QLabel("2.4G / FOC 可同时连接")
        card_sub.setObjectName("Hint")
        card_layout.addWidget(card_title)
        card_layout.addWidget(card_sub)
        self._root.addWidget(self._bottom_card)
        self._root.addSpacing(8)

        self._collapse_btn = QPushButton("收起侧栏")
        self._collapse_btn.setObjectName("CollapseBtn")
        self._collapse_btn.setIcon(make_icon("collapse_left", C.MUTED, 18))
        self._collapse_btn.setIconSize(QSize(16, 16))
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.clicked.connect(self.toggle)
        self._root.addWidget(self._collapse_btn)

        self._version = QLabel("v1.0.0 · MODULAR UI")
        self._version.setObjectName("SideVersion")
        self._version.setAlignment(Qt.AlignCenter)
        self._root.addWidget(self._version)

        self.setFixedWidth(self.EXPANDED_WIDTH)

    def add_section(self, text: str):
        label = QLabel(text)
        label.setObjectName("SideSection")
        label.setContentsMargins(10, 8, 0, 4)
        self._sections.append(label)
        self._nav_layout.addWidget(label)

    def add_item(self, key: str, text: str, icon_name: str):
        button = QPushButton(text)
        button.setObjectName("NavItem")
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        button.setIcon(nav_icon(icon_name, 20))
        button.setIconSize(QSize(20, 20))
        button.setFixedHeight(42)
        button.clicked.connect(lambda _=False, k=key: self.item_selected.emit(k))
        self._group.addButton(button)
        self._items[key] = button
        self._texts[key] = text
        self._nav_layout.addWidget(button)
        return button

    def set_active(self, key: str):
        button = self._items.get(key)
        if button is not None:
            button.setChecked(True)

    def current_key(self) -> str | None:
        for key, button in self._items.items():
            if button.isChecked():
                return key
        return None

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool, emit: bool = True):
        collapsed = bool(collapsed)
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._brand_box.itemAt(0).widget().setVisible(not collapsed)
        self._brand_box.itemAt(1).widget().setVisible(not collapsed)
        for label in self._sections:
            label.setVisible(not collapsed)
        self._bottom_card.setVisible(not collapsed)
        self._version.setVisible(not collapsed)
        self._header.setAlignment(
            self._logo,
            Qt.AlignHCenter | Qt.AlignVCenter if collapsed else Qt.AlignLeft | Qt.AlignVCenter,
        )
        for key, button in self._items.items():
            if collapsed:
                button.setText("")
                button.setIconSize(QSize(22, 22))
                button.setToolTip(self._texts[key])
                button.setFixedHeight(44)
            else:
                button.setText(self._texts[key])
                button.setIconSize(QSize(20, 20))
                button.setToolTip("")
                button.setFixedHeight(42)
        if collapsed:
            self._collapse_btn.setText("")
            self._collapse_btn.setIcon(make_icon("expand_right", C.MUTED, 18))
            self._collapse_btn.setToolTip("展开侧栏")
            self.setFixedWidth(self.COLLAPSED_WIDTH)
        else:
            self._collapse_btn.setText("收起侧栏")
            self._collapse_btn.setIcon(make_icon("collapse_left", C.MUTED, 18))
            self._collapse_btn.setToolTip("收起侧栏")
            self.setFixedWidth(self.EXPANDED_WIDTH)
        if emit:
            self.collapsed_changed.emit(collapsed)

    def toggle(self):
        self.set_collapsed(not self._collapsed)
