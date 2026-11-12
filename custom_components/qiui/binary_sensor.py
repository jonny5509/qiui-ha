"""Binary sensor platform for the QIUI integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import QiuiCoordinator
from .entity import QiuiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the connectivity sensor for 4G devices."""
    coordinator: QiuiCoordinator = entry.runtime_data
    if coordinator.device.family.supports_cloud:
        async_add_entities([QiuiOnlineSensor(coordinator)])


class QiuiOnlineSensor(QiuiEntity, BinarySensorEntity):
    """Whether the device currently has a 4G connection."""

    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: QiuiCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "online")

    @property
    def is_on(self) -> bool | None:
        """Return the online state."""
        return self.coordinator.state_data.online

    @property
    def available(self) -> bool:
        """Only report a value once the cloud has answered."""
        return self.coordinator.state_data.online is not None
