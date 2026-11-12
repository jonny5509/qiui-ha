"""Sensor platform for the QIUI integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import QiuiCoordinator
from .entity import QiuiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors for the device."""
    coordinator: QiuiCoordinator = entry.runtime_data
    entities: list[QiuiEntity] = []

    if coordinator.device.family.supports_cloud:
        entities.append(QiuiBatterySensor(coordinator))
        entities.append(QiuiStatusSensor(coordinator))

    entities.append(QiuiLastResponseSensor(coordinator))
    async_add_entities(entities)


class QiuiBatterySensor(QiuiEntity, SensorEntity):
    """Battery level reported by the 4G cloud endpoints."""

    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: QiuiCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "battery")

    @property
    def native_value(self) -> int | None:
        """Return the battery percentage."""
        return self.coordinator.state_data.battery


class QiuiStatusSensor(QiuiEntity, SensorEntity):
    """Online status reported by the 4G cloud endpoints."""

    _attr_name = "Status"
    _attr_icon = "mdi:cloud-check-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: QiuiCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "status")

    @property
    def native_value(self) -> str | None:
        """Return a human readable status."""
        status = self.coordinator.state_data
        if status.online is None:
            return None
        return "online" if status.online else "offline"


class QiuiLastResponseSensor(QiuiEntity, SensorEntity):
    """Last response received from the device.

    Useful while setting up a device, because the platform answers with an
    encrypted payload whose meaning depends on the firmware revision.
    """

    _attr_name = "Last device response"
    _attr_icon = "mdi:message-text-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: QiuiCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "last_response")

    @property
    def native_value(self) -> str | None:
        """Return the last command or error."""
        status = self.coordinator.state_data
        return status.last_error or status.last_response

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details about the last command."""
        super_attrs: dict[str, Any] = dict(super().extra_state_attributes)
        status = self.coordinator.state_data
        super_attrs.update(
            {
                "last_command": status.last_command,
                "last_error": status.last_error,
            }
        )
        return super_attrs
