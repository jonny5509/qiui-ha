"""Config flow for the QIUI integration."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components import bluetooth
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .api import QiuiApiClient
from .ble import async_probe_family
from .const import (
    COMMAND_FORMATS,
    CONF_ADDRESS,
    CONF_ALLOW_DANGEROUS,
    CONF_CLIENT_ID,
    CONF_COMMAND_FORMAT,
    CONF_ENVIRONMENT,
    CONF_NAME,
    CONF_NOTIFY_UUID,
    CONF_RESPONSE_TIMEOUT,
    CONF_SERIAL_NUMBER,
    CONF_SERVICE_UUID,
    CONF_TRANSPORT,
    CONF_TYPE_ID,
    CONF_WRITE_TOKEN,
    CONF_WRITE_UUID,
    DEFAULT_COMMAND_FORMAT,
    DEFAULT_ENVIRONMENT,
    DEFAULT_RESPONSE_TIMEOUT,
    DEFAULT_TRANSPORT,
    DOMAIN,
    ENVIRONMENTS,
    MAX_RESPONSE_TIMEOUT,
    MIN_RESPONSE_TIMEOUT,
    MODEL_NAMES,
    SUPPORTED_TYPE_IDS,
    TRANSPORTS,
    TYPE_ID_TO_FAMILY,
    FamilySpec,
    family_for_service_uuids,
    type_id_from_family,
)
from .exceptions import QiuiApiError, QiuiAuthError, QiuiConnectionError

if TYPE_CHECKING:
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

_LOGGER = logging.getLogger(__name__)

_MAC_RE = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")

#: Sentinel used in the nearby-device picker to switch to manual entry.
_MANUAL_ADDRESS = "__manual__"

_TYPE_CHOICES: dict[int, str] = {
    0: "Detect automatically",
    **{type_id: MODEL_NAMES.get(type_id, f"Type {type_id}") for type_id in SUPPORTED_TYPE_IDS},
}


def _normalise_address(value: str) -> str:
    """Normalise a Bluetooth address to upper case colon notation."""
    value = value.strip().replace("-", ":").replace(" ", "").upper()
    compact = value.replace(":", "")
    if re.fullmatch(r"[0-9A-F]{12}", compact):
        return ":".join(compact[index : index + 2] for index in range(0, 12, 2))
    return value


def _device_label(
    address: str, name: str | None, family: FamilySpec | None
) -> str:
    """Return the label shown for a nearby device."""
    label = f"{name.strip()} ({address})" if name and name.strip() else address
    if family is not None:
        label = f"{label} — {family.name}"
    return label


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the schema for the developer credentials step."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_CLIENT_ID, default=defaults.get(CONF_CLIENT_ID, "")
            ): str,
            vol.Required(
                CONF_ENVIRONMENT,
                default=defaults.get(CONF_ENVIRONMENT, DEFAULT_ENVIRONMENT),
            ): vol.In(ENVIRONMENTS),
        }
    )


class QiuiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the QIUI configuration flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._api: QiuiApiClient | None = None
        self._client_id: str | None = None
        self._environment: str | None = None

        self._discovered_address: str | None = None
        self._discovered_name: str = ""
        self._discovered_family: FamilySpec | None = None

        self._manual_defaults: dict[str, Any] = {}
        self._manual_errors: dict[str, str] = {}

    # -- step 1: developer credentials --------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the developer client id and environment."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID].strip()
            environment = user_input[CONF_ENVIRONMENT]
            api = QiuiApiClient(self.hass, client_id, environment)
            try:
                await api.async_validate()
            except QiuiAuthError:
                errors["base"] = "invalid_auth"
            except QiuiConnectionError:
                errors["base"] = "cannot_connect"
            except QiuiApiError as err:
                _LOGGER.debug("QIUI validation failed: %s", err)
                errors["base"] = "unknown"
            else:
                self._api = api
                self._client_id = client_id
                self._environment = environment
                return await self.async_step_device()

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
            errors=errors,
            description_placeholders={
                "url": "https://developers.qiuitoy.com",
            },
        )

    # -- step 2: pick a device ----------------------------------------------

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a nearby Bluetooth device."""
        if self._api is None:
            return await self.async_step_user()

        choices, infos = self._async_nearby_choices()

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if address == _MANUAL_ADDRESS:
                return await self.async_step_device_manual()

            address = _normalise_address(address)
            info = infos.get(address)
            if info is not None:
                self._discovered_address = address
                self._discovered_name = (info.name or "").strip()
                self._discovered_family = family_for_service_uuids(
                    info.service_uuids
                )
            return await self._async_bind_device(
                address,
                name=(user_input.get(CONF_NAME) or "").strip(),
            )

        if not choices:
            # Nothing is advertising right now: go straight to manual entry.
            return await self.async_step_device_manual()

        options = dict(choices)
        options[_MANUAL_ADDRESS] = "Enter a Bluetooth address manually"

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(options),
                    vol.Optional(CONF_NAME, default=""): str,
                }
            ),
            description_placeholders={"count": str(len(choices))},
        )

    async def async_step_device_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a device by typing its Bluetooth address."""
        if self._api is None:
            return await self.async_step_user()

        errors = dict(self._manual_errors)
        self._manual_errors = {}
        defaults = dict(self._manual_defaults)
        self._manual_defaults = {}

        if user_input is not None:
            address = _normalise_address(user_input.get(CONF_ADDRESS, ""))
            name = (user_input.get(CONF_NAME) or "").strip()
            manual_type = int(user_input.get(CONF_TYPE_ID) or 0)
            manual_serial = (user_input.get(CONF_SERIAL_NUMBER) or "").strip()

            if not _MAC_RE.match(address):
                errors = {**errors, CONF_ADDRESS: "invalid_address"}
                defaults = {**user_input, CONF_ADDRESS: address}
            else:
                return await self._async_bind_device(
                    address,
                    name=name,
                    manual_type=manual_type,
                    manual_serial=manual_serial,
                )

        return self.async_show_form(
            step_id="device_manual",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS, default=defaults.get(CONF_ADDRESS, "")
                    ): str,
                    vol.Optional(
                        CONF_NAME, default=defaults.get(CONF_NAME, "")
                    ): str,
                    vol.Optional(
                        CONF_TYPE_ID, default=int(defaults.get(CONF_TYPE_ID) or 0)
                    ): vol.All(vol.Coerce(int), vol.In(_TYPE_CHOICES)),
                    vol.Optional(
                        CONF_SERIAL_NUMBER,
                        default=defaults.get(CONF_SERIAL_NUMBER, ""),
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "address": defaults.get(CONF_ADDRESS, ""),
            },
        )

    # -- step 3: bind the device to the platform ----------------------------

    async def _async_bind_device(
        self,
        address: str,
        *,
        name: str = "",
        manual_type: int = 0,
        manual_serial: str = "",
    ) -> ConfigFlowResult:
        """Resolve the device on the QIUI platform and create the entry."""
        if self._api is None:
            return await self.async_step_user()

        errors: dict[str, str] = {}
        record: dict[str, Any] = {}
        query_failed = False

        try:
            await self._api.async_add_device(address)
        except QiuiApiError as err:
            # Binding is best effort; the query below is authoritative.
            _LOGGER.debug("Could not bind %s automatically: %s", address, err)

        try:
            record = await self._api.async_query_device(address)
        except QiuiApiError as err:
            _LOGGER.debug("Could not query %s: %s", address, err)
            query_failed = True

        try:
            type_id = manual_type or int(record.get("typeId") or 0)
        except (TypeError, ValueError):
            type_id = manual_type
        serial = str(record.get("serialNumber") or "") or manual_serial
        family = TYPE_ID_TO_FAMILY.get(type_id)

        if family is None and not type_id and not (query_failed and not serial):
            # No point in probing when the platform does not know the device
            # *and* there is no serial yet: the entry cannot be created anyway.
            family = await self._async_guess_family(address)
            type_id = type_id_from_family(family)

        if query_failed and not serial:
            errors["base"] = "device_not_found"
        elif family is None:
            errors["base"] = "unsupported_device" if type_id else "model_required"
        elif not serial:
            errors[CONF_SERIAL_NUMBER] = "serial_required"

        if errors:
            self._manual_defaults = {
                CONF_ADDRESS: address,
                CONF_NAME: name,
                CONF_TYPE_ID: type_id,
                CONF_SERIAL_NUMBER: serial,
            }
            self._manual_errors = errors
            return await self.async_step_device_manual()

        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        title = name or f"{family.name} {address[-5:]}"
        return self.async_create_entry(
            title=title,
            data={
                CONF_ADDRESS: address,
                CONF_SERIAL_NUMBER: serial,
                CONF_TYPE_ID: type_id,
                CONF_CLIENT_ID: self._client_id,
                CONF_ENVIRONMENT: self._environment,
            },
        )

    async def _async_guess_family(self, address: str) -> FamilySpec | None:
        """Infer the model from the advertisement or from a GATT probe."""
        if (
            self._discovered_address == address
            and self._discovered_family is not None
        ):
            return self._discovered_family

        family = await async_probe_family(self.hass, address)
        if family is not None:
            self._discovered_family = family
        return family

    # -- Bluetooth auto-discovery -------------------------------------------

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a device that Home Assistant discovered over Bluetooth."""
        address = _normalise_address(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        self._discovered_address = address
        self._discovered_name = (discovery_info.name or "").strip()
        self._discovered_family = family_for_service_uuids(
            discovery_info.service_uuids
        )
        self.context["title_placeholders"] = {
            "name": self._discovered_name or address,
        }

        credentials = self._async_known_credentials()
        if credentials is None:
            return await self.async_step_bluetooth_credentials()

        self._client_id, self._environment = credentials
        self._api = QiuiApiClient(self.hass, self._client_id, self._environment)
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for credentials before setting up a discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID].strip()
            environment = user_input[CONF_ENVIRONMENT]
            api = QiuiApiClient(self.hass, client_id, environment)
            try:
                await api.async_validate()
            except QiuiAuthError:
                errors["base"] = "invalid_auth"
            except QiuiConnectionError:
                errors["base"] = "cannot_connect"
            except QiuiApiError as err:
                _LOGGER.debug("QIUI validation failed: %s", err)
                errors["base"] = "unknown"
            else:
                self._api = api
                self._client_id = client_id
                self._environment = environment
                return await self._async_bind_discovered(
                    (user_input.get(CONF_NAME) or "").strip()
                )

        defaults = user_input or {}
        return self.async_show_form(
            step_id="bluetooth_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CLIENT_ID,
                        default=defaults.get(CONF_CLIENT_ID, ""),
                    ): str,
                    vol.Required(
                        CONF_ENVIRONMENT,
                        default=defaults.get(
                            CONF_ENVIRONMENT, DEFAULT_ENVIRONMENT
                        ),
                    ): vol.In(ENVIRONMENTS),
                    vol.Optional(
                        CONF_NAME,
                        default=defaults.get(CONF_NAME, self._suggested_name()),
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=self._discovery_placeholders(),
        )

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered device before adding it."""
        if user_input is not None:
            return await self._async_bind_discovered(
                (user_input.get(CONF_NAME) or "").strip()
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME, default=self._suggested_name()
                    ): str,
                }
            ),
            description_placeholders=self._discovery_placeholders(),
        )

    async def _async_bind_discovered(self, name: str) -> ConfigFlowResult:
        """Bind the device stored by ``async_step_bluetooth``."""
        address = self._discovered_address
        if not address:
            return self.async_abort(reason="unknown")
        return await self._async_bind_device(address, name=name)

    # -- discovery helpers ---------------------------------------------------

    def _async_known_credentials(self) -> tuple[str, str] | None:
        """Reuse the client id of an existing entry, when there is one."""
        for entry in self._async_current_entries(include_ignore=False):
            client_id = entry.data.get(CONF_CLIENT_ID)
            if client_id:
                return client_id, entry.data.get(
                    CONF_ENVIRONMENT, DEFAULT_ENVIRONMENT
                )
        return None

    def _async_nearby_choices(
        self,
    ) -> tuple[dict[str, str], dict[str, BluetoothServiceInfoBleak]]:
        """Return the nearby devices that can be added, keyed by address."""
        matches: dict[str, BluetoothServiceInfoBleak] = {}
        others: dict[str, BluetoothServiceInfoBleak] = {}
        configured = {
            (entry.unique_id or entry.data.get(CONF_ADDRESS, "")).upper()
            for entry in self._async_current_entries(include_ignore=False)
        }

        for info in bluetooth.async_discovered_service_info(
            self.hass, connectable=True
        ):
            address = _normalise_address(info.address)
            if address in configured:
                continue
            if family_for_service_uuids(info.service_uuids) is not None:
                matches.setdefault(address, info)
            elif info.name:
                others.setdefault(address, info)

        # Only fall back to unrelated devices when nothing matches, otherwise
        # the list would contain every phone and speaker in the room.
        devices = matches or dict(list(others.items())[:20])

        ordered = sorted(
            devices.items(),
            key=lambda item: _device_label(
                item[0],
                item[1].name,
                family_for_service_uuids(item[1].service_uuids),
            ).lower(),
        )[:25]

        choices = {
            address: _device_label(
                address,
                info.name,
                family_for_service_uuids(info.service_uuids),
            )
            for address, info in ordered
        }
        return choices, dict(ordered)

    def _suggested_name(self) -> str:
        """Return a sensible default name for a discovered device."""
        if self._discovered_name:
            return self._discovered_name
        address = self._discovered_address or ""
        family = self._discovered_family
        if family is not None:
            return f"{family.name} {address[-5:]}"
        return f"QIUI {address[-5:]}" if address else "QIUI"

    def _detected_model(self) -> str:
        """Describe what was inferred from the Bluetooth advertisement."""
        family = self._discovered_family
        if family is None:
            return "unknown, the platform will report it"
        type_id = type_id_from_family(family)
        if type_id:
            return MODEL_NAMES.get(type_id, family.name)
        return f"{family.name} (the platform reports the exact model)"

    def _discovery_placeholders(self) -> dict[str, str]:
        """Return the description placeholders for discovery steps."""
        return {
            "name": self._discovered_name or self._discovered_address or "",
            "address": self._discovered_address or "",
            "model": self._detected_model(),
            "url": "https://developers.qiuitoy.com",
        }

    # -- re-authentication --------------------------------------------------

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Start the re-authentication flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for fresh developer credentials."""
        errors: dict[str, str] = {}
        entry: ConfigEntry | None = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        if entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            api = QiuiApiClient(
                self.hass,
                user_input[CONF_CLIENT_ID].strip(),
                user_input[CONF_ENVIRONMENT],
            )
            try:
                await api.async_validate()
            except QiuiAuthError:
                errors["base"] = "invalid_auth"
            except QiuiConnectionError:
                errors["base"] = "cannot_connect"
            except QiuiApiError:
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_CLIENT_ID: user_input[CONF_CLIENT_ID].strip(),
                        CONF_ENVIRONMENT: user_input[CONF_ENVIRONMENT],
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_user_schema(
                {
                    CONF_CLIENT_ID: entry.data.get(CONF_CLIENT_ID, ""),
                    CONF_ENVIRONMENT: entry.data.get(
                        CONF_ENVIRONMENT, DEFAULT_ENVIRONMENT
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return QiuiOptionsFlowHandler()


class QiuiOptionsFlowHandler(OptionsFlow):
    """Behaviour options for a configured device."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entry = getattr(self, "config_entry", None) or (
            self.hass.config_entries.async_get_entry(self.handler)
        )
        if entry is None:
            return self.async_abort(reason="unknown")
        options = entry.options
        family = TYPE_ID_TO_FAMILY.get(int(entry.data.get(CONF_TYPE_ID) or 0))
        if family is None:
            return self.async_abort(reason="unsupported_device")

        schema: dict[Any, Any] = {}

        if family.supports_cloud and family.supports_bluetooth:
            schema[
                vol.Optional(
                    CONF_TRANSPORT,
                    default=options.get(CONF_TRANSPORT, DEFAULT_TRANSPORT),
                )
            ] = vol.In(TRANSPORTS)

        schema[
            vol.Optional(
                CONF_ALLOW_DANGEROUS,
                default=options.get(CONF_ALLOW_DANGEROUS, False),
            )
        ] = bool
        schema[
            vol.Optional(
                CONF_WRITE_TOKEN, default=options.get(CONF_WRITE_TOKEN, True)
            )
        ] = bool
        schema[
            vol.Optional(
                CONF_RESPONSE_TIMEOUT,
                default=options.get(
                    CONF_RESPONSE_TIMEOUT, DEFAULT_RESPONSE_TIMEOUT
                ),
            )
        ] = vol.All(
            vol.Coerce(float),
            vol.Range(min=MIN_RESPONSE_TIMEOUT, max=MAX_RESPONSE_TIMEOUT),
        )
        schema[
            vol.Optional(
                CONF_COMMAND_FORMAT,
                default=options.get(CONF_COMMAND_FORMAT, DEFAULT_COMMAND_FORMAT),
            )
        ] = vol.In(COMMAND_FORMATS)

        if family.supports_bluetooth:
            schema[
                vol.Optional(
                    CONF_SERVICE_UUID,
                    default=options.get(CONF_SERVICE_UUID, family.service_uuid or ""),
                )
            ] = str
            schema[
                vol.Optional(
                    CONF_WRITE_UUID,
                    default=options.get(CONF_WRITE_UUID, family.write_uuid or ""),
                )
            ] = str
            schema[
                vol.Optional(
                    CONF_NOTIFY_UUID,
                    default=options.get(CONF_NOTIFY_UUID, family.notify_uuid or ""),
                )
            ] = str

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema)
        )
