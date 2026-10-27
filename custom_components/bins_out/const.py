"""Constants for the Bins Out integration."""

from __future__ import annotations

DOMAIN = "bins_out"
VERSION = "0.1.0"

PLATFORMS = ["binary_sensor", "calendar", "sensor", "switch"]

# Options keys
CONF_BINS = "bins"
CONF_EVENING_TIME = "evening_time"
CONF_MORNING_TIME = "morning_time"
CONF_COLLECTION_TIME = "collection_time"

# Per-bin keys
CONF_BIN_ID = "id"
CONF_BIN_NAME = "name"
CONF_BIN_COLOUR = "colour"
CONF_FIRST_COLLECTION = "first_collection"
CONF_INTERVAL_WEEKS = "interval_weeks"
CONF_SOURCE = "source"
CONF_CALENDAR_ENTITY = "calendar_entity"
CONF_MATCH = "match"
CONF_REPEAT_WEEKS = "repeat_weeks"  # calendar bins: weeks apart, to estimate unpublished dates
CONF_CONTAINER = "container"  # what it is, for the card's picture and what Alexa calls it

# Kinds of container UK councils hand out -> the word used when speaking about one.
CONTAINER_WHEELIE_BIN = "wheelie_bin"
CONTAINER_FOOD_CADDY = "food_caddy"
CONTAINER_BOX = "box"
CONTAINER_BAG = "bag"
CONTAINER_NOUNS: dict[str, str] = {
    CONTAINER_WHEELIE_BIN: "bin",
    CONTAINER_FOOD_CADDY: "caddy",
    CONTAINER_BOX: "box",
    CONTAINER_BAG: "bag",
}

# Where a bin's dates come from.
SOURCE_MANUAL = "manual"  # every N weeks from a known date
SOURCE_CALENDAR = "calendar"  # events on a HA calendar, e.g. Waste Collection Schedule
CALENDAR_LOOKAHEAD_DAYS = 120
CALENDAR_REFRESH_MINUTES = 30

# Alexa announcements, through the Alexa Media Player integration (HACS).
ALEXA_DOMAIN = "alexa_media"
CONF_ALEXA_ENABLED = "alexa_enabled"
CONF_ALEXA_DEVICES = "alexa_devices"
CONF_ALEXA_MODE = "alexa_mode"  # "announce" (chime first) or "tts"
CONF_ALEXA_REMINDERS = "alexa_reminders"
ALEXA_MODES = ["announce", "tts"]

DEFAULT_EVENING_TIME = "19:00:00"
DEFAULT_MORNING_TIME = "06:30:00"
DEFAULT_COLLECTION_TIME = "07:00:00"

# Colour name -> hex, used by the frontend card and for spoken announcements.
BIN_COLOURS: dict[str, str] = {
    "black": "#2b2b2b",
    "grey": "#8a8d91",
    "blue": "#1e6fd9",
    "green": "#2e9e44",
    "brown": "#7b4a2a",
    "purple": "#7d3cbf",
    "red": "#d93a2b",
    "maroon": "#7a1f2e",
    "yellow": "#f2c230",
    "orange": "#f07a1a",
    "white": "#f4f4f4",
}

# Bin statuses (also the sensor enum options)
STATUS_UPCOMING = "upcoming"
STATUS_TOMORROW = "tomorrow"
STATUS_TODAY = "today"
STATUS_OUT = "out"
STATUS_FORGOTTEN = "forgotten"
STATUS_COLLECTED = "collected"
STATUS_NONE = "none"
STATUSES = [
    STATUS_UPCOMING,
    STATUS_TOMORROW,
    STATUS_TODAY,
    STATUS_OUT,
    STATUS_FORGOTTEN,
    STATUS_COLLECTED,
    STATUS_NONE,
]

# Fired on the bus at the reminder times when there is something to say.
EVENT_REMINDER = f"{DOMAIN}_reminder"
REMINDER_EVENING = "evening"
REMINDER_MORNING = "morning"
REMINDER_FORGOTTEN = "forgotten"
REMINDERS = [REMINDER_EVENING, REMINDER_MORNING, REMINDER_FORGOTTEN]

SERVICE_SET_PUT_OUT = "set_put_out"
SERVICE_MOVE_COLLECTION = "move_collection"
SERVICE_CLEAR_MOVED = "clear_moved"
SERVICE_CANCEL_COLLECTION = "cancel_collection"
SERVICE_RESTORE_COLLECTION = "restore_collection"

ATTR_BIN = "bin"
ATTR_PUT_OUT = "put_out"
ATTR_ORIGINAL_DATE = "original_date"
ATTR_NEW_DATE = "new_date"
ATTR_DATE = "date"

# Frontend card served by the integration (written separately).
CARD_FILENAME = "bins-out-card.js"
CARD_URL_BASE = f"/{DOMAIN}_static"
# The "Bins" sidebar page: the card on a page of its own, so nobody has to build a dashboard.
PANEL_FILENAME = "bins-out-panel.js"
PANEL_URL_PATH = "bins-out"
PANEL_TITLE = "Bins"
PANEL_ICON = "mdi:delete-empty"
# hass.data key: {filename: fingerprinted URL} for the files in frontend/.
DATA_FRONTEND_URLS = f"{DOMAIN}_frontend_urls"

UPCOMING_COUNT = 6
STORAGE_VERSION = 1
