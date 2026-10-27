"""Binary sensors: bin needs to go out now / bin was forgotten."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    entities: list[BinarySensorEntity] = []
    for bin_id in coordinator.bins:
        entities += [
            DueBinarySensor(coordinator, bin_id, "due"),
            ForgottenBinarySensor(coordinator, bin_id, "forgotten"),
        ]
    async_add_entities(entities)


class DueBinarySensor(BinEntity, BinarySensorEntity):
    """On from the evening reminder until collection time, unless put out."""

    _attr_icon = "mdi:delete-alert"

    @property
    def is_on(self) -> bool:
        return self.bin_state.due


class ForgottenBinarySensor(BinEntity, BinarySensorEntity):
    """On after collection time on collection day if the bin wasn't put out."""

    _attr_icon = "mdi:delete-off"

    @property
    def is_on(self) -> bool:
        return self.bin_state.forgotten
