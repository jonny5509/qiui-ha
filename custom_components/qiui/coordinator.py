"""State and command handling for the QIUI integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import QiuiApiClient, QiuiDevice
from .ble import CommandResult, QiuiBleTransport
from .const import (
    CMD_LOCK,
    CMD_UNLOCK,
    CONF_ALLOW_DANGEROUS,
    CONF_COMMAND_FORMAT,
    CONF_NOTIFY_UUID,
    CONF_RESPONSE_TIMEOUT,
    CONF_SERVICE_UUID,
    CONF_TRANSPORT,
    CONF_WRITE_TOKEN,
    CONF_WRITE_UUID,
    DEFAULT_COMMAND_FORMAT,
    DEFAULT_RESPONSE_TIMEOUT,
    DEFAULT_TRANSPORT,
    DOMAIN,
    TRANSPORT_BLUETOOTH,
    TRANSPORT_CLOUD,
)
from .exceptions import (
    QiuiApiError,
    QiuiAuthError,
    QiuiBleError,
    QiuiConnectionError,
    QiuiDeviceUnavailable,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class QiuiState:
    """Live state of a QIUI device."""

    lock_state: str | None = None
    battery: int | None = None
    online: bool | None = None
    last_command: str | None = None
    last_response: str | None = None
    last_error: str | None = None
    selections: dict[str, str] = field(default_factory=dict)
    cloud_status: dict[str, Any] = field(default_factory=dict)


class QiuiCoordinator(DataUpdateCoordinator[QiuiState]):
    """Coordinate cloud calls and Bluetooth round trips for one device.

    There is nothing to poll: the platform has no status endpoint and reading a
    BLE lock would require waking it up.  The coordinator therefore only carries
    state and serialises commands (QIUI hardware accepts one connection at a
    time).
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, device: QiuiDevice
    ) -> None:
        """Initialise the coordinator from a config entry."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}:{entry.title}",
            update_interval=None,
        )
        self.entry = entry
        self.api = QiuiApiClient(
            hass,
            client_id=entry.data["client_id"],
            environment=entry.data["environment"],
        )
        self.device = device
        self.state_data = QiuiState()
        self.params: dict[str, float] = {
            spec.param: spec.default
            for spec in self.device.family.numbers
            if spec.param
        }
        for spec in self.device.family.selects:
            self.state_data.selections[spec.key] = spec.default

        options = entry.options
        self.allow_dangerous = bool(options.get(CONF_ALLOW_DANGEROUS, False))
        self.transport_preference = options.get(CONF_TRANSPORT, DEFAULT_TRANSPORT)
        self.ble = QiuiBleTransport(
            hass,
            self.device,
            self.api,
            write_token=bool(options.get(CONF_WRITE_TOKEN, True)),
            response_timeout=float(
                options.get(CONF_RESPONSE_TIMEOUT, DEFAULT_RESPONSE_TIMEOUT)
            ),
            command_format=options.get(CONF_COMMAND_FORMAT, DEFAULT_COMMAND_FORMAT),
            service_uuid=options.get(CONF_SERVICE_UUID) or None,
            write_uuid=options.get(CONF_WRITE_UUID) or None,
            notify_uuid=options.get(CONF_NOTIFY_UUID) or None,
        )

    # -- DataUpdateCoordinator ----------------------------------------------

    async def _async_update_data(self) -> QiuiState:
        """Return the current state (this integration is push driven)."""
        return self.state_data

    async def async_setup(self) -> None:
        """Validate the cloud connection before entities are created."""
        try:
            await self.api.async_validate()
        except QiuiAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (QiuiApiError, QiuiConnectionError) as err:
            raise ConfigEntryNotReady(str(err)) from err

    # -- commands -----------------------------------------------------------

    async def async_execute(
        self, command: str, params: dict[str, Any] | None = None
    ) -> CommandResult:
        """Send a command to the device."""
        merged = {**self.params, **(params or {})}
        try:
            result = await self._async_send(command, merged)
        except QiuiAuthError as err:
            self.entry.async_start_reauth(self.hass)
            self._record_failure(command, str(err))
            raise
        except (QiuiBleError, QiuiApiError, QiuiConnectionError) as err:
            self._record_failure(command, str(err))
            raise

        self.state_data.last_command = command
        self.state_data.last_error = None
        if result.response_hex:
            self.state_data.last_response = result.response_hex
        elif result.status:
            self.state_data.last_response = str(result.status)

        if result.status:
            self._apply_cloud_status(result.status)
        if command == CMD_LOCK:
            self.state_data.lock_state = "locked"
        elif command == CMD_UNLOCK:
            self.state_data.lock_state = "unlocked"

        self.async_set_updated_data(self.state_data)
        return result

    async def _async_send(
        self, command: str, params: dict[str, Any]
    ) -> CommandResult:
        """Pick a transport and run the command."""
        if not self.device.family.supports_bluetooth:
            return await self._async_send_cloud(command, params)

        preference = self.transport_preference

        if preference == TRANSPORT_CLOUD:
            return await self._async_send_cloud(command, params)

        if preference == TRANSPORT_BLUETOOTH or not self.device.family.supports_cloud:
            return await self.ble.async_execute(command, params)

        # auto: prefer a nearby Bluetooth link, fall back to the 4G cloud path.
        try:
            return await self.ble.async_execute(command, params)
        except QiuiDeviceUnavailable as err:
            _LOGGER.debug(
                "%s not reachable over Bluetooth (%s), using the 4G cloud",
                self.device.address,
                err,
            )
            return await self._async_send_cloud(command, params)

    async def _async_send_cloud(
        self, command: str, params: dict[str, Any]
    ) -> CommandResult:
        """Send a command through the 4G cloud endpoints."""
        data = await self.api.async_build_command(
            self.device, command, params, cloud=True
        )
        return CommandResult(
            command=command, status=data if isinstance(data, dict) else {}
        )

    # -- helpers ------------------------------------------------------------

    def _apply_cloud_status(self, status: dict[str, Any]) -> None:
        """Copy battery / online information from a cloud response."""
        battery = status.get("battery")
        if isinstance(battery, (int, float)):
            self.state_data.battery = int(battery)

        online = status.get("onlineStatus")
        if online is not None:
            self.state_data.online = str(online) in ("1", "True", "true")

        self.state_data.cloud_status = status

    def _record_failure(self, command: str, message: str) -> None:
        """Store the last failure for the diagnostic sensor."""
        self.state_data.last_command = command
        self.state_data.last_error = message
        self.state_data.last_response = None
        self.async_set_updated_data(self.state_data)

    def set_param(self, key: str, value: float) -> None:
        """Store a tunable value used by the action buttons."""
        self.params[key] = value

    def set_selection(self, key: str, value: str) -> None:
        """Store a select value."""
        self.state_data.selections[key] = value
        self.async_set_updated_data(self.state_data)
