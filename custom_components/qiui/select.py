"""Select platform for the QIUI integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SelectSpec
from .coordinator import QiuiCoordinator
from .entity import QiuiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the selects for the device family."""
    coordinator: QiuiCoordinator = entry.runtime_data
    async_add_entities(
        QiuiSelect(coordinator, spec) for spec in coordinator.device.family.selects
    )


class QiuiSelect(QiuiEntity, SelectEntity):
    """A device setting that is pushed immediately when changed."""

    def __init__(self, coordinator: QiuiCoordinator, spec: SelectSpec) -> None:
        """Initialise the select."""
        super().__init__(coordinator, f"select_{spec.key}")
        self._spec = spec
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_options = list(spec.options)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self.coordinator.state_data.selections.get(
            self._spec.key, self._spec.default
        )

    async def async_select_option(self, option: str) -> None:
        """Send the new setting to the device."""
        if option not in self._spec.options:
            raise ValueError(f"Unsupported option: {option}")

        await self.coordinator.async_execute(
            self._spec.command, {self._spec.param: self._spec.options[option]}
        )
        self.coordinator.set_selection(self._spec.key, option)
