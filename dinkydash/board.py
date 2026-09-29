"""Turn stored iCal events into the seven-day visual calendar."""

import hashlib
from datetime import datetime, timedelta

from .calendars import events_on
from .clock import clock_of, format_time
from .schedule import refresh_interval

CALENDAR_START_HOUR = 8
CALENDAR_END_HOUR = 18
CALENDAR_COLOURS = ("sage", "lilac", "apricot", "sky", "butter", "rose")
SPANISH_MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
SPANISH_WEEKDAYS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
SPANISH_LONG_WEEKDAYS = (
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
)


def _week_start(day):
    return day - timedelta(days=day.weekday())


def _minutes(value, fallback):
    """Minutes after midnight from an ISO datetime or HH:MM string."""
    if not value:
        return fallback
    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value)
            return parsed.hour * 60 + parsed.minute
        hour, minute = value.split(":", 1)
        return int(hour) * 60 + int(minute[:2])
    except (TypeError, ValueError):
        return fallback


def _calendar_colour(label):
    # Stable pseudo-random colour: calendars look distinct without changing
    # colour every time the wall display refreshes.
    digest = hashlib.sha256((label or "Calendar").encode("utf-8")).digest()[0]
    return CALENDAR_COLOURS[digest % len(CALENDAR_COLOURS)]


def calendar_event(event, clock):
    """Add the geometry and labels used by the ten-hour visual timeline."""
    shown = as_shown([event], clock)[0]
    start = CALENDAR_START_HOUR * 60 if event.get("all_day") else _minutes(
        event.get("start") or event.get("time"), CALENDAR_START_HOUR * 60
    )
    default_end = start + (45 if event.get("all_day") else 60)
    end = _minutes(event.get("end"), default_end)
    start = max(CALENDAR_START_HOUR * 60, min(start, CALENDAR_END_HOUR * 60 - 15))
    end = max(start + 15, min(end, CALENDAR_END_HOUR * 60))
    span = (CALENDAR_END_HOUR - CALENDAR_START_HOUR) * 60
    shown.update({
        "top": (start - CALENDAR_START_HOUR * 60) * 100 / span,
        "height": (end - start) * 100 / span,
        "short": end - start <= 60,
        "colour": _calendar_colour(event.get("calendar")),
        "end_time": format_time(event.get("end"), clock) if event.get("end") else "",
    })
    return shown


def week_view(events, displayed_day, clock, actual_today=None):
    """Seven Monday-to-Sunday columns, including empty days."""
    first = _week_start(displayed_day)
    actual_today = actual_today or displayed_day
    days = []
    for offset in range(7):
        day = first + timedelta(days=offset)
        days.append({
            "date": day,
            "iso": day.isoformat(),
            "number": day.strftime("%d"),
            "name": SPANISH_WEEKDAYS[offset],
            "long_name": f"{SPANISH_LONG_WEEKDAYS[offset]}, {day.day} de "
                         f"{SPANISH_MONTHS[day.month - 1]}",
            "today": day == actual_today,
            "events": [calendar_event(event, clock) for event in events_on(events, day)],
        })
    return days

# Nothing pushes to the dashboard, so it reloads itself on a timer. Five minutes is
# the ceiling — it is a panel on a wall, not a page anyone is watching — and
# reloading faster than the calendars are fetched only shows the same thing
# again, so a shorter `refresh_minutes` is the only thing that lowers it.
MAX_RELOAD_SECONDS = 300
# Before the first run there is nothing to show, so ask more often: the screen
# then fills itself in a minute after the dashboard is written rather than five.
WAITING_RELOAD_SECONDS = 60


def as_shown(events, clock):
    """The same events, each time written the way this family reads it.

    Stored events carry `%H:%M` with the full ISO `start` beside it, so the
    displayed time is recomputed here rather than baked in at fetch time — a
    change to the setting then shows on the next redraw instead of waiting for
    the next calendar refresh. Copies rather than mutates: the payload it reads
    from belongs to the caller.
    """
    shown = []
    for event in events:
        if event.get("all_day"):
            shown.append(event)
            continue
        written = format_time(event.get("start") or event.get("time"), clock)
        shown.append({**event, "time": written or event.get("time")})
    return shown


def reload_seconds(config):
    """How long the dashboard waits before rendering itself again.

    Config-derived, so it is computed here rather than written into the
    template: a family that fetches every 15 minutes still reloads every 5, and
    only an interval shorter than that pulls it down.
    """
    return min(MAX_RELOAD_SECONDS, int(refresh_interval(config).total_seconds()))


def build_view(config, payload, today, now=None, displayed_day=None):
    """Build the calendar-only view model."""
    theme = config.get("theme", "light")
    theme = theme if theme in ("light", "dark") else "light"
    clock = clock_of(config)
    displayed_day = displayed_day or today
    first = _week_start(displayed_day)
    reference = first + timedelta(days=3)
    fetched = (payload or {}).get("events") or []
    month = SPANISH_MONTHS[reference.month - 1]
    return {
        "family_name": config.get("family_name", ""),
        "theme": theme,
        "clock": clock,
        "state": "ready" if payload is not None else "waiting",
        "set_up": True,
        "reload_seconds": reload_seconds(config) if payload is not None else WAITING_RELOAD_SECONDS,
        "today": today.isoformat(),
        "timezone": config.get("timezone") or "UTC",
        "week_days": week_view(fetched, displayed_day, clock, actual_today=today),
        "calendar_hours": list(range(CALENDAR_START_HOUR, CALENDAR_END_HOUR)),
        "month_display": f"{month.capitalize()} {reference.year}",
        "week_number": first.isocalendar().week,
        "previous_week": (first - timedelta(days=7)).isoformat(),
        "next_week": (first + timedelta(days=7)).isoformat(),
        "current_week": _week_start(today).isoformat(),
        "is_current_week": first == _week_start(today),
    }


def build_lapsed_view(config, payload, show_last_board):
    """Show the retained calendar, or the ended state when none may be shown."""
    if show_last_board and payload is not None:
        view = build_view(config, payload, datetime.now().date())
        view["state"] = "frozen"
        return view
    return {
        "state": "ended", "family_name": "", "reload_seconds": MAX_RELOAD_SECONDS,
        "theme": "dark" if config.get("theme") == "dark" else "light",
        "clock": clock_of(config), "timezone": config.get("timezone") or "UTC",
    }
