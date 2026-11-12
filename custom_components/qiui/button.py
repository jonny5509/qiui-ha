"""Button platform for the QIUI integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ButtonSpec
from .coordinator import QiuiCoordinator
from .entity import QiuiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the action buttons for the device family."""
    coordinator: QiuiCoordinator = entry.runtime_data
    entities = []
    for spec in coordinator.device.family.buttons:
        if spec.dangerous and not coordinator.allow_dangerous:
            continue
        entities.append(QiuiButton(coordinator, spec))
    async_add_entities(entities)


class QiuiButton(QiuiEntity, ButtonEntity):
    """A one-shot QIUI action."""

    def __init__(self, coordinator: QiuiCoordinator, spec: ButtonSpec) -> None:
        """Initialise the button."""
        super().__init__(coordinator, f"button_{spec.key}")
        self._spec = spec
        self._attr_name = spec.name
        self._attr_icon = spec.icon

    async def async_press(self) -> None:
        """Run the action."""
        await self.coordinator.async_execute(self._spec.command)
