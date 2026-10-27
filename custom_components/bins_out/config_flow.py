"""Config and options flows for Bins Out."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.loader import IntegrationNotFound, async_get_integration
from homeassistant.util import dt as dt_util

from .const import (
    ALEXA_DOMAIN,
    ALEXA_MODES,
    BIN_COLOURS,
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
    MOBILE_APP_DOMAIN,
    REMINDER_EVENING,
    REMINDERS,
    SOURCE_CALENDAR,
    SOURCE_MANUAL,
)
from .coordinator import async_calendar_events
from .schedule import dates_from_events, guess_colour, reminder_message

CONF_SELECTED_BIN = "selected_bin"
CONF_COLLECTIONS = "collections"
MATCH_LOOKAHEAD_DAYS = 90
WCS_DOMAIN = "waste_collection_schedule"
# Links shown on the council screens (kept out of the translations).
COUNCIL_LINKS = {
    "add_council_url": f"/config/integrations/dashboard/add?domain={WCS_DOMAIN}",
    "hacs_url": (
        "https://my.home-assistant.io/redirect/hacs_repository/"
        "?owner=mampfes&repository=hacs_waste_collection_schedule&category=integration"
    ),
    "uprn_url": "https://www.findmyaddress.co.uk",
}
ALEXA_LINKS = {
    "alexa_hacs_url": (
        "https://my.home-assistant.io/redirect/hacs_repository/"
        "?owner=alandtse&repository=alexa_media_player&category=integration"
    ),
}
CONF_ALEXA_TEST = "alexa_test"  # not saved: send a test announcement on save
CONF_PHONE_TEST = "phone_test"  # not saved: send a test notification on save
PHONE_TEST_MESSAGE = "This is Bins Out. Your bin reminders will pop up here."
CONF_MESSAGE_TRY = "message_try"  # not saved: say the evening reminder on Alexa on save
ALEXA_TEST_MESSAGE = "This is Bins Out. Your bin reminders will be announced here."


def _settings_schema(current: dict[str, Any]) -> vol.Schema:
    time = selector.TimeSelector()
    return vol.Schema(
        {
            vol.Required(
                CONF_EVENING_TIME, default=current.get(CONF_EVENING_TIME, DEFAULT_EVENING_TIME)
            ): time,
            vol.Required(
                CONF_MORNING_TIME, default=current.get(CONF_MORNING_TIME, DEFAULT_MORNING_TIME)
            ): time,
            vol.Required(
                CONF_COLLECTION_TIME,
                default=current.get(CONF_COLLECTION_TIME, DEFAULT_COLLECTION_TIME),
            ): time,
        }
    )


def _repeat_field(default: int) -> dict:
    """'Usually collected every N weeks' for council bins (0 = work it out)."""
    return {
        vol.Optional(CONF_REPEAT_WEEKS, default=default): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=8, step=1, mode=selector.NumberSelectorMode.BOX)
        )
    }


def _name_taken(bins: list[dict[str, Any]], name: str, except_id: str | None = None) -> bool:
    return any(
        b[CONF_BIN_NAME].lower() == name.strip().lower() and b[CONF_BIN_ID] != except_id
        for b in bins
    )


class BinStepsMixin:
    """Steps for adding or editing one bin, shared by the config and options flows.

    bin (name, colour, where dates come from)
      -> bin_manual (a collection date + every N weeks)
      -> bin_calendar (which calendar) -> bin_match (which events on it)
    then `_async_bin_done(bin)`.

    Or, for a council calendar (e.g. Waste Collection Schedule), all at once:
    council_pick (which calendar) -> council_bins (which collections are yours)
    then `_async_bins_added(bins)`, one bin per kind of collection. With no calendar
    to pick yet, `council` explains how to get one instead of showing an empty list.
    """

    _draft: dict[str, Any]
    _edit_id: str | None = None
    _council_calendar: str

    def _existing_bins(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def _async_bin_done(self, bin_cfg: dict[str, Any]) -> ConfigFlowResult:
        raise NotImplementedError

    async def _async_bins_added(self, bins: list[dict[str, Any]]) -> ConfigFlowResult:
        raise NotImplementedError

    def _current(self) -> dict[str, Any]:
        return next(
            (b for b in self._existing_bins() if b[CONF_BIN_ID] == self._edit_id), {}
        )

    async def _async_event_names(self, entity_id: str) -> tuple[list[dict[str, Any]], list[str]]:
        """Events on a calendar over the next few months, and their distinct names."""
        start = dt_util.start_of_local_day()
        try:
            events = await async_calendar_events(
                self.hass, entity_id, start, start + timedelta(days=MATCH_LOOKAHEAD_DAYS)
            )
        except (HomeAssistantError, KeyError):
            events = []
        return events, sorted({str(e.get("summary", "")) for e in events} - {""})

    def _unlinked(self, entity_id: str, names: list[str]) -> list[str]:
        """Event names on this calendar that no bin follows yet."""
        matches = [
            b[CONF_MATCH].strip().lower()
            for b in self._existing_bins()
            if b.get(CONF_CALENDAR_ENTITY) == entity_id and b.get(CONF_MATCH)
        ]
        return [n for n in names if not any(m in n.lower() for m in matches)]

    def _free_name(self, name: str, extra: list[dict[str, Any]]) -> str:
        """`name`, or `name 2`, `name 3`... if a bin already has it."""
        bins = [*self._existing_bins(), *extra]
        candidate, n = name, 2
        while _name_taken(bins, candidate):
            candidate, n = f"{name} {n}", n + 1
        return candidate

    def _own_calendars(self) -> list[str]:
        return [
            e.entity_id
            for e in er.async_get(self.hass).entities.values()
            if e.platform == DOMAIN and e.domain == "calendar"
        ]

    async def async_step_council(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a council calendar, or explain how to get one if there are none."""
        own = self._own_calendars()
        if any(s.entity_id not in own for s in self.hass.states.async_all("calendar")):
            return await self.async_step_council_pick()
        try:
            await async_get_integration(self.hass, WCS_DOMAIN)
        except IntegrationNotFound:
            step_id = "council_install"
        else:
            step_id = "council_add"
        # "council" checks again once they've added their council.
        return self.async_show_menu(
            step_id=step_id,
            menu_options=["council", "bin"],
            description_placeholders=COUNCIL_LINKS,
        )

    # Menus only; HA needs a step for each screen id.
    async_step_council_install = async_step_council
    async_step_council_add = async_step_council

    async def async_step_council_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = user_input[CONF_CALENDAR_ENTITY]
            _, names = await self._async_event_names(entity_id)
            if not names:
                errors[CONF_CALENDAR_ENTITY] = "no_events"
            elif not self._unlinked(entity_id, names):
                errors[CONF_CALENDAR_ENTITY] = "all_linked"
            else:
                self._council_calendar = entity_id
                return await self.async_step_council_bins()
        # Start empty so people pick their own council; keep their pick after an error.
        default = (user_input or {}).get(CONF_CALENDAR_ENTITY, vol.UNDEFINED)
        # Our own collections calendar is never a council's.
        schema = vol.Schema(
            {
                vol.Required(CONF_CALENDAR_ENTITY, default=default): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="calendar", exclude_entities=self._own_calendars()
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="council_pick",
            data_schema=schema,
            errors=errors,
            description_placeholders=COUNCIL_LINKS,
        )

    async def async_step_council_bins(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entity_id = self._council_calendar
        _, names = await self._async_event_names(entity_id)
        names = self._unlinked(entity_id, names)
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_COLLECTIONS]:
                errors[CONF_COLLECTIONS] = "none_selected"
            else:
                bins: list[dict[str, Any]] = []
                for match in user_input[CONF_COLLECTIONS]:
                    taken = {b[CONF_BIN_COLOUR] for b in [*self._existing_bins(), *bins]}
                    bins.append(
                        {
                            CONF_BIN_ID: uuid4().hex[:8],
                            CONF_BIN_NAME: self._free_name(match, bins),
                            CONF_BIN_COLOUR: guess_colour(match, taken),
                            CONF_SOURCE: SOURCE_CALENDAR,
                            CONF_CALENDAR_ENTITY: entity_id,
                            CONF_MATCH: match,
                        }
                    )
                return await self._async_bins_added(bins)
        schema = vol.Schema(
            {
                vol.Required(CONF_COLLECTIONS, default=names): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=names, multiple=True, mode=selector.SelectSelectorMode.LIST
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="council_bins",
            data_schema=schema,
            errors=errors,
            description_placeholders={"calendar": entity_id},
        )

    async def async_step_bin(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = self._current()
        if user_input is not None:
            if _name_taken(self._existing_bins(), user_input[CONF_BIN_NAME], self._edit_id):
                errors[CONF_BIN_NAME] = "name_taken"
            else:
                self._draft = {
                    CONF_BIN_ID: self._edit_id or uuid4().hex[:8],
                    CONF_BIN_NAME: user_input[CONF_BIN_NAME].strip(),
                    CONF_BIN_COLOUR: user_input[CONF_BIN_COLOUR],
                    CONF_SOURCE: user_input[CONF_SOURCE],
                }
                # Left blank: guessed from the name (e.g. "Food" -> food caddy).
                if user_input.get(CONF_CONTAINER):
                    self._draft[CONF_CONTAINER] = user_input[CONF_CONTAINER]
                if CONF_REPEAT_WEEKS in user_input:
                    self._draft[CONF_REPEAT_WEEKS] = int(user_input[CONF_REPEAT_WEEKS] or 0)
                if user_input[CONF_SOURCE] == SOURCE_CALENDAR:
                    return await self.async_step_bin_calendar()
                return await self.async_step_bin_manual()
        defaults = user_input or current
        schema = vol.Schema(
            {
                vol.Required(CONF_BIN_NAME, default=defaults.get(CONF_BIN_NAME, vol.UNDEFINED)): (
                    selector.TextSelector()
                ),
                vol.Required(CONF_BIN_COLOUR, default=defaults.get(CONF_BIN_COLOUR, "black")): (
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(BIN_COLOURS),
                            translation_key="colour",
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                ),
                vol.Optional(
                    CONF_CONTAINER, default=defaults.get(CONF_CONTAINER, vol.UNDEFINED)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(CONTAINER_NOUNS),
                        translation_key="container",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_SOURCE, default=defaults.get(CONF_SOURCE, SOURCE_MANUAL)): (
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[SOURCE_MANUAL, SOURCE_CALENDAR],
                            translation_key="source",
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                ),
            }
        )
        # Editing a council bin: offer how often it's collected right here, where it's easy to find.
        if current.get(CONF_SOURCE) == SOURCE_CALENDAR:
            schema = schema.extend(_repeat_field(defaults.get(CONF_REPEAT_WEEKS, 0)))
        return self.async_show_form(step_id="bin", data_schema=schema, errors=errors)

    async def async_step_bin_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None and CONF_FIRST_COLLECTION in user_input:
            return await self._async_bin_done(
                {
                    **self._draft,
                    CONF_FIRST_COLLECTION: user_input[CONF_FIRST_COLLECTION],
                    CONF_INTERVAL_WEEKS: int(user_input[CONF_INTERVAL_WEEKS]),
                }
            )
        current = self._current()
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_FIRST_COLLECTION, default=current.get(CONF_FIRST_COLLECTION, vol.UNDEFINED)
                ): selector.DateSelector(),
                vol.Required(CONF_INTERVAL_WEEKS, default=current.get(CONF_INTERVAL_WEEKS, 1)): (
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=8, step=1, mode=selector.NumberSelectorMode.BOX
                        )
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="bin_manual",
            data_schema=schema,
            description_placeholders={"name": self._draft[CONF_BIN_NAME]},
        )

    async def async_step_bin_calendar(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None and CONF_CALENDAR_ENTITY in user_input:
            self._draft[CONF_CALENDAR_ENTITY] = user_input[CONF_CALENDAR_ENTITY]
            return await self.async_step_bin_match()
        current = self._current()
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CALENDAR_ENTITY, default=current.get(CONF_CALENDAR_ENTITY, vol.UNDEFINED)
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="calendar")),
            }
        )
        return self.async_show_form(
            step_id="bin_calendar",
            data_schema=schema,
            description_placeholders={"name": self._draft[CONF_BIN_NAME]},
        )

    async def async_step_bin_match(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entity_id = self._draft[CONF_CALENDAR_ENTITY]
        events, summaries = await self._async_event_names(entity_id)

        errors: dict[str, str] = {}
        if user_input is not None:
            match = user_input[CONF_MATCH].strip()
            # An empty calendar is allowed (e.g. a garden bin paused for winter).
            if not match:
                errors[CONF_MATCH] = "no_match"
            elif events and not dates_from_events(events, match):
                errors[CONF_MATCH] = "no_match"
            else:
                # Set on the first screen when editing, or on this one for a new bin.
                weeks = int({**self._draft, **user_input}.get(CONF_REPEAT_WEEKS) or 0)
                bin_cfg = {k: v for k, v in self._draft.items() if k != CONF_REPEAT_WEEKS}
                bin_cfg[CONF_MATCH] = match
                # 0 = work it out from the council's dates.
                if weeks:
                    bin_cfg[CONF_REPEAT_WEEKS] = weeks
                return await self._async_bin_done(bin_cfg)

        name = self._draft[CONF_BIN_NAME].lower()
        colour = self._draft[CONF_BIN_COLOUR]
        suggested = self._current().get(CONF_MATCH) or next(
            (s for s in summaries if name in s.lower() or colour in s.lower()), vol.UNDEFINED
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_MATCH, default=suggested): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=summaries,
                        custom_value=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        # Already asked on the first screen when editing a council bin.
        if CONF_REPEAT_WEEKS not in self._draft:
            schema = schema.extend(_repeat_field(self._current().get(CONF_REPEAT_WEEKS, 0)))
        return self.async_show_form(
            step_id="bin_match",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "name": self._draft[CONF_BIN_NAME],
                "calendar": entity_id,
                "found": ", ".join(summaries) if summaries else "none in the next 90 days",
            },
        )


class BinsOutConfigFlow(BinStepsMixin, ConfigFlow, domain=DOMAIN):
    """Set reminder times, then add bins one by one."""

    VERSION = 1

    def __init__(self) -> None:
        self._options: dict[str, Any] = {CONF_BINS: []}

    def _existing_bins(self) -> list[dict[str, Any]]:
        return self._options[CONF_BINS]

    async def _async_bin_done(self, bin_cfg: dict[str, Any]) -> ConfigFlowResult:
        self._options[CONF_BINS].append(bin_cfg)
        return await self.async_step_more()

    async def _async_bins_added(self, bins: list[dict[str, Any]]) -> ConfigFlowResult:
        self._options[CONF_BINS].extend(bins)
        return await self.async_step_more()

    async def async_step_start(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="start", menu_options=["council", "bin"])

    async def async_step_more(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="more", menu_options=["bin", "council", "finish"])

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_start()
        return self.async_show_form(step_id="user", data_schema=_settings_schema({}))

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(title="Bins Out", data={}, options=self._options)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> BinsOutOptionsFlow:
        return BinsOutOptionsFlow()


class BinsOutOptionsFlow(BinStepsMixin, OptionsFlow):
    """Change times, add / edit / remove bins."""

    # Alexa or phone settings waiting while you check the test arrived.
    _tested_settings: dict[str, Any] | None = None

    def _existing_bins(self) -> list[dict[str, Any]]:
        return list(self.config_entry.options.get(CONF_BINS, []))

    async def _async_bin_done(self, bin_cfg: dict[str, Any]) -> ConfigFlowResult:
        bins = self._existing_bins()
        if self._edit_id:
            bins = [bin_cfg if b[CONF_BIN_ID] == self._edit_id else b for b in bins]
        else:
            bins.append(bin_cfg)
        return self._save(**{CONF_BINS: bins})

    async def _async_bins_added(self, bins: list[dict[str, Any]]) -> ConfigFlowResult:
        return self._save(**{CONF_BINS: [*self._existing_bins(), *bins]})

    def _save(self, **changes: Any) -> ConfigFlowResult:
        return self.async_create_entry(data={**self.config_entry.options, **changes})

    def _bin_choices(self) -> selector.SelectSelector:
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=b[CONF_BIN_ID], label=b[CONF_BIN_NAME])
                    for b in self._existing_bins()
                ]
            )
        )

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        menu = ["settings", "alexa", "phones", "messages", "council", "bin"]
        if self._existing_bins():
            menu += ["edit_bin", "remove_bin"]
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(**user_input)
        return self.async_show_form(
            step_id="settings", data_schema=_settings_schema(dict(self.config_entry.options))
        )

    async def async_step_alexa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Switch Alexa announcements of the reminders on or off."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.options, **(self._tested_settings or {}), **(user_input or {})}
        if user_input is not None:
            settings = {k: v for k, v in user_input.items() if k != CONF_ALEXA_TEST}
            devices = settings.get(CONF_ALEXA_DEVICES) or []
            wants_alexa = settings[CONF_ALEXA_ENABLED] or user_input.get(CONF_ALEXA_TEST)
            if wants_alexa:
                try:
                    await async_get_integration(self.hass, ALEXA_DOMAIN)
                except IntegrationNotFound:
                    errors["base"] = "alexa_not_installed"
                else:
                    if not devices:
                        errors[CONF_ALEXA_DEVICES] = "alexa_no_devices"
            if not errors and user_input.get(CONF_ALEXA_TEST):
                if await self._async_alexa_test(settings):
                    return self._tested("alexa", settings)
                errors["base"] = "alexa_test_failed"
            if not errors:
                return self._save(**settings)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ALEXA_ENABLED, default=current.get(CONF_ALEXA_ENABLED, False)
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_ALEXA_DEVICES, default=current.get(CONF_ALEXA_DEVICES, [])
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="media_player", integration=ALEXA_DOMAIN, multiple=True
                    )
                ),
                vol.Required(
                    CONF_ALEXA_MODE, default=current.get(CONF_ALEXA_MODE, "announce")
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=ALEXA_MODES,
                        translation_key="alexa_mode",
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(
                    CONF_ALEXA_REMINDERS, default=current.get(CONF_ALEXA_REMINDERS, REMINDERS)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=REMINDERS,
                        translation_key="alexa_reminders",
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(CONF_ALEXA_TEST, default=False): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="alexa",
            data_schema=schema,
            errors=errors,
            description_placeholders=ALEXA_LINKS,
        )

    async def async_step_phones(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pop the reminders up on phones with the Home Assistant app."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.options, **(self._tested_settings or {}), **(user_input or {})}
        if user_input is not None:
            settings = {k: v for k, v in user_input.items() if k != CONF_PHONE_TEST}
            services = self.config_entry.runtime_data.phone_services(
                settings.get(CONF_PHONE_DEVICES) or []
            )
            if (settings[CONF_PHONE_ENABLED] or user_input.get(CONF_PHONE_TEST)) and not services:
                errors[CONF_PHONE_DEVICES] = "phone_none"
            if not errors and user_input.get(CONF_PHONE_TEST):
                if await self._async_phone_test(settings):
                    return self._tested("phones", settings)
                errors["base"] = "phone_test_failed"
            if not errors:
                return self._save(**settings)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PHONE_ENABLED, default=current.get(CONF_PHONE_ENABLED, False)
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_PHONE_DEVICES, default=current.get(CONF_PHONE_DEVICES, [])
                ): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration=MOBILE_APP_DOMAIN, multiple=True)
                ),
                vol.Required(
                    CONF_PHONE_REMINDERS, default=current.get(CONF_PHONE_REMINDERS, REMINDERS)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=REMINDERS,
                        translation_key="phone_reminders",
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(CONF_PHONE_TEST, default=False): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="phones",
            data_schema=schema,
            errors=errors,
            description_placeholders={"app_url": "https://companion.home-assistant.io/"},
        )

    # ---- "Did it arrive?" after a test announcement or notification ----------

    def _tested(self, step: str, settings: dict[str, Any]) -> ConfigFlowResult:
        """Ask if the test arrived; keep the settings until they say save."""
        self._tested_settings = settings
        return self.async_show_menu(
            step_id=f"{step}_tested", menu_options=[f"{step}_save", f"{step}_again", step]
        )

    async def _async_alexa_test(self, settings: dict[str, Any]) -> bool:
        return await self.config_entry.runtime_data.async_announce(
            ALEXA_TEST_MESSAGE,
            settings.get(CONF_ALEXA_DEVICES) or [],
            settings.get(CONF_ALEXA_MODE, "announce"),
        )

    async def _async_phone_test(self, settings: dict[str, Any]) -> bool:
        coordinator = self.config_entry.runtime_data
        services = coordinator.phone_services(settings.get(CONF_PHONE_DEVICES) or [])
        return bool(services) and await coordinator.async_notify_phones(
            PHONE_TEST_MESSAGE, services
        )

    async def async_step_alexa_save(self, user_input: Any = None) -> ConfigFlowResult:
        return self._save(**(self._tested_settings or {}))

    async def async_step_alexa_again(self, user_input: Any = None) -> ConfigFlowResult:
        if await self._async_alexa_test(self._tested_settings or {}):
            return self._tested("alexa", self._tested_settings or {})
        return await self.async_step_alexa()

    async def async_step_phones_save(self, user_input: Any = None) -> ConfigFlowResult:
        return self._save(**(self._tested_settings or {}))

    async def async_step_phones_again(self, user_input: Any = None) -> ConfigFlowResult:
        if await self._async_phone_test(self._tested_settings or {}):
            return self._tested("phones", self._tested_settings or {})
        return await self.async_step_phones()

    # Menus only; HA needs a step for each screen id.
    async_step_alexa_tested = async_step_alexa
    async_step_phones_tested = async_step_phones

    async def async_step_messages(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Your own wording for each reminder."""
        errors: dict[str, str] = {}
        opts = self.config_entry.options
        if user_input is not None:
            # An empty box, or the default wording, is saved as "not set".
            custom = {
                key: text
                for kind, key in CONF_MESSAGES.items()
                if (text := (user_input.get(key) or "").strip())
                and text != DEFAULT_MESSAGES[kind]
            }
            if user_input.get(CONF_MESSAGE_TRY):
                devices = opts.get(CONF_ALEXA_DEVICES) or []
                if not (opts.get(CONF_ALEXA_ENABLED) and devices):
                    errors["base"] = "alexa_off"
                else:
                    coordinator = self.config_entry.runtime_data
                    template = custom.get(CONF_MESSAGES[REMINDER_EVENING]) or DEFAULT_MESSAGES[
                        REMINDER_EVENING
                    ]
                    names = [coordinator.spoken_name(b) for b in list(coordinator.bins)[:2]]
                    example = reminder_message(template, names or ["blue bin"])
                    if not await coordinator.async_announce(
                        example, devices, opts.get(CONF_ALEXA_MODE, "announce")
                    ):
                        errors["base"] = "alexa_test_failed"
            if not errors:
                kept = {k: v for k, v in opts.items() if k not in CONF_MESSAGES.values()}
                return self.async_create_entry(data={**kept, **custom})
        current = user_input or opts
        schema = vol.Schema(
            {
                **{
                    vol.Optional(
                        key,
                        description={
                            "suggested_value": current.get(key) or DEFAULT_MESSAGES[kind]
                        },
                    ): selector.TextSelector(selector.TextSelectorConfig(multiline=True))
                    for kind, key in CONF_MESSAGES.items()
                },
                vol.Optional(CONF_MESSAGE_TRY, default=False): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="messages",
            data_schema=schema,
            errors=errors,
            # Shown as-is, so the description can mention them.
            description_placeholders={"bins": "{bins}", "was": "{was}"},
        )

    async def async_step_edit_bin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._edit_id = user_input[CONF_SELECTED_BIN]
            return await self.async_step_bin()
        return self.async_show_form(
            step_id="edit_bin",
            data_schema=vol.Schema({vol.Required(CONF_SELECTED_BIN): self._bin_choices()}),
        )

    async def async_step_remove_bin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            remove = user_input[CONF_SELECTED_BIN]
            return self._save(
                **{CONF_BINS: [b for b in self._existing_bins() if b[CONF_BIN_ID] != remove]}
            )
        return self.async_show_form(
            step_id="remove_bin",
            data_schema=vol.Schema({vol.Required(CONF_SELECTED_BIN): self._bin_choices()}),
        )
