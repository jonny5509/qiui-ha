"""Client for the QIUI Open Platform."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ALREADY_BOUND_CODES,
    API_BASE_URL,
    CMD_DECRYPT,
    CMD_TOKEN,
    COMMAND_PARAMS,
    NESTED_COMMANDS,
    TOKEN_LIFETIME,
    TYPE_ID_TO_FAMILY,
    FamilySpec,
    error_message,
)
from .exceptions import QiuiApiError, QiuiAuthError, QiuiConnectionError
from .payload import build_command_body

_LOGGER = logging.getLogger(__name__)

#: The platform is inconsistent: the documentation uses ``code: 0`` while the
#: developer console treats ``code: 200`` as success, and errors sometimes use
#: ``message`` and sometimes ``msg``.
_SUCCESS_CODES = frozenset({0, 200, "0", "200"})
#: Body codes that mean the platform token has to be renewed.
_TOKEN_EXPIRED_CODES = frozenset({"401"})
#: Body codes that mean the credentials / developer application are wrong.
_AUTH_ERROR_CODES = frozenset(
    {"401", "403", "500037", "500038", "500039", "500040", "500044"}
)


@dataclass(frozen=True)
class QiuiDevice:
    """A physical device bound to the QIUI platform."""

    address: str
    serial_number: str
    type_id: int
    family: FamilySpec

    @property
    def body(self) -> dict[str, Any]:
        """Return the ``basicDeviceApiReq`` payload shared by all endpoints."""
        return {
            "bluetoothAddress": self.address,
            "serialNumber": self.serial_number,
            "typeId": self.type_id,
        }


class QiuiApiClient:
    """Thin, token-aware wrapper around the QIUI cloud API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client_id: str,
        environment: str,
        *,
        request_timeout: float = 30.0,
    ) -> None:
        """Initialise the client."""
        self._hass = hass
        self._client_id = client_id
        self._environment = environment
        self._request_timeout = request_timeout
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()

    @property
    def client_id(self) -> str:
        """Return the configured client id."""
        return self._client_id

    @property
    def environment(self) -> str:
        """Return the configured environment."""
        return self._environment

    # -- public API ---------------------------------------------------------

    async def async_validate(self) -> None:
        """Validate the credentials by requesting a platform token."""
        await self.async_get_token(force=True)

    async def async_get_token(self, *, force: bool = False) -> str:
        """Return a valid platform API token, refreshing it when needed."""
        async with self._token_lock:
            if (
                not force
                and self._token is not None
                and time.monotonic() < self._token_expires_at
            ):
                return self._token

            payload = {
                "clientId": self._client_id,
                "grantType": "client_credentials",
            }
            # A refresh has to present the (possibly expired) old token, and it
            # must not re-enter async_get_token() -- that would deadlock on the
            # token lock.
            refresh = self._token is not None
            endpoint = (
                "/device/common/refreshPlatformApiToken"
                if refresh
                else "/device/common/getPlatformApiToken"
            )

            try:
                data = await self._async_post(
                    endpoint,
                    payload,
                    auth=refresh,
                    token=self._token if refresh else None,
                )
            except QiuiAuthError:
                if refresh:
                    data = await self._async_post(
                        "/device/common/getPlatformApiToken", payload, auth=False
                    )
                else:
                    raise

            if not isinstance(data, dict) or not data.get("platformApiToken"):
                raise QiuiAuthError(
                    "The QIUI platform did not return an API token. Check that "
                    "the client id is correct and that the developer account is "
                    "approved."
                )

            self._token = str(data["platformApiToken"])
            self._token_expires_at = self._parse_expiry(data.get("expiresTime"))
            _LOGGER.debug(
                "Obtained QIUI platform token for client %s (valid for %.0f minutes)",
                self._client_id,
                (self._token_expires_at - time.monotonic()) / 60,
            )
            return self._token

    async def async_add_device(self, address: str) -> dict[str, Any]:
        """Bind a device to the platform (idempotent)."""
        try:
            data = await self._async_post(
                "/platform/device/addDeviceInfo", {"bluetoothAddress": address}
            )
        except QiuiApiError as err:
            # Already bound on the same platform is fine - that is what we want.
            if err.code is not None and str(err.code) in ALREADY_BOUND_CODES:
                _LOGGER.debug("Device %s is already bound to the platform", address)
                return {}
            raise
        return data if isinstance(data, dict) else {}

    async def async_query_device(self, address: str) -> dict[str, Any]:
        """Return the platform record for a device."""
        data = await self._async_post(
            "/platform/device/queryDeviceInfo", {"bluetoothAddress": address}
        )
        if not isinstance(data, dict):
            raise QiuiApiError(
                f"The platform returned no device information for {address}"
            )
        return data

    async def async_get_device_token(
        self, device: QiuiDevice, *, cloud: bool = False
    ) -> str:
        """Return the per-connection device token (may be empty)."""
        data = await self._async_post(
            device.family.endpoint(CMD_TOKEN, cloud=cloud), device.body
        )
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            for key in ("bluetoothCommand", "command", "token", "data"):
                value = data.get(key)
                if isinstance(value, str):
                    return value
        return ""

    async def async_build_command(
        self,
        device: QiuiDevice,
        command: str,
        params: dict[str, Any],
        *,
        cloud: bool = False,
    ) -> str | dict[str, Any]:
        """Ask the platform to build an encrypted command for the device.

        Bluetooth families receive an encrypted *string*.  The 4G endpoints
        return a status object instead, which is passed through untouched.
        """
        endpoint = device.family.endpoint(command, cloud=cloud)

        body = build_command_body(
            device.body,
            command,
            params,
            allowed_params=COMMAND_PARAMS.get(command, ()),
            nested=command in NESTED_COMMANDS,
        )

        data = await self._async_post(endpoint, body)
        if not data:
            raise QiuiApiError(
                f"The platform returned an empty command for '{command}'"
            )
        return data

    async def async_decrypt(
        self, device: QiuiDevice, raw_command: str
    ) -> Any | None:
        """Ask the platform to decrypt a command received from the device."""
        endpoint = device.family.endpoints.get(CMD_DECRYPT)
        if endpoint is None or not raw_command:
            return None
        try:
            return await self._async_post(
                endpoint,
                {
                    "lockCommand": raw_command,
                    "serialNumber": device.serial_number,
                },
            )
        except QiuiApiError as err:
            # Decryption is best effort: the command already reached the device.
            _LOGGER.debug("Could not decrypt device response: %s", err)
            return None

    # -- internals ----------------------------------------------------------

    async def _async_post(
        self,
        endpoint: str,
        payload: dict[str, Any],
        *,
        auth: bool = True,
        token: str | None = None,
        retry: bool = True,
    ) -> Any:
        """POST to the platform and return the ``data`` member."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Environment": self._environment,
        }
        if auth:
            headers["Authorization"] = token or await self.async_get_token()

        session = async_get_clientsession(self._hass)
        try:
            async with asyncio.timeout(self._request_timeout):
                response = await session.post(
                    f"{API_BASE_URL}{endpoint}", json=payload, headers=headers
                )
                if response.status in (401, 403):
                    response.release()
                    self._token_expires_at = 0.0
                    # Retry once with a brand new token.  This must not happen
                    # while the token lock is held (token is not None there),
                    # otherwise the refresh would deadlock.
                    if auth and token is None and retry:
                        self._token = None
                        return await self._async_post(
                            endpoint, payload, retry=False
                        )
                    raise QiuiAuthError(
                        f"The QIUI platform rejected the request (HTTP {response.status})"
                    )
                body = await response.json(content_type=None)
        except QiuiAuthError:
            raise
        except TimeoutError as err:
            raise QiuiConnectionError(
                f"Timed out talking to the QIUI platform ({endpoint})"
            ) from err
        except aiohttp.ClientError as err:
            raise QiuiConnectionError(
                f"Could not reach the QIUI platform: {err}"
            ) from err
        except ValueError as err:
            raise QiuiConnectionError(
                f"The QIUI platform returned invalid JSON ({endpoint})"
            ) from err

        if not isinstance(body, dict):
            raise QiuiConnectionError(
                f"Unexpected response from the QIUI platform ({endpoint})"
            )

        code = body.get("code")
        if code is not None and code not in _SUCCESS_CODES:
            # Prefer our English wording for known codes, but keep the
            # platform's message for anything we do not know.
            message = error_message(code)
            if message == "Unknown platform error":
                message = body.get("message") or body.get("msg") or message

            if str(code) in _AUTH_ERROR_CODES:
                self._token_expires_at = 0.0
                if (
                    str(code) in _TOKEN_EXPIRED_CODES
                    and auth
                    and token is None
                    and retry
                ):
                    # The token simply expired: get a new one and retry once.
                    self._token = None
                    return await self._async_post(
                        endpoint, payload, retry=False
                    )
                raise QiuiAuthError(f"{message} (code {code})")
            raise QiuiApiError(f"{message} (code {code})", code)

        return body.get("data") if "data" in body else body

    def _parse_expiry(self, expires: Any) -> float:
        """Convert ``expiresTime`` into a monotonic deadline."""
        now = time.monotonic()
        max_deadline = now + TOKEN_LIFETIME
        try:
            value = float(expires)
        except (TypeError, ValueError):
            return max_deadline

        if value <= 0:
            return max_deadline

        # Absolute epoch timestamps (seconds or milliseconds).
        now_epoch = time.time()
        if value > 1e12:  # milliseconds
            value /= 1000
        if value > now_epoch:
            return min(now + (value - now_epoch), max_deadline)

        # Otherwise it is a lifetime in seconds (or minutes for tiny values).
        if value < 100000:
            return min(now + value, max_deadline)
        return max_deadline


def build_device(address: str, serial_number: str, type_id: int) -> QiuiDevice:
    """Build a device from stored config entry data."""
    family = TYPE_ID_TO_FAMILY.get(int(type_id))
    if family is None:
        raise QiuiApiError(f"Unsupported QIUI device type: {type_id}")
    return QiuiDevice(
        address=address.upper(),
        serial_number=serial_number,
        type_id=int(type_id),
        family=family,
    )
