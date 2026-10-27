"""Base entities for Bins Out."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BIN_COLOUR, CONF_BIN_NAME, DOMAIN, VERSION
from .coordinator import BinsOutCoordinator
from .schedule import BinState


def hub_device(coordinator: BinsOutCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="Bins Out",
        entry_type=DeviceEntryType.SERVICE,
        sw_version=VERSION,
    )


class BinEntity(CoordinatorEntity[BinsOutCoordinator]):
    """An entity belonging to one bin (one device per bin)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BinsOutCoordinator, bin_id: str, key: str) -> None:
        super().__init__(coordinator)
        self.bin_id = bin_id
        cfg = coordinator.bins[bin_id]
        entry_id = coordinator.config_entry.entry_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{bin_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{bin_id}")},
            name=cfg[CONF_BIN_NAME],
            # e.g. "Grey food caddy"
            model=f"{cfg.get(CONF_BIN_COLOUR, '')} {coordinator.container(bin_id)}"
            .replace("_", " ")
            .strip()
            .capitalize(),
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def bin_state(self) -> BinState:
        return self.coordinator.data[self.bin_id]
