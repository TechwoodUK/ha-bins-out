"""Tests for the pure schedule logic."""

from datetime import date, datetime, time, timedelta

from custom_components.bins_out.schedule import (
    BinSchedule,
    compute_state,
    dates_from_events,
    evening_message,
    forgotten_message,
    guess_colour,
    guess_container,
    guess_repeat_weeks,
    learn_repeat_weeks,
    spoken_name,
    usual_weekday,
)

EVENING = time(19)
COLLECTION = time(7)
TUE = date(2026, 10, 27)  # a Tuesday


def state(sched, when, put_out_for=None):
    return compute_state(sched, when, put_out_for, EVENING, COLLECTION)


def test_weekly_and_fortnightly():
    weekly = BinSchedule(TUE, 1)
    assert weekly.collections(date(2026, 10, 26), date(2026, 11, 10)) == [
        date(2026, 10, 27),
        date(2026, 11, 3),
        date(2026, 11, 10),
    ]
    fortnightly = BinSchedule(TUE, 2)
    assert fortnightly.next_collection(date(2026, 10, 28)) == date(2026, 11, 10)
    # Anchor in the past: phase is preserved.
    assert BinSchedule(date(2025, 1, 7), 2).next_collection(date(2026, 10, 26)) == date(
        2026, 10, 27
    )


def test_nothing_before_first_collection():
    assert BinSchedule(TUE, 1).collections(date(2026, 10, 1), date(2026, 10, 26)) == []


def test_moved_collection():
    sched = BinSchedule(TUE, 1, moved={date(2026, 11, 3): date(2026, 11, 5)})
    assert sched.collections(date(2026, 11, 1), date(2026, 11, 8)) == [date(2026, 11, 5)]
    assert sched.next_collection(date(2026, 11, 1)) == date(2026, 11, 5)


def test_extra_collection_via_move_of_non_regular_date():
    sched = BinSchedule(TUE, 2, moved={date(2026, 11, 1): date(2026, 11, 2)})
    assert date(2026, 11, 2) in sched.collections(date(2026, 10, 28), date(2026, 11, 9))


def test_status_progression():
    sched = BinSchedule(TUE, 1)
    s = state(sched, datetime(2026, 10, 24, 12))
    assert (s.status, s.days_until, s.due) == ("upcoming", 3, False)

    s = state(sched, datetime(2026, 10, 26, 12))
    assert (s.status, s.due) == ("tomorrow", False)
    s = state(sched, datetime(2026, 10, 26, 19, 30))
    assert (s.status, s.due) == ("tomorrow", True)

    s = state(sched, datetime(2026, 10, 27, 6, 0))
    assert (s.status, s.due) == ("today", True)
    s = state(sched, datetime(2026, 10, 27, 8, 0))
    assert (s.status, s.forgotten, s.due) == ("forgotten", True, False)

    # Next day moves on to the following week.
    s = state(sched, datetime(2026, 10, 28, 0, 1))
    assert (s.next_collection, s.status) == (date(2026, 11, 3), "upcoming")


def test_put_out():
    sched = BinSchedule(TUE, 1)
    s = state(sched, datetime(2026, 10, 26, 20), put_out_for=TUE)
    assert (s.status, s.put_out, s.due) == ("out", True, False)
    s = state(sched, datetime(2026, 10, 27, 9), put_out_for=TUE)
    assert (s.status, s.forgotten) == ("collected", False)
    # Stale put-out doesn't carry to the next collection.
    s = state(sched, datetime(2026, 10, 28, 9), put_out_for=TUE)
    assert (s.status, s.put_out) == ("upcoming", False)


def test_messages():
    assert spoken_name("Recycling", "blue") == "blue recycling bin"
    assert spoken_name("Black bin", "black") == "black bin"
    assert evening_message([]) is None
    assert evening_message(["blue recycling bin", "green garden bin"]) == (
        "Reminder: put the blue recycling bin and the green garden bin out tonight. "
        "Collection is tomorrow."
    )
    assert forgotten_message(["black bin"]) == (
        "Looks like the black bin was not put out for collection today."
    )


def test_cancelled_regular_collection():
    sched = BinSchedule(TUE, 2, cancelled=frozenset({TUE}))
    assert sched.next_collection(date(2026, 10, 26)) == date(2026, 11, 10)
    # Several cancellations in a row still find the next real one.
    many = BinSchedule(TUE, 1, cancelled=frozenset(TUE + timedelta(weeks=i) for i in range(5)))
    assert many.upcoming(date(2026, 10, 26), 2) == [date(2026, 12, 1), date(2026, 12, 8)]


def test_cancelled_moved_collection():
    sched = BinSchedule(
        TUE, 1, moved={date(2026, 11, 3): date(2026, 11, 5)}, cancelled=frozenset({date(2026, 11, 5)})
    )
    assert sched.collections(date(2026, 11, 1), date(2026, 11, 8)) == []


def test_fixed_dates():
    days = (date(2026, 10, 27), date(2026, 11, 13), date(2027, 1, 20))
    sched = BinSchedule(fixed_dates=days, cancelled=frozenset({date(2026, 11, 13)}))
    assert sched.upcoming(date(2026, 10, 28), 6) == [date(2027, 1, 20)]
    assert BinSchedule(fixed_dates=()).next_collection(TUE) is None
    s = state(BinSchedule(fixed_dates=()), datetime(2026, 10, 26, 12))
    assert s.status == "none"


def test_dates_from_events():
    events = [
        {"start": "2026-10-27", "summary": "Grey Bin"},
        {"start": "2026-10-30T07:00:00+00:00", "summary": "Maroon bin"},
        {"start": "2026-10-30", "summary": "Food Caddy"},
        {"start": "garbage", "summary": "Grey Bin"},
    ]
    assert dates_from_events(events, "grey") == (date(2026, 10, 27),)
    assert dates_from_events(events, " MAROON ") == (date(2026, 10, 30),)
    assert dates_from_events(events, "purple") == ()


def test_guess_colour():
    # Colour named in the council's event (some councils' events are just colours).
    assert guess_colour("Maroon") == "maroon"
    assert guess_colour("Grey Bin") == "grey"
    assert guess_colour("Gray recycling") == "grey"
    assert guess_colour("Burgundy bin") == "maroon"
    # Otherwise a typical colour for the kind of waste.
    assert guess_colour("Garden Waste") == "green"
    assert guess_colour("Food Caddy") == "grey"
    assert guess_colour("Mixed Recycling") == "blue"
    assert guess_colour("General waste") == "black"
    # Otherwise the first colour no other bin uses.
    assert guess_colour("Collection", {"black", "grey"}) == "blue"
    # Colour words inside other words don't count ("Redbridge" isn't red).
    assert guess_colour("Redbridge refuse") == "black"


def test_estimates_after_published_dates():
    # Some councils: the council only publishes the next date.
    sched = BinSchedule(fixed_dates=(TUE,), repeat_weeks=1, cancelled=frozenset({TUE + timedelta(weeks=2)}))
    s = state(sched, datetime.combine(TUE - timedelta(days=1), time(12)))
    assert s.next_collection == TUE
    assert s.upcoming[:3] == [TUE, TUE + timedelta(weeks=1), TUE + timedelta(weeks=3)]
    assert s.estimated == s.upcoming[1:]
    # Reminders follow the published date only.
    assert s.status == "tomorrow"


def test_estimates_never_drive_reminders():
    # Collected yesterday, council hasn't published the next one yet.
    sched = BinSchedule(fixed_dates=(TUE,), repeat_weeks=1)
    s = state(sched, datetime.combine(TUE + timedelta(days=6), time(20)))
    assert s.next_collection is None
    assert s.status == "none" and not s.due
    assert s.upcoming[0] == TUE + timedelta(weeks=1)
    assert s.estimated == s.upcoming


def test_no_estimates_without_published_dates():
    # e.g. a garden bin paused for winter: nothing published, nothing guessed.
    sched = BinSchedule(fixed_dates=(), repeat_weeks=3)
    assert sched.estimated(TUE, TUE + timedelta(weeks=12)) == []
    assert BinSchedule(fixed_dates=(TUE,)).estimated(TUE, TUE + timedelta(weeks=12)) == []


def test_learn_repeat_weeks():
    assert learn_repeat_weeks([TUE]) is None
    assert learn_repeat_weeks([TUE, TUE + timedelta(weeks=2)]) == 2
    # A bank holiday shift (8 days) doesn't count; the last whole-week gap does.
    assert learn_repeat_weeks([TUE, TUE + timedelta(weeks=1), TUE + timedelta(days=15)]) == 1
    # A winter pause (16 weeks) doesn't either.
    assert learn_repeat_weeks([TUE, TUE + timedelta(weeks=3), TUE + timedelta(weeks=19)]) == 3


def test_guess_repeat_weeks():
    assert guess_repeat_weeks("Food", "Food") == 1
    assert guess_repeat_weeks("Kitchen caddy", "Food Waste") == 1
    assert guess_repeat_weeks("Grey", "Grey") is None


def test_estimates_stay_on_the_usual_day():
    # Bank holiday: the council moved this week's collection from Tuesday to Wednesday.
    wed = TUE + timedelta(days=1)
    sched = BinSchedule(fixed_dates=(wed,), repeat_weeks=1, usual_weekday=TUE.weekday())
    assert sched.estimated(TUE, TUE + timedelta(weeks=3)) == [
        TUE + timedelta(weeks=1),
        TUE + timedelta(weeks=2),
        TUE + timedelta(weeks=3),
    ]
    # Without a usual day the estimates follow the moved date.
    drift = BinSchedule(fixed_dates=(wed,), repeat_weeks=1)
    assert drift.estimated(TUE, TUE + timedelta(weeks=2))[0] == wed + timedelta(weeks=1)


def test_usual_weekday():
    assert usual_weekday([]) is None
    wed = TUE + timedelta(days=1)
    # Mostly Tuesdays, one Wednesday after a bank holiday.
    assert usual_weekday([TUE, TUE + timedelta(weeks=1), wed + timedelta(weeks=2)]) == TUE.weekday()
    # A tie goes to the latest (the council changed the collection day).
    assert usual_weekday([TUE, wed + timedelta(weeks=1)]) == wed.weekday()


def test_guess_container():
    assert guess_container("Food") == "food_caddy"
    assert guess_container("Kitchen", "Food Caddy") == "food_caddy"
    assert guess_container("Glass box") == "box"
    assert guess_container("Garden sack") == "bag"
    assert guess_container("Grey", "Grey") == "wheelie_bin"


def test_spoken_name_uses_the_container():
    assert spoken_name("Food", "grey", "caddy") == "grey food caddy"
    assert spoken_name("Recycling", "blue") == "blue recycling bin"
    # The name already says what it is.
    assert spoken_name("Glass box", "black", "box") == "black glass box"
    assert spoken_name("Food Caddy", "green", "caddy") == "green food caddy"
