"""Switch: 'this bin has been put out' for the next collection."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BinsOutConfigEntry
from .entity import BinEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BinsOutConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PutOutSwitch(coordinator, b, "put_out") for b in coordinator.bins)


class PutOutSwitch(BinEntity, SwitchEntity):
    """Turn on when the bin is at the kerb. Clears itself the day after collection."""

    _attr_icon = "mdi:delete-circle"

    @property
    def is_on(self) -> bool:
        return self.bin_state.put_out

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.set_put_out(self.bin_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.set_put_out(self.bin_id, False)
