# -*- coding: utf-8 -*-
"""FOC / DRV8320S 常量与遥测通道定义（行为与原 FOC 脚本一致）。"""

from __future__ import annotations

import struct

# 命令码（通信协议 v1.1）
CMD_SET_SPEED = 0x01
CMD_SET_CURRENT_PI = 0x02
CMD_SET_SPEED_PID = 0x03
CMD_MOTOR_START = 0x04
CMD_MOTOR_STOP = 0x05
CMD_REQUEST_TELEMETRY = 0x06
CMD_VERSION = 0x07
CMD_SET_STARTUP = 0x08
CMD_ALIGN = 0x09
CMD_GET_STARTUP = 0x0A
CMD_SET_MOTOR_PARAMS = 0x0B
CMD_GET_MOTOR_PARAMS = 0x0C
CMD_READ_DRV = 0x13
CMD_WRITE_DRV = 0x14
CMD_CLEAR_FAULT = 0x15
CMD_SET_TELEMETRY = 0x17
CMD_TELEMETRY_REPORT = 0x18
CMD_DEBUG = 0x19
CMD_ACK = 0x80
CMD_ERR_INVALID_CMD = 0x82
CMD_ERR_NOT_CONFIGURED = 0x83
CMD_ERR_PARAM = 0x84
CMD_ERR_BUSY = 0x85
CMD_ERR_HW = 0x86
CMD_ERR_STATE = 0x87
CMD_FAULT_REPORT = 0x88
CMD_ALIGN_DONE = 0x89

# 兼容旧代码里的命名
CMD_PI_D = CMD_SET_CURRENT_PI
CMD_PI_SPEED = CMD_SET_SPEED_PID

STARTUP_FORMAT = "<fIfIf"
MOTOR_FORMAT = "<ffffB"

DEFAULT_STARTUP = {
    "align_current_a": 1.0,
    "align_time_ms": 1000,
    "openloop_current_a": 1.5,
    "openloop_time_ms": 3000,
    "openloop_freq_hz": 120.0,
}

DEFAULT_MOTOR = {
    "R": 0.055,
    "Ld": 0.000020,
    "Lq": 0.000020,
    "flux_link": 0.0012,
    "pole_pairs": 7,
}

ERROR_NAMES = {
    CMD_ERR_INVALID_CMD: "ERR_INVALID_CMD",
    CMD_ERR_NOT_CONFIGURED: "ERR_NOT_CONFIGURED",
    CMD_ERR_PARAM: "ERR_PARAM",
    CMD_ERR_BUSY: "ERR_BUSY",
    CMD_ERR_HW: "ERR_HW",
    CMD_ERR_STATE: "ERR_STATE",
}

FAULT_NAMES = {
    0x00000000: "NONE",
    0x00000001: "HRTIM_FLT1",
    0xC0DE0001: "CORDIC_MODE",
    0xC0DE0002: "OPENLOOP_TIMEOUT",
    0xC0DE0003: "OVERCURRENT",
    0xC0DE0004: "INVALID_INPUT",
}


def pack_startup_config(values: dict) -> bytes:
    return struct.pack(
        STARTUP_FORMAT,
        float(values["align_current_a"]),
        int(values["align_time_ms"]),
        float(values["openloop_current_a"]),
        int(values["openloop_time_ms"]),
        float(values["openloop_freq_hz"]),
    )


def unpack_startup_config(data: bytes) -> dict:
    if len(data) < 20:
        raise ValueError("启动参数长度必须为 20 字节")
    a, b, c, d, e = struct.unpack(STARTUP_FORMAT, data[:20])
    return {
        "align_current_a": a,
        "align_time_ms": b,
        "openloop_current_a": c,
        "openloop_time_ms": d,
        "openloop_freq_hz": e,
    }


def pack_motor_params(values: dict) -> bytes:
    return struct.pack(
        MOTOR_FORMAT,
        float(values["R"]),
        float(values["Ld"]),
        float(values["Lq"]),
        float(values["flux_link"]),
        int(values["pole_pairs"]),
    )


def unpack_motor_params(data: bytes) -> dict:
    if len(data) < 17:
        raise ValueError("电机参数长度必须为 17 字节")
    r, ld, lq, flux, poles = struct.unpack(MOTOR_FORMAT, data[:17])
    return {
        "R": r,
        "Ld": ld,
        "Lq": lq,
        "flux_link": flux,
        "pole_pairs": poles,
    }


PWM_MODES = {0: "6x PWM (6路独立)", 1: "3x PWM (3路互补)", 2: "1x PWM (单路)", 3: "独立模式 (3路独立)"}
TDRIVE_OPTIONS = {0: "500 ns", 1: "1 µs", 2: "2 µs", 3: "4 µs"}
DEADTIME_OPTIONS = {0: "50 ns", 1: "100 ns", 2: "200 ns", 3: "400 ns"}
OCP_MODES = {0: "锁存模式 (Latch)", 1: "自动重试 (Auto-Retry)", 2: "仅报告 (Report Only)", 3: "禁用"}
OCP_DEGLITCH_OPTIONS = {0: "2 µs", 1: "4 µs", 2: "6 µs", 3: "8 µs"}
VDS_LEVELS = {
    0: "0.06 V", 1: "0.13 V", 2: "0.20 V", 3: "0.26 V", 4: "0.31 V", 5: "0.45 V",
    6: "0.53 V", 7: "0.60 V", 8: "0.68 V", 9: "0.75 V", 10: "0.94 V", 11: "1.13 V",
    12: "1.30 V", 13: "1.50 V", 14: "1.70 V", 15: "1.88 V",
}
RETRY_OPTIONS = {0: "4 ms", 1: "50 µs"}
IDRIVEP_OPTIONS = {
    0: "10 mA", 1: "30 mA", 2: "60 mA", 3: "80 mA", 4: "120 mA", 5: "140 mA",
    6: "170 mA", 7: "190 mA", 8: "260 mA", 9: "330 mA", 10: "370 mA",
    11: "440 mA", 12: "570 mA", 13: "680 mA", 14: "820 mA", 15: "1000 mA",
}
IDRIVEN_OPTIONS = {
    0: "20 mA", 1: "60 mA", 2: "120 mA", 3: "160 mA", 4: "240 mA", 5: "280 mA",
    6: "340 mA", 7: "380 mA", 8: "520 mA", 9: "660 mA", 10: "740 mA",
    11: "880 mA", 12: "1140 mA", 13: "1360 mA", 14: "1640 mA", 15: "2000 mA",
}

DEFAULT_DRV_CONFIG = {
    "pwm_mode": 0,
    "dead_time": 0,
    "vds_level": 7,
    "tdrive": 3,
    "idrive_hs_source": 11,
    "idrive_hs_sink": 11,
    "idrive_ls_source": 11,
    "idrive_ls_sink": 11,
    "ocp_mode": 0,
    "ocp_deglitch": 1,
    "retry_mode": 0,
    "cpuv_enabled": 1,
    "gdf_enabled": 1,
    "otw_report": 0,
}

# 遥测掩码位定义（与 handle_telemetry_report 一致）
TELEMETRY_BITS: dict[int, tuple[str, int]] = {
    0x001: ("ADC1源码", 2),
    0x002: ("ADC2源码", 2),
    0x004: ("Ia 电流", 2),
    0x008: ("Ib 电流", 2),
    0x010: ("Ic 电流", 2),
    0x020: ("D轴电流", 2),
    0x040: ("Q轴电流", 2),
    0x080: ("转速", 2),
    0x100: ("计算周期", 2),
    0x200: ("三相占空比", 6),
    0x400: ("D轴PI", 8),
    0x800: ("Q轴PI", 8),
    0x1000: ("反电动势", 2),
}

TELEMETRY_GROUPS: list[tuple[str, list[tuple[str, int]]]] = [
    ("基础量", [("ADC1源码", 0), ("ADC2源码", 1), ("计算周期", 8), ("转速", 7)]),
    ("电流环", [("三相电流", -1), ("D轴电流", 5), ("Q轴电流", 6), ("反电动势", 12)]),
    ("PWM / PI", [("三相占空比", 9), ("D轴PI", 10), ("Q轴PI", 11)]),
]

CHANNEL_OPTIONS = [
    ("ADC1 源码", "adc1"),
    ("ADC2 源码", "adc2"),
    ("三相电流", "three_phase"),
    ("D 轴电流", "id"),
    ("Q 轴电流", "iq"),
    ("转速", "speed"),
    ("计算周期", "calc_cycle"),
    ("三相占空比", "pwm"),
    ("反电动势", "bemf"),
    ("不使用", None),
]

CHANNEL_DISPLAY = {
    "adc1": "ADC1 源码",
    "adc2": "ADC2 源码",
    "three_phase": "三相电流",
    "id": "D 轴电流",
    "iq": "Q 轴电流",
    "speed": "转速",
    "calc_cycle": "计算周期",
    "pwm": "三相占空比",
    "bemf": "反电动势",
}

# 通道曲线颜色（与原名一致，改成主题色）
CURVE_COLORS = {
    "single": "#38BDF8",
    "three": ("#F87171", "#FBBF24", "#38BDF8"),
}


def calc_expected_len(mask: int) -> int:
    return sum(size for bit, (_, size) in TELEMETRY_BITS.items() if mask & bit)
