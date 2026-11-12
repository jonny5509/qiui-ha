"""Base entity for the QIUI integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import QiuiCoordinator


class QiuiEntity(CoordinatorEntity[QiuiCoordinator]):
    """Common behaviour for all QIUI entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: QiuiCoordinator, key: str) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device registry information."""
        device = self.coordinator.device
        return DeviceInfo(
            identifiers={(DOMAIN, device.address)},
            name=self.coordinator.entry.title,
            manufacturer="QIUI",
            model=device.family.name,
            serial_number=device.serial_number or None,
            connections={("bluetooth", device.address)},
        )

    @property
    def available(self) -> bool:
        """Return whether the entity can be controlled right now."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the device identifiers for troubleshooting."""
        device = self.coordinator.device
        return {
            "bluetooth_address": device.address,
            "serial_number": device.serial_number,
            "type_id": device.type_id,
            "family": device.family.key,
        }
