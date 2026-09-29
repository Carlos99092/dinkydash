"""Decide when calendar feeds need to be refreshed."""

import logging
from datetime import datetime, timedelta, timezone


log = logging.getLogger(__name__)

DEFAULT_REFRESH_MINUTES = 60

# Below a minute the tick interval is the real limit anyway, and zero would
# mean "fetch on every tick, forever".
MIN_REFRESH_MINUTES = 1


def due(config, payload, now):
    """`{"refresh": bool}` for this moment.

    `now` must be an aware datetime; the caller owns the clock.
    """
    payload = payload or {}
    return {"refresh": refresh_due(config, payload, now)}


def refresh_due(config, payload, now):
    """True when the stored agenda is older than `refresh_minutes`."""
    fetched = parse_stamp(payload.get("calendars_fetched_at"))
    if fetched is None:
        return True
    if fetched > now:
        # A stamp from the future means the clock moved, not that the fetch is
        # fresh. Fetching is free, so believe the clock rather than the file.
        return True
    return now - fetched >= refresh_interval(config)


def refresh_interval(config):
    """`refresh_minutes` as a timedelta, falling back to the default."""
    raw = config.get("refresh_minutes")
    try:
        minutes = int(raw) if raw is not None else DEFAULT_REFRESH_MINUTES
    except (TypeError, ValueError):
        log.warning("refresh_minutes is not a number (%r); using %d", raw, DEFAULT_REFRESH_MINUTES)
        minutes = DEFAULT_REFRESH_MINUTES
    return timedelta(minutes=max(minutes, MIN_REFRESH_MINUTES))


def parse_stamp(value):
    """A payload timestamp as an aware datetime, or None if there isn't one.

    Stamps are written in UTC. A naive one comes from an older payload, and is
    read as UTC rather than as the server's clock — which on a Pi is often not
    the family's clock at all.
    """
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        log.warning("Unreadable timestamp in the payload (%r); treating it as absent", value)
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
