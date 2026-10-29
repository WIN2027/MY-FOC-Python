# -*- coding: utf-8 -*-
"""控制中心协议层自检（不启动 GUI）。

运行：
    .venv\\Scripts\\python.exe tests\\test_protocol.py -v
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.protocol import build_frame, crc8, parse_stream, s16, s8, u16
from modules.foc.protocol import (
    CMD_SET_CURRENT_PI,
    CMD_SET_STARTUP,
    DEFAULT_MOTOR,
    DEFAULT_STARTUP,
    calc_expected_len,
    pack_motor_params,
    pack_startup_config,
    unpack_motor_params,
    unpack_startup_config,
)
from modules.lora.protocol import decode_local, decode_remote

SAMPLES = [
    "5A 19 0B 00 00 BF 01 A3 0B 59 0D F0 FF 0E 15",
    "5A 19 0B 00 00 C0 01 A7 0B 61 0D F0 FF 0E 14",
    "5A 19 0B 00 00 C1 01 A7 0B 6A 0D F0 FF 0E D2",
]


def sample_bytes(index=0) -> bytes:
    return bytes.fromhex(SAMPLES[index].replace(" ", ""))


class CoreProtocolTests(unittest.TestCase):
    def test_crc_known_frames(self):
        for text in SAMPLES:
            raw = bytes.fromhex(text.replace(" ", ""))
            self.assertEqual(crc8(raw[1:-1]), raw[-1], text)

    def test_parse_and_decode_remote(self):
        frames, bad, remain = parse_stream(sample_bytes())
        self.assertEqual(len(frames), 1)
        self.assertEqual(bad, [])
        self.assertEqual(remain, b"")
        frame = frames[0]
        self.assertEqual(frame.cmd, 0x19)
        telemetry = decode_remote(frame.payload)
        self.assertEqual(telemetry.seq, 447)
        self.assertAlmostEqual(telemetry.temp, 29.79, places=2)
        self.assertAlmostEqual(telemetry.hum, 34.17, places=2)
        self.assertEqual(telemetry.rssi, -16)
        self.assertEqual(telemetry.snr, 14)

    def test_sticky_and_fragmented(self):
        frames, _, remain = parse_stream(b"".join(sample_bytes(i) for i in range(3)))
        self.assertEqual(len(frames), 3)
        self.assertEqual(remain, b"")
        raw = sample_bytes()
        frames, _, remain = parse_stream(raw[:7])
        self.assertEqual(frames, [])
        self.assertEqual(remain, raw[:7])
        frames, _, remain = parse_stream(remain + raw[7:])
        self.assertEqual(len(frames), 1)

    def test_crc_error_resync(self):
        bad = bytearray(sample_bytes())
        bad[-1] ^= 0xFF
        frames, bad_frames, remain = parse_stream(bytes(bad))
        self.assertEqual(frames, [])
        self.assertEqual(len(bad_frames), 1)
        self.assertEqual(remain, b"")

    def test_build_roundtrip(self):
        payload = struct.pack("<bbHhHhb", 0, 0, 1234, -525, 6010, -40, 11)
        raw = build_frame(0x19, payload)
        frames, _, _ = parse_stream(raw)
        self.assertEqual(frames[0].payload, payload)
        self.assertEqual(frames[0].raw, raw)

    def test_local_decode(self):
        payload = struct.pack("<bHhH", 0, 42, -1250, 4512)
        frames, _, _ = parse_stream(build_frame(0x18, payload))
        telemetry = decode_local(frames[0].payload)
        self.assertEqual(telemetry.seq, 42)
        self.assertAlmostEqual(telemetry.temp, -12.50, places=2)
        self.assertAlmostEqual(telemetry.hum, 45.12, places=2)

    def test_signed_helpers(self):
        self.assertEqual(s8(0xFE), -2)
        self.assertEqual(s16(0xF0, 0xFF), -16)
        self.assertEqual(u16(0xBF, 0x01), 447)


class FocProtocolTests(unittest.TestCase):
    def test_expected_lengths(self):
        self.assertEqual(calc_expected_len(0x001), 2)
        self.assertEqual(calc_expected_len(0x200), 6)
        self.assertEqual(calc_expected_len(0x400), 8)
        self.assertEqual(calc_expected_len(0x004 | 0x008 | 0x010), 6)
        self.assertEqual(calc_expected_len(0x001 | 0x002 | 0x080), 6)

    def test_empty_payload_commands(self):
        for cmd in (0x04, 0x05, 0x07, 0x09, 0x13, 0x15):
            frames, bad, remain = parse_stream(build_frame(cmd))
            self.assertEqual(len(frames), 1)
            self.assertEqual(frames[0].cmd, cmd)
            self.assertEqual(frames[0].payload, b"")
            self.assertEqual(remain, b"")

    def test_startup_config_roundtrip(self):
        values = {
            "align_current_a": 1.0,
            "align_time_ms": 1000,
            "openloop_current_a": 1.5,
            "openloop_time_ms": 3000,
            "openloop_freq_hz": 120.0,
        }
        raw = pack_startup_config(values)
        self.assertEqual(len(raw), 20)
        self.assertEqual(unpack_startup_config(raw), values)
        frame = build_frame(CMD_SET_STARTUP, raw)
        frames, _, _ = parse_stream(frame)
        self.assertEqual(frames[0].payload, raw)

    def test_motor_params_roundtrip(self):
        values = {
            "R": 0.055,
            "Ld": 0.000020,
            "Lq": 0.000020,
            "flux_link": 0.0012,
            "pole_pairs": 7,
        }
        raw = pack_motor_params(values)
        self.assertEqual(len(raw), 17)
        decoded = unpack_motor_params(raw)
        for key in ("R", "Ld", "Lq", "flux_link"):
            self.assertAlmostEqual(decoded[key], values[key], places=9)
        self.assertEqual(decoded["pole_pairs"], values["pole_pairs"])

    def test_pi_payload_lengths(self):
        current_pi = struct.pack("<ffff", 0.05, 100.0, 0.05, 100.0)
        speed_pid = struct.pack("<fff", 0.01, 0.25, 0.01)
        self.assertEqual(len(current_pi), 16)
        self.assertEqual(len(speed_pid), 12)
        frames, _, _ = parse_stream(build_frame(CMD_SET_CURRENT_PI, current_pi))
        self.assertEqual(frames[0].cmd, CMD_SET_CURRENT_PI)
        self.assertEqual(len(frames[0].payload), 16)

    def test_default_param_payloads_match_protocol_examples(self):
        self.assertEqual(
            pack_startup_config(DEFAULT_STARTUP).hex(" ").upper(),
            "00 00 80 3F E8 03 00 00 00 00 C0 3F B8 0B 00 00 00 00 F0 42",
        )
        self.assertEqual(
            pack_motor_params(DEFAULT_MOTOR).hex(" ").upper(),
            "AE 47 61 3D AC C5 A7 37 AC C5 A7 37 52 49 9D 3A 07",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
