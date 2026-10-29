# -*- coding: utf-8 -*-
"""通用串口读取线程。

- 所有帧经 `core.protocol.parse_stream` 切分。
- `frames_received` 只发 CRC 正确的帧，供 2.4G 模块使用。
- `frame_received` 同时发 CRC 正确与 CRC 错误的原始帧，供 FOC 模块保留原有
  “在 handle_frame 中再次校验并记录 CRC 错误”的行为。
"""

from __future__ import annotations

import threading
import time

import serial
import serial.tools.list_ports
from PySide6.QtCore import QThread, Signal

from .protocol import Frame, parse_stream


class SerialWorker(QThread):
    opened = Signal(bool, str)
    closed = Signal()
    error_occurred = Signal(str)
    raw_data = Signal(bytes)
    frames_received = Signal(object)   # list[Frame]
    frame_received = Signal(bytes)     # 原始帧（含 CRC 错误帧）
    crc_error = Signal(bytes)

    def __init__(
        self,
        port: str,
        baud: int = 115200,
        bytesize: int = 8,
        stopbits: float = 1.0,
        parity: str = serial.PARITY_NONE,
        parent=None,
    ):
        super().__init__(parent)
        self.port = port
        self.baud = baud
        self.bytesize = bytesize
        self.stopbits = stopbits
        self.parity = parity
        self._serial: serial.Serial | None = None
        self._stop_event = threading.Event()
        self._write_lock = threading.Lock()
        self._rx_buffer = bytearray()

    def run(self):
        try:
            self._serial = serial.serial_for_url(
                self.port,
                baudrate=self.baud,
                bytesize=self.bytesize,
                stopbits=self.stopbits,
                parity=self.parity,
                timeout=0.05,
                write_timeout=1.0,
            )
        except Exception as exc:  # noqa: BLE001
            self.opened.emit(False, str(exc))
            self.closed.emit()
            return

        try:
            self._serial.reset_input_buffer()
        except Exception:
            pass
        self.opened.emit(True, "")

        while not self._stop_event.is_set():
            try:
                waiting = self._serial.in_waiting
                if waiting > 0:
                    chunk = self._serial.read(waiting)
                else:
                    # 和老 FOC 线程一致：短暂休眠让串口驱动攒批，避免按字节
                    # 产生大量 raw_data 信号，把 GUI 日志/事件队列拖垮。
                    time.sleep(0.005)
                    continue
            except Exception as exc:  # noqa: BLE001
                if not self._stop_event.is_set():
                    self.error_occurred.emit(f"串口读取失败：{exc}")
                break
            if not chunk:
                continue
            self.raw_data.emit(chunk)
            self._rx_buffer.extend(chunk)
            frames, bad_frames, remain = parse_stream(bytes(self._rx_buffer))
            self._rx_buffer = bytearray(remain)

            for bad in bad_frames:
                self.crc_error.emit(bad)
                self.frame_received.emit(bad)
            if frames:
                for frame in frames:
                    self.frame_received.emit(frame.raw)
                self.frames_received.emit(frames)

        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
        except Exception:
            pass
        self.closed.emit()

    def write(self, data: bytes) -> bool:
        if not data:
            return False
        try:
            with self._write_lock:
                if self._serial and self._serial.is_open:
                    self._serial.write(data)
                    return True
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"串口发送失败：{exc}")
        return False

    # FOC 原代码使用 send_data
    def send_data(self, data: bytes) -> bool:
        return self.write(data)

    def stop(self):
        self._stop_event.set()
        if not self.wait(1500):
            try:
                if self._serial and self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
            self.wait(500)
