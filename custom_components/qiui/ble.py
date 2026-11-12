"""Bluetooth transport for QIUI devices.

The QIUI platform does not talk to the hardware: it only *builds* encrypted
Bluetooth payloads.  This module connects to the device through Home
Assistant's Bluetooth stack (a local adapter or an ESPHome Bluetooth proxy),
subscribes to the notification characteristic, performs the token handshake
and writes the payload returned by the platform.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .api import QiuiApiClient, QiuiDevice
from .const import (
    CMD_LOCK,
    CMD_UNLOCK,
    FORMAT_AUTO,
    FamilySpec,
    family_for_service_uuids,
)
from .exceptions import QiuiBleError, QiuiDeviceUnavailable
from .payload import decode_payload

_LOGGER = logging.getLogger(__name__)

#: Small pause between repeated writes (the Pear Flower advances one detent per
#: written payload).
_REPEAT_DELAY = 0.15


@dataclass
class CommandResult:
    """Outcome of a single command round trip."""

    command: str
    payload: bytes | None = None
    response: bytes | None = None
    decrypted: Any = None
    status: dict[str, Any] = field(default_factory=dict)

    @property
    def response_hex(self) -> str | None:
        """Return the raw response as an upper case hex string."""
        return self.response.hex(" ").upper() if self.response else None


class QiuiBleTransport:
    """Execute commands against one device over Bluetooth LE."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: QiuiDevice,
        api: QiuiApiClient,
        *,
        write_token: bool = True,
        response_timeout: float = 8.0,
        command_format: str = FORMAT_AUTO,
        service_uuid: str | None = None,
        write_uuid: str | None = None,
        notify_uuid: str | None = None,
    ) -> None:
        """Initialise the transport."""
        self._hass = hass
        self._device = device
        self._api = api
        self._write_token = write_token
        self._response_timeout = response_timeout
        self._command_format = command_format
        self._service_uuid = (service_uuid or device.family.service_uuid or "").lower()
        self._write_uuid = (write_uuid or device.family.write_uuid or "").lower()
        self._notify_uuid = (notify_uuid or device.family.notify_uuid or "").lower()
        self._lock = asyncio.Lock()

    # -- public API ---------------------------------------------------------

    async def async_execute(
        self, command: str, params: dict[str, Any]
    ) -> CommandResult:
        """Run one command against the device."""
        async with self._lock:
            return await self._async_execute_locked(command, params)

    # -- internals ----------------------------------------------------------

    async def _async_execute_locked(
        self, command: str, params: dict[str, Any]
    ) -> CommandResult:
        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._device.address, connectable=True
        )
        if ble_device is None:
            raise QiuiDeviceUnavailable(
                f"{self._device.address} was not seen by any Bluetooth adapter. "
                "Move the device closer, or add a Bluetooth proxy in range."
            )

        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self._device.address,
                max_attempts=3,
            )
        except BleakError as err:
            raise QiuiBleError(
                f"Could not connect to {self._device.address}: {err}"
            ) from err

        try:
            write_char, notify_char = self._resolve_characteristics(client)
            return await self._async_run(
                client,
                command,
                params,
                write_uuid=write_char.uuid,
                notify_uuid=notify_char.uuid,
            )
        finally:
            try:
                await client.disconnect()
            except BleakError:  # pragma: no cover - best effort cleanup
                _LOGGER.debug("Ignoring error while disconnecting", exc_info=True)

    def _resolve_characteristics(
        self, client: BleakClient
    ) -> tuple[Any, Any]:
        """Find the write and notify characteristics."""
        services = client.services

        write_char = None
        notify_char = None

        if self._write_uuid:
            write_char = services.get_characteristic(self._write_uuid)
        if self._notify_uuid:
            notify_char = services.get_characteristic(self._notify_uuid)

        if write_char is None or notify_char is None:
            for service in services:
                if self._service_uuid and service.uuid.lower() != self._service_uuid:
                    continue
                for char in service.characteristics:
                    props = {prop.lower() for prop in char.properties}
                    if write_char is None and (
                        "write" in props or "write-without-response" in props
                    ):
                        write_char = char
                    if notify_char is None and (
                        "notify" in props or "indicate" in props
                    ):
                        notify_char = char
                if write_char is not None and notify_char is not None:
                    break

        if write_char is None or notify_char is None:
            discovered = [
                f"{service.uuid}: "
                + ", ".join(
                    f"{char.uuid} ({'/'.join(char.properties)})"
                    for char in service.characteristics
                )
                for service in services
            ]
            raise QiuiBleError(
                "Could not find the QIUI write/notify characteristics. "
                "Configure the UUIDs in the integration options. Discovered: "
                + ("; ".join(discovered) or "no services")
            )

        return write_char, notify_char

    async def _async_run(
        self,
        client: BleakClient,
        command: str,
        params: dict[str, Any],
        *,
        write_uuid: str,
        notify_uuid: str,
    ) -> CommandResult:
        """Subscribe, handshake, write and collect the response."""
        queue: asyncio.Queue[bytes] = asyncio.Queue()

        def _on_notify(_sender: Any, data: bytearray) -> None:
            _LOGGER.debug(
                "%s notification: %s", self._device.address, data.hex(" ").upper()
            )
            queue.put_nowait(bytes(data))

        await client.start_notify(notify_uuid, _on_notify)

        result = CommandResult(command=command)

        try:
            # 1. Per-connection handshake.  The platform asks for this *after*
            #    notifications are subscribed, and the returned payload has to
            #    be written before the actual command.
            if self._write_token:
                token = await self._api.async_get_device_token(self._device)
                if token:
                    handshake = self._decode(token, "handshake")
                    if handshake:
                        _LOGGER.debug(
                            "%s handshake payload: %s",
                            self._device.address,
                            handshake.hex(" ").upper(),
                        )
                        await self._async_write(client, write_uuid, handshake)
                        await self._async_collect(queue, 1.0)

            # 2. Build (cloud) and write the command.
            payload_value = await self._api.async_build_command(
                self._device, command, params
            )
            if not isinstance(payload_value, str):
                raise QiuiBleError(
                    "The platform returned a status object instead of a "
                    "Bluetooth payload. Check the device type."
                )
            payload = self._decode(payload_value, f"'{command}'")
            if not payload:
                raise QiuiBleError(
                    f"The platform returned an empty '{command}' payload"
                )

            result.payload = payload
            repeats = self._repeat_count(command, params)
            for index in range(repeats):
                _LOGGER.debug(
                    "%s writing '%s' (%d/%d): %s",
                    self._device.address,
                    command,
                    index + 1,
                    repeats,
                    payload.hex(" ").upper(),
                )
                await self._async_write(client, write_uuid, payload)
                if index + 1 < repeats:
                    await asyncio.sleep(_REPEAT_DELAY)

            # 3. Wait for the device to answer.  Plenty of commands are
            #    fire-and-forget, so a timeout is not an error.
            result.response = await self._async_collect(
                queue, self._response_timeout
            )
            if result.response:
                result.decrypted = await self._api.async_decrypt(
                    self._device, result.response.hex()
                )
                if isinstance(result.decrypted, dict):
                    result.status = result.decrypted
        finally:
            try:
                await client.stop_notify(notify_uuid)
            except BleakError:  # pragma: no cover - best effort cleanup
                _LOGGER.debug("Ignoring error while stopping notifications")

        return result

    def _decode(self, value: str, what: str) -> bytes:
        """Decode a payload, turning invalid encodings into a BLE error."""
        try:
            return decode_payload(value, self._command_format)
        except ValueError as err:
            raise QiuiBleError(
                f"Could not decode the {what} payload returned by the "
                f"platform: {err}"
            ) from err

    def _repeat_count(self, command: str, params: dict[str, Any]) -> int:
        """Return how often the payload has to be written."""
        if command not in self._device.family.repeat_commands:
            return 1
        try:
            steps = int(params.get("steps", 1))
        except (TypeError, ValueError):
            steps = 1
        if command == CMD_LOCK or command == CMD_UNLOCK:
            return max(1, min(steps, 20))
        return 1

    async def _async_write(
        self, client: BleakClient, write_uuid: str, payload: bytes
    ) -> None:
        """Write a payload to the device.

        QIUI firmware generally uses write-without-response, but a few units
        only acknowledge write-with-response, so fall back to that.
        """
        try:
            await client.write_gatt_char(write_uuid, payload, response=False)
            return
        except BleakError:
            _LOGGER.debug(
                "Write without response failed for %s, retrying with response",
                self._device.address,
                exc_info=True,
            )
        try:
            await client.write_gatt_char(write_uuid, payload, response=True)
        except BleakError as err:
            raise QiuiBleError(f"Writing to the device failed: {err}") from err

    async def _async_collect(
        self, queue: asyncio.Queue[bytes], timeout: float
    ) -> bytes | None:
        """Wait for a notification, returning ``None`` on timeout."""
        try:
            return await asyncio.wait_for(queue.get(), timeout)
        except TimeoutError:
            return None


async def async_probe_family(
    hass: HomeAssistant, address: str, *, timeout: float = 10.0
) -> FamilySpec | None:
    """Identify a device by briefly connecting and reading its GATT services.

    The config flow uses this when a device does not advertise its service UUID
    and the QIUI platform does not know its model yet.  Every failure is
    swallowed: the user can always pick the model manually.
    """
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    if ble_device is None:
        return None

    client: BleakClient | None = None
    try:
        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            address,
            max_attempts=1,
            timeout=timeout,
            use_services_cache=True,
        )
        family = family_for_service_uuids(
            service.uuid for service in client.services
        )
        if family is not None:
            _LOGGER.debug("%s probed as %s", address, family.name)
        return family
    except (BleakError, TimeoutError) as err:
        _LOGGER.debug("Could not probe %s: %s", address, err)
        return None
    finally:
        if client is not None:
            try:
                await client.disconnect()
            except BleakError:  # pragma: no cover - best effort cleanup
                _LOGGER.debug("Ignoring error while disconnecting", exc_info=True)
