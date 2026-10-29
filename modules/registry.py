# -*- coding: utf-8 -*-
"""功能模块注册表。

新增模块时：
1. 在 modules/ 下新建包；
2. 实现一个 QWidget 页面（含 title/subtitle/icon_name，可选 on_shown/on_hidden/
   shutdown/connection_changed/is_connected）；
3. 在 MODULE_SPECS 中加一条记录。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.settings import AppSettings


@dataclass(frozen=True)
class ModuleSpec:
    key: str
    name: str
    subtitle: str
    icon_name: str
    description: str
    tags: tuple[str, ...]
    factory: Callable[[AppSettings], object]


def _lora_factory(settings: AppSettings):
    from modules.lora.page import LoraPage

    return LoraPage(settings)


def _foc_factory(settings: AppSettings):
    from modules.foc.page import FocPage

    return FocPage(settings)


MODULE_SPECS: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        key="lora",
        name="2.4G 温湿度",
        subtitle="SX1280 · HDC1080 · 实时曲线与串口助手",
        icon_name="lora",
        description="双 Y 轴温湿度曲线、RSSI/SNR、丢包率、CSV 导出与完整的串口收发工具。",
        tags=("SX1280", "HDC1080", "0x18/0x19"),
        factory=_lora_factory,
    ),
    ModuleSpec(
        key="foc",
        name="FOC 电机控制",
        subtitle="DRV8320S · PID 调参 · 4 通道波形",
        icon_name="foc",
        description="DRV 配置、D/Q/速度环 PID、遥测波形、电机启停与 FOC 协议日志。",
        tags=("DRV8320S", "FOC", "PID"),
        factory=_foc_factory,
    ),
)


def spec_by_key(key: str) -> ModuleSpec | None:
    for spec in MODULE_SPECS:
        if spec.key == key:
            return spec
    return None
