"""The integration serves and auto-loads the Lovelace card when it exists."""

from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.bins_out.const import CARD_FILENAME, CARD_URL_BASE, DOMAIN

CARD = Path(__file__).parent.parent / "custom_components" / DOMAIN / "frontend" / CARD_FILENAME


async def test_card_served(hass: HomeAssistant, hass_client) -> None:
    pytest.importorskip("hass_frontend")
    created = not CARD.exists()
    if created:
        CARD.write_text("// placeholder\n")
    try:
        assert await async_setup_component(hass, "frontend", {})
        assert await async_setup_component(hass, "lovelace", {})
        entry = MockConfigEntry(domain=DOMAIN, data={}, options={"bins": []})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        resources = hass.data["lovelace"].resources.async_items()
        ours = [r for r in resources if r["url"].startswith(f"{CARD_URL_BASE}/{CARD_FILENAME}")]
        assert len(ours) == 1
        assert ours[0]["type"] == "module"

        # Setting up again (e.g. after a restart) must not add a duplicate.
        from custom_components.bins_out import _register_card

        await _register_card(hass)
        assert len(hass.data["lovelace"].resources.async_items()) == len(resources)

        client = await hass_client()
        resp = await client.get(f"{CARD_URL_BASE}/{CARD_FILENAME}")
        assert resp.status == 200
    finally:
        if created:
            CARD.unlink()
