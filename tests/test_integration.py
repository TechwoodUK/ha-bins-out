"""Integration tests running inside a real Home Assistant instance."""

from datetime import date, datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
    mock_integration,
    mock_platform,
)

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.bins_out.const import DOMAIN, EVENT_REMINDER

OPTIONS = {
    "evening_time": "19:00:00",
    "morning_time": "06:30:00",
    "collection_time": "07:00:00",
    "bins": [
        {
            "id": "rec",
            "name": "Recycling",
            "colour": "blue",
            "first_collection": "2026-10-27",
            "interval_weeks": 2,
        },
        {
            "id": "gen",
            "name": "General",
            "colour": "black",
            "first_collection": "2026-11-03",
            "interval_weeks": 2,
        },
    ],
}


def local(*args) -> datetime:
    return datetime(*args, tzinfo=dt_util.get_default_time_zone())


@pytest.fixture
async def entry(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> MockConfigEntry:
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(local(2026, 10, 26, 12, 0))
    entry = MockConfigEntry(domain=DOMAIN, title="Bins Out", data={}, options=OPTIONS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


class CouncilCalendar(CalendarEntity):
    """Stands in for e.g. Waste Collection Schedule's calendar."""

    _attr_name = "Council bins"
    _attr_unique_id = "council_bins"

    def __init__(self, collections: dict[date, list[str]]) -> None:
        self.collections = collections

    @property
    def event(self) -> CalendarEvent | None:
        return None

    async def async_get_events(self, hass, start_date, end_date) -> list[CalendarEvent]:
        return [
            CalendarEvent(start=day, end=day + timedelta(days=1), summary=summary)
            for day, summaries in sorted(self.collections.items())
            if start_date.date() <= day < end_date.date()
            for summary in summaries
        ]


COUNCIL = {
    date(2026, 10, 27): ["Grey Bin"],
    date(2026, 10, 30): ["Maroon Bin", "Food Caddy"],
    date(2026, 11, 3): ["Grey Bin"],
    date(2026, 11, 13): ["Maroon Bin"],
}


async def setup_council_calendar(hass: HomeAssistant) -> CouncilCalendar:
    calendar = CouncilCalendar(dict(COUNCIL))

    async def setup_platform(hass, config, async_add_entities, discovery_info=None):
        async_add_entities([calendar])

    mock_integration(hass, MockModule("council"))
    mock_platform(hass, "council.calendar", MockPlatform(async_setup_platform=setup_platform))
    assert await async_setup_component(hass, "calendar", {"calendar": {"platform": "council"}})
    await hass.async_block_till_done()
    return calendar


async def test_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"evening_time": "20:00:00", "morning_time": "06:00:00", "collection_time": "07:00:00"},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["council", "bin"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "bin"}
    )
    assert result["step_id"] == "bin"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Garden", "colour": "green", "source": "manual"}
    )
    assert result["step_id"] == "bin_manual"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"first_collection": "2026-10-28", "interval_weeks": 2}
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "bin"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "garden", "colour": "green", "source": "manual"}
    )
    assert result["errors"] == {"name": "name_taken"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Food", "colour": "grey", "source": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"first_collection": "2026-10-29", "interval_weeks": 1}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert [b["name"] for b in result["options"]["bins"]] == ["Garden", "Food"]
    assert result["options"]["bins"][0]["source"] == "manual"
    assert result["options"]["evening_time"] == "20:00:00"


async def test_config_flow_calendar_bin(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(local(2026, 10, 26, 12, 0))
    await setup_council_calendar(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"evening_time": "19:00:00", "morning_time": "06:30:00", "collection_time": "07:00:00"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "bin"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "General", "colour": "grey", "source": "calendar"}
    )
    assert result["step_id"] == "bin_calendar"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"calendar_entity": "calendar.council_bins"}
    )
    assert result["step_id"] == "bin_match"
    # The dropdown offers the event names found on the calendar.
    options = result["data_schema"].schema["match"].config["options"]
    assert options == ["Food Caddy", "Grey Bin", "Maroon Bin"]
    assert "Grey Bin" in result["description_placeholders"]["found"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"match": "purple"})
    assert result["errors"] == {"match": "no_match"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"match": "grey"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["bins"][0] | {"id": "x"} == {
        "id": "x",
        "name": "General",
        "colour": "grey",
        "source": "calendar",
        "calendar_entity": "calendar.council_bins",
        "match": "grey",
    }
    await hass.async_block_till_done()
    assert hass.states.get("sensor.general_next_collection").state == "2026-10-27"


async def test_config_flow_council(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(local(2026, 10, 26, 12, 0))
    await setup_council_calendar(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"evening_time": "19:00:00", "morning_time": "06:30:00", "collection_time": "07:00:00"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "council"}
    )
    assert result["step_id"] == "council_pick"
    assert "add_council_url" in result["description_placeholders"]
    # Starts empty so people pick their own council.
    field = next(k for k in result["data_schema"].schema if k == "calendar_entity")
    assert field.default is vol.UNDEFINED
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"calendar_entity": "calendar.council_bins"}
    )
    assert result["step_id"] == "council_bins"
    # Every kind of collection is offered and ticked by default.
    field = next(k for k in result["data_schema"].schema if k == "collections")
    assert result["data_schema"].schema[field].config["options"] == [
        "Food Caddy",
        "Grey Bin",
        "Maroon Bin",
    ]
    assert field.default() == ["Food Caddy", "Grey Bin", "Maroon Bin"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"collections": []}
    )
    assert result["errors"] == {"collections": "none_selected"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"collections": ["Grey Bin", "Maroon Bin"]}
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    bins = [{k: v for k, v in b.items() if k != "id"} for b in result["options"]["bins"]]
    assert bins == [
        {"name": "Grey Bin", "colour": "grey", "source": "calendar",
         "calendar_entity": "calendar.council_bins", "match": "Grey Bin"},
        {"name": "Maroon Bin", "colour": "maroon", "source": "calendar",
         "calendar_entity": "calendar.council_bins", "match": "Maroon Bin"},
    ]
    await hass.async_block_till_done()
    assert hass.states.get("sensor.grey_bin_next_collection").state == "2026-10-27"
    assert hass.states.get("sensor.maroon_bin_next_collection").state == "2026-10-30"


async def test_options_flow_council_adds_only_new_collections(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(local(2026, 10, 26, 12, 0))
    await setup_council_calendar(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            **{k: v for k, v in OPTIONS.items() if k != "bins"},
            "bins": [
                # Already follows the grey collections; a manual bin is named "Food Caddy".
                {"id": "gry", "name": "General", "colour": "grey", "source": "calendar",
                 "calendar_entity": "calendar.council_bins", "match": "grey"},
                {"id": "fd", "name": "Food Caddy", "colour": "green",
                 "first_collection": "2026-10-30", "interval_weeks": 1},
            ],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "council" in result["menu_options"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "council"}
    )
    # Our own collections calendar isn't offered as a council calendar.
    selector_cfg = next(iter(result["data_schema"].schema.values())).config
    assert selector_cfg["exclude_entities"] == ["calendar.bins_out_collections"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"calendar_entity": "calendar.council_bins"}
    )
    options = result["data_schema"].schema
    assert next(iter(options.values())).config["options"] == ["Food Caddy", "Maroon Bin"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"collections": ["Food Caddy", "Maroon Bin"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    names = [(b["name"], b["colour"]) for b in entry.options["bins"]]
    assert names == [
        ("General", "grey"),
        ("Food Caddy", "green"),
        ("Food Caddy 2", "grey"),
        ("Maroon Bin", "maroon"),
    ]

    # Once every collection has a bin, there's nothing left to add.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "council"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"calendar_entity": "calendar.council_bins"}
    )
    assert result["errors"] == {"calendar_entity": "all_linked"}


async def test_council_calendar_without_events(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(local(2026, 10, 26, 12, 0))
    calendar = await setup_council_calendar(hass)
    calendar.collections.clear()

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"evening_time": "19:00:00", "morning_time": "06:30:00", "collection_time": "07:00:00"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "council"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"calendar_entity": "calendar.council_bins"}
    )
    assert result["step_id"] == "council_pick"
    assert result["errors"] == {"calendar_entity": "no_events"}


async def _start_council_setup(hass: HomeAssistant) -> dict:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"evening_time": "19:00:00", "morning_time": "06:30:00", "collection_time": "07:00:00"},
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "council"}
    )


async def test_council_without_waste_collection_schedule(hass: HomeAssistant) -> None:
    # No calendars and Waste Collection Schedule isn't installed: explain, don't show an empty list.
    result = await _start_council_setup(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "council_install"
    assert result["menu_options"] == ["council", "bin"]
    assert "hacs_url" in result["description_placeholders"]
    # They can carry on by adding a bin themselves.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "bin"}
    )
    assert result["step_id"] == "bin"


async def test_council_not_added_yet_then_added(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(local(2026, 10, 26, 12, 0))
    mock_integration(hass, MockModule("waste_collection_schedule"))
    # Installed but no council added yet: point them at adding one.
    result = await _start_council_setup(hass)
    assert result["step_id"] == "council_add"
    assert result["description_placeholders"]["add_council_url"].endswith(
        "domain=waste_collection_schedule"
    )
    # They add their council, then choose "I've added my council".
    await setup_council_calendar(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "council"}
    )
    assert result["step_id"] == "council_pick"


async def test_calendar_source_follows_council_changes(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(local(2026, 10, 26, 12, 0))
    calendar = await setup_council_calendar(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            **{k: v for k, v in OPTIONS.items() if k != "bins"},
            "bins": [
                {"id": "gry", "name": "General", "colour": "grey", "source": "calendar",
                 "calendar_entity": "calendar.council_bins", "match": "Grey Bin"},
                {"id": "mar", "name": "Paper", "colour": "red", "source": "calendar",
                 "calendar_entity": "calendar.council_bins", "match": "maroon"},
            ],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.general_status").state == "tomorrow"
    assert hass.states.get("sensor.paper_next_collection").state == "2026-10-30"
    attrs = hass.states.get("sensor.paper_next_collection").attributes
    # Two published dates two weeks apart, then estimates every two weeks after them.
    assert attrs["upcoming"][:3] == ["2026-10-30", "2026-11-13", "2026-11-27"]
    assert attrs["estimated"] == attrs["upcoming"][2:]

    # The council moves the grey bin; Bins Out picks it up on its next calendar read.
    del calendar.collections[date(2026, 10, 27)]
    calendar.collections[date(2026, 10, 28)] = ["Grey Bin"]
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.general_next_collection").state == "2026-10-28"

    # If the calendar disappears, the saved dates are kept.
    await calendar.async_remove()
    assert hass.states.get("calendar.council_bins").state == "unavailable"
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.general_next_collection").state == "2026-10-28"


async def test_cancel_and_restore(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.recycling_put_out"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "cancel_collection", {"bin": "Recycling", "date": "2026-10-27"}, blocking=True
    )
    # Next collection skips to the one after; the put-out mark for the cancelled day is dropped.
    assert hass.states.get("sensor.recycling_next_collection").state == "2026-11-10"
    assert hass.states.get("switch.recycling_put_out").state == "off"
    summary = hass.states.get("sensor.bins_out_next_collection").attributes
    assert summary["tonight_message"] is None
    assert summary["bins"][0]["name"] == "General"
    assert next(b for b in summary["bins"] if b["id"] == "rec")["cancelled"] == ["2026-10-27"]

    await hass.services.async_call(
        DOMAIN, "restore_collection", {"bin": "Recycling", "date": "2026-10-27"}, blocking=True
    )
    assert hass.states.get("sensor.recycling_next_collection").state == "2026-10-27"

    from homeassistant.exceptions import ServiceValidationError

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "restore_collection", {"bin": "Recycling", "date": "2026-10-27"}, blocking=True
        )


async def test_options_flow_add_and_remove(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "bin"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Garden", "colour": "green", "source": "manual"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"first_collection": "2026-10-28", "interval_weeks": 2}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("sensor.garden_status") is not None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "remove_bin"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"selected_bin": "gen"}
    )
    await hass.async_block_till_done()
    assert [b["id"] for b in entry.options["bins"]][:1] == ["rec"]
    assert hass.states.get("sensor.general_status") is None


async def test_entities(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert hass.states.get("sensor.recycling_next_collection").state == "2026-10-27"
    assert hass.states.get("sensor.recycling_days_until_collection").state == "1"
    assert hass.states.get("sensor.recycling_status").state == "tomorrow"
    assert hass.states.get("sensor.general_status").state == "upcoming"
    assert hass.states.get("binary_sensor.recycling_needs_to_go_out").state == "off"
    assert hass.states.get("switch.recycling_put_out").state == "off"

    summary = hass.states.get("sensor.bins_out_next_collection")
    assert summary.state == "1"
    bins = summary.attributes["bins"]
    assert [b["name"] for b in bins] == ["Recycling", "General"]
    assert bins[0]["colour_hex"] == "#1e6fd9"
    assert bins[0]["entities"]["put_out"] == "switch.recycling_put_out"
    assert summary.attributes["next_bins"] == ["Recycling"]
    assert "blue recycling bin" in summary.attributes["tonight_message"]

    cal = hass.states.get("calendar.bins_out_collections")
    assert cal.attributes["message"] == "Recycling"


async def test_put_out_switch_and_service(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.recycling_put_out"}, blocking=True
    )
    assert hass.states.get("switch.recycling_put_out").state == "on"
    assert hass.states.get("sensor.recycling_status").state == "out"
    assert hass.states.get("sensor.bins_out_next_collection").attributes["tonight_message"] is None

    await hass.services.async_call(
        DOMAIN, "set_put_out", {"bin": "recycling", "put_out": False}, blocking=True
    )
    assert hass.states.get("switch.recycling_put_out").state == "off"


async def test_reminder_events_and_forgotten(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    events = async_capture_events(hass, EVENT_REMINDER)

    freezer.move_to(local(2026, 10, 26, 19, 0, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [e.data["type"] for e in events] == ["evening"]
    assert hass.states.get("binary_sensor.recycling_needs_to_go_out").state == "on"

    freezer.move_to(local(2026, 10, 27, 6, 30, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert events[-1].data["type"] == "morning"

    freezer.move_to(local(2026, 10, 27, 7, 0, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert events[-1].data["type"] == "forgotten"
    assert "blue recycling bin" in events[-1].data["message"]
    assert hass.states.get("binary_sensor.recycling_forgotten").state == "on"


async def test_move_collection_and_calendar(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.services.async_call(
        DOMAIN,
        "move_collection",
        {"bin": "Recycling", "original_date": "2026-10-27", "new_date": "2026-10-29"},
        blocking=True,
    )
    assert hass.states.get("sensor.recycling_next_collection").state == "2026-10-29"

    start = local(2026, 10, 26)
    resp = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": "calendar.bins_out_collections", "start_date_time": start,
         "end_date_time": start + timedelta(days=14)},
        blocking=True,
        return_response=True,
    )
    events = resp["calendar.bins_out_collections"]["events"]
    assert [(e["start"], e["summary"]) for e in events] == [
        ("2026-10-29", "Recycling"),
        ("2026-11-03", "General"),
    ]
    assert "Moved from" in events[0]["description"]


async def test_unknown_bin(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    from homeassistant.exceptions import ServiceValidationError

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "set_put_out", {"bin": "nope"}, blocking=True)


async def test_missing_calendar_warns_only_after_startup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, caplog: pytest.LogCaptureFixture
) -> None:
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(local(2026, 10, 26, 12, 0))
    hass.set_state(CoreState.starting)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            **{k: v for k, v in OPTIONS.items() if k != "bins"},
            "bins": [
                {"id": "gry", "name": "General", "colour": "grey", "source": "calendar",
                 "calendar_entity": "calendar.council_bins", "match": "grey"},
            ],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # The council's calendar isn't up yet while HA starts: normal, so no warning.
    assert "Can't read calendar.council_bins" not in caplog.text

    hass.set_state(CoreState.running)
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert "Can't read calendar.council_bins" in caplog.text


async def test_repairs_notice_when_council_calendar_is_removed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(local(2026, 10, 26, 12, 0))
    await setup_council_calendar(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            **{k: v for k, v in OPTIONS.items() if k != "bins"},
            "bins": [
                {"id": "gry", "name": "General", "colour": "grey", "source": "calendar",
                 "calendar_entity": "calendar.council_bins", "match": "Grey Bin"},
                {"id": "mar", "name": "Paper", "colour": "red", "source": "calendar",
                 "calendar_entity": "calendar.council_bins", "match": "maroon"},
                {"id": "rec", "name": "Recycling", "colour": "blue",
                 "first_collection": "2026-10-27", "interval_weeks": 2},
            ],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    issues = ir.async_get(hass)
    issue_id = f"calendar_missing_{entry.entry_id}_calendar.council_bins"
    assert issues.async_get_issue(DOMAIN, issue_id) is None

    # The council is removed from Waste Collection Schedule: its calendar goes altogether.
    er.async_get(hass).async_remove("calendar.council_bins")
    await hass.async_block_till_done()
    assert hass.states.get("calendar.council_bins") is None
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    issue = issues.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "calendar_missing"
    assert issue.translation_placeholders == {
        "calendar": "calendar.council_bins",
        "bins": "General, Paper",
    }
    # Bins keep their last dates meanwhile.
    assert hass.states.get("sensor.general_next_collection").state == "2026-10-27"

    # Removing the bins that used it clears the notice.
    for bin_id in ("gry", "mar"):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "remove_bin"}
        )
        await hass.config_entries.options.async_configure(
            result["flow_id"], {"selected_bin": bin_id}
        )
        await hass.async_block_till_done()
    assert issues.async_get_issue(DOMAIN, issue_id) is None


async def test_removing_bins_out_clears_its_notices(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    ir.async_create_issue(
        hass, DOMAIN, f"calendar_missing_{entry.entry_id}_calendar.gone",
        is_fixable=False, severity=ir.IssueSeverity.WARNING, translation_key="calendar_missing",
    )
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert not [i for d, i in ir.async_get(hass).issues if d == DOMAIN]


async def test_council_publishing_only_the_next_date(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Council publishes one date per bin, the rest estimated."""
    await hass.config.async_set_time_zone("Europe/London")
    freezer.move_to(local(2026, 10, 26, 12, 0))
    calendar = await setup_council_calendar(hass)
    calendar.collections.clear()
    calendar.collections.update({date(2026, 10, 27): ["Grey", "Food"], date(2026, 11, 3): ["Maroon"]})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            **{k: v for k, v in OPTIONS.items() if k != "bins"},
            "bins": [
                {"id": "fd", "name": "Food", "colour": "grey", "source": "calendar",
                 "calendar_entity": "calendar.council_bins", "match": "Food"},
                {"id": "gry", "name": "Grey", "colour": "grey", "source": "calendar",
                 "calendar_entity": "calendar.council_bins", "match": "Grey"},
            ],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Food is weekly from the start, so 3 Nov shows (as an estimate).
    food = hass.states.get("sensor.food_next_collection")
    assert food.state == "2026-10-27"
    assert food.attributes["upcoming"][:3] == ["2026-10-27", "2026-11-03", "2026-11-10"]
    assert food.attributes["estimated"][0] == "2026-11-03"
    events = await calendar_events(hass, "calendar.bins_out_collections", "2026-10-26", "2026-11-08")
    assert ("2026-11-03", "Food (estimated)") in events
    assert ("2026-10-27", "Food") in events
    # Grey: nothing to go on yet, so no guesses.
    grey = hass.states.get("sensor.grey_next_collection")
    assert grey.attributes["estimated"] == []

    # After collection day the council publishes Grey's next date: two weeks on.
    freezer.move_to(local(2026, 10, 28, 12, 0))
    calendar.collections.clear()
    calendar.collections.update({date(2026, 11, 10): ["Grey"], date(2026, 11, 3): ["Food", "Maroon"]})
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    grey = hass.states.get("sensor.grey_next_collection")
    assert grey.state == "2026-11-10"
    assert grey.attributes["estimated"][:2] == ["2026-11-24", "2026-12-08"]
    summary = hass.states.get("sensor.bins_out_next_collection").attributes["bins"]
    assert next(b for b in summary if b["id"] == "gry")["repeat_weeks"] == 2

    # The user can say how often it really is; that wins over what was learned.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "edit_bin"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"selected_bin": "gry"}
    )
    # For a council bin it's on the first Edit a bin screen, next to the name and colour.
    assert "repeat_weeks" in result["data_schema"].schema
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name": "Grey", "colour": "grey", "source": "calendar", "repeat_weeks": 4},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"calendar_entity": "calendar.council_bins"}
    )
    # ...and not asked again further on.
    assert "repeat_weeks" not in result["data_schema"].schema
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"match": "Grey"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    grey = hass.states.get("sensor.grey_next_collection")
    assert grey.attributes["estimated"][0] == "2026-12-08"


async def calendar_events(hass: HomeAssistant, entity_id: str, start: str, end: str) -> list:
    response = await hass.services.async_call(
        "calendar", "get_events",
        {"entity_id": entity_id, "start_date_time": f"{start}T00:00:00", "end_date_time": f"{end}T00:00:00"},
        blocking=True, return_response=True,
    )
    return [(e["start"], e["summary"]) for e in response[entity_id]["events"]]


ALEXA = {"alexa_mode": "announce", "alexa_reminders": ["evening", "morning", "forgotten"]}


async def _alexa_form(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "alexa" in result["menu_options"]
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "alexa"}
    )


async def test_alexa_needs_alexa_media_player(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    result = await _alexa_form(hass, entry)
    assert result["step_id"] == "alexa"
    assert "alexa_hacs_url" in result["description_placeholders"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ALEXA, "alexa_enabled": True, "alexa_devices": ["media_player.kitchen"]}
    )
    assert result["errors"] == {"base": "alexa_not_installed"}
    # Leaving it off is always fine.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ALEXA, "alexa_enabled": False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["alexa_enabled"] is False


async def test_alexa_announces_reminders(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    mock_integration(hass, MockModule("alexa_media"))
    calls = async_mock_service(hass, "notify", "alexa_media")

    result = await _alexa_form(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ALEXA, "alexa_enabled": True, "alexa_devices": []}
    )
    assert result["errors"] == {"alexa_devices": "alexa_no_devices"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**ALEXA, "alexa_enabled": True, "alexa_devices": ["media_player.kitchen"],
         "alexa_reminders": ["evening"], "alexa_test": True},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "alexa_test" not in entry.options
    # The test announcement went out.
    assert len(calls) == 1
    assert calls[0].data["target"] == ["media_player.kitchen"]
    assert calls[0].data["message"].startswith("This is Bins Out")
    await hass.async_block_till_done()

    # 19:00 the night before: announced.
    freezer.move_to(local(2026, 10, 26, 19, 0, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert "blue recycling bin" in calls[1].data["message"]
    assert calls[1].data["data"] == {"type": "announce"}

    # Morning reminder wasn't ticked: not announced.
    freezer.move_to(local(2026, 10, 27, 6, 30, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_alexa_off_announces_nothing(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    mock_integration(hass, MockModule("alexa_media"))
    calls = async_mock_service(hass, "notify", "alexa_media")
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, **ALEXA, "alexa_enabled": False,
                        "alexa_devices": ["media_player.kitchen"]}
    )
    await hass.async_block_till_done()
    freezer.move_to(local(2026, 10, 26, 19, 0, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls == []


async def test_alexa_test_announcement_failing(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    mock_integration(hass, MockModule("alexa_media"))

    async def broken(call):
        raise HomeAssistantError("Amazon login expired")

    hass.services.async_register("notify", "alexa_media", broken)
    result = await _alexa_form(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**ALEXA, "alexa_enabled": True, "alexa_devices": ["media_player.kitchen"], "alexa_test": True},
    )
    assert result["errors"] == {"base": "alexa_test_failed"}


async def test_container_type(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    summary = hass.states.get("sensor.bins_out_next_collection").attributes["bins"]
    assert {b["name"]: b["container"] for b in summary} == {
        "Recycling": "wheelie_bin",
        "General": "wheelie_bin",
    }
    # Add a food caddy without saying what it is: guessed from the name.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "bin"}
    )
    assert "container" in result["data_schema"].schema
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Food", "colour": "grey", "source": "manual"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"first_collection": "2026-10-27", "interval_weeks": 1}
    )
    await hass.async_block_till_done()
    food = next(b for b in entry.options["bins"] if b["name"] == "Food")
    assert "container" not in food
    summary = hass.states.get("sensor.bins_out_next_collection").attributes
    assert next(b for b in summary["bins"] if b["name"] == "Food")["container"] == "food_caddy"
    assert "grey food caddy" in summary["tonight_message"]

    # Say Recycling is a box: picture and wording follow.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "edit_bin"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"selected_bin": "rec"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name": "Recycling", "colour": "blue", "container": "box", "source": "manual"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"first_collection": "2026-10-27", "interval_weeks": 2}
    )
    await hass.async_block_till_done()
    summary = hass.states.get("sensor.bins_out_next_collection").attributes
    rec = next(b for b in summary["bins"] if b["name"] == "Recycling")
    assert rec["container"] == "box"
    assert rec["spoken_name"] == "blue recycling box"


async def _messages_form(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "messages" in result["menu_options"]
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "messages"}
    )


def _suggested(result: dict, key: str) -> str:
    field = next(k for k in result["data_schema"].schema if k == key)
    return field.description["suggested_value"]


async def test_own_reminder_messages(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    mock_integration(hass, MockModule("alexa_media"))
    calls = async_mock_service(hass, "notify", "alexa_media")
    events = async_capture_events(hass, EVENT_REMINDER)

    # The boxes start with the standard wording, so there's something to edit.
    result = await _messages_form(hass, entry)
    assert _suggested(result, "message_evening").startswith("Reminder: put {bins} out tonight")

    # Hearing it on Alexa needs Alexa switched on first.
    mine = {"message_evening": "Oi! Take {bins} out, it goes tomorrow.",
            "message_morning": "It's bin day! Put {bins} out now.",
            "message_forgotten": ""}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**mine, "message_try": True}
    )
    assert result["errors"] == {"base": "alexa_off"}
    assert _suggested(result, "message_evening") == mine["message_evening"]
    assert calls == []

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, **ALEXA, "alexa_enabled": True,
                        "alexa_devices": ["media_player.kitchen"]}
    )
    await hass.async_block_till_done()
    result = await _messages_form(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**mine, "message_try": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Said with your own bins' names.
    assert calls[0].data["message"] == (
        "Oi! Take the blue recycling bin and the black general bin out, it goes tomorrow."
    )
    # Only real changes are saved: unchanged and empty boxes keep the standard wording.
    assert entry.options["message_evening"] == mine["message_evening"]
    assert "message_morning" not in entry.options
    assert "message_forgotten" not in entry.options
    assert "message_try" not in entry.options
    await hass.async_block_till_done()

    # 19:00 the night before: your wording, on Alexa and in the event.
    freezer.move_to(local(2026, 10, 26, 19, 0, 0))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert events[-1].data["message"] == "Oi! Take the blue recycling bin out, it goes tomorrow."
    assert calls[-1].data["message"] == "Oi! Take the blue recycling bin out, it goes tomorrow."
