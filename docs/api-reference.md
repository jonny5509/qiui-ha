# QIUI Open Platform — API reference

Recovered from the public developer documentation at
<https://developers.qiuitoy.com> (the portal is a single-page app, so this file
captures the specification the integration is built against).

## Base URL

```
https://openapi.qiuitoy.com/system/api
```

All calls are `POST` with `Content-Type: application/json`.

## Headers

| Header | Required | Value |
| --- | --- | --- |
| `Environment` | always | `PRODUCT` (live devices) or `TEST` (sandbox) |
| `Authorization` | most endpoints | the `platformApiToken`, **without** a `Bearer` prefix |
| `Content-Type` | always | `application/json` |

## Response envelope

```json
{ "code": 0, "data": { }, "message": "" }
```

`code` is inconsistent across the platform: the documentation shows `0`, the
developer console treats `200` as success. Treat both as success. `data` is
sometimes a string (an encrypted command), sometimes an object. Errors arrive
with HTTP status 200 and a non-zero body `code`, so the body is authoritative.

Errors carry a `code` and a message. The field is usually `message`, but some
gateway-level errors use `msg` instead, so both are read. `const.py` maps the
documented codes to readable text. The codes that matter to a long-running
integration are:

| Code | Name | Meaning |
| --- | --- | --- |
| `401` | `PlatformApiTokenExpired` | refresh the platform token |
| `500019` / `500020` | `RequestHeaderNotEnvironmentKey` / `…Illegality` | the `Environment` header is missing or invalid |
| `500021` | `DecryptFailed` | the device answer could not be decrypted |
| `500022` | `DeviceNotExists` | the Bluetooth address is not bound to the platform |
| `500023` | `DeviceAlreadyExists` | already bound to this platform (treated as success by `addDeviceInfo`) |
| `500025` | `DeviceBindingWithOtherPlatform` | bound to a different platform account |
| `500026` | `DeviceNotBelongsPlatform` | the device belongs to another developer account |
| `500028` | `TestEnvironmentOnlyOneDevice` | the `TEST` environment allows only one device |
| `500030` / `500031` | `GetDeviceTokenError` / `DeviceTokenIsInvalid` | token handshake failed |
| `500036` | `PlatformNotBindDevice` | the platform has no device with that address |
| `500037` | `PlatformClientIdInvalid` | the `clientId` is wrong or not approved |
| `500038` / `500039` | `PlatformImportanceInfoDeficiency` / `PlatformInfoInvalid` | the developer application is incomplete |
| `500042` | `ExistTimingError` | a timed command is already running |
| `500043` | `CmdCallbackStatusFailure` | the device did not confirm the command |
| `500044` | `SecretKeyNotMatchDeviceEnvironment` | device registered in the other environment |
| `500032`–`500035`, `500045`–`500057` | per-model failures | the platform could not build that model's command |

## Authentication

1. **Platform token** — `POST /device/common/getPlatformApiToken`

   ```json
   { "clientId": "ClientId_…", "grantType": "client_credentials" }
   ```

   Returns `{ "platformApiToken": "…", "expiresTime": … }`, valid for 12 hours.
   The integration refreshes it at 11 hours, or on the first auth failure.

2. **Refresh** — `POST /device/common/refreshPlatformApiToken`
   Same body as above, but `Authorization` must carry the current token.

3. **Device token** — `POST /device/common/getDeviceToken`
   Called *after* subscribing to the device's notify characteristic. The
   returned string changes on every connection and must be written to the
   device before the actual command.

   ```json
   { "bluetoothAddress": "AA:BB:CC:DD:EE:FF", "serialNumber": "QIUI…", "typeId": 6 }
   ```

   Device families with their own token endpoint use it instead:

   | Family | Token endpoint |
   | --- | --- |
   | Key Pod | `/device/common/getDeviceToken` |
   | CellMate (BLE) | `/device/cellMate/bluetooth/buildCellMatePro4GTokenCmd` |
   | CellMate Pro 4G | `/device/cellMate/4g/sendCellMatePro4GTokenCmd` |
   | Metal Lock | `/device/toyMetalLockBluetooth/getMetalLockTokenCmd` |
   | Metal Shake | `/device/toyMetalShakeLockBluetooth/getMetalShakeLockTokenCmd` |
   | Pear Flower Three | `/device/pearFlowerThree/getToyToken` |

## Device binding

```text
POST /platform/device/addDeviceInfo      { "bluetoothAddress": "AA:BB:CC:DD:EE:FF" }
POST /platform/device/queryDeviceInfo    { "bluetoothAddress": "AA:BB:CC:DD:EE:FF" }
```

`queryDeviceInfo` returns:

```json
{
  "id": 0, "bluetoothAddress": "", "serialNumber": "", "typeId": 0,
  "iccid": "", "environmentType": 0, "userId": 0,
  "remark": "", "createBy": "", "createTime": "", "updateBy": "", "updateTime": ""
}
```

`GET /platform/device/list?page=N&limit=M` exists but requires the **developer
console** bearer token (email/SMS login), not the platform token, so it is not
usable from a long-running integration.

## Device types

| typeId | Model | Family key |
| --- | --- | --- |
| 1 | Cag Ink (I) | `cellmate` |
| 2 | Pear Flower plug | — (no public endpoints) |
| 3 | Little Devil | — |
| 4, 7 | Cag Ink (II) | `cellmate` |
| 5 | Shock paddle | — |
| 6 | Key Pod (I) | `keypod` |
| 9 | Second generation plug | — |
| 10 | Cag Ink (III) / CellMate Pro 4G | `cellmate_4g` |
| 11 | Key Pod (II) | `keypod` |
| 12 | Tail | — |
| 13 | Metal Lock | `metal_lock` |
| 15 | Metal Shake Lock | `metal_shake` |
| 18 | Pear Flower Three | `pear_flower` |

## Bluetooth profiles

The documentation lists three UUIDs per model: service, **notify**, write.

| Family | Service | Notify | Write |
| --- | --- | --- | --- |
| Key Pod | `0000fff0-…` | `0000fff2-…` | `0000fff1-…` |
| CellMate | `0000fee7-…` | `000036f6-…` | `000036f5-…` |
| Metal Lock | `0000fee5-…` | `00003ff6-…` | `00003ff5-…` |
| Metal Shake | `0000fee5-…` | `00003ff6-…` | `00003ff5-…` |
| Pear Flower Three | `0000ac3a-…` | `0000ac3c-…` | `0000ac3b-…` |

(`…` = `-0000-1000-8000-00805f9b34fb`.)

## Command round trip

```text
connect → discover service
        → start_notify(notify_uuid)
        → POST <token endpoint>              → write returned payload
        → POST <command endpoint>            → write returned payload
        → wait for notification (optional)
        → POST <decrypt endpoint>            → parsed device answer
        → disconnect
```

## Request shapes

Simple commands take the flat device body:

```json
{ "bluetoothAddress": "AA:BB:CC:DD:EE:FF", "serialNumber": "QIUI…", "typeId": 13 }
```

Commands with parameters wrap the device body:

```json
{
  "basicDeviceApiReq": {
    "bluetoothAddress": "AA:BB:CC:DD:EE:FF",
    "serialNumber": "QIUI…",
    "typeId": 18
  },
  "vibrationDuration": 5,
  "vibrationIntensity": 3,
  "vibrationModel": 1
}
```

Commands **without** `basicDeviceApiReq`: `unlock`, `lock`, `stop_shock`,
`clear_shock`, `clear_timing_unlock`, `clear_timing_lock`,
`cancel_timing_shake`, `stop_all`, `cancel_vibration`,
`cancel_timing_vibration`, `cancel_electric`, `cancel_timing_electric`,
`decrypt`, `token`.

Commands **with** `basicDeviceApiReq`: `timing_unlock`, `timing_lock`,
`timing_shock`, `timing_shake`, `shock_1s`, `shock_5s`, `shake_now`,
`line_shake`, `vibration`, `timing_vibration`, `electric`, `timing_electric`,
`offline_mode`, `work_mode`, `display_direction`, `reset`.

## Parameter ranges

| Parameter | Command(s) | Range |
| --- | --- | --- |
| `shockVolt` | `shock_1s`, `shock_5s`, `timing_shock`, `timing_unlock` | 0–4 (timed unlock), 1–5 (shock) |
| `shockModel` | shock commands | 1–3 |
| `shockDuration` | `timing_shock` | 1–99 s |
| `timingDuration` | `timing_shock`, `timing_unlock`, `timing_lock`, `timing_shake` | 1–8 640 000 s |
| `shakeDuration` / `vibrationDuration` | shake / vibration commands | 1–9 999 |
| `shakeIntensity` / `vibrationIntensity` | shake / vibration commands | 1–5 |
| `shakeModel` / `vibrationModel` | shake / vibration commands | 1–5 |
| `lineSpeedValue` | `line_shake` | 1–100 |
| `electricDuration` | `electric`, `timing_electric` | 1–99 s |
| `electricIntensity` / `electricModel` | `electric`, `timing_electric` | 1–5 / 1–3 |
| `timingTime` | Pear Flower timing commands | 1–8 640 000 s |
| `workStatus` | `work_mode` | 0 off, 1 always online, 2 periodic |
| `direction` | `display_direction` | 0 forward, 1 reverse |
| `openOfflineFlag` | `offline_mode` | 1 on, 2 off |

## 4G cloud endpoints

The CellMate Pro 4G can be driven without Bluetooth. These endpoints return the
device status instead of a command payload:

```json
{
  "serialNumber": "QIUI…", "mqttType": "mqtt_h00002", "cmdStatus": false,
  "bluetoothAddress": "E5:A5:42:15:01:3D", "onlineStatus": 1,
  "battery": 92, "lat": 123, "lon": 456
}
```

They live under `/device/cellMate/4g/` and mirror the Bluetooth command names:
`sendCellMatePro4G{Token,Notify,UnLock,Lock}Cmd`,
`sendCellMateProTimingUnlock`, `sendCellMateProClearTimingUnlockCmd`,
`sendToyTimingElectricShock`, `sendClearAllElectricShockCmd`,
`sendCellMateProShockImmediatelyShockCmd`,
`sendCellMateProShockContinuedFiveSecond`,
`sendCellMateProStopAllShockCmd`, `sendCellMatePro4GWorkModelCmd`.

Over Bluetooth the same model uses the `/device/cellMate/bluetooth/` endpoints
from the section above; the integration picks the right set per transport.

Additional MQTT helpers (not used by this integration, because they return
credential material rather than device state):

```text
POST /device/common/getPlatformMqttSubscribeInfoRes
POST /device/common/platformOpen4GSubscribe
POST /device/common/updateMqttSubscribeOpenFlag
POST /device/common/updateMqttEncryptFlag
POST /device/common/updateMqttEncryptEnvironment
```

## Endpoint index

Every documented endpoint, grouped by family. All are `POST`.

**Common / platform**

```text
/device/common/getPlatformApiToken
/device/common/refreshPlatformApiToken
/device/common/getDeviceToken
/platform/device/addDeviceInfo
/platform/device/queryDeviceInfo
/platform/device/list?page=N&limit=M      (developer console token only)
```

**Key Pod** — `/device/keyPod/`

```text
decryBluetoothCommand
getKeyPodUnlockCmd
getKeyPodLockCmd
```

Error codes mention `getKeyPodStateCmd` and `getKeyPodShutdownCmd`; they are
not documented as callable endpoints.

**CellMate (BLE)** — `/device/cellMate/`

```text
decryBluetoothCommand
bluetooth/buildCellMatePro4GTokenCmd
bluetooth/buildCellMatePro4GUnLockCmd
bluetooth/buildCellMatePro4GLockCmd
bluetooth/buildCellMateProTimingUnlock
bluetooth/buildCellMateProClearTimingUnlockCmd
bluetooth/buildToyTimingElectricShock
bluetooth/buildClearAllElectricShockCmd
bluetooth/buildCellMateProShockImmediatelyShockCmd
bluetooth/buildCellMateProShockContinuedFiveSecond
bluetooth/buildCellMateProStopAllShockCmd
bluetooth/buildDisplayDirectionCmd
bluetooth/buildServerIpAndPortCmd
bluetooth/buildCellMatePro4GWorkModelCmd
```

**Metal Lock** — `/device/toyMetalLockBluetooth/`

```text
getMetalLockTokenCmd
decryBluetoothCommand
getMetalLockUnLockCmd
getMetalLockCmd
getMetalLockTimingLockCmd
getMetalClearTimingLockCmd
```

**Metal Shake Lock** — `/device/toyMetalShakeLockBluetooth/`

```text
getMetalShakeLockTokenCmd
decryBluetoothCommand
getMetalShakeLockUnLockCmd
getMetalShakeLockCmd
getMetalShakeLockTimingLockCmd
getMetalShakeClearTimingLockCmd
getShakeMetalTimingShakeCmd
getShakeMetalCancelTimingShakeCmd
getShakeMetalLockImmediatelyShakeCmd
stopAllShakeAndElectricCmd
getLineModelShakeCmd
```

**Pear Flower Three** — `/device/pearFlowerThree/`

```text
getToyToken
decryBluetoothCommand
generatePearFlowerThreeToyUnlock
generatePearFlowerThreeToyLock
generatePearFlowerThreeToyVibration
generatePearFlowerThreeToyCancelVibration
generatePearFlowerThreeToyTimingVibration
generatePearFlowerThreeToyCancelTimingVibration
generatePearFlowerThreeToyElectric
generatePearFlowerThreeToyCancelElectric
generatePearFlowerThreeToyTimingElectric
generatePearFlowerThreeToyCancelTimingElectric
generatePearFlowerThreeToyIsOpenOfflineFlag
generatePearFlowerThreeReset
```

Pear Flower `lock` / `unlock` return a *step* payload: every write advances one
detent, so the payload has to be written repeatedly (the integration's
*Steps per lock command* number controls how often).
