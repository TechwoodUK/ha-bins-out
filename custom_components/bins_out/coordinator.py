"""Coordinator: owns bin config, persisted state and reminder timers."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util, slugify

from .const import (
    ALEXA_DOMAIN,
    CALENDAR_LOOKAHEAD_DAYS,
    CALENDAR_REFRESH_MINUTES,
    CONF_ALEXA_DEVICES,
    CONF_ALEXA_ENABLED,
    CONF_ALEXA_MODE,
    CONF_ALEXA_REMINDERS,
    CONF_BIN_COLOUR,
    CONF_BIN_ID,
    CONF_BIN_NAME,
    CONF_BINS,
    CONF_CALENDAR_ENTITY,
    CONF_COLLECTION_TIME,
    CONF_CONTAINER,
    CONF_EVENING_TIME,
    CONF_FIRST_COLLECTION,
    CONF_INTERVAL_WEEKS,
    CONF_MATCH,
    CONF_MESSAGES,
    CONF_MORNING_TIME,
    CONF_PHONE_DEVICES,
    CONF_PHONE_ENABLED,
    CONF_PHONE_REMINDERS,
    CONF_REPEAT_WEEKS,
    CONF_SOURCE,
    CONTAINER_NOUNS,
    DEFAULT_COLLECTION_TIME,
    DEFAULT_EVENING_TIME,
    DEFAULT_MESSAGES,
    DEFAULT_MORNING_TIME,
    DOMAIN,
    EVENT_REMINDER,
    MOBILE_APP_DOMAIN,
    PANEL_ICON,
    PANEL_URL_PATH,
    PUT_OUT_ACTION,
    REMINDER_EVENING,
    REMINDER_FORGOTTEN,
    REMINDER_MORNING,
    REMINDERS,
    SOURCE_CALENDAR,
    STORAGE_VERSION,
    UPCOMING_COUNT,
)
from .schedule import (
    BinSchedule,
    BinState,
    compute_state,
    dates_from_events,
    guess_container,
    guess_repeat_weeks,
    learn_repeat_weeks,
    reminder_message,
    spoken_name,
    usual_weekday,
)

# Published dates remembered per calendar bin, to learn how far apart they are.
SEEN_DATES_KEPT = 12

_LOGGER = logging.getLogger(__name__)

type BinsOutConfigEntry = ConfigEntry[BinsOutCoordinator]


ISSUE_CALENDAR_MISSING = "calendar_missing"


def storage_key(entry_id: str) -> str:
    """Where an entry's put-out flags, moved dates and learned dates are saved."""
    return f"{DOMAIN}.{entry_id}"


def calendar_issue_prefix(entry_id: str) -> str:
    """Repairs issue ids for an entry's missing calendars start with this."""
    return f"{ISSUE_CALENDAR_MISSING}_{entry_id}_"


async def async_calendar_events(
    hass: HomeAssistant, entity_id: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    """Events on a HA calendar entity, via the public calendar.get_events action."""
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": entity_id, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    return response[entity_id]["events"]


class BinsOutCoordinator(DataUpdateCoordinator[dict[str, BinState]]):
    """Recomputes every bin's state once a minute."""

    config_entry: BinsOutConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BinsOutConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        opts = entry.options
        self.bins: dict[str, dict[str, Any]] = {
            b[CONF_BIN_ID]: b for b in opts.get(CONF_BINS, [])
        }
        self.evening_time = time.fromisoformat(
            opts.get(CONF_EVENING_TIME, DEFAULT_EVENING_TIME)
        )
        self.morning_time = time.fromisoformat(
            opts.get(CONF_MORNING_TIME, DEFAULT_MORNING_TIME)
        )
        self.collection_time = time.fromisoformat(
            opts.get(CONF_COLLECTION_TIME, DEFAULT_COLLECTION_TIME)
        )
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, storage_key(entry.entry_id)
        )
        self._put_out: dict[str, date] = {}
        self._moved: dict[str, dict[date, date]] = {}
        self._cancelled: dict[str, set[date]] = {}
        # Last dates read from each calendar-sourced bin's calendar. Persisted, so
        # an outage of the calendar (or the council website behind it) keeps them.
        self._calendar_dates: dict[str, tuple[date, ...]] = {}
        # Every published date seen per calendar bin, and the weeks between them.
        self._seen_dates: dict[str, list[date]] = {}
        self._learned_weeks: dict[str, int] = {}
        self._calendar_fetched: datetime | None = None
        self._calendar_warned: set[str] = set()

    # ---- persistence -------------------------------------------------------

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}

        def per_bin(key: str) -> dict[str, Any]:
            return {k: v for k, v in stored.get(key, {}).items() if k in self.bins}

        self._put_out = {k: date.fromisoformat(d) for k, d in per_bin("put_out").items()}
        self._moved = {
            k: {date.fromisoformat(a): date.fromisoformat(b) for a, b in m.items()}
            for k, m in per_bin("moved").items()
        }
        self._cancelled = {
            k: {date.fromisoformat(d) for d in ds} for k, ds in per_bin("cancelled").items()
        }
        self._calendar_dates = {
            k: tuple(date.fromisoformat(d) for d in ds)
            for k, ds in per_bin("calendar_dates").items()
        }
        self._seen_dates = {
            k: [date.fromisoformat(d) for d in ds] for k, ds in per_bin("seen_dates").items()
        }
        self._learned_weeks = {k: int(w) for k, w in per_bin("learned_weeks").items()}

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(
            lambda: {
                "put_out": {k: v.isoformat() for k, v in self._put_out.items()},
                "moved": {
                    bin_id: {k.isoformat(): v.isoformat() for k, v in m.items()}
                    for bin_id, m in self._moved.items()
                },
                "cancelled": {
                    k: sorted(d.isoformat() for d in ds) for k, ds in self._cancelled.items()
                },
                "calendar_dates": {
                    k: [d.isoformat() for d in ds] for k, ds in self._calendar_dates.items()
                },
                "seen_dates": {
                    k: [d.isoformat() for d in ds] for k, ds in self._seen_dates.items()
                },
                "learned_weeks": dict(self._learned_weeks),
            },
            1,
        )

    # ---- state -------------------------------------------------------------

    def is_calendar(self, bin_id: str) -> bool:
        return self.bins[bin_id].get(CONF_SOURCE) == SOURCE_CALENDAR

    def schedule(self, bin_id: str) -> BinSchedule:
        cfg = self.bins[bin_id]
        common = {
            "moved": self._moved.get(bin_id, {}),
            "cancelled": frozenset(self._cancelled.get(bin_id, ())),
        }
        if self.is_calendar(bin_id):
            published = self._calendar_dates.get(bin_id, ())
            return BinSchedule(
                fixed_dates=published,
                repeat_weeks=self.repeat_weeks(bin_id),
                usual_weekday=usual_weekday([*self._seen_dates.get(bin_id, ()), *published]),
                **common,
            )
        return BinSchedule(
            first_collection=date.fromisoformat(cfg[CONF_FIRST_COLLECTION]),
            interval_weeks=int(cfg[CONF_INTERVAL_WEEKS]),
            **common,
        )

    def repeat_weeks(self, bin_id: str) -> int | None:
        """Weeks between a calendar bin's collections: set by the user, learned, or guessed."""
        cfg = self.bins[bin_id]
        if weeks := int(cfg.get(CONF_REPEAT_WEEKS) or 0):
            return weeks
        return self._learned_weeks.get(bin_id) or guess_repeat_weeks(
            cfg[CONF_BIN_NAME], cfg.get(CONF_MATCH, "")
        )

    def moved(self, bin_id: str) -> dict[date, date]:
        return dict(self._moved.get(bin_id, {}))

    def cancelled(self, bin_id: str) -> list[date]:
        return sorted(self._cancelled.get(bin_id, ()))

    async def _async_refresh_calendars(self) -> None:
        """Re-read dates for calendar-sourced bins, at most every 30 minutes."""
        now = dt_util.now()
        if self._calendar_fetched and now - self._calendar_fetched < timedelta(
            minutes=CALENDAR_REFRESH_MINUTES
        ):
            return
        by_calendar: dict[str, list[str]] = {}
        for bin_id, cfg in self.bins.items():
            if self.is_calendar(bin_id):
                by_calendar.setdefault(cfg[CONF_CALENDAR_ENTITY], []).append(bin_id)
        if not by_calendar:
            self._sync_calendar_issues({})
            return

        all_ok = True
        missing: dict[str, list[str]] = {}
        start = dt_util.start_of_local_day(now) - timedelta(days=1)
        for entity_id, bin_ids in by_calendar.items():
            try:
                events = await async_calendar_events(
                    self.hass, entity_id, start, start + timedelta(days=CALENDAR_LOOKAHEAD_DAYS)
                )
            except (HomeAssistantError, KeyError) as err:
                # Usually the calendar's integration hasn't finished starting; retry next minute.
                # Only worth a warning if it still fails once HA has fully started.
                all_ok = False
                if self.hass.state is CoreState.running and entity_id not in self._calendar_warned:
                    self._calendar_warned.add(entity_id)
                    _LOGGER.warning("Can't read %s yet, using saved dates: %s", entity_id, err)
                # Gone altogether (e.g. the council was removed), not just unavailable.
                if self.hass.states.get(entity_id) is None:
                    missing[entity_id] = bin_ids
                continue
            self._calendar_warned.discard(entity_id)
            for bin_id in bin_ids:
                dates = dates_from_events(events, self.bins[bin_id].get(CONF_MATCH, ""))
                self._calendar_dates[bin_id] = dates
                seen = sorted({*self._seen_dates.get(bin_id, ()), *dates})[-SEEN_DATES_KEPT:]
                self._seen_dates[bin_id] = seen
                if weeks := learn_repeat_weeks(seen):
                    self._learned_weeks[bin_id] = weeks
        self._save()
        if all_ok:
            self._calendar_fetched = now
        # While HA starts, calendars appearing late is normal: leave notices as they are.
        if self.hass.state is CoreState.running:
            self._sync_calendar_issues(missing)

    @callback
    def _sync_calendar_issues(self, missing: dict[str, list[str]]) -> None:
        """Show a Repairs notice for each council calendar that's gone; clear the rest."""
        prefix = calendar_issue_prefix(self.config_entry.entry_id)
        for domain, issue_id in list(ir.async_get(self.hass).issues):
            if (
                domain == DOMAIN
                and issue_id.startswith(prefix)
                and issue_id.removeprefix(prefix) not in missing
            ):
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        for entity_id, bin_ids in missing.items():
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                prefix + entity_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_CALENDAR_MISSING,
                translation_placeholders={
                    "calendar": entity_id,
                    "bins": ", ".join(self.bins[b][CONF_BIN_NAME] for b in bin_ids),
                },
            )

    def container(self, bin_id: str) -> str:
        """Wheelie bin, food caddy, box or bag: as set, or guessed from the names."""
        cfg = self.bins[bin_id]
        return cfg.get(CONF_CONTAINER) or guess_container(
            cfg[CONF_BIN_NAME], cfg.get(CONF_MATCH, "")
        )

    def spoken_name(self, bin_id: str) -> str:
        cfg = self.bins[bin_id]
        return spoken_name(
            cfg[CONF_BIN_NAME],
            cfg.get(CONF_BIN_COLOUR, ""),
            CONTAINER_NOUNS.get(self.container(bin_id), "bin"),
        )

    @callback
    def _compute(self) -> dict[str, BinState]:
        now = dt_util.now()
        today = now.date()
        if stale := [k for k, d in self._put_out.items() if d < today]:
            for k in stale:
                del self._put_out[k]
            self._save()
        return {
            bin_id: compute_state(
                self.schedule(bin_id),
                now,
                self._put_out.get(bin_id),
                self.evening_time,
                self.collection_time,
                UPCOMING_COUNT,
            )
            for bin_id in self.bins
        }

    async def _async_update_data(self) -> dict[str, BinState]:
        await self._async_refresh_calendars()
        return self._compute()

    @callback
    def _push(self) -> None:
        self.async_set_updated_data(self._compute())

    # ---- announcements -----------------------------------------------------

    def reminder_bins(self, kind: str) -> list[str]:
        """Ids of the bins a reminder is about right now."""
        due = {
            REMINDER_EVENING: lambda s: s.days_until == 1 and not s.put_out,
            REMINDER_MORNING: lambda s: s.days_until == 0 and not s.put_out,
            REMINDER_FORGOTTEN: lambda s: s.forgotten,
        }[kind]
        return [b for b, s in (self.data or {}).items() if due(s)]

    def message_template(self, kind: str) -> str:
        """A reminder's wording: your own from Configure, or the default."""
        return self.config_entry.options.get(CONF_MESSAGES[kind]) or DEFAULT_MESSAGES[kind]

    def message_for(self, kind: str, bin_ids: list[str] | None = None) -> str | None:
        if bin_ids is None:
            bin_ids = self.reminder_bins(kind)
        return reminder_message(
            self.message_template(kind), [self.spoken_name(b) for b in bin_ids]
        )

    def tonight_message(self) -> str | None:
        return self.message_for(REMINDER_EVENING)

    def morning_message(self) -> str | None:
        return self.message_for(REMINDER_MORNING)

    def forgotten_message(self) -> str | None:
        return self.message_for(REMINDER_FORGOTTEN)

    @callback
    def _announce_on_alexa(self, kind: str, message: str) -> None:
        """Speak a reminder on Alexa, if that's switched on in Configure."""
        opts = self.config_entry.options
        if not opts.get(CONF_ALEXA_ENABLED):
            return
        if kind not in opts.get(CONF_ALEXA_REMINDERS, REMINDERS):
            return
        if not (devices := opts.get(CONF_ALEXA_DEVICES)):
            return
        if not self.hass.services.has_service("notify", ALEXA_DOMAIN):
            _LOGGER.warning(
                "Alexa announcements are on, but Alexa Media Player isn't set up: %s", message
            )
            return
        self.config_entry.async_create_background_task(
            self.hass,
            self.async_announce(message, devices, opts.get(CONF_ALEXA_MODE, "announce")),
            "bins_out_alexa",
        )

    async def async_announce(self, message: str, devices: list[str], mode: str) -> bool:
        """Speak `message` on these Echo devices. False if Alexa Media Player failed."""
        try:
            await self.hass.services.async_call(
                "notify",
                ALEXA_DOMAIN,
                {"target": devices, "message": message, "data": {"type": mode}},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Couldn't announce on Alexa: %s", err)
            return False
        return True

    def phone_services(self, device_ids: list[str]) -> list[str]:
        """notify services of these phones (Home Assistant app), e.g. "mobile_app_ste_s_iphone"."""
        devices = dr.async_get(self.hass)
        services = []
        for device_id in device_ids:
            if (device := devices.async_get(device_id)) is None:
                continue
            entry = self.hass.config_entries.async_get_entry(device.config_entry_id)
            if entry and entry.domain == MOBILE_APP_DOMAIN:
                service = slugify(f"{MOBILE_APP_DOMAIN}_{entry.data['device_name']}")
                if self.hass.services.has_service("notify", service):
                    services.append(service)
        return services

    @callback
    def _notify_phones(self, kind: str, message: str, bin_ids: list[str]) -> None:
        """Pop a reminder up on phones, if that's switched on in Configure."""
        opts = self.config_entry.options
        if not opts.get(CONF_PHONE_ENABLED):
            return
        if kind not in opts.get(CONF_PHONE_REMINDERS, REMINDERS):
            return
        services = self.phone_services(opts.get(CONF_PHONE_DEVICES) or [])
        if not services:
            _LOGGER.warning("Phone notifications are on, but no phone could be reached: %s", message)
            return
        # Nothing to put out once it's been collected.
        put_out = bin_ids if kind != REMINDER_FORGOTTEN else []
        self.config_entry.async_create_background_task(
            self.hass, self.async_notify_phones(message, services, put_out), "bins_out_phones"
        )

    async def async_notify_phones(
        self, message: str, services: list[str], put_out: list[str] | None = None
    ) -> bool:
        """Send `message` to these phones. With `put_out`, add an "It's out" button for them."""
        data: dict[str, Any] = {
            "tag": DOMAIN,  # a newer reminder replaces the last one
            "url": f"/{PANEL_URL_PATH}",  # tap to open the Bins page (iPhone)
            "clickAction": f"/{PANEL_URL_PATH}",  # (Android)
            "notification_icon": PANEL_ICON,
            # Android: pop up and vibrate, on a channel of its own.
            "channel": "Bins Out",
            "importance": "high",
            "priority": "high",
            "ttl": 0,
            "vibrationPattern": "0, 600, 300, 600, 300, 600",  # three firm buzzes
            # iPhone: sound and vibration, even in a Focus that allows time-sensitive alerts.
            "push": {"sound": "default", "interruption-level": "time-sensitive"},
        }
        if put_out:
            data["actions"] = [
                {"action": f"{PUT_OUT_ACTION}:{','.join(put_out)}", "title": "It's out"}
            ]
        ok = True
        for service in services:
            try:
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {"title": "Bins Out", "message": message, "data": data},
                    blocking=True,
                )
            except HomeAssistantError as err:
                _LOGGER.warning("Couldn't send the reminder to %s: %s", service, err)
                ok = False
        return ok

    @callback
    def async_put_out_from_phone(self, action: str) -> None:
        """The notification's "It's out" button: mark those bins out, if still due."""
        prefix = f"{PUT_OUT_ACTION}:"
        if not action.startswith(prefix):
            return
        data = self.data or {}
        for bin_id in action.removeprefix(prefix).split(","):
            state = data.get(bin_id)
            if state is not None and state.days_until in (0, 1) and not state.put_out:
                self.set_put_out(bin_id, True)

    @callback
    def async_setup_reminders(self) -> None:
        """Fire `bins_out_reminder` events at the configured times."""

        def make(kind: str):
            @callback
            def _fire(_now) -> None:
                self._push()
                bin_ids = self.reminder_bins(kind)
                if message := self.message_for(kind, bin_ids):
                    self.hass.bus.async_fire(
                        EVENT_REMINDER, {"type": kind, "message": message}
                    )
                    self._announce_on_alexa(kind, message)
                    self._notify_phones(kind, message, bin_ids)

            return _fire

        for kind, at in (
            (REMINDER_EVENING, self.evening_time),
            (REMINDER_MORNING, self.morning_time),
            (REMINDER_FORGOTTEN, self.collection_time),
        ):
            self.config_entry.async_on_unload(
                async_track_time_change(
                    self.hass,
                    make(kind),
                    hour=at.hour,
                    minute=at.minute,
                    second=at.second,
                )
            )

    # ---- actions -----------------------------------------------------------

    def resolve_bin(self, ref: str) -> str:
        """Find a bin by id or (case-insensitive) name."""
        if ref in self.bins:
            return ref
        for bin_id, cfg in self.bins.items():
            if cfg[CONF_BIN_NAME].strip().lower() == ref.strip().lower():
                return bin_id
        raise ServiceValidationError(f"No bin called '{ref}'")

    @callback
    def set_put_out(self, bin_id: str, put_out: bool) -> None:
        if put_out:
            nxt = self.schedule(bin_id).next_collection(dt_util.now().date())
            if nxt is None:
                raise ServiceValidationError("This bin has no upcoming collection")
            self._put_out[bin_id] = nxt
        else:
            self._put_out.pop(bin_id, None)
        self._save()
        self._push()

    @callback
    def move_collection(self, bin_id: str, original: date, new: date) -> None:
        self._moved.setdefault(bin_id, {})[original] = new
        self._save()
        self._push()

    @callback
    def clear_moved(self, bin_id: str) -> None:
        self._moved.pop(bin_id, None)
        self._save()
        self._push()

    @callback
    def cancel_collection(self, bin_id: str, day: date) -> None:
        self._cancelled.setdefault(bin_id, set()).add(day)
        if self._put_out.get(bin_id) == day:
            del self._put_out[bin_id]
        self._save()
        self._push()

    @callback
    def restore_collection(self, bin_id: str, day: date) -> None:
        if day not in self._cancelled.get(bin_id, set()):
            raise ServiceValidationError(f"{day.isoformat()} isn't cancelled for this bin")
        self._cancelled[bin_id].discard(day)
        self._save()
        self._push()
