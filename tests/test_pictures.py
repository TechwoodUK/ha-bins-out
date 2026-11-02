"""Bin pictures for phone notifications."""

from io import BytesIO

from PIL import Image

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.bins_out.const import BIN_COLOURS, DOMAIN
from custom_components.bins_out.pictures import (
    AVAILABLE,
    MAX_BINS,
    compose,
    parse_picture_name,
    picture_name,
)

CONTAINERS = ("wheelie_bin", "food_caddy", "box", "bag")


def test_every_bin_has_a_picture():
    assert AVAILABLE == {f"{c}-{colour}" for c in CONTAINERS for colour in BIN_COLOURS}


def test_names():
    assert picture_name([("wheelie_bin", "blue"), ("food_caddy", "grey")]) == (
        "wheelie_bin-blue+food_caddy-grey.png"
    )
    # Anything we can't draw is left out; nothing drawable means no picture.
    assert picture_name([("wheelie_bin", "tartan"), ("box", "green")]) == "box-green.png"
    assert picture_name([("wheelie_bin", "tartan")]) is None
    assert parse_picture_name("wheelie_bin-blue+food_caddy-grey.png") == [
        "wheelie_bin-blue",
        "food_caddy-grey",
    ]
    for bad in ("../const.py", "wheelie_bin-blue", "wheelie_bin-tartan.png", ".png",
                "+".join(["box-red"] * (MAX_BINS + 1)) + ".png"):
        assert parse_picture_name(bad) is None, bad


def test_compose_puts_bins_side_by_side():
    one = Image.open(BytesIO(compose(("wheelie_bin-blue",))))
    three = Image.open(BytesIO(compose(("wheelie_bin-blue", "food_caddy-grey", "wheelie_bin-maroon"))))
    for image in (one, three):
        assert image.format == "PNG" and image.mode == "RGBA"
        assert image.width == 2 * image.height  # what Android's big picture shows
        assert image.getpixel((0, 0))[3] == 0  # transparent background
    assert three.width > one.width


async def test_picture_served_without_login(hass: HomeAssistant, hass_client_no_auth) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client_no_auth()
    resp = await client.get("/api/bins_out/picture/wheelie_bin-blue+food_caddy-grey.png")
    assert resp.status == 200
    assert resp.content_type == "image/png"
    assert Image.open(BytesIO(await resp.read())).width > 0
    for bad in ("wheelie_bin-tartan.png", "..%2Fconst.py", "nothing"):
        # Refused by Bins Out (404), or by Home Assistant before it gets that far (400).
        assert (await client.get(f"/api/bins_out/picture/{bad}")).status in (400, 404)
