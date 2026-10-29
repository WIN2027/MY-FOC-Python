# -*- coding: utf-8 -*-
"""公共串口协议：0x5A + CMD + LEN + DATA + CRC8。

FOC 与 2.4G 工程使用完全相同的帧格式：
    - 帧头 0x5A
    - CRC8: poly=0x07, init=0xFF, refin/refout=False, xorout=0x00
    - 校验范围 CMD + LEN + DATA
"""

from __future__ import annotations

from dataclasses import dataclass

SOF = 0x5A
CRC8_POLY = 0x07
CRC8_INIT = 0xFF


def crc8(data: bytes) -> int:
    crc = CRC8_INIT
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ CRC8_POLY) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def u16(lo: int, hi: int) -> int:
    return (lo & 0xFF) | ((hi & 0xFF) << 8)


def s16(lo: int, hi: int) -> int:
    value = u16(lo, hi)
    return value - 0x10000 if value & 0x8000 else value


def s8(value: int) -> int:
    return value - 0x100 if value >= 0x80 else value


def build_frame(cmd: int, payload: bytes = b"") -> bytes:
    if not 0 <= cmd <= 0xFF:
        raise ValueError("CMD 必须在 0x00~0xFF 之间")
    payload = bytes(payload)
    if len(payload) > 255:
        raise ValueError("净荷不能超过 255 字节")
    body = bytes((cmd, len(payload))) + payload
    return bytes((SOF,)) + body + bytes((crc8(body),))


@dataclass(frozen=True, slots=True)
class Frame:
    cmd: int
    payload: bytes
    raw: bytes


def parse_stream(buffer: bytes) -> tuple[list[Frame], list[bytes], bytes]:
    """从字节流中切出帧。

    返回 (CRC 正确的帧, CRC 错误的原始帧, 剩余未成帧字节)。
    遇到 CRC 错误只前移 1 字节，便于在坏帧内部重新同步 0x5A。
    """
    frames: list[Frame] = []
    bad_frames: list[bytes] = []
    index = 0
    length = len(buffer)
    while True:
        start = buffer.find(b"\x5a", index)
        if start < 0:
            return frames, bad_frames, b""
        if start + 4 > length:
            return frames, bad_frames, buffer[start:]
        cmd = buffer[start + 1]
        data_len = buffer[start + 2]
        total = 4 + data_len
        if start + total > length:
            return frames, bad_frames, buffer[start:]
        payload = buffer[start + 3:start + 3 + data_len]
        crc_rx = buffer[start + 3 + data_len]
        raw = bytes(buffer[start:start + total])
        if crc8(bytes((cmd, data_len)) + payload) != crc_rx:
            bad_frames.append(raw)
            index = start + 1
            continue
        frames.append(Frame(cmd, payload, raw))
        index = start + total
