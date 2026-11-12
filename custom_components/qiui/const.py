"""Constants, device profiles and command definitions for the QIUI integration.

Everything in this module was derived from the public QIUI Open Platform
documentation at https://developers.qiuitoy.com.  The platform exposes a
*command builder*: you send the Bluetooth address / serial number / type id of
a device and it returns an encrypted payload that has to be written to the
device over Bluetooth LE.

The BLE profile (service / notify / write characteristic) for each family is
also published by the platform.  They can be overridden per config entry from
the integration options in case a device ships with a different profile.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from homeassistant.components.number import NumberMode

DOMAIN: Final = "qiui"
NAME: Final = "QIUI"
VERSION: Final = "0.2.0"

API_BASE_URL: Final = "https://openapi.qiuitoy.com/system/api"

# ---------------------------------------------------------------------------
# Configuration keys
# ---------------------------------------------------------------------------

CONF_CLIENT_ID: Final = "client_id"
CONF_ENVIRONMENT: Final = "environment"
CONF_ADDRESS: Final = "bluetooth_address"
CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_TYPE_ID: Final = "type_id"
CONF_NAME: Final = "name"

CONF_TRANSPORT: Final = "transport"
CONF_ALLOW_DANGEROUS: Final = "allow_dangerous_actions"
CONF_WRITE_TOKEN: Final = "write_token"
CONF_RESPONSE_TIMEOUT: Final = "response_timeout"
CONF_COMMAND_FORMAT: Final = "command_format"
CONF_SERVICE_UUID: Final = "service_uuid"
CONF_WRITE_UUID: Final = "write_uuid"
CONF_NOTIFY_UUID: Final = "notify_uuid"

CONF_DEVICE_ID: Final = "device_id"
CONF_COMMAND: Final = "command"
CONF_PARAMETERS: Final = "parameters"

ENV_PRODUCT: Final = "PRODUCT"
ENV_TEST: Final = "TEST"
ENVIRONMENTS: Final[tuple[str, ...]] = (ENV_PRODUCT, ENV_TEST)
DEFAULT_ENVIRONMENT: Final = ENV_PRODUCT

TRANSPORT_AUTO: Final = "auto"
TRANSPORT_BLUETOOTH: Final = "bluetooth"
TRANSPORT_CLOUD: Final = "cloud"
TRANSPORTS: Final[tuple[str, ...]] = (
    TRANSPORT_AUTO,
    TRANSPORT_BLUETOOTH,
    TRANSPORT_CLOUD,
)
DEFAULT_TRANSPORT: Final = TRANSPORT_AUTO

FORMAT_AUTO: Final = "auto"
FORMAT_HEX: Final = "hex"
FORMAT_BASE64: Final = "base64"
FORMAT_TEXT: Final = "text"
COMMAND_FORMATS: Final[tuple[str, ...]] = (
    FORMAT_AUTO,
    FORMAT_HEX,
    FORMAT_BASE64,
    FORMAT_TEXT,
)
DEFAULT_COMMAND_FORMAT: Final = FORMAT_AUTO

DEFAULT_RESPONSE_TIMEOUT: Final = 8.0
MIN_RESPONSE_TIMEOUT: Final = 2.0
MAX_RESPONSE_TIMEOUT: Final = 30.0

TOKEN_LIFETIME: Final = 11 * 60 * 60  # the platform hands out 12h tokens

# ---------------------------------------------------------------------------
# Command names
# ---------------------------------------------------------------------------

CMD_TOKEN: Final = "token"
CMD_DECRYPT: Final = "decrypt"
CMD_UNLOCK: Final = "unlock"
CMD_LOCK: Final = "lock"
CMD_TIMING_UNLOCK: Final = "timing_unlock"
CMD_CLEAR_TIMING_UNLOCK: Final = "clear_timing_unlock"
CMD_TIMING_LOCK: Final = "timing_lock"
CMD_CLEAR_TIMING_LOCK: Final = "clear_timing_lock"
CMD_SHOCK_1S: Final = "shock_1s"
CMD_SHOCK_5S: Final = "shock_5s"
CMD_STOP_SHOCK: Final = "stop_shock"
CMD_TIMING_SHOCK: Final = "timing_shock"
CMD_CLEAR_SHOCK: Final = "clear_shock"
CMD_SHAKE_NOW: Final = "shake_now"
CMD_TIMING_SHAKE: Final = "timing_shake"
CMD_CANCEL_TIMING_SHAKE: Final = "cancel_timing_shake"
CMD_STOP_ALL: Final = "stop_all"
CMD_LINE_SHAKE: Final = "line_shake"
CMD_VIBRATION: Final = "vibration"
CMD_CANCEL_VIBRATION: Final = "cancel_vibration"
CMD_TIMING_VIBRATION: Final = "timing_vibration"
CMD_CANCEL_TIMING_VIBRATION: Final = "cancel_timing_vibration"
CMD_ELECTRIC: Final = "electric"
CMD_CANCEL_ELECTRIC: Final = "cancel_electric"
CMD_TIMING_ELECTRIC: Final = "timing_electric"
CMD_CANCEL_TIMING_ELECTRIC: Final = "cancel_timing_electric"
CMD_OFFLINE_MODE: Final = "offline_mode"
CMD_RESET: Final = "reset"
CMD_WORK_MODE: Final = "work_mode"
CMD_DISPLAY_DIRECTION: Final = "display_direction"

#: Commands whose request body wraps the device data in ``basicDeviceApiReq``.
NESTED_COMMANDS: Final[frozenset[str]] = frozenset(
    {
        CMD_TIMING_UNLOCK,
        CMD_TIMING_LOCK,
        CMD_TIMING_SHOCK,
        CMD_TIMING_SHAKE,
        CMD_SHOCK_1S,
        CMD_SHOCK_5S,
        CMD_SHAKE_NOW,
        CMD_LINE_SHAKE,
        CMD_VIBRATION,
        CMD_TIMING_VIBRATION,
        CMD_ELECTRIC,
        CMD_TIMING_ELECTRIC,
        CMD_OFFLINE_MODE,
        CMD_WORK_MODE,
        CMD_DISPLAY_DIRECTION,
        CMD_RESET,
    }
)

#: Extra parameters accepted by each command.  Anything not listed here is
#: never sent to the platform (``steps`` for example is local only).
COMMAND_PARAMS: Final[Mapping[str, tuple[str, ...]]] = {
    CMD_TIMING_UNLOCK: ("shockVolt", "timingDuration"),
    CMD_TIMING_LOCK: ("timingDuration",),
    CMD_SHOCK_1S: ("shockVolt", "shockModel"),
    CMD_SHOCK_5S: ("shockVolt", "shockModel"),
    CMD_TIMING_SHOCK: ("shockVolt", "shockModel", "shockDuration", "timingDuration"),
    CMD_SHAKE_NOW: ("shakeDuration", "shakeIntensity", "shakeModel"),
    CMD_TIMING_SHAKE: (
        "timingDuration",
        "shakeDuration",
        "shakeIntensity",
        "shakeModel",
    ),
    CMD_LINE_SHAKE: ("lineSpeedValue",),
    CMD_VIBRATION: ("vibrationDuration", "vibrationIntensity", "vibrationModel"),
    CMD_TIMING_VIBRATION: (
        "timingTime",
        "vibrationDuration",
        "vibrationIntensity",
        "vibrationModel",
    ),
    CMD_ELECTRIC: ("electricDuration", "electricIntensity", "electricModel"),
    CMD_TIMING_ELECTRIC: (
        "electricDuration",
        "electricIntensity",
        "electricModel",
        "timingTime",
    ),
    CMD_OFFLINE_MODE: ("openOfflineFlag",),
    CMD_WORK_MODE: ("workStatus",),
    CMD_DISPLAY_DIRECTION: ("direction",),
}

# ---------------------------------------------------------------------------
# Entity descriptions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ButtonSpec:
    """A one-shot action exposed as a button."""

    key: str
    name: str
    command: str
    icon: str = "mdi:gesture-tap-button"
    dangerous: bool = False


@dataclass(frozen=True, kw_only=True)
class NumberSpec:
    """A tunable value that is used by the action buttons."""

    key: str
    name: str
    minimum: float
    maximum: float
    default: float
    param: str | None = None
    step: float = 1
    unit: str | None = None
    icon: str = "mdi:tune-variant"
    mode: NumberMode = NumberMode.BOX


@dataclass(frozen=True, kw_only=True)
class SelectSpec:
    """A value that is pushed to the device immediately when selected."""

    key: str
    name: str
    param: str
    options: Mapping[str, int]
    default: str
    command: str
    icon: str = "mdi:form-select"


@dataclass(frozen=True, kw_only=True)
class FamilySpec:
    """Everything the integration knows about one QIUI hardware family."""

    key: str
    name: str
    type_ids: tuple[int, ...]
    endpoints: Mapping[str, str]
    #: Endpoints used when the command goes through the 4G cloud instead of
    #: Bluetooth.  Only the CellMate Pro 4G has these; for every other family
    #: ``endpoints`` is used.
    cloud_endpoints: Mapping[str, str] = field(default_factory=dict)
    service_uuid: str | None = None
    write_uuid: str | None = None
    notify_uuid: str | None = None
    supports_bluetooth: bool = True
    supports_cloud: bool = False
    repeat_commands: tuple[str, ...] = ()
    buttons: tuple[ButtonSpec, ...] = ()
    numbers: tuple[NumberSpec, ...] = ()
    selects: tuple[SelectSpec, ...] = ()
    params: Mapping[str, float] = field(default_factory=dict)

    def endpoint(self, command: str, *, cloud: bool = False) -> str:
        """Return the endpoint for a command, raising a helpful error."""
        endpoints = (
            self.cloud_endpoints
            if cloud and self.cloud_endpoints
            else self.endpoints
        )
        try:
            return endpoints[command]
        except KeyError:
            raise KeyError(
                f"Command '{command}' is not supported by {self.name}"
            ) from None

    def supports(self, command: str) -> bool:
        """Return whether the family can send a command over any transport."""
        return command in self.endpoints or command in self.cloud_endpoints

    @property
    def commands(self) -> frozenset[str]:
        """Return every command the family can send."""
        return frozenset(self.endpoints) | frozenset(self.cloud_endpoints)

    @property
    def dangerous_commands(self) -> frozenset[str]:
        """Return the commands that are gated behind the safety option."""
        return frozenset(button.command for button in self.buttons if button.dangerous)


# ---------------------------------------------------------------------------
# BLE command families
# ---------------------------------------------------------------------------

_KEYPOD_ENDPOINTS: Final[Mapping[str, str]] = {
    CMD_TOKEN: "/device/common/getDeviceToken",
    CMD_DECRYPT: "/device/keyPod/decryBluetoothCommand",
    CMD_UNLOCK: "/device/keyPod/getKeyPodUnlockCmd",
    CMD_LOCK: "/device/keyPod/getKeyPodLockCmd",
}

_CELLMATE_ENDPOINTS: Final[Mapping[str, str]] = {
    CMD_TOKEN: "/device/cellMate/bluetooth/buildCellMatePro4GTokenCmd",
    CMD_DECRYPT: "/device/cellMate/decryBluetoothCommand",
    CMD_UNLOCK: "/device/cellMate/bluetooth/buildCellMatePro4GUnLockCmd",
    CMD_LOCK: "/device/cellMate/bluetooth/buildCellMatePro4GLockCmd",
    CMD_TIMING_UNLOCK: "/device/cellMate/bluetooth/buildCellMateProTimingUnlock",
    CMD_CLEAR_TIMING_UNLOCK: (
        "/device/cellMate/bluetooth/buildCellMateProClearTimingUnlockCmd"
    ),
    CMD_SHOCK_1S: (
        "/device/cellMate/bluetooth/buildCellMateProShockImmediatelyShockCmd"
    ),
    CMD_SHOCK_5S: (
        "/device/cellMate/bluetooth/buildCellMateProShockContinuedFiveSecond"
    ),
    CMD_TIMING_SHOCK: "/device/cellMate/bluetooth/buildToyTimingElectricShock",
    CMD_CLEAR_SHOCK: "/device/cellMate/bluetooth/buildClearAllElectricShockCmd",
    CMD_STOP_SHOCK: "/device/cellMate/bluetooth/buildCellMateProStopAllShockCmd",
    CMD_WORK_MODE: "/device/cellMate/bluetooth/buildCellMatePro4GWorkModelCmd",
    CMD_DISPLAY_DIRECTION: "/device/cellMate/bluetooth/buildDisplayDirectionCmd",
}

_CELLMATE_4G_ENDPOINTS: Final[Mapping[str, str]] = {
    CMD_TOKEN: "/device/cellMate/4g/sendCellMatePro4GTokenCmd",
    CMD_UNLOCK: "/device/cellMate/4g/sendCellMatePro4GUnLockCmd",
    CMD_LOCK: "/device/cellMate/4g/sendCellMatePro4GLockCmd",
    CMD_TIMING_UNLOCK: "/device/cellMate/4g/sendCellMateProTimingUnlock",
    CMD_CLEAR_TIMING_UNLOCK: "/device/cellMate/4g/sendCellMateProClearTimingUnlockCmd",
    CMD_SHOCK_1S: "/device/cellMate/4g/sendCellMateProShockImmediatelyShockCmd",
    CMD_SHOCK_5S: "/device/cellMate/4g/sendCellMateProShockContinuedFiveSecond",
    CMD_TIMING_SHOCK: "/device/cellMate/4g/sendToyTimingElectricShock",
    CMD_CLEAR_SHOCK: "/device/cellMate/4g/sendClearAllElectricShockCmd",
    CMD_STOP_SHOCK: "/device/cellMate/4g/sendCellMateProStopAllShockCmd",
    CMD_WORK_MODE: "/device/cellMate/4g/sendCellMatePro4GWorkModelCmd",
}

_METAL_LOCK_ENDPOINTS: Final[Mapping[str, str]] = {
    CMD_TOKEN: "/device/toyMetalLockBluetooth/getMetalLockTokenCmd",
    CMD_DECRYPT: "/device/toyMetalLockBluetooth/decryBluetoothCommand",
    CMD_UNLOCK: "/device/toyMetalLockBluetooth/getMetalLockUnLockCmd",
    CMD_LOCK: "/device/toyMetalLockBluetooth/getMetalLockCmd",
    CMD_TIMING_LOCK: "/device/toyMetalLockBluetooth/getMetalLockTimingLockCmd",
    CMD_CLEAR_TIMING_LOCK: (
        "/device/toyMetalLockBluetooth/getMetalClearTimingLockCmd"
    ),
}

_METAL_SHAKE_ENDPOINTS: Final[Mapping[str, str]] = {
    CMD_TOKEN: "/device/toyMetalShakeLockBluetooth/getMetalShakeLockTokenCmd",
    CMD_DECRYPT: "/device/toyMetalShakeLockBluetooth/decryBluetoothCommand",
    CMD_UNLOCK: "/device/toyMetalShakeLockBluetooth/getMetalShakeLockUnLockCmd",
    CMD_LOCK: "/device/toyMetalShakeLockBluetooth/getMetalShakeLockCmd",
    CMD_TIMING_LOCK: (
        "/device/toyMetalShakeLockBluetooth/getMetalShakeLockTimingLockCmd"
    ),
    CMD_CLEAR_TIMING_LOCK: (
        "/device/toyMetalShakeLockBluetooth/getMetalShakeClearTimingLockCmd"
    ),
    CMD_SHAKE_NOW: (
        "/device/toyMetalShakeLockBluetooth/getShakeMetalLockImmediatelyShakeCmd"
    ),
    CMD_TIMING_SHAKE: (
        "/device/toyMetalShakeLockBluetooth/getShakeMetalTimingShakeCmd"
    ),
    CMD_CANCEL_TIMING_SHAKE: (
        "/device/toyMetalShakeLockBluetooth/getShakeMetalCancelTimingShakeCmd"
    ),
    CMD_STOP_ALL: "/device/toyMetalShakeLockBluetooth/stopAllShakeAndElectricCmd",
    CMD_LINE_SHAKE: "/device/toyMetalShakeLockBluetooth/getLineModelShakeCmd",
}

_PEAR_FLOWER_ENDPOINTS: Final[Mapping[str, str]] = {
    CMD_TOKEN: "/device/pearFlowerThree/getToyToken",
    CMD_DECRYPT: "/device/pearFlowerThree/decryBluetoothCommand",
    CMD_UNLOCK: "/device/pearFlowerThree/generatePearFlowerThreeToyUnlock",
    CMD_LOCK: "/device/pearFlowerThree/generatePearFlowerThreeToyLock",
    CMD_VIBRATION: "/device/pearFlowerThree/generatePearFlowerThreeToyVibration",
    CMD_CANCEL_VIBRATION: (
        "/device/pearFlowerThree/generatePearFlowerThreeToyCancelVibration"
    ),
    CMD_TIMING_VIBRATION: (
        "/device/pearFlowerThree/generatePearFlowerThreeToyTimingVibration"
    ),
    CMD_CANCEL_TIMING_VIBRATION: (
        "/device/pearFlowerThree/generatePearFlowerThreeToyCancelTimingVibration"
    ),
    CMD_ELECTRIC: "/device/pearFlowerThree/generatePearFlowerThreeToyElectric",
    CMD_CANCEL_ELECTRIC: (
        "/device/pearFlowerThree/generatePearFlowerThreeToyCancelElectric"
    ),
    CMD_TIMING_ELECTRIC: (
        "/device/pearFlowerThree/generatePearFlowerThreeToyTimingElectric"
    ),
    CMD_CANCEL_TIMING_ELECTRIC: (
        "/device/pearFlowerThree/generatePearFlowerThreeToyCancelTimingElectric"
    ),
    CMD_OFFLINE_MODE: (
        "/device/pearFlowerThree/generatePearFlowerThreeToyIsOpenOfflineFlag"
    ),
    CMD_RESET: "/device/pearFlowerThree/generatePearFlowerThreeReset",
}

# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------

KEYPOD: Final = FamilySpec(
    key="keypod",
    name="Key Pod",
    type_ids=(6, 11),
    endpoints=_KEYPOD_ENDPOINTS,
    service_uuid="0000fff0-0000-1000-8000-00805f9b34fb",
    write_uuid="0000fff1-0000-1000-8000-00805f9b34fb",
    notify_uuid="0000fff2-0000-1000-8000-00805f9b34fb",
)

CELLMATE: Final = FamilySpec(
    key="cellmate",
    name="CellMate",
    type_ids=(1, 4, 7),
    endpoints=_CELLMATE_ENDPOINTS,
    service_uuid="0000fee7-0000-1000-8000-00805f9b34fb",
    write_uuid="000036f5-0000-1000-8000-00805f9b34fb",
    notify_uuid="000036f6-0000-1000-8000-00805f9b34fb",
    buttons=(
        ButtonSpec(
            key="shock_1s",
            name="Shock 1 second",
            command=CMD_SHOCK_1S,
            icon="mdi:flash",
            dangerous=True,
        ),
        ButtonSpec(
            key="shock_5s",
            name="Shock 5 seconds",
            command=CMD_SHOCK_5S,
            icon="mdi:flash",
            dangerous=True,
        ),
        ButtonSpec(
            key="timing_shock",
            name="Start timed shock",
            command=CMD_TIMING_SHOCK,
            icon="mdi:flash-alert",
            dangerous=True,
        ),
        ButtonSpec(
            key="stop_shock",
            name="Stop shock",
            command=CMD_STOP_SHOCK,
            icon="mdi:flash-off",
        ),
        ButtonSpec(
            key="clear_shock",
            name="Clear timed shocks",
            command=CMD_CLEAR_SHOCK,
            icon="mdi:calendar-remove",
        ),
        ButtonSpec(
            key="timing_unlock",
            name="Start timed unlock",
            command=CMD_TIMING_UNLOCK,
            icon="mdi:lock-clock",
        ),
        ButtonSpec(
            key="clear_timing_unlock",
            name="Clear timed unlock",
            command=CMD_CLEAR_TIMING_UNLOCK,
            icon="mdi:calendar-remove",
        ),
    ),
    numbers=(
        NumberSpec(
            key="shock_volt",
            name="Shock level",
            param="shockVolt",
            minimum=1,
            maximum=5,
            default=1,
            icon="mdi:flash",
        ),
        NumberSpec(
            key="shock_model",
            name="Shock mode",
            param="shockModel",
            minimum=1,
            maximum=3,
            default=1,
            icon="mdi:flash-outline",
        ),
        NumberSpec(
            key="shock_duration",
            name="Shock duration",
            param="shockDuration",
            minimum=1,
            maximum=99,
            default=5,
            unit="s",
            icon="mdi:timer-outline",
        ),
        NumberSpec(
            key="timing_seconds",
            name="Timing duration",
            param="timingDuration",
            minimum=1,
            maximum=8640000,
            default=3600,
            unit="s",
            icon="mdi:timer-sand",
        ),
    ),
    selects=(
        SelectSpec(
            key="work_mode",
            name="4G work mode",
            param="workStatus",
            command=CMD_WORK_MODE,
            options={"off": 0, "always_online": 1, "periodic": 2},
            default="off",
            icon="mdi:access-point-network",
        ),
        SelectSpec(
            key="display_direction",
            name="Display direction",
            param="direction",
            command=CMD_DISPLAY_DIRECTION,
            options={"forward": 0, "reverse": 1},
            default="forward",
            icon="mdi:screen-rotation",
        ),
    ),
)

CELLMATE_4G: Final = FamilySpec(
    key="cellmate_4g",
    name="CellMate Pro (4G)",
    type_ids=(10,),
    # Over Bluetooth the 4G model speaks the same protocol as the CellMate.
    endpoints=_CELLMATE_ENDPOINTS,
    cloud_endpoints=_CELLMATE_4G_ENDPOINTS,
    supports_cloud=True,
    # The Bluetooth profile is the same hardware as the standard CellMate.
    service_uuid="0000fee7-0000-1000-8000-00805f9b34fb",
    write_uuid="000036f5-0000-1000-8000-00805f9b34fb",
    notify_uuid="000036f6-0000-1000-8000-00805f9b34fb",
    # Cloud endpoints return the device status instead of a command payload.
    numbers=CELLMATE.numbers,
    buttons=CELLMATE.buttons,
    selects=(
        SelectSpec(
            key="work_mode",
            name="4G work mode",
            param="workStatus",
            command=CMD_WORK_MODE,
            options={"off": 0, "always_online": 1, "periodic": 2},
            default="off",
            icon="mdi:access-point-network",
        ),
    ),
)

METAL_LOCK: Final = FamilySpec(
    key="metal_lock",
    name="Metal Lock",
    type_ids=(13,),
    endpoints=_METAL_LOCK_ENDPOINTS,
    service_uuid="0000fee5-0000-1000-8000-00805f9b34fb",
    write_uuid="00003ff5-0000-1000-8000-00805f9b34fb",
    notify_uuid="00003ff6-0000-1000-8000-00805f9b34fb",
    buttons=(
        ButtonSpec(
            key="timing_lock",
            name="Start timed lock",
            command=CMD_TIMING_LOCK,
            icon="mdi:lock-clock",
        ),
        ButtonSpec(
            key="clear_timing_lock",
            name="Clear timed lock",
            command=CMD_CLEAR_TIMING_LOCK,
            icon="mdi:calendar-remove",
        ),
    ),
    numbers=(
        NumberSpec(
            key="timing_seconds",
            name="Timing duration",
            param="timingDuration",
            minimum=1,
            maximum=8640000,
            default=3600,
            unit="s",
            icon="mdi:timer-sand",
        ),
    ),
)

METAL_SHAKE: Final = FamilySpec(
    key="metal_shake",
    name="Metal Shake Lock",
    type_ids=(15,),
    endpoints=_METAL_SHAKE_ENDPOINTS,
    service_uuid="0000fee5-0000-1000-8000-00805f9b34fb",
    write_uuid="00003ff5-0000-1000-8000-00805f9b34fb",
    notify_uuid="00003ff6-0000-1000-8000-00805f9b34fb",
    buttons=(
        ButtonSpec(
            key="shake_now",
            name="Vibrate now",
            command=CMD_SHAKE_NOW,
            icon="mdi:vibrate",
        ),
        ButtonSpec(
            key="timing_shake",
            name="Start timed vibration",
            command=CMD_TIMING_SHAKE,
            icon="mdi:vibrate",
        ),
        ButtonSpec(
            key="cancel_timing_shake",
            name="Cancel timed vibration",
            command=CMD_CANCEL_TIMING_SHAKE,
            icon="mdi:calendar-remove",
        ),
        ButtonSpec(
            key="line_shake",
            name="Linear vibration",
            command=CMD_LINE_SHAKE,
            icon="mdi:sine-wave",
        ),
        ButtonSpec(
            key="stop_all",
            name="Stop all",
            command=CMD_STOP_ALL,
            icon="mdi:stop-circle-outline",
        ),
        ButtonSpec(
            key="timing_lock",
            name="Start timed lock",
            command=CMD_TIMING_LOCK,
            icon="mdi:lock-clock",
        ),
        ButtonSpec(
            key="clear_timing_lock",
            name="Clear timed lock",
            command=CMD_CLEAR_TIMING_LOCK,
            icon="mdi:calendar-remove",
        ),
    ),
    numbers=(
        NumberSpec(
            key="shake_duration",
            name="Vibration duration",
            param="shakeDuration",
            minimum=1,
            maximum=9999,
            default=5,
            unit="s",
            icon="mdi:timer-outline",
        ),
        NumberSpec(
            key="shake_intensity",
            name="Vibration intensity",
            param="shakeIntensity",
            minimum=1,
            maximum=5,
            default=3,
            icon="mdi:speedometer",
        ),
        NumberSpec(
            key="shake_model",
            name="Vibration mode",
            param="shakeModel",
            minimum=1,
            maximum=5,
            default=1,
            icon="mdi:waveform",
        ),
        NumberSpec(
            key="line_speed",
            name="Linear speed",
            param="lineSpeedValue",
            minimum=1,
            maximum=100,
            default=50,
            icon="mdi:speedometer-slow",
        ),
        NumberSpec(
            key="timing_seconds",
            name="Timing duration",
            param="timingDuration",
            minimum=1,
            maximum=8640000,
            default=3600,
            unit="s",
            icon="mdi:timer-sand",
        ),
    ),
)

PEAR_FLOWER: Final = FamilySpec(
    key="pear_flower",
    name="Pear Flower Three",
    type_ids=(18,),
    endpoints=_PEAR_FLOWER_ENDPOINTS,
    service_uuid="0000ac3a-0000-1000-8000-00805f9b34fb",
    write_uuid="0000ac3b-0000-1000-8000-00805f9b34fb",
    notify_uuid="0000ac3c-0000-1000-8000-00805f9b34fb",
    # Lock / unlock advance the toy one detent per written payload.
    repeat_commands=(CMD_LOCK, CMD_UNLOCK),
    buttons=(
        ButtonSpec(
            key="vibration",
            name="Vibrate now",
            command=CMD_VIBRATION,
            icon="mdi:vibrate",
        ),
        ButtonSpec(
            key="cancel_vibration",
            name="Stop vibration",
            command=CMD_CANCEL_VIBRATION,
            icon="mdi:vibrate-off",
        ),
        ButtonSpec(
            key="timing_vibration",
            name="Start timed vibration",
            command=CMD_TIMING_VIBRATION,
            icon="mdi:vibrate",
        ),
        ButtonSpec(
            key="cancel_timing_vibration",
            name="Cancel timed vibration",
            command=CMD_CANCEL_TIMING_VIBRATION,
            icon="mdi:calendar-remove",
        ),
        ButtonSpec(
            key="electric",
            name="Shock now",
            command=CMD_ELECTRIC,
            icon="mdi:flash",
            dangerous=True,
        ),
        ButtonSpec(
            key="cancel_electric",
            name="Stop shock",
            command=CMD_CANCEL_ELECTRIC,
            icon="mdi:flash-off",
        ),
        ButtonSpec(
            key="timing_electric",
            name="Start timed shock",
            command=CMD_TIMING_ELECTRIC,
            icon="mdi:flash-alert",
            dangerous=True,
        ),
        ButtonSpec(
            key="cancel_timing_electric",
            name="Cancel timed shock",
            command=CMD_CANCEL_TIMING_ELECTRIC,
            icon="mdi:calendar-remove",
        ),
        ButtonSpec(
            key="reset",
            name="Emergency unlock",
            command=CMD_RESET,
            icon="mdi:lock-open-alert",
        ),
    ),
    numbers=(
        NumberSpec(
            key="steps",
            name="Steps per lock command",
            param="steps",
            minimum=1,
            maximum=20,
            default=1,
            icon="mdi:stairs",
        ),
        NumberSpec(
            key="vibration_duration",
            name="Vibration duration",
            param="vibrationDuration",
            minimum=1,
            maximum=9999,
            default=5,
            unit="s",
            icon="mdi:timer-outline",
        ),
        NumberSpec(
            key="vibration_intensity",
            name="Vibration intensity",
            param="vibrationIntensity",
            minimum=1,
            maximum=5,
            default=3,
            icon="mdi:speedometer",
        ),
        NumberSpec(
            key="vibration_model",
            name="Vibration mode",
            param="vibrationModel",
            minimum=1,
            maximum=5,
            default=1,
            icon="mdi:waveform",
        ),
        NumberSpec(
            key="electric_duration",
            name="Shock duration",
            param="electricDuration",
            minimum=1,
            maximum=99,
            default=1,
            unit="s",
            icon="mdi:timer-outline",
        ),
        NumberSpec(
            key="electric_intensity",
            name="Shock level",
            param="electricIntensity",
            minimum=1,
            maximum=5,
            default=1,
            icon="mdi:flash",
        ),
        NumberSpec(
            key="electric_model",
            name="Shock mode",
            param="electricModel",
            minimum=1,
            maximum=3,
            default=1,
            icon="mdi:flash-outline",
        ),
        NumberSpec(
            key="timing_seconds",
            name="Timing duration",
            param="timingTime",
            minimum=1,
            maximum=8640000,
            default=3600,
            unit="s",
            icon="mdi:timer-sand",
        ),
    ),
    selects=(
        SelectSpec(
            key="offline_mode",
            name="Offline mode",
            param="openOfflineFlag",
            command=CMD_OFFLINE_MODE,
            options={"off": 2, "on": 1},
            default="off",
            icon="mdi:bluetooth-off",
        ),
    ),
)

FAMILIES: Final[tuple[FamilySpec, ...]] = (
    KEYPOD,
    CELLMATE,
    CELLMATE_4G,
    METAL_LOCK,
    METAL_SHAKE,
    PEAR_FLOWER,
)

FAMILY_BY_KEY: Final[Mapping[str, FamilySpec]] = {f.key: f for f in FAMILIES}


def normalise_uuid(value: str) -> str:
    """Expand a 16 or 32 bit Bluetooth UUID to its 128 bit form.

    Advertisements are not consistent: some adapters report ``fff0`` while
    others report the full ``0000fff0-0000-1000-8000-00805f9b34fb``.
    """
    value = value.strip().lower().removeprefix("0x")
    if "-" in value:
        return value
    if len(value) == 4:
        return f"0000{value}-0000-1000-8000-00805f9b34fb"
    if len(value) == 8:
        return f"{value}-0000-1000-8000-00805f9b34fb"
    return value


def _build_service_uuid_index() -> dict[str, tuple[FamilySpec, ...]]:
    """Group the families by the BLE service UUID they speak."""
    index: dict[str, list[FamilySpec]] = {}
    for family in FAMILIES:
        if family.service_uuid:
            index.setdefault(normalise_uuid(family.service_uuid), []).append(family)
    return {uuid: tuple(families) for uuid, families in index.items()}


#: BLE service UUID -> the families that use it.  A UUID can be shared (the
#: CellMate Pro 4G speaks the CellMate protocol over Bluetooth), which is why
#: this maps to a tuple instead of a single model.
SERVICE_UUID_FAMILIES: Final[Mapping[str, tuple[FamilySpec, ...]]] = (
    _build_service_uuid_index()
)


def families_for_service_uuids(service_uuids: Iterable[str]) -> tuple[FamilySpec, ...]:
    """Return every QIUI family advertised by a set of service UUIDs."""
    found: list[FamilySpec] = []
    for value in service_uuids:
        for family in SERVICE_UUID_FAMILIES.get(normalise_uuid(value), ()):
            if family not in found:
                found.append(family)
    return tuple(found)


def family_for_service_uuids(service_uuids: Iterable[str]) -> FamilySpec | None:
    """Return the most likely family for a set of advertised service UUIDs."""
    families = families_for_service_uuids(service_uuids)
    return families[0] if families else None


def type_id_from_family(family: FamilySpec | None) -> int:
    """Return the type id of a family, or ``0`` when it has several models."""
    if family is not None and len(family.type_ids) == 1:
        return family.type_ids[0]
    return 0


#: type id -> human readable model, taken from the developer console.
MODEL_NAMES: Final[Mapping[int, str]] = {
    1: "Cag Ink (I)",
    2: "Pear Flower plug",
    3: "Little Devil",
    4: "Cag Ink (II)",
    5: "Shock paddle",
    6: "Key Pod (I)",
    7: "Cag Ink (II)",
    9: "Second generation plug",
    10: "Cag Ink (III) / CellMate Pro 4G",
    11: "Key Pod (II)",
    12: "Tail",
    13: "Metal Lock",
    15: "Metal Shake Lock",
    18: "Pear Flower Three",
}

TYPE_ID_TO_FAMILY: Final[Mapping[int, FamilySpec]] = {
    type_id: family for family in FAMILIES for type_id in family.type_ids
}

SUPPORTED_TYPE_IDS: Final[tuple[int, ...]] = tuple(sorted(TYPE_ID_TO_FAMILY))

# ---------------------------------------------------------------------------
# Platform error codes
# ---------------------------------------------------------------------------

#: Human readable messages for the ``code`` values the platform returns.  The
#: names come from the developer console's error table; the messages are the
#: integration's own wording.
ERROR_CODES: Final[Mapping[int, str]] = {
    401: "The platform API token is invalid or expired",
    500000: "Unexpected platform error",
    500011: "The platform received an empty request",
    500019: "The Environment header is missing",
    500020: "The Environment header is invalid",
    500021: "The platform could not decrypt the device answer",
    500022: "The device is not bound to the platform",
    500023: "The device is already bound to this platform",
    500024: "The platform could not bind the device",
    500025: "The device is bound to another QIUI platform",
    500026: "The device does not belong to this platform",
    500027: "The platform could not release the device",
    500028: "The test environment only allows one device",
    500030: "The platform could not create a device token",
    500031: "The device token is invalid",
    500032: "The platform could not build the Key Pod unlock command",
    500033: "The platform could not build the Key Pod lock command",
    500034: "The platform could not build the Key Pod state command",
    500035: "The platform could not build the Key Pod shutdown command",
    500036: "The platform has no device bound with this Bluetooth address",
    500037: "The developer client id is invalid",
    500038: "The developer application is missing required information",
    500039: "The developer application information is invalid",
    500040: "The platform could not refresh the API token",
    500041: "The username and password do not match",
    500042: "A timed command is already active on this device",
    500043: "The device did not confirm the command",
    500044: "The device is registered in a different environment (PRODUCT/TEST)",
    500045: "The platform could not build the CellMate notify command",
    500046: "The platform could not build the CellMate work mode command",
    500047: "The platform could not build the CellMate unlock command",
    500048: "The platform could not build the CellMate timed unlock command",
    500049: "The platform could not build the CellMate clear-timed-unlock command",
    500050: "The platform could not build the CellMate shock command",
    500051: "The platform could not build the CellMate 5 second shock command",
    500052: "The platform could not build the CellMate stop-shock command",
    500053: "The platform could not build the CellMate timed shock command",
    500054: "The platform could not build the CellMate clear-timed-shock command",
    500055: "The platform could not build the CellMate location command",
    500056: "The platform could not build the display direction command",
    500057: "The platform could not build the server IP/port command",
}

#: Codes that mean "the device is already bound to this platform", which is a
#: success for ``addDeviceInfo``.
ALREADY_BOUND_CODES: Final[frozenset[str]] = frozenset({"500023"})


def error_message(code: Any) -> str:
    """Return a readable message for a platform error code."""
    try:
        return ERROR_CODES.get(int(code), "Unknown platform error")
    except (TypeError, ValueError):
        return "Unknown platform error"
