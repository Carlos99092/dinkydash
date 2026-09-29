"""Fetch calendar feeds and publish the merged agenda."""

import logging
from datetime import datetime, timedelta, timezone

from . import config as config_module
from .budget import NoBudget
from .calendars import fetch_events, sort_key
from .errors import GenerationError

log = logging.getLogger(__name__)


def refresh_calendars(config, store, now=None, today=None, budget=None):
    """Re-fetch every enabled feed and store the merged agenda. No model call.

    `now` is when this is happening and becomes the `calendars_fetched_at`
    stamp. `today` is the day the fourteen-day window starts on, and defaults
    to today on the family's clock — they are the same thing except under
    `generate.py --date`, where the window is moved but the stamp is not.
    The budget checks account access here without charging a model call.
    """
    (budget or NoBudget()).check_access()
    now = now or datetime.now(timezone.utc)
    tzinfo = config_module.tzinfo_for(config)
    today = today or now.astimezone(tzinfo).date()

    days_ahead = int(config.get("calendar_days_ahead") or 14)
    events, statuses = fetch_events(
        config.get("calendars"), today, tzinfo, days_ahead=days_ahead,
    )

    # Read only to find out what a failing feed last gave us. Nothing from this
    # read is written back except the events themselves.
    previous = (store.load_payload(config) or {}).get("events")

    failed = {s["label"] for s in statuses if s["ok"] is False}
    if failed:
        log.warning("Calendars that did not answer: %s", ", ".join(sorted(failed)))
        events = _with_last_known(events, previous, failed,
                                  today, today + timedelta(days=days_ahead))

    agenda = {
        "events": events,
        "calendar_statuses": statuses,
        "calendars_fetched_at": now.astimezone(timezone.utc).isoformat(),
    }
    if not store.save_agenda(config, agenda):
        raise GenerationError("Calendar settings changed during the refresh. Please refresh again.")
    log.info("Calendars refreshed: %d events stored", len(events))
    return agenda


def _with_last_known(fresh, previous, failed_labels, start, end):
    """Fresh events, plus the last-known events of the feeds that did not answer.

    A missing event is invisible while a stale one is still on the right day —
    the previous fetch reached the same fourteen days ahead — so a feed that
    fails holds its last agenda rather than emptying it. Only that feed does:
    the ones that answered are always fresh, or a single dead URL would freeze
    the whole dashboard for as long as nobody fixed it.

    Events are kept only inside the current window, so a permanently broken feed
    empties out as the days pass instead of accumulating a tail of past events.
    """
    window = (start.isoformat(), end.isoformat())
    seen = {(e.get("calendar"), e.get("title"), e.get("start")) for e in fresh}
    kept = []
    for event in previous or []:
        if event.get("calendar") not in failed_labels:
            continue
        if not window[0] <= str(event.get("date")) <= window[1]:
            continue
        key = (event.get("calendar"), event.get("title"), event.get("start"))
        if key in seen:  # two feeds sharing one label
            continue
        seen.add(key)
        kept.append(event)
    if kept:
        log.info("Kept %d event(s) from the feeds that did not answer", len(kept))
    return sorted(fresh + kept, key=sort_key)


def run(config, store, today=None, client=None, budget=None):
    """Refresh and return the calendar. No generated text or model call."""
    return refresh_calendars(config, store, today=today, budget=budget)
