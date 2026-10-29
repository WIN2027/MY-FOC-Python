# -*- coding: utf-8 -*-
"""2.4G LoRa 温湿度协议（STM32/2.4G）。"""

from __future__ import annotations

from dataclasses import dataclass

from core.protocol import Frame, build_frame, crc8, s16, s8, u16

CMD_LOCAL = 0x18
CMD_REMOTE = 0x19
CMD_STACK_OVERFLOW = 0xE0
CMD_SX_FAIL = 0xE1
CMD_ACK = 0x80
CMD_ERR_CRC = 0x81
CMD_ERR_CMD = 0x82

CMD_NAMES = {
    CMD_LOCAL: "本地遥测",
    CMD_REMOTE: "空中接收上报",
    CMD_STACK_OVERFLOW: "栈溢出告警",
    CMD_SX_FAIL: "SX1280 初始化失败",
    CMD_ACK: "通用应答",
    CMD_ERR_CRC: "CRC 错误应答",
    CMD_ERR_CMD: "无效命令应答",
}

RX_STATUS_TEXT = {0: "正常", -4: "包头错误", -8: "长度错误"}
HDC_STATUS_TEXT = {
    0: "正常",
    -1: "I2C 通信失败",
    -2: "CRC 校验失败",
    -3: "参数错误",
    -4: "转换超时",
    -5: "器件 ID 错误",
}
SX_STATUS_TEXT = {
    0: "正常",
    -1: "参数错误",
    -2: "SPI 通信失败",
    -3: "等待超时",
    -4: "命令错误",
    -5: "状态异常",
    -6: "CRC 错误",
    -7: "器件错误",
    -8: "长度错误",
    -9: "BUSY 超时",
}
SOURCE_NAMES = {"RX": "接收端", "TX": "发射端"}


@dataclass(slots=True)
class Sample:
    ts: float
    temp: float
    hum: float
    rssi: int | None
    snr: int | None
    seq: int
    source: str


@dataclass(slots=True)
class RemoteTelemetry:
    status: int
    remote_status: int
    seq: int
    temp: float
    hum: float
    rssi: int
    snr: int


@dataclass(slots=True)
class LocalTelemetry:
    status: int
    seq: int
    temp: float
    hum: float


def decode_remote(payload: bytes) -> RemoteTelemetry:
    if len(payload) != 11:
        raise ValueError("0x19 净荷长度必须为 11")
    return RemoteTelemetry(
        status=s8(payload[0]),
        remote_status=s8(payload[1]),
        seq=u16(payload[2], payload[3]),
        temp=s16(payload[4], payload[5]) / 100.0,
        hum=u16(payload[6], payload[7]) / 100.0,
        rssi=s16(payload[8], payload[9]),
        snr=s8(payload[10]),
    )


def decode_local(payload: bytes) -> LocalTelemetry:
    if len(payload) != 7:
        raise ValueError("0x18 净荷长度必须为 7")
    return LocalTelemetry(
        status=s8(payload[0]),
        seq=u16(payload[1], payload[2]),
        temp=s16(payload[3], payload[4]) / 100.0,
        hum=u16(payload[5], payload[6]) / 100.0,
    )


def hdc_status_text(code: int) -> str:
    return HDC_STATUS_TEXT.get(code, f"未知错误码 {code}")


def sx_status_text(code: int) -> str:
    return SX_STATUS_TEXT.get(code, f"未知错误码 {code}")


def rx_status_text(code: int) -> str:
    return RX_STATUS_TEXT.get(code, f"未知状态 {code}")


__all__ = [
    "CMD_LOCAL",
    "CMD_REMOTE",
    "CMD_STACK_OVERFLOW",
    "CMD_SX_FAIL",
    "CMD_ACK",
    "CMD_ERR_CRC",
    "CMD_ERR_CMD",
    "CMD_NAMES",
    "SOURCE_NAMES",
    "Sample",
    "RemoteTelemetry",
    "LocalTelemetry",
    "decode_remote",
    "decode_local",
    "hdc_status_text",
    "sx_status_text",
    "rx_status_text",
    "Frame",
    "build_frame",
    "crc8",
    "u16",
    "s16",
    "s8",
]
