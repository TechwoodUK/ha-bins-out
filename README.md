# Bins Out for Home Assistant

Tells you when your bins need to go out, nags you the night before and on the morning,
and notices when you forgot.

By **Techwood**, built with AI assistance. For family use only, see [About](#about).

## What you need

- **Home Assistant** 2026.10 or newer.
- **For automatic dates from your council (recommended):**
  [Waste Collection Schedule](https://github.com/mampfes/hacs_waste_collection_schedule), a free
  integration from HACS that supports hundreds of councils. Install it and add your council and
  address to it, then Bins Out reads your collection days from it. See the quick start below.
- **Without Waste Collection Schedule** Bins Out still works: you enter one collection date per bin
  and how many weeks apart collections are. You'll need to handle bank holiday changes yourself.
- **Optional:** [Alexa Media Player](https://github.com/alandtse/alexa_media_player) (HACS) for spoken
  reminders on Echo devices.

## Install

**1. Get HACS** (the community store for Home Assistant), if you haven't already.
Settings → Add-ons → Add-on store → ⋮ → Repositories → add `https://github.com/hacs/addons`.
Install **Get HACS**, start it, wait for its log to say it's done, then restart Home Assistant.
Finally Settings → Devices & services → Add integration → **HACS**, and sign in with GitHub when asked.

**2. Add Bins Out to HACS.** Open this page on a computer or phone that can reach your Home
Assistant, and click:

[![Open your Home Assistant instance and open Bins Out in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=TechwoodUK&repository=ha-bins-out&category=integration)

The first time, it asks for your Home Assistant address (e.g. `http://homeassistant.local:8123`).
Then click **Add**, **Download**, **Download**.

<details><summary>Button not working?</summary>

In HACS: ⋮ (top right) → **Custom repositories** → Repository `https://github.com/TechwoodUK/ha-bins-out`,
Type **Integration** → **Add**. Then search HACS for **Bins Out** → **Download**.
</details>

**3. Restart Home Assistant.** Settings → System → ⏻ (top right) → Restart Home Assistant.

**4. Set it up.** Settings → Devices & services → Add integration → **Bins Out**. Choose your reminder
times, then **From my council** (recommended, see below) or **I'll add my bins myself**.
When you're done, click **Bins** in the left menu to see your bins.

Add, edit or remove bins later: **Settings → Devices & services → Bins Out**, then the **⚙** button
next to Bins Out (this page calls it **⚙ settings**). Updates appear in
Settings → Updates when there's a new version.

## Quick start: bins from your council

Bins Out gets your council's dates from [Waste Collection Schedule](https://github.com/mampfes/hacs_waste_collection_schedule),
a free integration that supports hundreds of councils. Set it up once and your dates stay up to date by themselves.

1. **Install Waste Collection Schedule.** In HACS, search for it, download it, and restart Home Assistant.
2. **Add your council there.** Settings → Devices & services → Add integration → **Waste Collection Schedule**.
   Choose your country, type your council's name in the search box, and enter your address details.
   Many UK councils ask for your **UPRN** (your property's reference number):
   find it by searching your address at [findmyaddress.co.uk](https://www.findmyaddress.co.uk).
3. **Get your bins.** Add Bins Out and choose **From my council** (or later: Bins Out → **⚙ settings** → **Add bins from my council**).
   Pick your council, tick your collections, done.

If you skip step 1 or 2, Bins Out tells you what's missing and links to it.
The council list in step 3 only shows councils you've added in step 2. For a second address, add it in step 2 again.

Council not supported? Choose **I'll add my bins myself** and enter one collection date and how many weeks apart they are.

## Collection dates

Each bin gets its dates one of two ways.

**Every few weeks from a date I know.** Enter any one date the bin is collected and how many weeks
apart collections are. Every other date is worked out from that.

**From a calendar (automatic).** The bin follows events on a Home Assistant calendar, so changes
from your council are picked up automatically. Bins Out re-reads the calendar every 30 minutes and
keeps the last dates it found if the calendar is temporarily unavailable. The best source is
[Waste Collection Schedule](https://github.com/mampfes/hacs_waste_collection_schedule) (HACS),
which supports hundreds of councils.

Example: a UK council
1. In HACS, install **Waste Collection Schedule** and restart Home Assistant.
2. Settings → Devices & services → Add integration → **Waste Collection Schedule**. Choose the UK,
   then your council or borough (type its name to search), and enter what it asks for, often your
   **postcode** and **UPRN**.
   You can find your UPRN by entering your address at [findmyaddress.co.uk](https://www.findmyaddress.co.uk).
3. It creates a calendar of your collections.
4. When you set up Bins Out choose **From my council** (or later: **⚙ settings** →
   **Add bins from my council**), pick that calendar, and tick your collections. Bins Out makes
   one bin per collection and guesses its colour from the name (e.g. "Maroon" → maroon,
   "Garden Waste" → green). Rename or recolour them with **⚙ settings** → **Edit a bin**.

Any council that Waste Collection Schedule supports works the same way: add your council and
address there, then choose **From my council**. To link a single bin instead, use
**Add a bin** / **Edit a bin** → *Collection dates:* **From a calendar** → pick the calendar →
pick the event name for this bin.

**One-off changes** work with both kinds: move a collection with `bins_out.move_collection`, or
cancel one with `bins_out.cancel_collection` (see Services).

## Times

| Setting          | Default | What it does                                                              |
|------------------|---------|---------------------------------------------------------------------------|
| Evening reminder | 19:00   | Night before collection: reminder fires, "Needs to go out" turns on.      |
| Morning reminder | 06:30   | Collection day: reminder fires if a bin still isn't out.                  |
| Collection time  | 07:00   | After this, any bin not marked out counts as **forgotten**.               |

## Entities

Per bin (one device per bin):

| Entity                                | Example state                  |
|---------------------------------------|--------------------------------|
| `sensor.<bin>_next_collection`        | `2026-10-27` (+ `upcoming` list) |
| `sensor.<bin>_days_until_collection`  | `1`                            |
| `sensor.<bin>_status`                 | `upcoming` / `tomorrow` / `today` / `out` / `collected` / `forgotten` |
| `binary_sensor.<bin>_needs_to_go_out` | on from evening reminder until collection, unless put out |
| `binary_sensor.<bin>_forgotten`       | on if collection time passed and it wasn't put out |
| `switch.<bin>_put_out`                | turn on when it's at the kerb; clears itself after collection day |

Shared:

- `sensor.bins_out_next_collection`: days to the soonest collection, with every bin's details in attributes (used by the dashboard card).
- `calendar.bins_out_collections`: every collection, so it works in the HA calendar too.

## Services

- `bins_out.set_put_out`: `bin: Recycling`, `put_out: true`. Handy for an NFC tag stuck on the bin.
- `bins_out.move_collection`: one-off change such as a bank holiday:
  `bin: Recycling`, `original_date: 2026-12-25`, `new_date: 2026-12-27`.
- `bins_out.clear_moved`: remove all moved collections for a bin.
- `bins_out.cancel_collection`: a collection isn't happening (`bin: Recycling`, `date: 2026-12-25`).
  The bin moves on to its next collection and no reminders are sent for that day.
- `bins_out.restore_collection`: undo a cancellation (same fields).

You can run these from Developer tools → Actions, or from a dashboard button or script.

## Reminders and Alexa

At each reminder time, if there's something to say, the integration fires a `bins_out_reminder` event:

```yaml
event_type: bins_out_reminder
data:
  type: evening        # evening | morning | forgotten
  message: "Reminder: put the blue recycling bin out tonight. Collection is tomorrow."
```

**Alexa:** install [Alexa Media Player](https://github.com/alandtse/alexa_media_player) from HACS,
restart, add it in Settings → Devices & services and sign in to Amazon (choose `amazon.co.uk` in the UK).
Then open Bins Out → **⚙ settings** → **Alexa announcements**: switch it on, pick your Echo devices,
choose *Announce* (chime first) or *Just speak* and which reminders to say, and tick
**Send a test announcement** to check it works. On an Echo Show the words also appear on screen.
Switch it off again any time from the same screen.

**Phone notifications:** install the free [Home Assistant app](https://companion.home-assistant.io/)
on your phone and sign in to your Home Assistant. Then Bins Out → **⚙ settings** → **Phone
notifications**: switch it on, pick your phones and which reminders, and tick **Send a test
notification**. Reminders pop up, vibrate and ask **Have you put it out?** Tap **Yes** to mark the
bins as out, or **Not yet** to be asked again an hour later (until 22:00 the night before, or until
collection time in the morning). Tap the notification to open the Bins page. Tick **Only phones
that are at home** to skip anyone who's out (if everyone's out, everyone is reminded). On an
iPhone, allow *Time Sensitive* notifications for the app so they come through in a Focus.

**Your own wording:** Bins Out → **⚙ settings** → **Reminder messages**. Write what each reminder
should say; `{bins}` is replaced by the bins' names (e.g. *the blue bin and the grey food caddy*)
and `{was}` by *was* or *were*. Tick **Say the evening message on Alexa** to hear it. Clear a box
to go back to the standard wording. Your wording is used on Alexa and in the `bins_out_reminder` event.

For more control (e.g. also notify a phone, or only on some days) use the blueprint
`blueprints/automation/bins_out/alexa_bin_reminders.yaml` instead (copy it to
`config/blueprints/automation/bins_out/` and create an automation from it). Use one or the other,
not both, or Alexa will say each reminder twice.

**Tell Alexa it's out:** expose `switch.<bin>_put_out` to Alexa and say *"Alexa, turn on recycling put out"*,
or make an Alexa routine ("Alexa, I've put the bins out") that turns the switches on.

## The Bins page and card

Once Bins Out is set up, a **Bins** page appears in the left menu for everyone in your home,
showing all your bins, when they're next collected, and a calendar. Nothing to set up.

To put the same card on one of your own dashboards too: open the dashboard → ✏️ (top right) →
**+ Add card** → search **Bins Out** → **Save**. (If there's no ✏️, use ⋮ → **Edit dashboard**.)

<details><summary>Dashboards in YAML</summary>

```yaml
type: custom:bins-out-card
entity: sensor.bins_out_next_collection
```

The card is added to your dashboard resources for you. If your resources are in YAML mode, add
`url: /bins_out_static/bins-out-card.js`, `type: module` yourself (change the URL, e.g. add
`?v=2`, after updating so browsers fetch the new card).
</details>


## Development

```bash
python -m venv venv && ./venv/bin/pip install pytest-homeassistant-custom-component home-assistant-frontend
./venv/bin/python -m pytest
```

## Ideas for later

- Auto-move collections around bank holidays (UK `holidays` package) instead of using `move_collection` by hand.
- A "bring the bin back in" reminder in the evening of collection day (the `collected` status already exists for this).
- Use a door or contact sensor on the side gate to mark bins out automatically.
- Holiday mode: pause reminders while you're away.

## About

Bins Out was designed and built by **Techwood**. Much of the code was written with AI coding
assistants (Anthropic's Claude and Google's Gemini) under Techwood's direction, and every
feature was tested on a real Home Assistant system.

Copyright © 2026 Techwood. All rights reserved. It's shared for family use only: you may
install it if Techwood sent you the link. See [LICENSE](LICENSE) for what is and isn't allowed.
