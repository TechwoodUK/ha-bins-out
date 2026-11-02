"""Pictures of the bins for phone notifications, made from the card's drawings.

pictures/<container>-<colour>.png are rendered from frontend/bins-out-card.js by
tools/render_bin_pictures.py. A notification shows the bins it's about side by side.
"""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.http import KEY_HASS

PICTURES = Path(__file__).parent / "pictures"
# Listed once, when Bins Out is imported (not on the event loop).
AVAILABLE = frozenset(p.stem for p in PICTURES.glob("*.png"))
PICTURE_URL = "/api/bins_out/picture"
MAX_BINS = 6
GAP = 24  # px between bins
PADDING = 24


def picture_name(bins: list[tuple[str, str]]) -> str | None:
    """'wheelie_bin-blue+food_caddy-grey.png' for these (container, colour) pairs, if drawable."""
    parts = [f"{c}-{colour}" for c, colour in bins if f"{c}-{colour}" in AVAILABLE]
    return "+".join(parts[:MAX_BINS]) + ".png" if parts else None


def parse_picture_name(name: str) -> list[str] | None:
    """The picture files a name stands for, or None if it isn't one of ours."""
    if not name.endswith(".png"):
        return None
    parts = name.removesuffix(".png").split("+")
    if not 0 < len(parts) <= MAX_BINS:
        return None
    return parts if all(p in AVAILABLE for p in parts) else None


@lru_cache(maxsize=32)
def compose(parts: tuple[str, ...], square: bool = False) -> bytes:
    """The bins standing side by side on a transparent canvas.

    2:1 for Android's big picture. Square for a small notification picture: the bins
    then overlap a little, so they stay big enough to recognise.
    """
    from PIL import Image  # noqa: PLC0415  (only when a picture is asked for)

    images = []
    for part in parts:
        image = Image.open(PICTURES / f"{part}.png").convert("RGBA")
        # Trim the empty space around the drawing (a caddy has a lot below it).
        images.append(image.crop(image.getbbox() or (0, 0, image.width, image.height)))
    gap = -min(i.width for i in images) // 4 if square else GAP
    padding = PADDING // 3 if square else PADDING
    row_w = sum(i.width for i in images) + gap * (len(images) - 1)
    row_h = max(i.height for i in images)
    if square:
        width = height = max(row_w, row_h) + 2 * padding
    else:
        width = max(row_w + 2 * padding, 2 * (row_h + 2 * padding))
        height = width // 2
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = (width - row_w) // 2
    ground = (height + row_h) // 2  # bins stand on the same line, like at the kerb
    for image in images:
        canvas.alpha_composite(image, (x, ground - image.height))
        x += image.width + gap
    out = BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


class BinsOutPictureView(HomeAssistantView):
    """Serves the notification pictures.

    No login needed: the phone fetches the picture itself, and it only ever shows bin
    drawings that ship with Bins Out (names are checked against the files).
    """

    url = PICTURE_URL + "/{name}"
    name = "api:bins_out:picture"
    requires_auth = False

    async def get(self, request: web.Request, name: str) -> web.Response:
        parts = parse_picture_name(name)
        if parts is None:
            return web.Response(status=404)
        square = request.query.get("shape") == "square"
        body = await request.app[KEY_HASS].async_add_executor_job(compose, tuple(parts), square)
        return web.Response(
            body=body, content_type="image/png", headers={"Cache-Control": "public, max-age=86400"}
        )
