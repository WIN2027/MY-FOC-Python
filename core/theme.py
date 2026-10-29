# -*- coding: utf-8 -*-
"""控制中心视觉主题：深蓝色板、QSS、图标资源生成。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)

APP_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = APP_DIR / "assets"


class C:
    """深蓝主题色板。"""

    BG = "#040A16"
    PANEL = "#071226"
    CARD = "#0A1830"
    CARD_DARK = "#081427"
    BORDER = "#17315A"
    BORDER_HI = "#24497A"
    TEXT = "#DCE8FA"
    MUTED = "#7C93B4"
    DIM = "#50698C"
    BLUE = "#3B82F6"
    BLUE_DARK = "#2459C9"
    CYAN = "#38BDF8"
    TEAL = "#2DD4BF"
    VIOLET = "#9AA7FF"
    GREEN = "#34D399"
    AMBER = "#FBBF24"
    RED = "#F87171"
    PINK = "#F472B6"


def q_rgba(color: str, alpha: float) -> str:
    c = QColor(color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


APP_QSS = """
QWidget {
    color: #DCE8FA;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 13px;
}
QMainWindow { background-color: #040A16; }
QWidget#Root { background-color: #040A16; }
QWidget#MainPane {
    background: qradialgradient(cx:0.82, cy:0.0, radius:1.15, fx:0.82, fy:0.0,
        stop:0 #0B1E3C, stop:0.45 #060F20, stop:1 #040A16);
}
QWidget#Page { background: transparent; }
QLabel { background: transparent; }

/* ===================== 应用侧边栏 ===================== */
QFrame#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #07162E, stop:0.55 #050F20, stop:1 #040A16);
    border-right: 1px solid #12294A;
}
QLabel#BrandTitle {
    font-family: "Bahnschrift", "Segoe UI";
    font-size: 21px; font-weight: 700; color: #F3F8FF;
}
QLabel#BrandSub { font-size: 11px; color: #8FA6C8; }
QLabel#SideSection { font-size: 10px; color: #50698C; }
QPushButton#NavItem {
    text-align: left; background: transparent; border: none;
    border-left: 3px solid transparent; border-radius: 9px;
    padding: 10px 10px; color: #8FA6C8; font-size: 13px;
}
QPushButton#NavItem:hover { background-color: #0A1B34; color: #E8F1FF; }
QPushButton#NavItem:checked {
    background-color: #0E2548; color: #FFFFFF;
    border-left: 3px solid #3B82F6; font-weight: 600;
}
QPushButton#CollapseBtn {
    background-color: #081528; border: 1px solid #142B4E;
    border-radius: 7px; color: #7C93B4; padding: 6px 8px;
    font-size: 11px; text-align: center;
}
QPushButton#CollapseBtn:hover { background-color: #0E2140; color: #FFFFFF; border-color: #2B5688; }
QFrame#SideCard { background-color: #081528; border: 1px solid #142B4E; border-radius: 10px; }
QLabel#SideVersion { font-size: 10px; color: #42597A; }

/* ===================== 页面标题 / 顶栏 ===================== */
QLabel#PageTitle { font-size: 25px; font-weight: 700; color: #F4F9FF; }
QLabel#PageSub { font-size: 12px; color: #7C93B4; }
QLabel#Clock { font-family: "Bahnschrift", "Segoe UI"; font-size: 13px; color: #8FA6C8; }
QLabel#Pill { border-radius: 10px; padding: 4px 11px; font-size: 12px; }
QLabel#HeaderHint { font-size: 11px; color: #5E7699; }

/* ===================== 总览 / 模块卡片 ===================== */
QFrame#HeroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0C2A58, stop:0.55 #0A1B36, stop:1 #071226);
    border: 1px solid #1E4A7E; border-radius: 16px;
}
QLabel#HeroTitle { font-size: 26px; font-weight: 700; color: #F6FAFF; }
QLabel#HeroSub { font-size: 13px; color: #9FB6D8; }
QLabel#HeroBadge {
    color: #8FC7FF; background-color: #0B2A4A; border: 1px solid #1E4A7E;
    border-radius: 10px; padding: 4px 10px; font-size: 11px;
}
QFrame#ModuleCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0A1A33, stop:1 #071226);
    border: 1px solid #17315A; border-radius: 14px;
}
QFrame#ModuleCard:hover { border-color: #3B82F6; }
QLabel#ModuleTitle { font-size: 18px; font-weight: 700; color: #F3F8FF; }
QLabel#ModuleDesc { font-size: 12px; color: #7C93B4; }
QLabel#Tag {
    font-size: 10px; color: #8FC7FF; background-color: #0B2A4A;
    border-radius: 7px; padding: 2px 8px;
}
QFrame#AddCard {
    border: 1px dashed #24497A; border-radius: 14px; background: transparent;
}
QLabel#AddTitle { font-size: 15px; font-weight: 600; color: #5E7699; }
QLabel#AddDesc { font-size: 11px; color: #42597A; }

/* ===================== 二级模块标签 ===================== */
QFrame#ModuleTabs {
    background-color: #071226; border: 1px solid #142B4E;
    border-radius: 11px;
}
QPushButton#ModuleTab {
    background: transparent; border: none; border-radius: 8px;
    padding: 8px 16px; color: #7C93B4; font-size: 13px;
}
QPushButton#ModuleTab:hover { background-color: #0B1C36; color: #DCE8FA; }
QPushButton#ModuleTab:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1B4C8F, stop:1 #123766);
    color: #FFFFFF; font-weight: 600;
}

/* ===================== 串口条 ===================== */
QFrame#SerialBar { background-color: #081528; border: 1px solid #17315A; border-radius: 11px; }
QLabel#BarLabel { font-size: 12px; color: #7C93B4; }

/* ===================== 卡片 ===================== */
QFrame#Card {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A1A33, stop:1 #071226);
    border: 1px solid #17315A; border-radius: 13px;
}
QFrame#MetricCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0B1C38, stop:1 #071226);
    border: 1px solid #17315A; border-radius: 13px;
}
QFrame#MetricCard:hover { border-color: #28527F; }
QFrame#ParamCard {
    background-color: #081528; border: 1px solid #142B4E; border-radius: 9px;
}
QFrame#ParamCard:hover { border-color: #28527F; }
QFrame#PidCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A1A33, stop:1 #071226);
    border: 1px solid #17315A; border-radius: 12px;
}
QFrame#PidGroup {
    background-color: #071226; border: 1px solid #12294A; border-radius: 8px;
}
QFrame#WaveformCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #081629, stop:1 #061020);
    border: 1px solid #17315A; border-radius: 11px;
}
QLabel#CardTitle { font-size: 15px; font-weight: 600; color: #E9F2FF; }
QLabel#CardSub { font-size: 11px; color: #6E86A8; }
QLabel#SectionBadge {
    font-size: 10px; color: #8FC7FF; background-color: #0B2A4A;
    border-radius: 7px; padding: 2px 7px;
}
QLabel#MetricTitle { font-size: 12px; color: #8FA6C8; }
QLabel#MetricValue {
    font-family: "Bahnschrift", "Segoe UI";
    font-size: 31px; font-weight: 600; color: #F6FAFF;
}
QLabel#MetricUnit { font-size: 12px; color: #7C93B4; padding-bottom: 5px; }
QLabel#MetricSub { font-size: 11px; color: #6E86A8; }
QLabel#MetricBadge {
    font-size: 10px; color: #8FC7FF; background-color: #0B2A4A;
    border-radius: 7px; padding: 2px 7px;
}

/* ===================== 告警横幅 ===================== */
QFrame#Alert { border-radius: 9px; }
QLabel#AlertText { font-size: 12px; }
QLabel#AlertIcon { font-size: 13px; font-weight: 700; border-radius: 9px; }

/* ===================== 按钮 ===================== */
QPushButton {
    background-color: #0D2242; border: 1px solid #1E3D66; border-radius: 6px;
    padding: 7px 13px; color: #C9D9F0;
}
QPushButton:hover { background-color: #12305A; border-color: #2B5688; color: #FFFFFF; }
QPushButton:pressed { background-color: #0A1A33; }
QPushButton:disabled { color: #4E6484; border-color: #14294A; background-color: #081427; }
QPushButton#Primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3B82F6, stop:1 #2459C9);
    border: 1px solid #4A8CFF; color: #FFFFFF; font-weight: 600; padding: 7px 16px;
}
QPushButton#Primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4C90FF, stop:1 #2E66DD);
}
QPushButton#Primary:pressed { background: #1D4ED8; }
QPushButton#Primary:disabled {
    background: #122A4D; border-color: #1B3A63; color: #5E7699;
}
QPushButton#Danger {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #EF4444, stop:1 #B91C1C);
    border: 1px solid #F87171; color: #FFFFFF; font-weight: 600;
}
QPushButton#Danger:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F87171, stop:1 #DC2626);
}
QPushButton#Ghost { background: transparent; border: none; color: #8FA6C8; padding: 6px 8px; }
QPushButton#Ghost:hover { background-color: #0E2140; color: #FFFFFF; }
QPushButton#Ghost:disabled { color: #42597A; background: transparent; }
QPushButton#Chip {
    background-color: #0A1A33; border: 1px solid #1C3A61; border-radius: 12px;
    padding: 4px 12px; color: #7C93B4; font-size: 11px;
}
QPushButton#Chip:hover { border-color: #2B5688; color: #DCE8FA; }
QPushButton#Chip:checked { background-color: #102C52; color: #EAF4FF; border-color: #2F6FE4; }
QPushButton#Chip[caption="temp"]:checked {
    border-color: #38BDF8; color: #BAE6FD; background-color: #0B2A44;
}
QPushButton#Chip[caption="hum"]:checked {
    border-color: #2DD4BF; color: #A7F3D0; background-color: #0A2C2A;
}
QPushButton#RangeChip {
    background-color: #081528; border: 1px solid #1D3B63; border-radius: 6px;
    padding: 4px 8px; color: #7C93B4; font-size: 11px;
}
QPushButton#RangeChip:hover { border-color: #2B5688; color: #DCE8FA; }
QPushButton#RangeChip:checked {
    background-color: #15376A; border-color: #3B82F6; color: #EAF4FF; font-weight: 600;
}
QPushButton#TelemetryChip {
    background-color: #081528; border: 1px solid #1C3A61; border-radius: 8px;
    padding: 6px 12px; color: #7C93B4; font-size: 11px; text-align: left;
}
QPushButton#TelemetryChip:hover { border-color: #2B5688; color: #DCE8FA; }
QPushButton#TelemetryChip:checked {
    background-color: #0E2B4E; border-color: #38BDF8; color: #BAE6FD; font-weight: 600;
}
QPushButton#Chip[active="true"],
QPushButton#RangeChip[active="true"],
QPushButton#TelemetryChip[active="true"] {
    background-color: #15376A; border-color: #3B82F6; color: #EAF4FF; font-weight: 600;
}
QLabel#ParamLabel { font-size: 12px; color: #8FA6C8; }
QLabel#GroupLabel { font-size: 11px; color: #6E86A8; }
QLabel#MeasureValue {
    color: #FBBF24; font-family: "Bahnschrift", "Segoe UI";
    font-size: 15px; font-weight: 600;
}
QPushButton#ChannelBtn {
    background-color: #081528; border: 1px solid #1D3B63; border-radius: 6px;
    padding: 4px 9px; color: #A9BDD8; font-size: 11px; text-align: left;
}
QPushButton#ChannelBtn:hover { border-color: #3B82F6; color: #FFFFFF; }
QPushButton#ChannelBtn:disabled { color: #4E6484; border-color: #14294A; }

/* ===================== 输入 ===================== */
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #081528; border: 1px solid #1D3B63; border-radius: 6px;
    padding: 6px 9px; color: #DCE8FA; selection-background-color: #2459C9;
}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #2B5688; }
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #3B82F6; }
QComboBox:disabled, QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: #4E6484; background-color: #071226; border-color: #14294A;
}
QComboBox::drop-down {
    border: none; background-color: #081528; width: 24px;
    border-top-right-radius: 6px; border-bottom-right-radius: 6px;
}
QComboBox::drop-down:disabled { background-color: #071226; }
QComboBox::down-arrow { image: url("__CHEVRON_DOWN__"); width: 10px; height: 6px; }
QComboBox QAbstractItemView {
    background-color: #0B1B35; border: 1px solid #244A7A; color: #DCE8FA;
    selection-background-color: #1B4C8F; selection-color: #FFFFFF; outline: none;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border; subcontrol-position: top right; width: 18px;
    background-color: #102544; border: none; border-top-right-radius: 6px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border; subcontrol-position: bottom right; width: 18px;
    background-color: #102544; border: none; border-bottom-right-radius: 6px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #1B3A63;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("__CHEVRON_UP__"); width: 8px; height: 5px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("__CHEVRON_DOWN__"); width: 8px; height: 5px;
}

QCheckBox { color: #A9BDD8; spacing: 7px; font-size: 12px; }
QCheckBox:checked { color: #EAF3FF; }
QCheckBox::indicator {
    width: 14px; height: 14px; border-radius: 4px;
    border: 1px solid #2A4C78; background-color: #081528;
}
QCheckBox::indicator:hover { border-color: #3B82F6; }
QCheckBox::indicator:checked {
    background-color: #2F6FE4; border-color: #5B9BFF;
    image: url("__CHECK__");
}

QSlider::groove:horizontal { height: 4px; background: #132A4A; border-radius: 2px; }
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2459C9, stop:1 #38BDF8);
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
    background: #EAF4FF; border: 2px solid #2459C9;
}
QSlider::handle:horizontal:hover { background: #FFFFFF; border-color: #38BDF8; }

/* ===================== 表格 / 文本 ===================== */
QTableWidget {
    background: transparent; border: none; gridline-color: transparent;
    alternate-background-color: #081629; selection-background-color: #12305C;
    selection-color: #FFFFFF;
}
QTableWidget::item { padding: 5px 8px; border-bottom: 1px solid #102442; }
QTableWidget::item:selected { background-color: #12305C; }
QHeaderView::section {
    background-color: #0A1830; color: #7C93B4; border: none;
    border-bottom: 1px solid #17315A; padding: 7px 8px;
    font-size: 11px; font-weight: 600;
}
QTableCornerButton::section { background-color: #0A1830; border: none; }

QPlainTextEdit, QTextEdit {
    background-color: #06101F; border: 1px solid #142B4E; border-radius: 8px;
    color: #B9CCE6; selection-background-color: #1D4ED8; padding: 6px;
}
QTextEdit#FocLog { background-color: #06101F; border: 1px solid #142B4E; border-radius: 9px; }
QTextBrowser {
    background-color: #06101F; border: 1px solid #17315A; border-radius: 10px;
    color: #C9D9F0; padding: 10px; selection-background-color: #1D4ED8;
}

QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #1C3A61; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #2B5688; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #1C3A61; border-radius: 5px; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: #2B5688; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QFrame#HLine { background-color: #142B4E; max-height: 1px; border: none; }
QFrame#VLine { background-color: #142B4E; max-width: 1px; border: none; }
QLabel#KvKey { font-size: 12px; color: #7C93B4; }
QLabel#KvVal { font-family: "Bahnschrift", "Segoe UI"; font-size: 13px; color: #E9F2FF; }
QLabel#StatTitle { font-size: 10px; color: #6E86A8; }
QLabel#StatValue {
    font-family: "Bahnschrift", "Segoe UI";
    font-size: 16px; font-weight: 600; color: #EAF3FF;
}
QFrame#StatTile { background-color: #081528; border: 1px solid #12294A; border-radius: 8px; }
QLabel#FramePreview {
    background-color: #06101F; border: 1px solid #142B4E; border-radius: 7px;
    color: #8FC7FF; font-family: "Consolas", "Microsoft YaHei UI";
    font-size: 11px; padding: 7px;
}
QLabel#Hint { font-size: 11px; color: #5E7699; }
QLabel#HintWarn { font-size: 11px; color: #FBBF24; }
QLabel#UnitHint { font-size: 10px; color: #50698C; }

QToolTip {
    background-color: #0E2140; color: #DCE8FA; border: 1px solid #2B5688;
    padding: 5px 8px; border-radius: 4px;
}
QMessageBox, QDialog { background-color: #071226; }
QMessageBox QLabel { color: #DCE8FA; }
QMenu { background-color: #0B1B35; color: #DCE8FA; border: 1px solid #244A7A; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background-color: #1B4C8F; }
QMenu::separator { height: 1px; background: #17315A; margin: 4px 6px; }
"""


def _chevron_pixmap(up: bool) -> QPixmap:
    pixmap = QPixmap(22, 14)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#8FA6C8"))
    pen.setWidthF(2.4)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    if up:
        points = [QPointF(4, 10), QPointF(11, 4), QPointF(18, 10)]
    else:
        points = [QPointF(4, 4), QPointF(11, 10), QPointF(18, 4)]
    painter.drawPolyline(points)
    painter.end()
    return pixmap


def _check_pixmap() -> QPixmap:
    pixmap = QPixmap(28, 28)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(3.2)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline([QPointF(6, 14), QPointF(12, 20), QPointF(22, 8)])
    painter.end()
    return pixmap


def ensure_ui_assets() -> tuple[str, str, str]:
    base = ASSETS_DIR
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        return "", "", ""
    down = base / "chevron_down.png"
    up = base / "chevron_up.png"
    check = base / "check.png"
    try:
        if not down.exists():
            _chevron_pixmap(False).save(str(down), "PNG")
        if not up.exists():
            _chevron_pixmap(True).save(str(up), "PNG")
        if not check.exists():
            _check_pixmap().save(str(check), "PNG")
    except Exception:
        pass
    return (
        down.as_posix() if down.exists() else "",
        up.as_posix() if up.exists() else "",
        check.as_posix() if check.exists() else "",
    )


def build_stylesheet() -> str:
    down, up, check = ensure_ui_assets()
    return (
        APP_QSS.replace("__CHEVRON_DOWN__", down)
        .replace("__CHEVRON_UP__", up)
        .replace("__CHECK__", check)
    )


def dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(C.BG))
    palette.setColor(QPalette.WindowText, QColor(C.TEXT))
    palette.setColor(QPalette.Base, QColor("#081528"))
    palette.setColor(QPalette.AlternateBase, QColor(C.CARD))
    palette.setColor(QPalette.Text, QColor(C.TEXT))
    palette.setColor(QPalette.Button, QColor("#0D2242"))
    palette.setColor(QPalette.ButtonText, QColor(C.TEXT))
    palette.setColor(QPalette.Highlight, QColor(C.BLUE))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipBase, QColor("#0E2140"))
    palette.setColor(QPalette.ToolTipText, QColor(C.TEXT))
    palette.setColor(QPalette.PlaceholderText, QColor("#4F6688"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#4E6484"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#4E6484"))
    return palette
