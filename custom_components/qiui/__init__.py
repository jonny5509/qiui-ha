"""The QIUI integration."""

from __future__ import annotations

import logging
from typing import Any, TypeAlias

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .api import build_device
from .const import (
    CONF_COMMAND,
    CONF_DEVICE_ID,
    CONF_PARAMETERS,
    DOMAIN,
    NAME,
)
from .coordinator import QiuiCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LOCK,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

SERVICE_SEND_COMMAND = "send_command"

SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_COMMAND): cv.string,
        vol.Optional(CONF_PARAMETERS): dict,
    }
)

QiuiConfigEntry: TypeAlias = ConfigEntry[QiuiCoordinator]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register the integration level service."""

    async def _async_handle_send_command(call: ServiceCall) -> None:
        coordinator = _coordinator_for_device(hass, call.data[CONF_DEVICE_ID])
        command = call.data[CONF_COMMAND]
        if not coordinator.device.family.supports(command):
            raise ServiceValidationError(
                f"'{command}' is not supported by {coordinator.device.family.name}. "
                f"Supported commands: "
                f"{', '.join(sorted(coordinator.device.family.commands))}"
            )
        if (
            command in coordinator.device.family.dangerous_commands
            and not coordinator.allow_dangerous
        ):
            raise ServiceValidationError(
                "This command is disabled. Turn on 'Enable shock actions' in "
                "the integration options first."
            )
        await coordinator.async_execute(command, call.data.get(CONF_PARAMETERS) or {})

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        _async_handle_send_command,
        schema=SEND_COMMAND_SCHEMA,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: QiuiConfigEntry) -> bool:
    """Set up one QIUI device from a config entry."""
    device = build_device(
        address=entry.data["bluetooth_address"],
        serial_number=entry.data["serial_number"],
        type_id=entry.data["type_id"],
    )

    coordinator = QiuiCoordinator(hass, entry, device)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    _LOGGER.debug(
        "%s ready (%s, type %s, %s)",
        NAME,
        device.address,
        device.type_id,
        device.family.name,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: QiuiConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: QiuiConfigEntry
) -> None:
    """Reload the entry when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _coordinator_for_device(
    hass: HomeAssistant, device_id: str
) -> QiuiCoordinator:
    """Resolve the coordinator that belongs to a device registry entry."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(f"Unknown device: {device_id}")

    for entry_id in device_entry.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN:
            coordinator: QiuiCoordinator | None = getattr(
                entry, "runtime_data", None
            )
            if coordinator is not None:
                return coordinator

    raise ServiceValidationError(
        f"{device_id} is not managed by the {NAME} integration"
    )
