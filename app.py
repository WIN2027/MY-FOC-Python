# -*- coding: utf-8 -*-
"""嵌入式控制中心入口：可收起侧边栏 + 模块页面栈。"""

from __future__ import annotations

import sys
import time
import traceback

from PySide6.QtCore import QLibraryInfo, QSize, Qt, QTimer, QTranslator
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.icons import app_icon, draw_icon, make_icon
from core.settings import AppSettings
from core.theme import C, build_stylesheet, dark_palette
from core.widgets import StatusPill
from modules.overview.about import AboutPage
from modules.overview.page import OverviewPage
from modules.registry import MODULE_SPECS, ModuleSpec


class ControlCenter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("嵌入式控制中心 · 2.4G / FOC")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1280, 800)
        self.resize(1480, 920)
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(
                min(1480, max(1280, available.width() - 60)),
                min(920, max(800, available.height() - 60)),
            )

        self.settings = AppSettings()
        self.pages: dict[str, QWidget] = {}
        self.specs: dict[str, ModuleSpec] = {spec.key: spec for spec in MODULE_SPECS}
        self.current_key = ""

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = None
        from core.sidebar import Sidebar

        self.sidebar = Sidebar()
        self.sidebar.add_section("工作台")
        self.sidebar.add_item("overview", "总览", "overview")
        self.sidebar.add_section("功能模块")
        for spec in MODULE_SPECS:
            self.sidebar.add_item(spec.key, spec.name, spec.icon_name)
        self.sidebar.add_section("系统")
        self.sidebar.add_item("about", "关于", "about")
        self.sidebar.item_selected.connect(self.switch_to)
        self.sidebar.collapsed_changed.connect(self._on_sidebar_collapsed)
        outer.addWidget(self.sidebar)

        main = QWidget()
        main.setObjectName("MainPane")
        layout = QVBoxLayout(main)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)
        layout.addLayout(self._build_header())

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        outer.addWidget(main, 1)

        self.overview = OverviewPage(MODULE_SPECS)
        self.overview.open_module.connect(self.switch_to)
        self._add_page("overview", self.overview)

        for spec in MODULE_SPECS:
            page = spec.factory(self.settings)
            self._add_page(spec.key, page)
            signal = getattr(page, "connection_changed", None)
            if signal is not None:
                signal.connect(
                    lambda connected, key=spec.key: self._on_module_connection(
                        key, connected
                    )
                )

        self.about = AboutPage()
        self._add_page("about", self.about)

        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._tick_clock)
        self.clock_timer.start()

        shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut.setContext(Qt.WindowShortcut)
        shortcut.activated.connect(self.toggle_sidebar)

        self._restore_settings()
        self._tick_clock()

    def _add_page(self, key: str, page: QWidget):
        self.pages[key] = page
        self.stack.addWidget(page)

    # ------------------------------------------------------------------
    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(12)
        self.page_icon = QLabel()
        self.page_icon.setFixedSize(42, 42)
        self.page_icon.setAlignment(Qt.AlignCenter)
        header.addWidget(self.page_icon)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.page_title = QLabel("控制中心")
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel("总览与模块入口")
        self.page_subtitle.setObjectName("PageSub")
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_subtitle)
        header.addLayout(titles)
        header.addStretch(1)

        self.status_pill = StatusPill("就绪")
        header.addWidget(self.status_pill)

        self.clock_label = QLabel("")
        self.clock_label.setObjectName("Clock")
        self.clock_label.setMinimumWidth(140)
        self.clock_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.clock_label)

        self.sidebar_btn = QPushButton()
        self.sidebar_btn.setObjectName("Ghost")
        self.sidebar_btn.setFixedSize(34, 34)
        self.sidebar_btn.setToolTip("收起 / 展开侧边栏 (Ctrl+B)")
        self.sidebar_btn.clicked.connect(self.toggle_sidebar)
        header.addWidget(self.sidebar_btn)
        return header

    def _restore_settings(self):
        geometry = self.settings.get("ui/geometry")
        if geometry is not None:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(
                min(self.width(), max(1280, available.width() - 20)),
                min(self.height(), max(800, available.height() - 50)),
            )
        collapsed = self.settings.get("ui/sidebar_collapsed", False, bool)
        self.sidebar.set_collapsed(bool(collapsed), emit=False)
        self._update_sidebar_button()
        last = str(self.settings.get("ui/last_module", "overview"))
        if last not in self.pages:
            last = "overview"
        self.switch_to(last)

    def switch_to(self, key: str):
        if key not in self.pages:
            key = "overview"
        if key == self.current_key:
            return
        old = self.pages.get(self.current_key)
        if old is not None and hasattr(old, "on_hidden"):
            old.on_hidden()
        self.current_key = key
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active(key)
        if hasattr(page, "on_shown"):
            page.on_shown()

        if key == "overview":
            self.page_title.setText("控制中心")
            self.page_subtitle.setText("2.4G 温湿度 · FOC 电机控制 · 模块化扩展")
            self.page_icon.setPixmap(draw_icon("overview", C.BLUE, 26))
            self.status_pill.set_state(f"{len(MODULE_SPECS)} 个模块", C.BLUE)
        elif key == "about":
            self.page_title.setText("关于")
            self.page_subtitle.setText("版本、依赖、路径与快捷键")
            self.page_icon.setPixmap(draw_icon("about", C.BLUE, 26))
            self.status_pill.set_state("v1.0.0", C.VIOLET)
        else:
            spec = self.specs.get(key)
            if spec is not None:
                self.page_title.setText(spec.name)
                self.page_subtitle.setText(spec.subtitle)
                self.page_icon.setPixmap(draw_icon(spec.icon_name, C.BLUE, 26))
            self._refresh_module_status()
        self.settings.set("ui/last_module", key)

    def _refresh_module_status(self):
        page = self.pages.get(self.current_key)
        connected = bool(getattr(page, "is_connected", False))
        if connected:
            self.status_pill.set_state("串口已连接", C.GREEN)
        else:
            self.status_pill.set_state("串口未连接", C.DIM)

    def _on_module_connection(self, key: str, connected: bool):
        self.overview.set_module_connected(key, connected)
        if key == self.current_key:
            self.status_pill.set_state(
                "串口已连接" if connected else "串口未连接",
                C.GREEN if connected else C.DIM,
            )

    def _on_sidebar_collapsed(self, collapsed: bool):
        self.settings.set("ui/sidebar_collapsed", bool(collapsed))
        self._update_sidebar_button()

    def toggle_sidebar(self):
        self.sidebar.set_collapsed(not self.sidebar.is_collapsed())

    def _update_sidebar_button(self):
        icon_name = "expand_right" if self.sidebar.is_collapsed() else "collapse_left"
        self.sidebar_btn.setIcon(make_icon(icon_name, C.MUTED, 18))
        self.sidebar_btn.setIconSize(QSize(18, 18))

    def _tick_clock(self):
        self.clock_label.setText(time.strftime("%Y-%m-%d %H:%M:%S"))
        if self.current_key not in ("overview", "about"):
            self._refresh_module_status()

    # ------------------------------------------------------------------
    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if not getattr(self, "_titlebar_done", False):
            self._titlebar_done = True
            QTimer.singleShot(0, self._apply_dark_titlebar)

    def _apply_dark_titlebar(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi
            enabled = ctypes.c_int(1)
            for attribute in (20, 19):
                if (
                    dwm.DwmSetWindowAttribute(
                        hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
                    )
                    == 0
                ):
                    break
            caption = ctypes.c_int(0x00261207)
            border = ctypes.c_int(0x00593017)
            text = ctypes.c_int(0x00FAE8DC)
            for attribute, value in ((35, caption), (34, border), (36, text)):
                dwm.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
                )
        except Exception:
            pass

    def closeEvent(self, event):  # noqa: N802
        try:
            self.settings.set("ui/geometry", self.saveGeometry())
            self.settings.set("ui/sidebar_collapsed", self.sidebar.is_collapsed())
            self.settings.set("ui/last_module", self.current_key)
        except Exception:
            pass
        self.clock_timer.stop()
        for page in self.pages.values():
            shutdown = getattr(page, "shutdown", None)
            if shutdown is not None:
                try:
                    shutdown()
                except Exception:
                    traceback.print_exc()
        try:
            self.settings.sync()
        except Exception:
            pass
        event.accept()


def _install_excepthook():
    def hook(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        sys.stderr.write(text)
        try:
            QMessageBox.critical(None, "程序异常", text[-2500:])
        except Exception:
            pass

    sys.excepthook = hook


def main():
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "LoRaTools.ControlCenter"
            )
        except Exception:
            pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(build_stylesheet())
    app.setApplicationName("嵌入式控制中心")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("LoRaTools")
    app.setWindowIcon(app_icon())

    translator = QTranslator()
    translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load("qtbase_zh_CN", translations):
        app.installTranslator(translator)
        app._translator = translator

    _install_excepthook()
    window = ControlCenter()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
