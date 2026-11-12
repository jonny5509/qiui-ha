"""Pure helpers for QIUI command payloads (no Home Assistant imports).

Keeping these functions free of Home Assistant imports makes them easy to unit
test and to reuse from tooling that talks to the platform outside of HA.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Iterable, Mapping
from typing import Any, Final

FORMAT_AUTO: Final = "auto"
FORMAT_HEX: Final = "hex"
FORMAT_BASE64: Final = "base64"
FORMAT_TEXT: Final = "text"

_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_B64_RE = re.compile(r"^[A-Za-z0-9+/_-]*={0,2}$")
_B64_ALPHABET = str.maketrans("-_", "+/")


def decode_payload(value: str, command_format: str = FORMAT_AUTO) -> bytes:
    """Decode a payload returned by the platform into raw bytes.

    The platform does not document the encoding and has used both hex and
    base64 strings, so ``auto`` tries hex first, then base64, then UTF-8.
    """
    if not value:
        return b""

    text = "".join(str(value).split())

    if command_format == FORMAT_HEX:
        return bytes.fromhex(text.removeprefix("0x"))

    if command_format == FORMAT_BASE64:
        decoded = _b64decode(text)
        if decoded is None:
            raise ValueError("Payload is not valid base64")
        return decoded

    if command_format == FORMAT_TEXT:
        return text.encode()

    if len(text) % 2 == 0 and _HEX_RE.match(text):
        try:
            return bytes.fromhex(text)
        except ValueError:
            pass

    decoded = _b64decode(text)
    if decoded is not None:
        return decoded

    return text.encode()


def _b64decode(text: str) -> bytes | None:
    """Decode base64 defensively, accepting the standard and URL safe alphabet."""
    if not text or not _B64_RE.match(text):
        return None
    padded = text + "=" * (-len(text) % 4)
    try:
        return base64.b64decode(padded.translate(_B64_ALPHABET), validate=True)
    except (binascii.Error, ValueError):
        return None


def build_command_body(
    device_body: Mapping[str, Any],
    command: str,
    params: Mapping[str, Any],
    *,
    allowed_params: Iterable[str] = (),
    nested: bool = False,
) -> dict[str, Any]:
    """Build the JSON body for a command endpoint.

    Some endpoints expect a flat body, others wrap the device data in
    ``basicDeviceApiReq``.  Only parameters that the endpoint documents are
    copied, so local settings such as ``steps`` never reach the platform.
    """
    body: dict[str, Any] = dict(device_body)
    extra = {
        key: params[key]
        for key in allowed_params
        if params.get(key) is not None
    }

    if nested:
        return {"basicDeviceApiReq": body, **extra}

    body.update(extra)
    return body
