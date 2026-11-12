# QIUI for Home Assistant

Control QIUI Bluetooth devices from Home Assistant, using the official
[QIUI Open Platform](https://developers.qiuitoy.com) for command generation and
Bluetooth (a local adapter, or an ESP32 running ESPHome as a proxy) for the
radio link.

```
        Home Assistant                          QIUI cloud
   ┌────────────────────────┐            ┌──────────────────────────┐
   │  qiui integration      │  HTTPS     │  openapi.qiuitoy.com     │
   │  · token handling      │ ─────────► │  · encrypts BLE command  │
   │  · entity /services    │ ◄───────── │  · decrypts BLE answer   │
   └──────────┬─────────────┘            └──────────────────────────┘
              │ Bluetooth LE (GATT)
              │
     ┌────────┴─────────┐
     │ local adapter or │
     │ ESP32 BT proxy   │  ← recommended: ESP32 next to the device
     └────────┬─────────┘
              │
        ┌─────┴──────┐
        │ QIUI device│
        └────────────┘
```

## Why it needs both a cloud account and Bluetooth

The QIUI developer API is **not** a remote-control API. It is a *command
builder*: you send it a device's Bluetooth address, serial number and type, and
it returns an encrypted payload. Your app then writes that payload to the
device's GATT characteristic and, optionally, sends the device's answer back to
the platform for decryption.

That means Home Assistant needs to be within Bluetooth range of the device. An
ESP32 with ESPHome is the cheapest and most reliable way to put a radio next to
a device that lives in another room. Only the CellMate Pro 4G can be controlled
over the internet, through the platform's MQTT/4G endpoints.

## Supported devices

| Model | Type ID | Lock | Actions | Notes |
| --- | --- | --- | --- | --- |
| Key Pod (I) | 6 | ✅ | – | |
| Key Pod (II) | 11 | ✅ | – | |
| Cag Ink (I) | 1 | ✅ | shock, timed shock/unlock | |
| Cag Ink (II) | 4, 7 | ✅ | shock, timed shock/unlock | |
| Cag Ink (III) / CellMate Pro 4G | 10 | ✅ | shock, timed shock/unlock | Bluetooth **and** 4G cloud |
| Metal Lock | 13 | ✅ | timed lock | |
| Metal Shake Lock | 15 | ✅ | vibration, timed vibration, linear vibration, timed lock | |
| Pear Flower Three | 18 | ✅ | vibration, shock, timed vibration/shock, offline mode | lock/unlock advance one detent per step |

Older models without a documented endpoint (types 2, 3, 5, 9, 12) can be added
but are rejected as unsupported, because their commands are not published.

## Requirements

- Home Assistant 2024.6 or newer.
- A QIUI developer account with an approved application (`clientId`).
- Bluetooth LE access: the Home Assistant host's adapter, or an ESPHome
  Bluetooth proxy in range (see below).

## Installation

### HACS (custom repository)

1. HACS → Integrations → ⋮ → **Custom repositories**.
2. Add the URL of this repository, category **Integration**.
3. Install **QIUI**, then restart Home Assistant.

### Manual

Copy `custom_components/qiui` into your Home Assistant `config/custom_components`
folder and restart.

## ESP32 Bluetooth proxy

Flash [`esphome/qiui-ble-proxy.yaml`](esphome/qiui-ble-proxy.yaml) to an ESP32
within a few metres of the device:

```bash
esphome run esphome/qiui-ble-proxy.yaml
```

The board needs no QIUI credentials; it only relays GATT connections. The
important bits are:

```yaml
esp32_ble_tracker:
  scan_parameters:
    interval: 1100ms
    window: 1100ms
    active: true

bluetooth_proxy:
  active: true
```

Put the ESP32 on Ethernet, or use an ESP32-S3, if the Wi-Fi signal where the
device lives is weak — BLE and Wi-Fi share the radio on the original ESP32.

The YAML expects these entries in `esphome/secrets.yaml` (or your ESPHome
dashboard's secrets):

```yaml
api_key: "…"          # 32 byte base64 key for the native API
ota_password: "…"
wifi_ssid: "…"
wifi_password: "…"
```

Home Assistant will pick the nearest proxy automatically. Nothing in this
integration has to be configured for it.

## Configuration

1. Open <https://developers.qiuitoy.com>, register as a developer and create an
   application. Copy its **clientId**.
2. In Home Assistant: **Settings → Devices & services → Add integration →
   QIUI**.
3. Enter the client id and pick the environment (`PRODUCT` for real devices,
   `TEST` for the platform's sandbox).
4. Add the device. Detection happens in layers, so you normally only have to
   confirm:
   - **Bluetooth discovery** – devices that advertise one of the QIUI service
     UUIDs (`fff0`, `fee7`, `fee5`, `ac3a`) show up on the *Devices & services*
     page as a discovered device. The client id of an existing QIUI entry is
     reused automatically.
   - **Nearby device picker** – otherwise the integration lists the Bluetooth
     devices it can currently reach, with the detected model next to each one.
   - **GATT probe** – if the advertisement has no service UUID and the platform
     does not report the model, the integration briefly connects and reads the
     GATT services to identify the family.
   - **Platform lookup** – the device is bound to your account and the platform
     returns the exact serial number and type id.
   - **Manual fallback** – if the platform does not know the device, pick the
     model and type the serial number by hand.
5. Repeat step 4 for every device. One config entry = one physical device.

### Options

| Option | Default | Meaning |
| --- | --- | --- |
| Transport | `auto` | 4G-capable devices: use Bluetooth when the device is visible, otherwise the cloud. |
| Enable shock actions | off | Shock/electric entities are not created unless this is on. |
| Write handshake token | on | Write the per-connection token before the command (as the docs describe). |
| Response timeout | 8 s | How long to wait for a notification. Many commands never answer, so a timeout is not an error. |
| Command payload format | `auto` | How the platform's payload string is decoded (`hex`, `base64`, `text`). |
| Service / write / notify UUID | per model | Override the BLE profile if a device ships with different characteristics. |

### Entities

- **Lock** – the primary entity, named after the device.
- **Buttons** – one-shot actions: shock, timed shock, stop shock, vibration,
  timed vibration, linear vibration, timed lock, emergency unlock, …
- **Numbers** – values used by those actions: intensity, mode, duration,
  timing duration, steps.
- **Selects** – settings that are pushed immediately: 4G work mode, display
  direction, offline mode.
- **Sensors** – battery and online status (4G models only), plus a diagnostic
  *Last device response* sensor (disabled by default).
- **Binary sensor** – online state for 4G models.

The lock state is **optimistic**: these devices do not report whether they are
locked, so the entity follows the last command the platform accepted.

### Service

`qiui.send_command` sends a raw command to a device, which is useful for models
or firmware revisions that are not fully covered:

```yaml
action: qiui.send_command
data:
  device_id: 0f1e2d3c4b5a69788796a5b4c3d2e1f0
  command: shock_1s
  parameters:
    shockVolt: 2
    shockModel: 1
```

The service only accepts commands the model supports, and it refuses shock /
electric commands unless *Enable shock actions* is turned on in the options.

## Limitations

- **Bluetooth range is mandatory** for every model except the CellMate Pro 4G.
  There is no internet path for the others.
- Only one application can hold the Bluetooth connection. While Home Assistant
  is sending a command the phone app cannot be connected, and the device
  ignores commands if the vendor app is already connected.
- The lock state and the numeric settings are not readable from the device.
  Battery, 4G online state and location are only available from the 4G cloud
  responses.
- Timing values are in **seconds** (the platform accepts 1 … 8 640 000).
- Payload framing is not documented by QIUI. If a device ignores commands, try
  the other *Command payload format* values, and open an issue with the
  diagnostic download attached.

## Safety

This integration can trigger electrical stimulation on devices that support it.

- Shock and electric entities are **disabled by default** and only created when
  *Enable shock actions* is turned on in the options.
- Levels are capped by the ranges the platform documents (1–5).
- Never use these actions on a person who cannot remove the device themselves,
  and never combine them with a timed lock you cannot override. Keep the
  physical key or the vendor app available as an emergency release.

## Troubleshooting

**The device is not offered as a discovered device** – many QIUI models only
advertise while they are awake. Press the device's button or plug in the charger
and wait a few seconds. If it still does not appear, use **Add integration →
QIUI**: the nearby-device picker also lists devices that do not advertise a
QIUI service UUID.

**"Device was not seen by any Bluetooth adapter"** – Home Assistant has not seen
an advertisement from the device. Check the proxy is online, move it closer, or
wake the device (some models only advertise after a button press).

**"Could not find the QIUI write/notify characteristics"** – the device uses a
different BLE profile. Download diagnostics, look at the discovered services in
the log, and set the UUIDs in the options.

**Commands return an empty payload** – the platform does not know the device or
the serial/type combination is wrong. Re-add the device and let the platform
fill in the serial number.

**Enable debug logging**

```yaml
logger:
  default: warning
  logs:
    custom_components.qiui: debug
```

## Development

The integration is a plain custom component; no build step.

```bash
python -m pytest tests -q
```

`docs/api-reference.md` documents every endpoint the integration uses, as
recovered from the public developer documentation.

Before publishing the repository, update `codeowners`, `documentation` and
`issue_tracker` in `custom_components/qiui/manifest.json` to point at your own
GitHub repository.

## Disclaimer

Not affiliated with QIUI. Use at your own risk, and only on devices you own.
