"""Bins Out: tells you when your bins need to go out."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_BIN,
    ATTR_DATE,
    ATTR_NEW_DATE,
    ATTR_ORIGINAL_DATE,
    ATTR_PUT_OUT,
    CARD_FILENAME,
    CARD_URL_BASE,
    DOMAIN,
    PLATFORMS,
    SERVICE_CANCEL_COLLECTION,
    SERVICE_CLEAR_MOVED,
    SERVICE_MOVE_COLLECTION,
    SERVICE_RESTORE_COLLECTION,
    SERVICE_SET_PUT_OUT,
    VERSION,
)
from .coordinator import BinsOutConfigEntry, BinsOutCoordinator, calendar_issue_prefix

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SET_PUT_OUT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_BIN): cv.string,
        vol.Optional(ATTR_PUT_OUT, default=True): cv.boolean,
    }
)
MOVE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_BIN): cv.string,
        vol.Required(ATTR_ORIGINAL_DATE): cv.date,
        vol.Required(ATTR_NEW_DATE): cv.date,
    }
)
CLEAR_MOVED_SCHEMA = vol.Schema({vol.Required(ATTR_BIN): cv.string})
DATE_SCHEMA = vol.Schema({vol.Required(ATTR_BIN): cv.string, vol.Required(ATTR_DATE): cv.date})


def _coordinator(hass: HomeAssistant) -> BinsOutCoordinator:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Bins Out is not set up")
    return entries[0].runtime_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services and the frontend card."""

    async def set_put_out(call: ServiceCall) -> None:
        coord = _coordinator(hass)
        coord.set_put_out(coord.resolve_bin(call.data[ATTR_BIN]), call.data[ATTR_PUT_OUT])

    async def move_collection(call: ServiceCall) -> None:
        coord = _coordinator(hass)
        coord.move_collection(
            coord.resolve_bin(call.data[ATTR_BIN]),
            call.data[ATTR_ORIGINAL_DATE],
            call.data[ATTR_NEW_DATE],
        )

    async def clear_moved(call: ServiceCall) -> None:
        coord = _coordinator(hass)
        coord.clear_moved(coord.resolve_bin(call.data[ATTR_BIN]))

    async def cancel_collection(call: ServiceCall) -> None:
        coord = _coordinator(hass)
        coord.cancel_collection(coord.resolve_bin(call.data[ATTR_BIN]), call.data[ATTR_DATE])

    async def restore_collection(call: ServiceCall) -> None:
        coord = _coordinator(hass)
        coord.restore_collection(coord.resolve_bin(call.data[ATTR_BIN]), call.data[ATTR_DATE])

    hass.services.async_register(DOMAIN, SERVICE_SET_PUT_OUT, set_put_out, SET_PUT_OUT_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_MOVE_COLLECTION, move_collection, MOVE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_MOVED, clear_moved, CLEAR_MOVED_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_COLLECTION, cancel_collection, DATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESTORE_COLLECTION, restore_collection, DATE_SCHEMA
    )

    await _register_card(hass)
    return True


async def _register_card(hass: HomeAssistant) -> None:
    """Serve frontend/ and add the card as a Lovelace resource.

    Not add_extra_js_url: modules loaded that way run before the frontend swaps in
    its custom element registry (HA 2026.10), so the card's definition is lost.
    """
    frontend_dir = Path(__file__).parent / "frontend"
    if not (frontend_dir / CARD_FILENAME).is_file() or "frontend" not in hass.config.components:
        return
    # Imported lazily so the integration still loads where frontend isn't available.
    from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_BASE, str(frontend_dir), cache_headers=False)]
    )

    base_url = f"{CARD_URL_BASE}/{CARD_FILENAME}"
    # Fingerprint the file so browsers never reuse a stale or already-evaluated copy.
    digest = await hass.async_add_executor_job(
        lambda: hashlib.sha256((frontend_dir / CARD_FILENAME).read_bytes()).hexdigest()[:8]
    )
    url = f"{base_url}?v={VERSION}-{digest}"
    lovelace = hass.data.get("lovelace")
    if lovelace is None or lovelace.resource_mode != "storage":
        _LOGGER.info(
            "Lovelace resources are in YAML mode; add the Bins Out card manually: "
            "url: %s, type: module",
            url,
        )
        return

    resources = lovelace.resources
    await resources.async_get_info()  # make sure the collection is loaded
    for item in resources.async_items():
        if item["url"].split("?")[0] == base_url:
            if item["url"] != url:
                await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
            return
    await resources.async_create_item({"res_type": "module", "url": url})


async def async_setup_entry(hass: HomeAssistant, entry: BinsOutConfigEntry) -> bool:
    coordinator = BinsOutCoordinator(hass, entry)
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _remove_deleted_bin_devices(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_setup_reminders()
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BinsOutConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BinsOutConfigEntry) -> None:
    """Bins Out removed: drop its "council calendar missing" notices."""
    prefix = calendar_issue_prefix(entry.entry_id)
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith(prefix):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def _async_reload(hass: HomeAssistant, entry: BinsOutConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _remove_deleted_bin_devices(
    hass: HomeAssistant, entry: BinsOutConfigEntry, coordinator: BinsOutCoordinator
) -> None:
    registry = dr.async_get(hass)
    keep = {(DOMAIN, f"{entry.entry_id}_{b}") for b in coordinator.bins}
    keep.add((DOMAIN, entry.entry_id))
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not device.identifiers & keep:
            registry.async_remove_device(device.id)
