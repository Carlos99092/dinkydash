"""What a new family still has to do, worked out from the config.

The settings home has two personalities. While a family is being set up it
shows a checklist that leads somewhere; once the first dashboard is written it
shows the day's controls. Which one, and which steps are done, is decided
here from the config and the stored dashboard and nothing else — no stored
"onboarding step", no mode check — so a freshly cloned Pi running the
untouched example file gets the same checklist as a hosted family five
seconds old.

`config.is_set_up` is the engine's half of the same question: it is what
holds the first brief back until the answers are real, and the two must keep
agreeing. That is why every "done" below is read off the same helpers rather
than decided here.
"""

from flask import url_for

from dinkydash import config as config_module


def status(config, payload):
    """The checklist, and whether the page should be showing it.

    `in_progress` while the family is not set up *or* no brief has been
    written yet — the second half because a set-up family waiting for its
    first dashboard still wants the screen link and the button, not a status line
    about a dashboard that does not exist. `ready` is when the screen step may be
    shown: the household is real and the timezone chosen, so a dashboard written
    now would be theirs.
    """
    set_up = config_module.is_set_up(config)
    return {
        "in_progress": not set_up,
        "ready": set_up,
        "written": bool((payload or {}).get("calendars_fetched_at")),
        "steps": [timezone(config), calendar(config)],
    }


def timezone(config):
    """Step one: the one setting that changes what the dashboard says."""
    done = config_module.timezone_is_set(config)
    return {
        "key": "timezone", "title": "Time zone", "done": done,
        "detail": config.get("timezone") if done else (
            "Still UTC. It decides when the day rolls over, when the morning's "
            "line is written, and what time an appointment shows."),
        "href": url_for("settings.system"),
    }


def calendar(config):
    """Step two: optional, and said to be — but it is the product."""
    on = [c.get("label") or "Calendar" for c in config.get("calendars") or []
          if isinstance(c, dict) and c.get("enabled")]
    return {
        "key": "calendar", "title": "A calendar", "done": bool(on),
        "detail": names(on) if on else (
            "None yet. The dashboard works without one, but this is what puts "
            "today's plans on it."),
        "href": url_for("settings.section_list", section_name="calendars"),
    }


def names(items):
    """"Mia", "Mia and Theo", "Mia, Theo and Biscuit"."""
    items = [str(item) for item in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]
