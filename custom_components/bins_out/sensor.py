"""Sensors: per-bin next collection / days until / status, plus a summary sensor."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BIN_COLOURS,
    CONF_BIN_COLOUR,
    CONF_BIN_NAME,
    CONF_INTERVAL_WEEKS,
    CONF_SOURCE,
    DOMAIN,
    SOURCE_MANUAL,
    STATUSES,
)
from .coordinator import BinsOutConfigEntry, BinsOutCoordinator
from .entity import BinEntity, hub_device

# (platform, key) of every per-bin entity, so the summary can list entity_ids.
BIN_ENTITY_KEYS = {
    "next_collection": "sensor",
    "days_until": "sensor",
    "status": "sensor",
    "due": "binary_sensor",
    "forgotten": "binary_sensor",
    "put_out": "switch",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BinsOutConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [SummarySensor(coordinator)]
    for bin_id in coordinator.bins:
        entities += [
            NextCollectionSensor(coordinator, bin_id, "next_collection"),
            DaysUntilSensor(coordinator, bin_id, "days_until"),
            StatusSensor(coordinator, bin_id, "status"),
        ]
    async_add_entities(entities)


class NextCollectionSensor(BinEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self) -> date | None:
        return self.bin_state.next_collection

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "upcoming": [d.isoformat() for d in self.bin_state.upcoming],
            "estimated": [d.isoformat() for d in self.bin_state.estimated],
        }


class DaysUntilSensor(BinEntity, SensorEntity):
    _attr_native_unit_of_measurement = "d"
    _attr_icon = "mdi:calendar-clock"

    @property
    def native_value(self) -> int | None:
        return self.bin_state.days_until


class StatusSensor(BinEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    @property
    def native_value(self) -> str:
        return self.bin_state.status

    @property
    def icon(self) -> str:
        return {
            "tomorrow": "mdi:delete-alert",
            "today": "mdi:delete-alert",
            "forgotten": "mdi:delete-off",
            "out": "mdi:delete-circle",
            "collected": "mdi:delete-restore",
        }.get(self.bin_state.status, "mdi:delete")


class SummarySensor(CoordinatorEntity[BinsOutCoordinator], SensorEntity):
    """One entity carrying everything the dashboard card needs.

    State: days until the soonest collection of any bin.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "summary"
    _attr_native_unit_of_measurement = "d"
    _attr_icon = "mdi:delete-empty"
    # The bins list is large and changes often; keep it out of the recorder.
    _unrecorded_attributes = frozenset(
        {"bins", "tonight_message", "morning_message", "forgotten_message"}
    )

    def __init__(self, coordinator: BinsOutCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_summary"
        self._attr_device_info = hub_device(coordinator)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        registry = er.async_get(self.hass)

        @callback
        def _ours(data: er.EventEntityRegistryUpdatedData) -> bool:
            entry = registry.async_get(data["entity_id"])
            return entry is not None and entry.platform == DOMAIN

        @callback
        def _refresh(_event) -> None:
            self.async_write_ha_state()

        # Other platforms register after this one, and users can rename
        # entities; refresh the entity_ids we publish when that happens.
        self.async_on_remove(
            self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, _refresh, event_filter=_ours
            )
        )

    @property
    def native_value(self) -> int | None:
        days = [s.days_until for s in self.coordinator.data.values() if s.days_until is not None]
        return min(days, default=None)

    def _entity_ids(self, bin_id: str) -> dict[str, str | None]:
        registry = er.async_get(self.hass)
        prefix = f"{self.coordinator.config_entry.entry_id}_{bin_id}"
        return {
            key: registry.async_get_entity_id(platform, DOMAIN, f"{prefix}_{key}")
            for key, platform in BIN_ENTITY_KEYS.items()
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        coord = self.coordinator
        bins = []
        for bin_id, state in coord.data.items():
            cfg = coord.bins[bin_id]
            colour = cfg.get(CONF_BIN_COLOUR, "")
            bins.append(
                {
                    "id": bin_id,
                    "name": cfg[CONF_BIN_NAME],
                    "colour": colour,
                    "colour_hex": BIN_COLOURS.get(colour, "#8a8d91"),
                    "spoken_name": coord.spoken_name(bin_id),
                    "container": coord.container(bin_id),
                    "source": cfg.get(CONF_SOURCE, SOURCE_MANUAL),
                    "interval_weeks": int(cfg[CONF_INTERVAL_WEEKS])
                    if CONF_INTERVAL_WEEKS in cfg
                    else None,
                    "next_collection": state.next_collection.isoformat()
                    if state.next_collection
                    else None,
                    "days_until": state.days_until,
                    "status": state.status,
                    "put_out": state.put_out,
                    "due": state.due,
                    "forgotten": state.forgotten,
                    "upcoming": [d.isoformat() for d in state.upcoming],
                    "estimated": [d.isoformat() for d in state.estimated],
                    "repeat_weeks": coord.repeat_weeks(bin_id)
                    if coord.is_calendar(bin_id)
                    else None,
                    "moved": {
                        k.isoformat(): v.isoformat() for k, v in coord.moved(bin_id).items()
                    },
                    "cancelled": [d.isoformat() for d in coord.cancelled(bin_id)],
                    "entities": self._entity_ids(bin_id),
                }
            )
        bins.sort(key=lambda b: (b["days_until"] is None, b["days_until"], b["name"]))
        soonest = bins[0]["days_until"] if bins else None
        return {
            "bins": bins,
            "next_bins": [b["name"] for b in bins if b["days_until"] == soonest and soonest is not None],
            "evening_time": coord.evening_time.isoformat(),
            "morning_time": coord.morning_time.isoformat(),
            "collection_time": coord.collection_time.isoformat(),
            "tonight_message": coord.tonight_message(),
            "morning_message": coord.morning_message(),
            "forgotten_message": coord.forgotten_message(),
        }
