"""The integration serves the card, adds it to dashboards and gives it a sidebar page."""

from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.bins_out.const import (
    CARD_FILENAME,
    CARD_URL_BASE,
    DOMAIN,
    PANEL_FILENAME,
    PANEL_URL_PATH,
)

FRONTEND = Path(__file__).parent.parent / "custom_components" / DOMAIN / "frontend"


def our_resources(hass: HomeAssistant) -> list[dict]:
    return [
        r
        for r in hass.data["lovelace"].resources.async_items()
        if r["url"].startswith(f"{CARD_URL_BASE}/{CARD_FILENAME}")
    ]


async def test_card_served(hass: HomeAssistant, hass_client, hass_storage) -> None:
    pytest.importorskip("hass_frontend")
    assert (FRONTEND / CARD_FILENAME).is_file()
    assert (FRONTEND / PANEL_FILENAME).is_file()
    assert await async_setup_component(hass, "frontend", {})
    assert await async_setup_component(hass, "lovelace", {})
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={"bins": []})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ours = our_resources(hass)
    assert len(ours) == 1
    assert ours[0]["type"] == "module"

    # Setting up again (e.g. after a restart) must not add a duplicate.
    from custom_components.bins_out import _register_card

    await _register_card(hass)
    assert len(our_resources(hass)) == 1

    client = await hass_client()
    for name in (CARD_FILENAME, PANEL_FILENAME):
        resp = await client.get(f"{CARD_URL_BASE}/{name}")
        assert resp.status == 200

    # A "Bins" page in the sidebar shows the card, for everyone (not just admins).
    panel = hass.data["frontend_panels"][PANEL_URL_PATH]
    assert panel.sidebar_title == "Bins"
    assert panel.require_admin is False
    custom = panel.config["_panel_custom"]
    assert custom["name"] == "bins-out-panel"
    assert custom["module_url"].startswith(f"{CARD_URL_BASE}/{PANEL_FILENAME}?v=")
    assert panel.config["card_url"] == ours[0]["url"]
    assert panel.config["entity"] == "sensor.bins_out_next_collection"

    # Reloading (e.g. after Configure) puts the page back.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert PANEL_URL_PATH in hass.data["frontend_panels"]

    # Removing Bins Out leaves nothing behind: page, dashboard card link, saved data.
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {"version": 1, "data": {}}
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert PANEL_URL_PATH not in hass.data["frontend_panels"]
    assert our_resources(hass) == []
    assert f"{DOMAIN}.{entry.entry_id}" not in hass_storage
