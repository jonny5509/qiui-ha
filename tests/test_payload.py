"""Tests for the pure payload helpers.

The component itself imports Home Assistant, so the module is loaded straight
from its file to keep these tests dependency free.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "custom_components" / "qiui" / "payload.py"
)
_spec = importlib.util.spec_from_file_location("qiui_payload", _MODULE_PATH)
payload = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(payload)


def test_decode_hex() -> None:
    assert payload.decode_payload("0001ABff") == b"\x00\x01\xab\xff"


def test_decode_hex_ignores_whitespace() -> None:
    assert payload.decode_payload("AA BB\nCC") == b"\xaa\xbb\xcc"


def test_decode_hex_with_prefix() -> None:
    assert payload.decode_payload("0x00ff", payload.FORMAT_HEX) == b"\x00\xff"


def test_decode_base64() -> None:
    assert payload.decode_payload("AAEC", payload.FORMAT_BASE64) == b"\x00\x01\x02"


def test_decode_auto_falls_back_to_base64() -> None:
    # "AQID" is not valid hex (odd length) and decodes to 0x01 0x02 0x03.
    assert payload.decode_payload("AQID") == b"\x01\x02\x03"


def test_decode_text() -> None:
    assert payload.decode_payload("hello", payload.FORMAT_TEXT) == b"hello"


def test_decode_empty() -> None:
    assert payload.decode_payload("") == b""


def test_decode_invalid_base64_raises() -> None:
    with pytest.raises(ValueError):
        payload.decode_payload("not base64!", payload.FORMAT_BASE64)


DEVICE = {
    "bluetoothAddress": "AA:BB:CC:DD:EE:FF",
    "serialNumber": "QIUI123",
    "typeId": 18,
}


def test_build_flat_body() -> None:
    body = payload.build_command_body(DEVICE, "unlock", {"steps": 3})
    assert body == DEVICE
    assert "steps" not in body


def test_build_nested_body_filters_parameters() -> None:
    body = payload.build_command_body(
        DEVICE,
        "vibration",
        {"vibrationDuration": 5, "vibrationIntensity": 3, "steps": 9},
        allowed_params=("vibrationDuration", "vibrationIntensity", "vibrationModel"),
        nested=True,
    )
    assert body["basicDeviceApiReq"] == DEVICE
    assert body["vibrationDuration"] == 5
    assert body["vibrationIntensity"] == 3
    assert "vibrationModel" not in body
    assert "steps" not in body


def test_build_flat_body_with_parameters() -> None:
    body = payload.build_command_body(
        DEVICE,
        "work_mode",
        {"workStatus": 1},
        allowed_params=("workStatus",),
        nested=False,
    )
    assert body["workStatus"] == 1
    assert body["typeId"] == 18
