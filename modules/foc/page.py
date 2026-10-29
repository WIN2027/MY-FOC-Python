# -*- coding: utf-8 -*-
"""FOC 电机控制模块页面；逻辑来自 FocLogicMixin，UI 由 ui.py 构建。"""

from __future__ import annotations

from collections import deque

import pyqtgraph as pg
from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMenu, QMessageBox, QWidget

from core.settings import AppSettings
from core.theme import C, q_rgba

from .logic import FocLogicMixin
from .protocol import CHANNEL_DISPLAY, CHANNEL_OPTIONS, CURVE_COLORS
from .ui import build_foc_ui


class FocPage(FocLogicMixin, QWidget):
    title = "FOC 电机控制"
    subtitle = "DRV8320S · FOC 参数、波形监测与串口调试"
    icon_name = "foc"

    connection_changed = Signal(bool)

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("Page")
        self._visible = False
        self._init_state()
        build_foc_ui(self)
        self.refresh_ports()
        self._restore_serial_settings()
        self._setup_shortcuts()
        self._apply_monitor_state("idle")
        self._load_presets()
        if self.preset_combo is not None and self.preset_combo.count() == 0:
            self.preset_combo.addItem("（暂无预设）")
        self.load_pid_config()
        try:
            tab = int(self.settings.get("foc/tab", 0))
        except Exception:
            tab = 0
        self.switch_tab(max(0, min(3, tab)))
        self.log_message("FOC 模块已就绪，请选择串口并打开。", "info")

    # ------------------------------------------------------------------
    def _init_state(self):
        self.serial_worker = None
        self.slave_online = False
        self.serial_assistant_mode = False
        self.telemetry_mask = 0
        self.parsing_mask = 0
        self.cmd_set_mask = 0x17
        self.cmd_telemetry_report = 0x18

        self.data_buf_adc1 = deque(maxlen=600)
        self.data_buf_adc2 = deque(maxlen=600)
        self.data_buf_ia = deque(maxlen=600)
        self.data_buf_ib = deque(maxlen=600)
        self.data_buf_ic = deque(maxlen=600)
        self.data_buf_id = deque(maxlen=600)
        self.data_buf_iq = deque(maxlen=600)
        self.data_buf_speed = deque(maxlen=600)
        self.data_buf_calc_cycle = deque(maxlen=600)
        self.data_buf_pwm_u = deque(maxlen=600)
        self.data_buf_pwm_v = deque(maxlen=600)
        self.data_buf_pwm_w = deque(maxlen=600)
        self.data_buf_dpi_1 = deque(maxlen=600)
        self.data_buf_dpi_2 = deque(maxlen=600)
        self.data_buf_dpi_3 = deque(maxlen=600)
        self.data_buf_dpi_4 = deque(maxlen=600)
        self.data_buf_qpi_1 = deque(maxlen=600)
        self.data_buf_qpi_2 = deque(maxlen=600)
        self.data_buf_qpi_3 = deque(maxlen=600)
        self.data_buf_qpi_4 = deque(maxlen=600)
        self.data_buf_bemf = deque(maxlen=600)

        self.plot_widgets = [None, None, None, None]
        self.area_config = [None, None, None, None]
        self.area_curves = [[], [], [], []]
        self.select_btns = []
        self.nav_buttons = []

        self.plot_timer = QTimer(self)
        self.plot_timer.setInterval(50)
        self.plot_timer.timeout.connect(self.update_waveforms)
        self.pending_ack = None
        self.debug_mode_active = False
        self.dpi_mode_active = False
        self.qpi_mode_active = False
        self.saved_area_configs = [None, None, None, None]
        self.saved_select_texts = ["—", "—", "—", "—"]
        self.drv_widgets = {}
        self.pid_sliders = {"d": {}, "q": {}, "speed": {}}
        self.pid_btn_groups = {"d": {}, "q": {}, "speed": {}}
        self.waveform_data_updated = False
        self.monitor_mode = "telemetry"

        self.speed_min = 0
        self.speed_max = 3500
        self.speed_slider = None
        self.speed_slider_capsule = None
        self.speed_interval_spin = None
        self.motor_running = False
        self.last_sent_speed = 1500

        self.speed_poll_timer = QTimer(self)
        self.speed_poll_timer.timeout.connect(self.send_target_speed_periodic)

        self.startup_spins = {}
        self.read_startup_btn = None
        self.write_startup_btn = None
        self.motor_spins = {}
        self.read_motor_btn = None
        self.write_motor_btn = None
        self.send_all_pid_btn = None

        self.paused = False
        self.auto_range_enabled = True
        self.log_entries = deque(maxlen=5000)
        self.max_log_entries = 5000
        self.log_filter = None
        self.presets = {}
        self.preset_combo = None
        self.drv_verify_pending = None
        self.motor_state_label = None
        self.assistant_send_row = None
        self.assistant_input = None
        self.assistant_hex_chk = None

    def _restore_serial_settings(self):
        port = self.settings.get("foc/port", "")
        if port:
            index = self.port_combo.findText(str(port))
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        baud = self.settings.get("foc/baud", "115200")
        if self.baud_combo.findText(str(baud)) >= 0:
            self.baud_combo.setCurrentText(str(baud))

    # ------------------------------------------------------------------
    def switch_tab(self, index: int):
        index = max(0, min(3, int(index)))
        self.stack.setCurrentIndex(index)
        self.tabs.set_current(index)
        if self._visible and index == 2:
            self.plot_timer.start(50)
        else:
            self.plot_timer.stop()
        self.update_sub_nav(index)
        self.settings.set("foc/tab", index)

    def update_sub_nav(self, index: int):
        if index != 2:
            return
        telemetry = self.monitor_mode == "telemetry"
        self.telemetry_panel.setVisible(telemetry)
        self.control_panel.setVisible(not telemetry)
        self.func_switch_btn.setText("电机控制" if telemetry else "返回遥测")
        self.range_btn_min.setEnabled(not telemetry)
        self.range_btn_max.setEnabled(not telemetry)

    def on_shown(self):
        self._visible = True
        if self.stack.currentIndex() == 2:
            self.plot_timer.start(50)
        self.update_sub_nav(2)

    def on_hidden(self):
        self._visible = False
        self.plot_timer.stop()

    @property
    def is_connected(self) -> bool:
        return self.serial_worker is not None

    # ------------------------------------------------------------------
    def _set_btn_active(self, btn, active: bool):
        if btn is None:
            return
        btn.setProperty("active", "true" if active else "false")
        style = btn.style()
        if style is not None:
            style.unpolish(btn)
            style.polish(btn)
        btn.update()

    def _apply_monitor_state(self, state: str):
        styles = {
            "idle": ("空闲", C.MUTED),
            "align": ("对齐中", C.AMBER),
            "running": ("运行", C.GREEN),
            "fault": ("故障", C.RED),
        }
        text, color = styles.get(state, styles["idle"])
        if self.motor_state_label is None:
            return
        self.motor_state_label.setText(f"● {text}")
        if state == "idle":
            background, border = "#0E2140", "#2B5688"
        else:
            background, border = q_rgba(color, 0.14), q_rgba(color, 0.50)
        self.motor_state_label.setStyleSheet(
            f"color:{color}; background-color:{background};"
            f"border:1px solid {border}; border-radius:10px;"
            "padding:4px 10px; font-size:12px; font-weight:600;"
        )

    # ------------------------------------------------------------------
    def refresh_ports(self, *_):
        if self.serial_worker is not None:
            return
        current = self.port_combo.currentText()
        try:
            import serial.tools.list_ports

            ports = sorted(serial.tools.list_ports.comports(), key=lambda p: p.device)
        except Exception:
            ports = []
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        for port in ports:
            self.port_combo.addItem(port.device, port.device)
            description = (port.description or "").strip()
            if description and description.lower() not in ("n/a", "none"):
                self.port_combo.setItemData(
                    self.port_combo.count() - 1, description, Qt.ToolTipRole
                )
        if not ports:
            self.port_combo.addItem("未检测到串口")
        else:
            index = self.port_combo.findText(current)
            self.port_combo.setCurrentIndex(index if index >= 0 else 0)
        self.port_combo.blockSignals(False)

    def open_serial(self):
        if self.serial_worker is not None:
            return
        port = self.port_combo.currentText().strip()
        if not port or port == "未检测到串口":
            QMessageBox.warning(
                self, "警告", "未检测到可用串口，请检查连接后点击“刷新”。"
            )
            self._update_serial_ui_closed()
            return
        self.status_label.set_state("打开中…", C.AMBER)
        self.open_btn.setEnabled(False)
        super().open_serial()
        if self.serial_worker is None:
            self._update_serial_ui_closed()

    def on_serial_opened(self, success: bool, err_msg: str):
        worker = self.serial_worker
        if worker is None:
            return
        if success:
            self.open_btn.setText("关闭串口")
            self.open_btn.setEnabled(True)
            for widget in self.serial_controls:
                widget.setEnabled(False)
            self.status_label.set_state("已连接", C.GREEN)
            port = self.port_combo.currentText()
            self.log_message(f"串口 {port} 打开成功", "info")
            self.connection_changed.emit(True)
        else:
            self.serial_worker = None
            worker.wait(400)
            self.log_message(f"打开串口失败: {err_msg}", "error")
            self._update_serial_ui_closed()
            QMessageBox.critical(self, "错误", f"打开串口失败:\n{err_msg}")

    def _update_serial_ui_closed(self):
        if self.open_btn is None:
            return
        self.open_btn.setText("打开串口")
        self.open_btn.setEnabled(True)
        for widget in getattr(self, "serial_controls", []):
            widget.setEnabled(True)
        self.status_label.set_state("未连接", C.RED)
        self.connection_changed.emit(False)

    # ------------------------------------------------------------------
    def _setup_shortcuts(self):
        for sequence, handler in (
            ("Ctrl+O", self.toggle_serial),
            ("Ctrl+S", self.save_log),
            ("F5", self.check_slave),
            ("Ctrl+R", self.refresh_ports),
            ("Alt+P", self.toggle_pause),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)

    # ------------------------------------------------------------------
    def show_selection_popup(self, index: int):
        if self.dpi_mode_active or self.qpi_mode_active:
            QMessageBox.information(self, "提示", "当前处于 D/Q 轴 PI 模式")
            return
        menu = QMenu(self)
        for text, value in CHANNEL_OPTIONS:
            if value is None:
                menu.addSeparator()
            action = menu.addAction(text)
            action.triggered.connect(
                lambda _checked=False, v=value, i=index: self.on_selection_made(i, v)
            )
        button = self.select_btns[index]
        menu.exec(button.mapToGlobal(QPoint(0, button.height())))

    def on_selection_made(self, index: int, val):
        if self.dpi_mode_active or self.qpi_mode_active:
            return
        self.select_btns[index].setText(CHANNEL_DISPLAY.get(val, "—") if val else "—")
        for curve in self.area_curves[index]:
            self.plot_widgets[index].removeItem(curve)
        self.area_curves[index].clear()
        self.area_config[index] = val
        if val in ("three_phase", "pwm"):
            colors = CURVE_COLORS["three"]
            self.area_curves[index] = [
                self.plot_widgets[index].plot(pen=pg.mkPen(color=color, width=2))
                for color in colors
            ]
            if val == "three_phase":
                self.data_buf_ia.clear()
                self.data_buf_ib.clear()
                self.data_buf_ic.clear()
            else:
                self.data_buf_pwm_u.clear()
                self.data_buf_pwm_v.clear()
                self.data_buf_pwm_w.clear()
        elif val is not None:
            self.area_curves[index] = [
                self.plot_widgets[index].plot(
                    pen=pg.mkPen(color=CURVE_COLORS["single"], width=2)
                )
            ]
            buf_map = {
                "adc1": self.data_buf_adc1,
                "adc2": self.data_buf_adc2,
                "id": self.data_buf_id,
                "iq": self.data_buf_iq,
                "speed": self.data_buf_speed,
                "calc_cycle": self.data_buf_calc_cycle,
                "bemf": self.data_buf_bemf,
            }
            if val in buf_map:
                buf_map[val].clear()
        self.plot_widgets[index].autoRange()

    # ------------------------------------------------------------------
    def save_settings(self):
        self.settings.set("foc/tab", self.stack.currentIndex())
        port = self.port_combo.currentText()
        if port:
            self.settings.set("foc/port", port)
        self.settings.set("foc/baud", self.baud_combo.currentText())

    def shutdown(self):
        self.save_settings()
        self.plot_timer.stop()
        self.speed_poll_timer.stop()
        if self.pending_ack is not None:
            try:
                self.pending_ack["timer"].stop()
            except Exception:
                pass
            self.pending_ack = None
        if self.serial_worker is not None:
            worker = self.serial_worker
            self.serial_worker = None
            worker.stop()
