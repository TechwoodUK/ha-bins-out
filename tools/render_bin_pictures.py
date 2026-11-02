"""Render the card's bin drawings to PNGs for phone notifications.

Run after changing the drawings in frontend/bins-out-card.js:

    python tools/render_bin_pictures.py

Needs Playwright with Chromium (`pip install playwright && playwright install chromium`).
Writes custom_components/bins_out/pictures/<container>-<colour>.png.
"""

from __future__ import annotations

import functools
import http.server
import json
import pathlib
import shutil
import tempfile
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
INTEGRATION = ROOT / "custom_components" / "bins_out"
OUT = INTEGRATION / "pictures"
CONTAINERS = ["wheelie_bin", "food_caddy", "box", "bag"]
SCALE = 3  # 72px drawings -> about 216px wide
MARGIN = 6  # CSS px around each drawing


def bin_colours() -> dict[str, str]:
    text = (INTEGRATION / "const.py").read_text()
    block = text[text.index("BIN_COLOURS"):].split("}", 1)[0]
    pairs = [line.split(":") for line in block.splitlines() if line.strip().startswith('"')]
    return {k.strip().strip('"'): v.strip().strip('",') for k, v in pairs}


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:transparent;--primary-text-color:#555}</style>
<script>customElements.define("ha-card", class extends HTMLElement {
  constructor(){super();this.attachShadow({mode:"open"}).innerHTML="<slot></slot>";}});</script>
</head><body><bins-out-card></bins-out-card>
<script type="module">
  const bins = __BINS__;
  await import("./bins-out-card.js");
  const card = document.querySelector("bins-out-card");
  card.setConfig({ title: "", show_calendar: false });
  card.hass = { states: { "sensor.bins_out_next_collection": { state: "1", last_updated: "x",
    attributes: { bins, next_bins: [] } } }, callService() {} };
  // Just the drawing: no status badge, no fading.
  const style = document.createElement("style");
  style.textContent = ".badge{display:none!important} .bin-art{opacity:1!important;filter:none!important}"
    + " .bin{background:none!important;border-color:transparent!important;box-shadow:none!important}";
  card.shadowRoot.appendChild(style);
  window.__ready = true;
</script></body></html>"""


def main() -> None:
    colours = bin_colours()
    bins = [
        {"id": f"{c}-{name}", "name": f"{c}-{name}", "colour": name, "colour_hex": hexc,
         "container": c, "status": "tomorrow", "next_collection": None, "days_until": 1,
         "upcoming": [], "entities": {}}
        for c in CONTAINERS for name, hexc in colours.items()
    ]
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        site = pathlib.Path(tmp)
        shutil.copy(INTEGRATION / "frontend" / "bins-out-card.js", site)
        (site / "index.html").write_text(PAGE.replace("__BINS__", json.dumps(bins)))
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(args=["--no-sandbox"])
                page = browser.new_page(device_scale_factor=SCALE, viewport={"width": 1000, "height": 4000})
                page.goto(f"http://127.0.0.1:{server.server_address[1]}/index.html")
                page.wait_for_function("window.__ready === true")
                page.wait_for_timeout(500)
                drawings = page.locator("bins-out-card >> svg.bin-svg")
                assert drawings.count() == len(bins), drawings.count()
                for i, b in enumerate(bins):
                    # A margin around the box, so the shadow and edges aren't clipped.
                    box = drawings.nth(i).bounding_box()
                    clip = {"x": box["x"] - MARGIN, "y": box["y"] - MARGIN,
                            "width": box["width"] + 2 * MARGIN, "height": box["height"] + 2 * MARGIN}
                    page.screenshot(path=str(OUT / f"{b['id']}.png"), clip=clip, omit_background=True)
                browser.close()
        finally:
            server.shutdown()
    print(f"Wrote {len(bins)} pictures to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
