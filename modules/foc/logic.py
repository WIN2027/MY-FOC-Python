# -*- coding: utf-8 -*-
"""FOC 控制逻辑（从 FOC-Python/Text.py 抽取，行为保持不变）。

本文件只包含协议、串口、遥测、DRV 配置、PID、波形和日志逻辑；
UI 由 modules/foc/ui.py 与 page.py 提供。原脚本作为备份不被修改。
"""

from __future__ import annotations

import csv
import json
import struct
import time
from datetime import datetime

import pyqtgraph as pg
import serial
import serial.tools.list_ports
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from core.protocol import build_frame as build_foc_frame
from core.protocol import crc8 as crc8_foc
from core.serial_worker import SerialWorker
from core.theme import APP_DIR
from .protocol import (
    CMD_ACK,
    CMD_ALIGN_DONE,
    CMD_ALIGN,
    CMD_FAULT_REPORT,
    CMD_GET_MOTOR_PARAMS,
    CMD_GET_STARTUP,
    CMD_MOTOR_START,
    CMD_MOTOR_STOP,
    CMD_READ_DRV,
    CMD_SET_CURRENT_PI,
    CMD_SET_MOTOR_PARAMS,
    CMD_SET_SPEED,
    CMD_SET_SPEED_PID,
    CMD_SET_STARTUP,
    CMD_TELEMETRY_REPORT,
    CMD_VERSION,
    CMD_DEBUG,
    ERROR_NAMES,
    FAULT_NAMES,
    pack_motor_params,
    pack_startup_config,
    unpack_motor_params,
    unpack_startup_config,
)


class FocLogicMixin:
    def toggle_auto_range(self):
        self.auto_range_enabled = not self.auto_range_enabled
        if self.auto_range_enabled:
            self.auto_range_btn.setText("自动缩放:开")
            self._set_btn_active(self.auto_range_btn, True)
        else:
            self.auto_range_btn.setText("自动缩放:关")
            self._set_btn_active(self.auto_range_btn, False)

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.setText("继续波形")
            self._set_btn_active(self.pause_btn, True)
        else:
            self.pause_btn.setText("暂停波形")
            self._set_btn_active(self.pause_btn, False)

    def send_speed_cmd(self, speed_val) -> bool:
        if not self.serial_worker or not self.serial_worker.isRunning():
            return False
        data = struct.pack('<h', speed_val)
        frame = build_foc_frame(CMD_SET_SPEED, data)
        if self.send_raw_bytes(frame, "[Tx 设定转速]"):
            self.last_sent_speed = speed_val
            return True
        return False

    def send_target_speed_periodic(self):
        """运行中按“下发间隔”周期重发当前目标转速。"""
        if not self.motor_running or self.pending_ack is not None:
            return
        self.send_speed_cmd(self.speed_slider.value())

    def on_speed_interval_changed(self, value):
        interval = max(50, int(value))
        if self.speed_poll_timer.isActive():
            self.speed_poll_timer.setInterval(interval)

    def toggle_monitor_mode(self):
        if self.monitor_mode == "telemetry":
            self.monitor_mode = "control"
            self.range_btn_min.setEnabled(True)
            self.range_btn_max.setEnabled(True)
            self.select_range_min()
        else:
            self.monitor_mode = "telemetry"
            self.range_btn_min.setEnabled(False)
            self.range_btn_max.setEnabled(False)
            self._set_btn_active(self.range_btn_min, False)
            self._set_btn_active(self.range_btn_max, False)
        self.update_sub_nav(2)

    def select_range_min(self):
        self._set_btn_active(self.range_btn_min, True)
        self._set_btn_active(self.range_btn_max, False)
        self.speed_slider.setRange(0, 3500)
        self.speed_spinbox.setRange(0, 3500)
        if self.speed_slider.value() > 3500:
            self.speed_slider.setValue(3500)

    def select_range_max(self):
        self._set_btn_active(self.range_btn_min, False)
        self._set_btn_active(self.range_btn_max, True)
        self.speed_slider.setRange(0, 7000)
        self.speed_spinbox.setRange(0, 7000)
        if self.speed_slider.value() > 7000:
            self.speed_slider.setValue(7000)

    def toggle_serial_assistant(self, checked):
        self.serial_assistant_mode = bool(checked)
        self._set_btn_active(self.serial_assistant_btn, self.serial_assistant_mode)
    
        # 显示/隐藏发送栏
        if self.assistant_send_row is not None:
            self.assistant_send_row.setVisible(self.serial_assistant_mode)
            # 切到通讯信息页方便操作
            if self.serial_assistant_mode:
                self.switch_tab(3)
    
        if self.serial_assistant_mode:
            self.log_message("已进入串口助手模式：数据透传，不再解析 FOC 协议", 'info')
        else:
            self.log_message("已退出串口助手模式", 'info')

    def assistant_send(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        text = self.assistant_input.text()
        if not text:
            return
        if self.assistant_hex_chk.isChecked():
            try:
                hex_str = (text.replace(' ', '')
                                .replace(',', '')
                                .replace('0x', '')
                                .replace('0X', ''))
                if len(hex_str) % 2 != 0:
                    raise ValueError("十六进制字符个数必须是偶数")
                data = bytes.fromhex(hex_str)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"HEX 格式错误: {e}")
                return
        else:
            data = text.encode('utf-8')
        self.send_raw_bytes(data, "[Tx 串口助手]")
        self.assistant_input.clear()

    def _config_dir(self):
        d = APP_DIR / "config"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _presets_path(self):
        return self._config_dir() / "presets.json"

    def _load_presets(self):
        try:
            with open(self._presets_path(), 'r', encoding='utf-8') as f:
                self.presets = json.load(f)
        except Exception:
            self.presets = {}
        if self.preset_combo is not None:
            self.preset_combo.clear()
            for name in self.presets:
                self.preset_combo.addItem(name)

    def _save_presets(self):
        try:
            with open(self._presets_path(), 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            self.log_message(f"保存预设失败: {e}", 'error')
            return False

    def _on_preset_save(self):
        name, ok = QInputDialog.getText(self, "保存预设", "预设名称:")
        if not ok or not name.strip():
            return
        name = name.strip()
        self.presets[name] = {
            'd': self.get_axis_state('d'),
            'q': self.get_axis_state('q'),
            'speed': self.get_axis_state('speed'),
        }
        if not self._save_presets():
            return
        if self.preset_combo is not None:
            if self.preset_combo.findText(name) < 0:
                self.preset_combo.addItem(name)
            self.preset_combo.setCurrentText(name)
        self.log_message(f"已保存预设 '{name}'", 'info')

    def _on_preset_load(self):
        if self.preset_combo is None:
            return
        name = self.preset_combo.currentText()
        if not name or name not in self.presets:
            QMessageBox.information(self, "提示", "请先选择预设")
            return
        data = self.presets[name]
        for axis in ('d', 'q', 'speed'):
            if axis not in data:
                continue
            for param, cfg in data[axis].items():
                if axis not in self.pid_sliders or param not in self.pid_sliders[axis]:
                    continue
                slider = self.pid_sliders[axis][param]
                btn_group = self.pid_btn_groups[axis][param]
                target_btn = None
                for b in btn_group.buttons():
                    if abs(b.min_val - cfg['min']) < 1e-6 and abs(b.max_val - cfg['max']) < 1e-6:
                        target_btn = b
                        break
                if target_btn:
                    slider.blockSignals(True)
                    target_btn.setChecked(True)
                    if abs(cfg['max'] - cfg['min']) < 1e-6:
                        pos = 5000
                    else:
                        pos = int(((cfg['value'] - cfg['min']) / (cfg['max'] - cfg['min'])) * 10000.0)
                    slider.setValue(max(0, min(10000, pos)))
                    slider.blockSignals(False)
                    if hasattr(slider, '_spin'):
                        spin = slider._spin
                        spin.blockSignals(True)
                        spin.setRange(cfg['min'], cfg['max'])
                        spin.setValue(cfg['value'])
                        spin.blockSignals(False)
        self.log_message(f"已加载预设 '{name}'", 'info')

    def _on_preset_delete(self):
        if self.preset_combo is None:
            return
        name = self.preset_combo.currentText()
        if not name or name not in self.presets:
            return
        if QMessageBox.question(self, "确认", f"删除预设 '{name}' ?") != QMessageBox.Yes:
            return
        del self.presets[name]
        self._save_presets()
        self.preset_combo.removeItem(self.preset_combo.currentIndex())
        self.log_message(f"已删除预设 '{name}'", 'info')

    @staticmethod
    def _get_range(btn_group):
        for b in btn_group.buttons():
            if b.isChecked():
                return b.min_val, b.max_val
        return 0.0, 1.0

    def get_axis_state(self, axis):
        state = {}
        for param in self.pid_sliders[axis]:
            val = self.get_slider_val(axis, param)
            btn_group = self.pid_btn_groups[axis][param]
            min_val, max_val = self._get_range(btn_group)
            state[param] = {'value': val, 'min': min_val, 'max': max_val}
        return state

    def _pid_config_dir(self):
        return self._config_dir()

    def save_pid_config(self, axis):
        try:
            config_file = self._pid_config_dir() / "pid_config.json"
        except Exception as e:
            self.log_message(f"创建配置目录失败: {e}", 'error')
            return
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            config = {}
        config[axis] = self.get_axis_state(axis)
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.log_message(f"已保存 {axis.upper()} 轴PI配置: {config_file}", 'info')
        except Exception as e:
            self.log_message(f"保存配置失败: {str(e)}", 'error')

    def load_pid_config(self):
        config_file = self._pid_config_dir() / "pid_config.json"
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            return
        for axis, params in config.items():
            if axis not in self.pid_sliders:
                continue
            for param, data in params.items():
                if param not in self.pid_sliders[axis]:
                    continue
                slider = self.pid_sliders[axis][param]
                btn_group = self.pid_btn_groups[axis][param]
                target_btn = None
                for b in btn_group.buttons():
                    if abs(b.min_val - data['min']) < 1e-6 and abs(b.max_val - data['max']) < 1e-6:
                        target_btn = b
                        break
                if target_btn:
                    target_btn.setChecked(True)
                    tmin, tmax = data['min'], data['max']
                    if abs(tmax - tmin) < 1e-9:
                        pos = 5000
                    else:
                        pos = int(((data['value'] - tmin) / (tmax - tmin)) * 10000.0)
                    slider.setValue(max(0, min(10000, pos)))
                    if hasattr(slider, '_spin'):
                        spin = slider._spin
                        spin.blockSignals(True)
                        spin.setRange(tmin, tmax)
                        spin.setSingleStep(max((tmax - tmin) / 1000.0, 1e-6))
                        spin.setValue(data['value'])
                        spin.blockSignals(False)

    def send_all_pid(self):
        """统一先下发 0x02（D/Q 四参数），确认后再下发 0x03（速度环）。"""
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        if self.pending_ack is not None:
            self.log_message("有命令正在等待确认", 'info')
            return
        d_kp = self.get_slider_val('d', 'Kp')
        d_ki = self.get_slider_val('d', 'Ki')
        q_kp = self.get_slider_val('q', 'Kp')
        q_ki = self.get_slider_val('q', 'Ki')
        values = (d_kp, d_ki, q_kp, q_ki)
        data = struct.pack('<ffff', *values)
        frame = build_foc_frame(CMD_SET_CURRENT_PI, data)
        self.send_request(
            frame, CMD_SET_CURRENT_PI, "下发电流环 PI", 1000,
            on_success=lambda _payload: self._send_speed_pid(),
            on_timeout=lambda: self.log_message("电流环 PI 下发超时", 'error'),
        )
        self.record_param_change(
            "D/Q PI", "—", ", ".join(f"{v:.5f}" for v in values), "发送"
        )

    def _send_speed_pid(self):
        values = (
            self.get_slider_val('speed', 'Kp'),
            self.get_slider_val('speed', 'Ki'),
            self.get_slider_val('speed', 'Kd'),
        )
        data = struct.pack('<fff', *values)
        frame = build_foc_frame(CMD_SET_SPEED_PID, data)
        self.send_request(
            frame, CMD_SET_SPEED_PID, "下发速度环 PID", 1000,
            on_timeout=lambda: self.log_message("速度环 PID 下发超时", 'error'),
        )
        self.record_param_change(
            "速度环 PID", "—", ", ".join(f"{v:.5f}" for v in values), "发送"
        )

    def get_slider_val(self, axis, param):
        if axis not in self.pid_sliders or param not in self.pid_sliders[axis]:
            return 0.0
        slider = self.pid_sliders[axis][param]
        btn_group = self.pid_btn_groups[axis][param]
        min_val, max_val = self._get_range(btn_group)
        return min_val + (slider.value() / 10000.0) * (max_val - min_val)

    def _startup_values(self):
        spins = getattr(self, "startup_spins", {})
        return {
            "align_current_a": spins["align_current"].value(),
            "align_time_ms": int(spins["align_time"].value()),
            "openloop_current_a": spins["openloop_current"].value(),
            "openloop_time_ms": int(spins["openloop_time"].value()),
            "openloop_freq_hz": spins["openloop_freq"].value(),
        }

    def read_startup_config(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        frame = build_foc_frame(CMD_GET_STARTUP)
        self.send_request(
            frame, CMD_GET_STARTUP, "读取启动参数", 1000,
            on_timeout=lambda: self.log_message("读取启动参数超时", 'error'),
        )

    def write_startup_config(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        if self.motor_running:
            self.log_message("电机运行中，禁止写入启动参数", 'error')
            return
        try:
            data = pack_startup_config(self._startup_values())
        except Exception as exc:
            self.log_message(f"启动参数格式错误: {exc}", 'error')
            return
        frame = build_foc_frame(CMD_SET_STARTUP, data)
        self.send_with_ack(
            frame, CMD_SET_STARTUP, "写入启动参数", 1000,
            on_success=lambda _p: self.log_message("启动参数写入成功", 'info'),
            on_timeout=lambda: self.log_message("启动参数写入超时", 'error'),
        )

    def _motor_values(self):
        spins = getattr(self, "motor_spins", {})
        return {
            "R": spins["R"].value(),
            "Ld": spins["Ld"].value(),
            "Lq": spins["Lq"].value(),
            "flux_link": spins["flux_link"].value(),
            "pole_pairs": int(spins["pole_pairs"].value()),
        }

    def read_motor_params(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        frame = build_foc_frame(CMD_GET_MOTOR_PARAMS)
        self.send_request(
            frame, CMD_GET_MOTOR_PARAMS, "读取电机参数", 1000,
            on_timeout=lambda: self.log_message("读取电机参数超时", 'error'),
        )

    def write_motor_params(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        if self.motor_running:
            self.log_message("电机运行中，禁止写入电机参数", 'error')
            return
        try:
            data = pack_motor_params(self._motor_values())
        except Exception as exc:
            self.log_message(f"电机参数格式错误: {exc}", 'error')
            return
        frame = build_foc_frame(CMD_SET_MOTOR_PARAMS, data)
        self.send_with_ack(
            frame, CMD_SET_MOTOR_PARAMS, "写入电机参数", 1000,
            on_success=lambda _p: self.log_message("电机参数写入成功", 'info'),
            on_timeout=lambda: self.log_message("电机参数写入超时", 'error'),
        )

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(p.device)

    def toggle_serial(self):
        if self.serial_worker is not None:
            self.close_serial()
        else:
            self.open_serial()

    def open_serial(self):
        port = self.port_combo.currentData() or self.port_combo.currentText()
        if not port:
            QMessageBox.warning(self, "警告", "请选择串口号")
            return
    
        baud = int(self.baud_combo.currentText())
        data_bits = int(self.data_combo.currentText())
        stop_bits = float(self.stop_combo.currentText())
        parity_str = self.parity_combo.currentText()
        parity = serial.PARITY_NONE
        if parity_str == '奇':
            parity = serial.PARITY_ODD
        elif parity_str == '偶':
            parity = serial.PARITY_EVEN
    
        worker = SerialWorker(port, baud, data_bits, stop_bits, parity)
        self.serial_worker = worker
        worker.raw_data.connect(self.display_received_data)
        worker.frame_received.connect(self.handle_frame)
        worker.error_occurred.connect(self.on_serial_error)
        worker.opened.connect(self.on_serial_opened)
        worker.closed.connect(self.on_serial_closed)
        worker.start()

    def on_serial_opened(self, success, err_msg):
        if success:
            self.open_btn.setText("关闭串口")
            port_name = self.port_combo.currentText()
            self.status_label.setText(f"状态: 已打开 ({port_name})")
            self.status_label.setStyleSheet("color: #4ade80; font-weight: bold;")
            self.log_message(f"串口 {port_name} 打开成功", 'info')
        else:
            self.log_message(f"打开串口失败: {err_msg}", 'error')
            QMessageBox.critical(self, "错误", f"打开串口失败:\n{err_msg}")
            self.serial_worker = None
            self._update_serial_ui_closed()

    def on_serial_error(self, err_msg):
        self.log_message(f"串口通信异常: {err_msg}", 'error')

    def on_serial_closed(self):
        if self.serial_worker is None:
            return
        self.serial_worker = None
        self._update_serial_ui_closed()
        self.reset_serial_state()
        self.log_message("串口连接已关闭", 'info')

    def _update_serial_ui_closed(self):
        self.open_btn.setText("打开串口")
        self.status_label.setText("状态: 关闭")
        self.status_label.setStyleSheet("color: #ff3333; font-weight: bold;")

    def close_serial(self):
        if self.serial_worker:
            worker = self.serial_worker
            self.serial_worker = None
            worker.stop()
        self._update_serial_ui_closed()
        self.reset_serial_state()
        self.log_message("串口已关闭", 'info')

    def reset_serial_state(self):
        self.speed_poll_timer.stop()
        self.motor_running = False
        self.last_sent_speed = self.speed_slider.value() if self.speed_slider else 1500
    
        self.telemetry_mask = 0
        self.parsing_mask = 0
        for btn in [self.adc1_btn, self.adc2_btn, self.three_phase_btn,
                    self.id_btn, self.iq_btn, self.speed_btn, self.calc_cycle_btn,
                    self.pwm_btn, self.dpi_btn, self.qpi_btn, self.bemf_btn]:
            if btn is not None:
                self._set_btn_active(btn, False)
    
        self.slave_online = False
        if self.slave_indicator is not None:
            self.slave_indicator.setText("● 从机离线")
            self.slave_indicator.setStyleSheet("color: #6B7280; font-weight: bold;")
    
        if self.pending_ack is not None:
            try:
                self.pending_ack['timer'].stop()
            except Exception:
                pass
            self.pending_ack = None
    
        self.debug_mode_active = False
        if self.debug_btn is not None:
            self.update_debug_btn_ui()
    
        self.dpi_mode_active = False
        self.qpi_mode_active = False
    
        # 退出串口助手模式
        if getattr(self, "serial_assistant_btn", None) is not None and self.serial_assistant_btn.isChecked():
            self.serial_assistant_btn.setChecked(False)
    
        self._apply_monitor_state("idle")

    def display_received_data(self, data):
        hex_str = ' '.join(f'{b:02X}' for b in data)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        html = f"[{ts}] [Rx] HEX: {hex_str}  ASCII: {ascii_str}"
        self._append_log("rx", html)

    def handle_frame(self, frame: bytes):
        # 串口助手模式：不解析任何 FOC 帧
        if self.serial_assistant_mode:
            return
        if len(frame) < 4 or frame[0] != 0x5A:
            return
        cmd = frame[1]
        data_len = frame[2]
        if len(frame) < 4 + data_len:
            return
        payload = frame[3:3 + data_len]
        recv_crc = frame[3 + data_len]
        calc_crc = crc8_foc(frame[1:3 + data_len])
        if calc_crc != recv_crc:
            self.log_message(f"CRC 校验失败 (0x{calc_crc:02X} != 0x{recv_crc:02X})", 'error')
            return
    
        if cmd == CMD_VERSION:
            self._complete_pending(cmd, payload)
            self.handle_version_response(payload)
        elif cmd == CMD_SET_CURRENT_PI or cmd == CMD_SET_SPEED_PID:
            self._complete_pending(cmd, payload)
            self.handle_pid_response(cmd, payload)
        elif cmd == CMD_GET_STARTUP:
            self._complete_pending(cmd, payload)
            self.handle_startup_config_response(payload)
        elif cmd == CMD_GET_MOTOR_PARAMS:
            self._complete_pending(cmd, payload)
            self.handle_motor_params_response(payload)
        elif cmd == CMD_READ_DRV:
            self._complete_pending(cmd, payload)
            self.handle_drv_config_response(payload)
        elif cmd == CMD_TELEMETRY_REPORT:
            self.handle_telemetry_report(payload)
        elif cmd == CMD_ACK:
            self.handle_ack(payload)
        elif 0x82 <= cmd <= 0x87:
            self.handle_error_response(cmd)
        elif cmd == CMD_FAULT_REPORT:
            self.handle_fault_report(payload)
        elif cmd == CMD_ALIGN_DONE:
            self.handle_align_done()
        else:
            self.log_message(f"未处理命令 0x{cmd:02X}, 长度 {data_len}", 'info')

    def _on_pending_ack_timeout(self):
        if self.pending_ack is None:
            return
        entry = self.pending_ack
        self.pending_ack = None
        try:
            entry['timer'].stop()
        except Exception:
            pass
        self.log_message(f"{entry['name']} 请求超时", 'error')
        cb = entry.get('on_timeout')
        if cb:
            cb()

    def send_with_ack(self, frame, cmd, name, timeout_ms=2000, on_success=None, on_timeout=None):
        if self.pending_ack is not None:
            self.log_message(f"已有待确认命令: {self.pending_ack['name']}", 'error')
            return False
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._on_pending_ack_timeout)
        self.pending_ack = {
            'cmd': cmd, 'name': name, 'timer': timer,
            'on_success': on_success, 'on_timeout': on_timeout,
        }
        timer.start(timeout_ms)
        if not self.send_raw_bytes(frame, f"[Tx {name}]"):
            timer.stop()
            self.pending_ack = None
            return False
        return True

    def handle_ack(self, payload):
        if self.pending_ack is None:
            # 0x01 周期转速等命令不建立等待项，其 ACK 属于正常流量，不刷日志。
            return
        entry = self.pending_ack
        try:
            entry['timer'].stop()
        except Exception:
            pass
        self.pending_ack = None
        self.log_message(f"{entry['name']} 已确认", 'info')
        cb = entry.get('on_success')
        if cb:
            cb(payload)

    def send_request(self, frame, expect_cmd, name, timeout_ms=1000,
                     on_success=None, on_timeout=None):
        """发送一条“应答命令码 = expect_cmd”的请求（参数读取/PID 回显）。"""
        if self.pending_ack is not None:
            self.log_message(f"已有待确认命令: {self.pending_ack['name']}", 'error')
            return False
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._on_pending_ack_timeout)
        self.pending_ack = {
            'cmd': expect_cmd, 'name': name, 'timer': timer,
            'on_success': on_success, 'on_timeout': on_timeout,
        }
        timer.start(timeout_ms)
        if not self.send_raw_bytes(frame, f"[Tx {name}]"):
            timer.stop()
            self.pending_ack = None
            return False
        return True

    def _complete_pending(self, cmd, payload):
        entry = self.pending_ack
        if entry is None or entry.get('cmd') != cmd:
            return False
        try:
            entry['timer'].stop()
        except Exception:
            pass
        self.pending_ack = None
        self.log_message(f"{entry['name']} 已确认", 'info')
        cb = entry.get('on_success')
        if cb:
            cb(payload)
        return True

    def handle_pid_response(self, cmd, payload):
        if cmd == CMD_SET_CURRENT_PI:
            if len(payload) >= 16:
                values = struct.unpack('<ffff', payload[:16])
                self.log_message(
                    "电流环 PI 回读: Kp_d=%.5f Ki_d=%.5f Kp_q=%.5f Ki_q=%.5f"
                    % values, 'info'
                )
        elif cmd == CMD_SET_SPEED_PID:
            if len(payload) >= 12:
                values = struct.unpack('<fff', payload[:12])
                self.log_message(
                    "速度环 PID 回读: Kp=%.5f Ki=%.5f Kd=%.5f" % values, 'info'
                )

    def handle_startup_config_response(self, payload):
        try:
            values = unpack_startup_config(payload)
        except Exception as exc:
            self.log_message(f"启动参数解析失败: {exc}", 'error')
            return
        spins = getattr(self, "startup_spins", {})
        mapping = {
            "align_current_a": "align_current",
            "align_time_ms": "align_time",
            "openloop_current_a": "openloop_current",
            "openloop_time_ms": "openloop_time",
            "openloop_freq_hz": "openloop_freq",
        }
        for key, widget_key in mapping.items():
            widget = spins.get(widget_key)
            if widget is not None:
                widget.blockSignals(True)
                widget.setValue(values[key])
                widget.blockSignals(False)
        self.log_message(
            "启动参数: 对齐 %.2fA/%dms，强拖 %.2fA/%dms/%.1fHz"
            % (values["align_current_a"], values["align_time_ms"],
               values["openloop_current_a"], values["openloop_time_ms"],
               values["openloop_freq_hz"]),
            'info',
        )

    def handle_motor_params_response(self, payload):
        try:
            values = unpack_motor_params(payload)
        except Exception as exc:
            self.log_message(f"电机参数解析失败: {exc}", 'error')
            return
        spins = getattr(self, "motor_spins", {})
        for key, widget in spins.items():
            if key in values:
                widget.blockSignals(True)
                widget.setValue(values[key])
                widget.blockSignals(False)
        self.log_message(
            "电机参数: R=%.6fΩ Ld=%.8fH Lq=%.8fH flux=%.8fWb 极对数=%d"
            % (values["R"], values["Ld"], values["Lq"],
               values["flux_link"], values["pole_pairs"]),
            'info',
        )

    def handle_error_response(self, cmd):
        name = ERROR_NAMES.get(cmd, f"ERR_0x{cmd:02X}")
        if self.pending_ack is not None:
            entry = self.pending_ack
            try:
                entry['timer'].stop()
            except Exception:
                pass
            self.pending_ack = None
            self.log_message(f"{entry['name']} 失败: {name}", 'error')
        else:
            self.log_message(f"设备返回错误: {name}", 'error')

    def handle_fault_report(self, payload):
        if len(payload) < 4:
            return
        code = struct.unpack('<I', payload[:4])[0]
        name = FAULT_NAMES.get(code, f"0x{code:08X}")
        self.log_message(f"FOC 故障上报: {name} (0x{code:08X})", 'error')
        if self.pending_ack is not None:
            try:
                self.pending_ack['timer'].stop()
            except Exception:
                pass
            self.pending_ack = None
        self.motor_running = False
        self.speed_poll_timer.stop()
        self._apply_monitor_state("fault")

    def handle_align_done(self):
        self.log_message("转子对齐完成", 'info')
        self._apply_monitor_state("idle")

    def toggle_debug_mode(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        if self.pending_ack is not None:
            self.log_message("有命令正在等待确认", 'info')
            return
        target_state = not self.debug_mode_active
        val = 1 if target_state else 0
        frame = build_foc_frame(0x19, struct.pack('<B', val))
        self.send_with_ack(frame, 0x19, "调试模式切换", 2000,
                           on_success=lambda p: self._on_debug_confirmed(target_state),
                           on_timeout=lambda: QMessageBox.warning(self, "无响应", "调试模式切换超时"))
        self.log_message(f"已发送调试模式请求 (值: {val})", 'info')

    def _on_debug_confirmed(self, target_state):
        self.debug_mode_active = target_state
        self.update_debug_btn_ui()
        self.log_message(f"调试模式已{'开启' if target_state else '关闭'}", 'info')

    def update_debug_btn_ui(self):
        self._set_btn_active(self.debug_btn, self.debug_mode_active)

    @staticmethod
    def _calc_expected_len(mask: int) -> int:
        n = 0
        for bit, sz in [(0x001, 2), (0x002, 2), (0x004, 2), (0x008, 2), (0x010, 2),
                        (0x020, 2), (0x040, 2), (0x080, 2), (0x100, 2), (0x200, 6),
                        (0x400, 8), (0x800, 8), (0x1000, 2)]:
            if mask & bit:
                n += sz
        return n

    def handle_telemetry_report(self, payload):
        t = time.monotonic()
        expected = self._calc_expected_len(self.parsing_mask)
        if expected != len(payload):
            expected_ui = self._calc_expected_len(self.telemetry_mask)
            if expected_ui == len(payload):
                self.parsing_mask = self.telemetry_mask
            else:
                self.log_message(
                    f"遥测长度不匹配: {len(payload)} / parsing期望 {expected} / ui期望 {expected_ui}",
                    'error')
                return
        mask = self.parsing_mask
        off = 0
    
        def take(n):
            nonlocal off
            b = payload[off:off+n]
            off += n
            return b
    
        if mask & 0x01:
            self.data_buf_adc1.append((t, struct.unpack('<H', take(2))[0] / 16.0))
        if mask & 0x02:
            self.data_buf_adc2.append((t, struct.unpack('<H', take(2))[0] / 16.0))
        if mask & 0x04:
            self.data_buf_ia.append((t, struct.unpack('<h', take(2))[0] / 100.0))
        if mask & 0x08:
            self.data_buf_ib.append((t, struct.unpack('<h', take(2))[0] / 100.0))
        if mask & 0x10:
            self.data_buf_ic.append((t, struct.unpack('<h', take(2))[0] / 100.0))
        if mask & 0x20:
            self.data_buf_id.append((t, struct.unpack('<h', take(2))[0] / 100.0))
        if mask & 0x40:
            self.data_buf_iq.append((t, struct.unpack('<h', take(2))[0] / 100.0))
        if mask & 0x80:
            self.data_buf_speed.append((t, struct.unpack('<h', take(2))[0]))
        if mask & 0x100:
            self.data_buf_calc_cycle.append((t, struct.unpack('<H', take(2))[0]))
        if mask & 0x200:
            self.data_buf_pwm_u.append((t, struct.unpack('<H', take(2))[0]))
            self.data_buf_pwm_v.append((t, struct.unpack('<H', take(2))[0]))
            self.data_buf_pwm_w.append((t, struct.unpack('<H', take(2))[0]))
        if mask & 0x400:
            self.data_buf_dpi_1.append((t, struct.unpack('<h', take(2))[0] / 100.0))
            self.data_buf_dpi_2.append((t, struct.unpack('<h', take(2))[0] / 100.0))
            self.data_buf_dpi_3.append((t, struct.unpack('<h', take(2))[0] / 100.0))
            self.data_buf_dpi_4.append((t, struct.unpack('<h', take(2))[0] / 100.0))
        if mask & 0x800:
            self.data_buf_qpi_1.append((t, struct.unpack('<h', take(2))[0] / 100.0))
            self.data_buf_qpi_2.append((t, struct.unpack('<h', take(2))[0] / 100.0))
            self.data_buf_qpi_3.append((t, struct.unpack('<h', take(2))[0] / 100.0))
            self.data_buf_qpi_4.append((t, struct.unpack('<h', take(2))[0] / 100.0))
        if mask & 0x1000:
            self.data_buf_bemf.append((t, struct.unpack('<h', take(2))[0] / 100.0))
    
        self.waveform_data_updated = True

    @staticmethod
    def _buf_to_xy(buf):
        if not buf:
            return [], []
        t0 = buf[0][0]
        xs = [p[0] - t0 for p in buf]
        ys = [p[1] for p in buf]
        return xs, ys

    def update_waveforms(self):
        if self.paused:
            return
        for i, config in enumerate(self.area_config):
            if config is None:
                continue
            curves = self.area_curves[i]
            if not curves:
                continue
    
            if config == "adc1":
                xs, ys = self._buf_to_xy(self.data_buf_adc1)
                if xs:
                    curves[0].setData(xs, ys)
            elif config == "adc2":
                xs, ys = self._buf_to_xy(self.data_buf_adc2)
                if xs:
                    curves[0].setData(xs, ys)
            elif config == "three_phase":
                if len(curves) >= 3:
                    xs, ys = self._buf_to_xy(self.data_buf_ia)
                    if xs:
                        curves[0].setData(xs, ys)
                    xs, ys = self._buf_to_xy(self.data_buf_ib)
                    if xs:
                        curves[1].setData(xs, ys)
                    xs, ys = self._buf_to_xy(self.data_buf_ic)
                    if xs:
                        curves[2].setData(xs, ys)
            elif config == "pwm":
                if len(curves) >= 3:
                    xs, ys = self._buf_to_xy(self.data_buf_pwm_u)
                    if xs:
                        curves[0].setData(xs, ys)
                    xs, ys = self._buf_to_xy(self.data_buf_pwm_v)
                    if xs:
                        curves[1].setData(xs, ys)
                    xs, ys = self._buf_to_xy(self.data_buf_pwm_w)
                    if xs:
                        curves[2].setData(xs, ys)
            elif config == "dpi":
                bufs = [self.data_buf_dpi_1, self.data_buf_dpi_2,
                        self.data_buf_dpi_3, self.data_buf_dpi_4]
                if i < len(bufs):
                    xs, ys = self._buf_to_xy(bufs[i])
                    if xs:
                        curves[0].setData(xs, ys)
            elif config == "qpi":
                bufs = [self.data_buf_qpi_1, self.data_buf_qpi_2,
                        self.data_buf_qpi_3, self.data_buf_qpi_4]
                if i < len(bufs):
                    xs, ys = self._buf_to_xy(bufs[i])
                    if xs:
                        curves[0].setData(xs, ys)
            elif config == "id":
                xs, ys = self._buf_to_xy(self.data_buf_id)
                if xs:
                    curves[0].setData(xs, ys)
            elif config == "iq":
                xs, ys = self._buf_to_xy(self.data_buf_iq)
                if xs:
                    curves[0].setData(xs, ys)
            elif config == "speed":
                xs, ys = self._buf_to_xy(self.data_buf_speed)
                if xs:
                    curves[0].setData(xs, ys)
            elif config == "calc_cycle":
                xs, ys = self._buf_to_xy(self.data_buf_calc_cycle)
                if xs:
                    curves[0].setData(xs, ys)
            elif config == "bemf":
                xs, ys = self._buf_to_xy(self.data_buf_bemf)
                if xs:
                    curves[0].setData(xs, ys)
    
        if self.waveform_data_updated:
            if self.auto_range_enabled:
                for i in range(4):
                    if self.area_config[i] is not None:
                        self.plot_widgets[i].autoRange()
            self.waveform_data_updated = False

    def export_waveforms_csv(self):
        if not any(self.area_config[i] is not None for i in range(4)):
            QMessageBox.information(self, "提示", "当前没有可导出的波形")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出波形", "waveforms.csv", "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        if not filepath:
            return
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for i, config in enumerate(self.area_config):
                    if config is None:
                        continue
                    writer.writerow([f"# Area {i+1}: {config}"])
                    if config in ("three_phase", "pwm"):
                        if config == "three_phase":
                            bufs = [self.data_buf_ia, self.data_buf_ib, self.data_buf_ic]
                            names = ["Ia", "Ib", "Ic"]
                        else:
                            bufs = [self.data_buf_pwm_u, self.data_buf_pwm_v, self.data_buf_pwm_w]
                            names = ["PWM_U", "PWM_V", "PWM_W"]
                        n = min(len(b) for b in bufs) if bufs else 0
                        if n > 0:
                            t0 = bufs[0][0][0]
                            writer.writerow(["time_s"] + names)
                            for k in range(n):
                                t = bufs[0][k][0] - t0
                                writer.writerow([f"{t:.4f}"] + [f"{bufs[j][k][1]:.4f}" for j in range(3)])
                    else:
                        buf = self._get_buf_by_config(config, i)
                        if buf:
                            t0 = buf[0][0]
                            writer.writerow(["time_s", config])
                            for t, v in buf:
                                writer.writerow([f"{t-t0:.4f}", f"{v:.4f}"])
                    writer.writerow([])
            self.log_message(f"波形已导出: {filepath}", 'info')
        except Exception as e:
            self.log_message(f"导出失败: {e}", 'error')

    def _get_buf_by_config(self, config, idx):
        mapping = {
            "adc1": self.data_buf_adc1, "adc2": self.data_buf_adc2,
            "id": self.data_buf_id, "iq": self.data_buf_iq,
            "speed": self.data_buf_speed, "calc_cycle": self.data_buf_calc_cycle,
            "bemf": self.data_buf_bemf,
        }
        if config in mapping:
            return mapping[config]
        if config == "dpi":
            bufs = [self.data_buf_dpi_1, self.data_buf_dpi_2,
                    self.data_buf_dpi_3, self.data_buf_dpi_4]
            return bufs[idx] if idx < 4 else None
        if config == "qpi":
            bufs = [self.data_buf_qpi_1, self.data_buf_qpi_2,
                    self.data_buf_qpi_3, self.data_buf_qpi_4]
            return bufs[idx] if idx < 4 else None
        return None

    def toggle_single_telemetry(self, bit_index, btn_widget):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        self.telemetry_mask ^= (1 << bit_index)
        self._set_btn_active(btn_widget, bool((self.telemetry_mask >> bit_index) & 1))
        self.send_telemetry_mask()

    def toggle_three_phase_telemetry(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        all_on = (self.telemetry_mask & 0x04) and (self.telemetry_mask & 0x08) and (self.telemetry_mask & 0x10)
        if all_on:
            self.telemetry_mask &= ~(0x04 | 0x08 | 0x10)
            self._set_btn_active(self.three_phase_btn, False)
        else:
            self.telemetry_mask |= (0x04 | 0x08 | 0x10)
            self._set_btn_active(self.three_phase_btn, True)
        self.send_telemetry_mask()

    def send_telemetry_mask(self):
        lsb = self.telemetry_mask & 0xFF
        msb = (self.telemetry_mask >> 8) & 0xFF
        enable = 1 if self.telemetry_mask > 0 else 0
        data = struct.pack('<BBB', lsb, msb, enable)
        frame = build_foc_frame(self.cmd_set_mask, data)
        if self.send_raw_bytes(frame, "[Tx 设置遥测掩码]"):
            self.parsing_mask = self.telemetry_mask

    def toggle_dpi_mode(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        if self.qpi_mode_active:
            self.toggle_qpi_mode()
        if not self.dpi_mode_active:
            self.saved_area_configs = self.area_config.copy()
            self.saved_select_texts = [b.text() for b in self.select_btns]
            for i in range(4):
                for curve in self.area_curves[i]:
                    self.plot_widgets[i].removeItem(curve)
                self.area_curves[i].clear()
                self.area_config[i] = "dpi"
                self.area_curves[i] = [self.plot_widgets[i].plot(pen=pg.mkPen(color='#00FF00', width=2))]
            for btn in self.select_btns:
                btn.setText("D轴PI")
                btn.setEnabled(False)
            self._set_btn_active(self.dpi_btn, True)
            self.telemetry_mask |= (1 << 10)
            self.dpi_mode_active = True
            self.send_telemetry_mask()
        else:
            for i in range(4):
                for curve in self.area_curves[i]:
                    self.plot_widgets[i].removeItem(curve)
                self.area_curves[i].clear()
                self.area_config[i] = None
            for i in range(4):
                sv = self.saved_area_configs[i]
                if sv is not None:
                    self.area_config[i] = sv
                    if sv in ("three_phase", "pwm"):
                        c1 = self.plot_widgets[i].plot(pen=pg.mkPen(color='#FF0000', width=2))
                        c2 = self.plot_widgets[i].plot(pen=pg.mkPen(color='#FFA500', width=2))
                        c3 = self.plot_widgets[i].plot(pen=pg.mkPen(color='#0000FF', width=2))
                        self.area_curves[i] = [c1, c2, c3]
                    else:
                        self.area_curves[i] = [self.plot_widgets[i].plot(pen=pg.mkPen(color='#00FF00', width=2))]
            for i, btn in enumerate(self.select_btns):
                btn.setText(self.saved_select_texts[i])
                btn.setEnabled(True)
            self._set_btn_active(self.dpi_btn, False)
            self.telemetry_mask &= ~(1 << 10)
            self.dpi_mode_active = False
            self.send_telemetry_mask()

    def toggle_qpi_mode(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        if self.dpi_mode_active:
            self.toggle_dpi_mode()
        if not self.qpi_mode_active:
            self.saved_area_configs = self.area_config.copy()
            self.saved_select_texts = [b.text() for b in self.select_btns]
            for i in range(4):
                for curve in self.area_curves[i]:
                    self.plot_widgets[i].removeItem(curve)
                self.area_curves[i].clear()
                self.area_config[i] = "qpi"
                self.area_curves[i] = [self.plot_widgets[i].plot(pen=pg.mkPen(color='#00FF00', width=2))]
            for btn in self.select_btns:
                btn.setText("Q轴PI")
                btn.setEnabled(False)
            self._set_btn_active(self.qpi_btn, True)
            self.telemetry_mask |= (1 << 11)
            self.qpi_mode_active = True
            self.send_telemetry_mask()
        else:
            for i in range(4):
                for curve in self.area_curves[i]:
                    self.plot_widgets[i].removeItem(curve)
                self.area_curves[i].clear()
                self.area_config[i] = None
            for i in range(4):
                sv = self.saved_area_configs[i]
                if sv is not None:
                    self.area_config[i] = sv
                    if sv in ("three_phase", "pwm"):
                        c1 = self.plot_widgets[i].plot(pen=pg.mkPen(color='#FF0000', width=2))
                        c2 = self.plot_widgets[i].plot(pen=pg.mkPen(color='#FFA500', width=2))
                        c3 = self.plot_widgets[i].plot(pen=pg.mkPen(color='#0000FF', width=2))
                        self.area_curves[i] = [c1, c2, c3]
                    else:
                        self.area_curves[i] = [self.plot_widgets[i].plot(pen=pg.mkPen(color='#00FF00', width=2))]
            for i, btn in enumerate(self.select_btns):
                btn.setText(self.saved_select_texts[i])
                btn.setEnabled(True)
            self._set_btn_active(self.qpi_btn, False)
            self.telemetry_mask &= ~(1 << 11)
            self.qpi_mode_active = False
            self.send_telemetry_mask()

    def handle_version_response(self, payload):
        self.slave_online = True
        version = payload.decode('ascii', errors='replace').strip()
        self.slave_indicator.setText("● 从机在线")
        self.slave_indicator.setStyleSheet("color: #10b981; font-weight: bold;")
        self.log_message(f"从机在线，固件版本: {version or '未知'}", 'info')

    def handle_drv_config_response(self, payload):
        if len(payload) < 18:
            self.log_message(f"DRV配置长度异常: {len(payload)}", 'error')
            return
        unpacked = struct.unpack('<BBBBBBBBBBBBBBHH', payload[:18])
        config = {
            'pwm_mode': unpacked[0], 'idrive_hs_source': unpacked[1], 'idrive_hs_sink': unpacked[2],
            'idrive_ls_source': unpacked[3], 'idrive_ls_sink': unpacked[4], 'tdrive': unpacked[5],
            'dead_time': unpacked[6], 'ocp_mode': unpacked[7], 'ocp_deglitch': unpacked[8],
            'vds_level': unpacked[9], 'retry_mode': unpacked[10], 'cpuv_enabled': unpacked[11],
            'gdf_enabled': unpacked[12], 'otw_report': unpacked[13],
            'fault1': unpacked[14], 'fault2': unpacked[15],
        }
        self.log_message("已读取 DRV 配置", 'info')
        self.update_drv_config_ui(config)
    
        if self.drv_verify_pending is not None:
            expected = self.drv_verify_pending
            self.drv_verify_pending = None
            mismatches = []
            key_map = {
                'pwm_mode': 'pwmMode', 'idrive_hs_source': 'idriveHsSource',
                'idrive_hs_sink': 'idriveHsSink', 'idrive_ls_source': 'idriveLsSource',
                'idrive_ls_sink': 'idriveLsSink', 'tdrive': 'tDrive',
                'dead_time': 'deadTime', 'ocp_mode': 'ocpMode',
                'ocp_deglitch': 'ocpDeglitch', 'vds_level': 'vdsLevel',
                'retry_mode': 'retryTime', 'cpuv_enabled': 'enableCpuv',
                'gdf_enabled': 'enableGdf', 'otw_report': 'enableOtwReport',
            }
            for k, expect_v in expected.items():
                actual_v = config.get(k)
                if actual_v != expect_v:
                    mismatches.append(f"{key_map.get(k, k)}: 期望 {expect_v} 实际 {actual_v}")
            if mismatches:
                msg = "DRV 配置回读不一致:\n" + "\n".join(mismatches)
                self.log_message(msg, 'error')
                QMessageBox.warning(self, "回读校验失败", msg)
            else:
                self.log_message("DRV 配置回读校验通过 ✓", 'info')

    def send_raw_bytes(self, data: bytes, log_prefix="[Tx]") -> bool:
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "串口未打开")
            return False
        try:
            ok = self.serial_worker.send_data(data)
            ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            hex_show = ' '.join(f'{b:02X}' for b in data)
            if ok:
                self._append_log("tx", f"[{ts}] {log_prefix} HEX: {hex_show}")
            else:
                self._append_log("error",
                                 f'<span style="color:#e74c3c;">[{ts}] {log_prefix} 发送失败 HEX: {hex_show}</span>')
            return ok
        except Exception as e:
            self.log_message(f"发送失败: {str(e)}", 'error')
            return False

    def check_slave(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        self.slave_online = False
        self.slave_indicator.setText("● 从机离线")
        self.slave_indicator.setStyleSheet("color: #6B7280; font-weight: bold;")
        frame = build_foc_frame(0x07, b'')
        self.send_raw_bytes(frame, "[Tx 从机验证]")
        self.log_message("已发送从机验证请求", 'info')

    def request_drv_config(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        frame = build_foc_frame(CMD_READ_DRV)
        self.send_request(
            frame, CMD_READ_DRV, "读取DRV配置", 1000,
            on_timeout=lambda: self.log_message("读取 DRV 配置超时", 'error'),
        )

    def write_drv_config(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
    
        def get_val(key):
            widget, options = self.drv_widgets[key]
            cur = widget.currentText()
            if options:
                for val, text in options.items():
                    if text == cur:
                        return val
                return 0
            return 0
    
        cfg_raw = {
            'pwm_mode': get_val('pwm_mode'), 'idrive_hs_source': get_val('idrive_hs_source'),
            'idrive_hs_sink': get_val('idrive_hs_sink'), 'idrive_ls_source': get_val('idrive_ls_source'),
            'idrive_ls_sink': get_val('idrive_ls_sink'), 'tdrive': get_val('tdrive'),
            'dead_time': get_val('dead_time'), 'ocp_mode': get_val('ocp_mode'),
            'ocp_deglitch': get_val('ocp_deglitch'), 'vds_level': get_val('vds_level'),
            'retry_mode': get_val('retry_mode'), 'cpuv_enabled': get_val('cpuv_enabled'),
            'gdf_enabled': get_val('gdf_enabled'), 'otw_report': get_val('otw_report'),
        }
        data = struct.pack('<14B',
            cfg_raw['pwm_mode'], cfg_raw['idrive_hs_source'], cfg_raw['idrive_hs_sink'],
            cfg_raw['idrive_ls_source'], cfg_raw['idrive_ls_sink'], cfg_raw['tdrive'],
            cfg_raw['dead_time'], cfg_raw['ocp_mode'], cfg_raw['ocp_deglitch'],
            cfg_raw['vds_level'], cfg_raw['retry_mode'], cfg_raw['cpuv_enabled'],
            cfg_raw['gdf_enabled'], cfg_raw['otw_report'])
        frame = build_foc_frame(0x14, data)
        self.send_raw_bytes(frame, "[Tx 写入DRV配置]")
        self.log_message("已发送 DRV 配置写入请求", 'info')
    
        for k, v in cfg_raw.items():
            self.record_param_change(f"DRV.{k}", "—", str(v), "发送")
    
        self.drv_verify_pending = dict(cfg_raw)
        QTimer.singleShot(300, self._verify_drv_readback)

    def _verify_drv_readback(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            return
        if self.drv_verify_pending is None:
            return
        frame = build_foc_frame(0x13, b'')
        self.send_raw_bytes(frame, "[Tx 回读DRV配置]")

    def clear_drv_faults(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        frame = build_foc_frame(0x15, b'')
        self.send_raw_bytes(frame, "[Tx 清除故障]")

    def update_drv_config_ui(self, config_data):
        for key, value in config_data.items():
            if key not in self.drv_widgets:
                continue
            widget, options = self.drv_widgets[key]
            if options:
                text = options.get(value)
                if text:
                    widget.setCurrentText(text)
            else:
                widget.setText(f"0x{value:04X}")

    def run_rotor_alignment(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        frame = build_foc_frame(CMD_ALIGN, b'')
        self.send_with_ack(
            frame, CMD_ALIGN, "转子对齐", 1000,
            on_success=lambda _p: self._on_align_accepted(),
            on_timeout=lambda: self.log_message("转子对齐命令超时", 'error'),
        )

    def _on_align_accepted(self):
        self._apply_monitor_state("align")
        self.log_message("转子对齐已开始，等待 0x89 完成事件", 'info')

    def run_motor_start(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        if self.motor_running:
            self.log_message("电机已在运行", 'info')
            return
        self.motor_running = True
        target = self.speed_slider.value()
        self.last_sent_speed = None
        self.send_speed_cmd(target)
        interval = max(50, int(self.speed_interval_spin.value()))
        self.speed_poll_timer.setInterval(interval)
        self.speed_poll_timer.start()
        self._apply_monitor_state("running")

        frame = build_foc_frame(CMD_MOTOR_START, b'')
        self.send_raw_bytes(frame, "[Tx 电机启动]")
        self.log_message(
            f"已发送电机启动命令，目标 {target} RPM，下发间隔 {interval} ms",
            'info',
        )

    def run_motor_stop(self):
        if not self.serial_worker or not self.serial_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        self.motor_running = False
        self.speed_poll_timer.stop()
        self._apply_monitor_state("idle")
        frame = build_foc_frame(CMD_MOTOR_STOP, b'')
        self.send_raw_bytes(frame, "[Tx 电机停止]")
        self.log_message("已发送电机停止命令", 'info')

    def _append_log(self, tag, html):
        self.log_entries.append((tag, html))
        if self._log_passes_filter(tag):
            self.log_area.append(html)
            self.scroll_log_to_bottom()

    def _log_passes_filter(self, tag):
        if self.log_filter is None:
            return True
        f = self.log_filter.currentText()
        if f == "全部":
            return True
        if f == "仅Tx":
            return tag == "tx"
        if f == "仅Rx":
            return tag == "rx"
        if f == "仅错误":
            return tag == "error"
        if f == "仅参数":
            return tag == "param"
        return True

    def _rebuild_log(self):
        if self.log_filter is None or self.log_area is None:
            return
        self.log_area.clear()
        for tag, html in self.log_entries:
            if self._log_passes_filter(tag):
                self.log_area.append(html)
        self.scroll_log_to_bottom()

    def record_param_change(self, name, old, new, success):
        ts = datetime.now().strftime('%H:%M:%S')
        html = (f'<span style="color:#FBBF24;">[{ts}] [PARAM] '
                f'{name}: {old} → {new} ({success})</span>')
        self._append_log("param", html)

    def log_message(self, msg, tag='info'):
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        if tag == 'error':
            html = f'<span style="color:#e74c3c;">[{ts}] {msg}</span>'
        elif tag == 'info':
            html = f'<span style="color:#9ca3af;">[{ts}] {msg}</span>'
        else:
            html = f'[{ts}] {msg}'
        self._append_log(tag, html)

    def scroll_log_to_bottom(self):
        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_area.setTextCursor(cursor)

    def clear_log(self):
        self.log_entries.clear()
        self.log_area.clear()

    def save_log(self):
        content = self.log_area.toPlainText()
        if not content.strip():
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "保存日志", "", "文本文件 (*.txt);;所有文件 (*.*)")
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log_message(f"日志已保存: {filepath}", 'info')
            except Exception as e:
                self.log_message(f"保存失败: {e}", 'error')
