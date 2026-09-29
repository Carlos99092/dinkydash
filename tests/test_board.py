"""The dashboard is a calendar and nothing else."""

from datetime import date

from dinkydash.board import build_view

TODAY = date(2026, 9, 3)
CONFIG = {"family_name": "Mi calendario", "timezone": "Europe/Madrid", "theme": "light"}


def event(day, time_, title, calendar="Familia", end=None):
    return {"title": title, "date": day, "time": time_, "all_day": False,
            "start": f"{day}T{time_}:00+02:00", "end": end,
            "location": None, "calendar": calendar}


def test_builds_a_spanish_monday_to_sunday_week():
    view = build_view(CONFIG, {"events": [event("2026-09-03", "08:20", "Colegio")]}, TODAY)
    assert [day["iso"] for day in view["week_days"]] == [
        "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03",
        "2026-09-04", "2026-09-05", "2026-09-06",
    ]
    assert [day["name"] for day in view["week_days"]] == [
        "lun", "mar", "mié", "jue", "vie", "sáb", "dom",
    ]
    assert view["month_display"] == "Septiembre 2026"
    assert view["week_days"][3]["today"] is True


def test_only_calendar_data_is_exposed_to_the_template():
    view = build_view(CONFIG, {"events": []}, TODAY)
    forbidden = {"people", "pets", "chores", "countdowns", "special_dates",
                 "headline", "note", "tomorrow"}
    assert forbidden.isdisjoint(view)


def test_calendar_colours_are_stable_and_duration_controls_geometry():
    first = event("2026-09-03", "09:00", "Uno", end="2026-09-03T10:30:00+02:00")
    second = event("2026-09-04", "09:00", "Dos")
    view = build_view(CONFIG, {"events": [first, second]}, TODAY)
    events = [item for day in view["week_days"] for item in day["events"]]
    assert events[0]["colour"] == events[1]["colour"]
    assert events[0]["height"] == 15
    assert events[0]["end_time"] == "10:30"


def test_no_payload_shows_the_calendar_connection_state():
    view = build_view(CONFIG, None, TODAY)
    assert view["state"] == "waiting"
    assert view["week_days"]


def test_can_build_the_previous_or_next_week_without_moving_today():
    displayed = date(2026, 9, 10)
    view = build_view(CONFIG, {"events": []}, TODAY, displayed_day=displayed)
    assert view["week_number"] == 37
    assert view["previous_week"] == "2026-08-31"
    assert view["next_week"] == "2026-09-14"
    assert view["current_week"] == "2026-08-31"
    assert view["is_current_week"] is False
    assert not any(day["today"] for day in view["week_days"])
