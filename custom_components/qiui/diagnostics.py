"""Diagnostics support for the QIUI integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_CLIENT_ID, VERSION


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The platform API token is never stored on the entry and the client id is
    redacted, so the output is safe to attach to a GitHub issue.
    """
    coordinator = getattr(entry, "runtime_data", None)
    data = dict(entry.data)
    client_id = data.pop(CONF_CLIENT_ID, "") or ""
    data[CONF_CLIENT_ID] = f"{client_id[:8]}…" if client_id else ""

    diagnostics: dict[str, Any] = {
        "version": VERSION,
        "entry": {
            "title": entry.title,
            "data": data,
            "options": dict(entry.options),
        },
        "family": None,
        "device": None,
        "state": None,
        "parameters": None,
    }

    if coordinator is not None:
        device = coordinator.device
        state = coordinator.state_data
        diagnostics.update(
            {
                "family": {
                    "key": device.family.key,
                    "name": device.family.name,
                    "supports_bluetooth": device.family.supports_bluetooth,
                    "supports_cloud": device.family.supports_cloud,
                    "commands": sorted(device.family.endpoints),
                },
                "device": {
                    "address": device.address,
                    "serial_number": device.serial_number,
                    "type_id": device.type_id,
                },
                "state": {
                    "lock_state": state.lock_state,
                    "battery": state.battery,
                    "online": state.online,
                    "last_command": state.last_command,
                    "last_error": state.last_error,
                    "last_response": state.last_response,
                    "selections": dict(state.selections),
                },
                "parameters": dict(coordinator.params),
            }
        )

    return diagnostics
