"""Number platform for the QIUI integration."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NumberSpec
from .coordinator import QiuiCoordinator
from .entity import QiuiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the tunable parameters for the device family."""
    coordinator: QiuiCoordinator = entry.runtime_data
    async_add_entities(
        QiuiNumber(coordinator, spec) for spec in coordinator.device.family.numbers
    )


class QiuiNumber(QiuiEntity, RestoreNumber):
    """A value used by the QIUI action buttons.

    Values are kept locally and only sent to the device as part of the command
    that uses them; the platform has no endpoint to read them back.
    """

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: QiuiCoordinator, spec: NumberSpec) -> None:
        """Initialise the number."""
        super().__init__(coordinator, f"number_{spec.key}")
        self._spec = spec
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_native_min_value = spec.minimum
        self._attr_native_max_value = spec.maximum
        self._attr_native_step = spec.step
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_native_value = spec.default

    async def async_added_to_hass(self) -> None:
        """Restore the previous value."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data is not None and last_data.native_value is not None:
            self._attr_native_value = last_data.native_value
        if self._spec.param:
            self.coordinator.set_param(self._spec.param, self._attr_native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Store a new value."""
        self._attr_native_value = value
        if self._spec.param:
            self.coordinator.set_param(self._spec.param, value)
        self.async_write_ha_state()
