"""Pure collection-schedule logic. No Home Assistant imports, so it is easy to test."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import re

from .const import (
    BIN_COLOURS,
    CONTAINER_BAG,
    CONTAINER_BOX,
    CONTAINER_FOOD_CADDY,
    CONTAINER_WHEELIE_BIN,
    STATUS_COLLECTED,
    STATUS_FORGOTTEN,
    STATUS_NONE,
    STATUS_OUT,
    STATUS_TODAY,
    STATUS_TOMORROW,
    STATUS_UPCOMING,
)

# How far a one-off move (e.g. bank holiday) may shift a collection.
MAX_SHIFT = timedelta(days=14)


@dataclass(frozen=True)
class BinSchedule:
    """When a bin is collected.

    Either regular (every `interval_weeks` weeks from `first_collection`) or, when
    `fixed_dates` is set, exactly those dates (e.g. read from a council calendar).
    One-off `moved` and `cancelled` dates are applied on top of both.

    Some councils only publish the next date. With `repeat_weeks`, `estimated()` guesses
    the ones after the last published date. Estimates are for showing ahead only:
    reminders use the published dates.
    """

    first_collection: date | None = None
    interval_weeks: int = 1
    fixed_dates: tuple[date, ...] | None = None
    moved: dict[date, date] = field(default_factory=dict)
    cancelled: frozenset[date] = frozenset()
    repeat_weeks: int | None = None
    usual_weekday: int | None = None  # estimates stay on this day (0 = Monday)

    def _base(self, start: date, end: date) -> list[date]:
        if self.fixed_dates is not None:
            return [d for d in self.fixed_dates if start <= d <= end]
        if self.first_collection is None or end < self.first_collection:
            return []
        step = timedelta(weeks=self.interval_weeks)
        if start <= self.first_collection:
            current = self.first_collection
        else:
            periods = -(-(start - self.first_collection).days // step.days)
            current = self.first_collection + step * periods
        dates = []
        while current <= end:
            dates.append(current)
            current += step
        return dates

    def collections(self, start: date, end: date) -> list[date]:
        """Collection dates in [start, end], with moves and cancellations applied."""
        candidates = self._base(start - MAX_SHIFT, end + MAX_SHIFT)
        # Moves whose original date isn't a scheduled date act as extra collections.
        extra = [d for d in self.moved if d not in candidates]
        result = {self.moved.get(d, d) for d in [*candidates, *extra]} - self.cancelled
        return sorted(d for d in result if start <= d <= end)

    def next_collection(self, today: date) -> date | None:
        """The first collection on or after `today`."""
        found = self.upcoming(today, 1)
        return found[0] if found else None

    def upcoming(self, today: date, count: int) -> list[date]:
        """The next `count` collections on or after `today`."""
        if self.fixed_dates is not None:
            end = max((*self.fixed_dates, *self.moved.values()), default=today)
        else:
            # Each cancellation can push the window out by one more collection.
            weeks = self.interval_weeks * (count + len(self.cancelled))
            end = today + timedelta(weeks=weeks) + MAX_SHIFT
        return self.collections(today, end)[:count]

    def estimated(self, start: date, end: date) -> list[date]:
        """Likely collections in [start, end] after the last published date.

        Nothing is guessed when nothing is published (e.g. a garden bin paused for winter).
        If the last published date was shifted off the usual day (e.g. a bank holiday),
        the estimates after it go back to the usual day.
        """
        if self.fixed_dates is None or not self.repeat_weeks:
            return []
        known = [*self.fixed_dates, *self.moved.values()]
        if not known:
            return []
        last = max(known)
        anchor = last
        if self.usual_weekday is not None:
            # Nearest usual day, at most 3 days either side.
            anchor = last + timedelta(days=(self.usual_weekday - last.weekday() + 3) % 7 - 3)
        step = timedelta(weeks=self.repeat_weeks)
        current = anchor + step
        while current <= last:
            current += step
        dates = []
        while current <= end:
            if current >= start and current not in self.cancelled:
                dates.append(current)
            current += step
        return dates


@dataclass(frozen=True)
class BinState:
    """Everything the entities need to know about a bin at a moment in time."""

    next_collection: date | None
    days_until: int | None
    status: str
    put_out: bool
    due: bool
    forgotten: bool
    upcoming: list[date]  # published and estimated, for showing ahead
    estimated: list[date] = field(default_factory=list)  # which of `upcoming` are guesses


def compute_state(
    schedule: BinSchedule,
    now: datetime,
    put_out_for: date | None,
    evening_time: time,
    collection_time: time,
    upcoming_count: int = 6,
) -> BinState:
    """Work out a bin's state.

    `put_out_for` is the collection date the user said the bin was put out for.
    Stale values (before today) are ignored.
    """
    today = now.date()
    clock = now.time()
    published = schedule.upcoming(today, upcoming_count)
    horizon = today + timedelta(weeks=(schedule.repeat_weeks or 1) * upcoming_count)
    guesses = schedule.estimated(today, horizon)
    upcoming = sorted({*published, *guesses})[:upcoming_count]
    estimated = [d for d in upcoming if d not in published]
    # Reminders only ever follow published dates.
    nxt = published[0] if published else None

    if nxt is None:
        return BinState(None, None, STATUS_NONE, False, False, False, upcoming, estimated)

    days = (nxt - today).days
    put_out = put_out_for is not None and put_out_for == nxt
    forgotten = False

    if days == 0:
        if put_out:
            status = STATUS_COLLECTED if clock >= collection_time else STATUS_OUT
        elif clock >= collection_time:
            status = STATUS_FORGOTTEN
            forgotten = True
        else:
            status = STATUS_TODAY
        # Should go out now: collection day, not yet out, before the lorry comes.
        due = not put_out and clock < collection_time
    elif days == 1:
        status = STATUS_OUT if put_out else STATUS_TOMORROW
        due = not put_out and clock >= evening_time
    else:
        status = STATUS_OUT if put_out else STATUS_UPCOMING
        due = False

    return BinState(nxt, days, status, put_out, due, forgotten, upcoming, estimated)


def learn_repeat_weeks(seen: list[date]) -> int | None:
    """How many weeks apart a bin's collections are, from dates seen so far.

    Uses the latest gap that is a whole number of weeks (1-8), so a one-off bank holiday
    shift or a winter pause doesn't change it.
    """
    days = sorted(set(seen))
    for earlier, later in reversed(list(zip(days, days[1:]))):
        gap = (later - earlier).days
        if gap % 7 == 0 and 1 <= gap // 7 <= 8:
            return gap // 7
    return None


def usual_weekday(dates: list[date]) -> int | None:
    """The day of the week most collections fall on (latest wins a tie)."""
    if not dates:
        return None
    counts: dict[int, int] = {}
    for d in sorted(dates):
        counts[d.weekday()] = counts.get(d.weekday(), 0) + 1
    latest = max(dates).weekday()
    return max(counts, key=lambda wd: (counts[wd], wd == latest))


def guess_repeat_weeks(*names: str) -> int | None:
    """A starting guess before any gap has been seen: food caddies are weekly."""
    return 1 if any("food" in n.lower() for n in names) else None


def dates_from_events(events: list[dict], match: str) -> tuple[date, ...]:
    """Dates of calendar events whose summary contains `match` (case-insensitive).

    `events` are as returned by `calendar.get_events`: `start` is an ISO date or
    a local ISO datetime, so the first 10 characters are the local date.
    """
    needle = match.strip().lower()
    found = set()
    for event in events:
        if needle not in str(event.get("summary", "")).lower():
            continue
        try:
            found.add(date.fromisoformat(str(event.get("start", ""))[:10]))
        except ValueError:
            continue
    return tuple(sorted(found))


CONTAINER_WORDS = ("bin", "caddy", "box", "bag", "sack")


def spoken_name(name: str, colour: str, noun: str = "bin") -> str:
    """'Recycling' + 'blue' -> 'blue recycling bin'; 'Food' + 'grey' + 'caddy' -> 'grey food caddy'."""
    text = name.strip().lower()
    if colour and colour.lower() not in text:
        text = f"{colour.lower()} {text}"
    if not any(word in text for word in CONTAINER_WORDS):
        text = f"{text} {noun}"
    return text


def guess_container(*names: str) -> str:
    """What kind of container a bin probably is, from its name or the council's event name."""
    text = " ".join(names).lower()
    if "food" in text or "caddy" in text:
        return CONTAINER_FOOD_CADDY
    if "box" in text:
        return CONTAINER_BOX
    if "bag" in text or "sack" in text:
        return CONTAINER_BAG
    return CONTAINER_WHEELIE_BIN


COLOUR_ALIASES = {"gray": "grey", "burgundy": "maroon", "claret": "maroon", "navy": "blue"}
# Typical UK colours when the council's event name doesn't say, e.g. "Garden Waste".
WASTE_TYPE_COLOURS = (
    ("garden", "green"),
    ("food", "grey"),
    ("recycl", "blue"),
    ("paper", "blue"),
    ("glass", "purple"),
    ("general", "black"),
    ("refuse", "black"),
    ("rubbish", "black"),
    ("residual", "black"),
    ("landfill", "black"),
)


def guess_colour(event_name: str, taken: set[str] | None = None) -> str:
    """Best-guess bin colour for a council calendar event, e.g. 'Maroon Bin' -> 'maroon'.

    A colour named in the event wins, then a typical colour for the waste type, then
    the first colour no other bin uses yet.
    """
    words = [COLOUR_ALIASES.get(w, w) for w in re.findall(r"[a-z]+", event_name.lower())]
    for word in words:
        if word in BIN_COLOURS:
            return word
    text = event_name.lower()
    for keyword, colour in WASTE_TYPE_COLOURS:
        if keyword in text:
            return colour
    taken = taken or set()
    return next((c for c in BIN_COLOURS if c not in taken), "black")


def join_names(names: list[str]) -> str:
    """['a', 'b', 'c'] -> 'the a, the b and the c'."""
    parts = [f"the {n}" for n in names]
    if len(parts) <= 1:
        return "".join(parts)
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def evening_message(names: list[str]) -> str | None:
    if not names:
        return None
    return f"Reminder: put {join_names(names)} out tonight. Collection is tomorrow."


def morning_message(names: list[str]) -> str | None:
    if not names:
        return None
    return f"It's bin day! Put {join_names(names)} out now."


def forgotten_message(names: list[str]) -> str | None:
    if not names:
        return None
    verb = "were" if len(names) > 1 else "was"
    return f"Looks like {join_names(names)} {verb} not put out for collection today."
