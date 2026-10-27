"""Calendar of all bin collections."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_BIN_NAME
from .coordinator import BinsOutConfigEntry, BinsOutCoordinator
from .entity import hub_device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BinsOutConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([BinsCalendar(entry.runtime_data)])


class BinsCalendar(CoordinatorEntity[BinsOutCoordinator], CalendarEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "collections"

    def __init__(self, coordinator: BinsOutCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_calendar"
        self._attr_device_info = hub_device(coordinator)

    def _events(self, start, end) -> list[CalendarEvent]:
        events = []
        for bin_id, cfg in self.coordinator.bins.items():
            original = {v: k for k, v in self.coordinator.moved(bin_id).items()}
            schedule = self.coordinator.schedule(bin_id)
            for day in schedule.estimated(start, end):
                events.append(
                    CalendarEvent(
                        start=day,
                        end=day + timedelta(days=1),
                        summary=f"{cfg[CONF_BIN_NAME]} (estimated)",
                        description=(
                            f"Probably: the {self.coordinator.spoken_name(bin_id)}. "
                            "The council hasn't published this date yet."
                        ),
                        uid=f"{bin_id}_{day.isoformat()}_estimated",
                    )
                )
            for day in schedule.collections(start, end):
                description = f"Put the {self.coordinator.spoken_name(bin_id)} out."
                if day in original:
                    description += f" Moved from {original[day].strftime('%A %d %B')}."
                events.append(
                    CalendarEvent(
                        start=day,
                        end=day + timedelta(days=1),
                        summary=cfg[CONF_BIN_NAME],
                        description=description,
                        uid=f"{bin_id}_{day.isoformat()}",
                    )
                )
        events.sort(key=lambda e: (e.start, e.summary))
        return events

    @property
    def event(self) -> CalendarEvent | None:
        today = dt_util.now().date()
        upcoming = self._events(today, today + timedelta(days=62))
        return upcoming[0] if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start = dt_util.as_local(start_date).date()
        # end_date is exclusive.
        end = (dt_util.as_local(end_date) - timedelta(microseconds=1)).date()
        return self._events(start, end)
