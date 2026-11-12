"""Lock platform for the QIUI integration."""

from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CMD_LOCK, CMD_UNLOCK
from .coordinator import QiuiCoordinator
from .entity import QiuiEntity

_PLATFORMS = (CMD_LOCK, CMD_UNLOCK)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the QIUI lock."""
    coordinator: QiuiCoordinator = entry.runtime_data
    family = coordinator.device.family
    if all(family.supports(command) for command in _PLATFORMS):
        async_add_entities([QiuiLock(coordinator)])


class QiuiLock(QiuiEntity, LockEntity):
    """A QIUI lock.

    The hardware does not report its state, so the state is optimistic: it
    follows the last command that was accepted by the platform.
    """

    _attr_name = None
    _attr_assumed_state = True

    def __init__(self, coordinator: QiuiCoordinator) -> None:
        """Initialise the lock."""
        super().__init__(coordinator, "lock")

    @property
    def is_locked(self) -> bool | None:
        """Return the last known lock state."""
        state = self.coordinator.state_data.lock_state
        if state is None:
            return None
        return state == "locked"

    async def async_lock(self, **kwargs) -> None:
        """Lock the device."""
        await self.coordinator.async_execute(CMD_LOCK)

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the device."""
        await self.coordinator.async_execute(CMD_UNLOCK)
