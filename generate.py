#!/usr/bin/env python3
"""Refresh the calendar dashboard from cron or the command line."""

import argparse
import logging
import sys
from contextlib import contextmanager
from datetime import date, datetime, timezone

try:
    import fcntl  # POSIX only; the dashboard runs on a Pi
except ImportError:  # pragma: no cover - Windows has no flock
    fcntl = None

from dotenv import load_dotenv

from dinkydash import config as config_module
from dinkydash.errors import GenerationError
from dinkydash.runner import refresh_calendars, run
from dinkydash.schedule import due
from dinkydash.store import FileStore

load_dotenv()
log = logging.getLogger("dinkydash")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate the DinkyDash dashboard.")
    parser.add_argument("--config", help="path to config.yaml")
    parser.add_argument("--date", help="generate for this date (YYYY-MM-DD) instead of today")
    parser.add_argument("--tick", action="store_true",
                        help="do only what is due now, and nothing when nothing is")
    parser.add_argument("--quiet", action="store_true", help="only log warnings and errors")
    args = parser.parse_args(argv)

    if args.tick and args.date:
        parser.error("--tick works from the real clock; --date is for one-off runs")

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    # Generated data sits beside the config it was generated from, so --config
    # moves the payload and the history with it.
    store = FileStore(args.config)
    try:
        config = store.load_config()
    except FileNotFoundError:
        log.error("No config found at %s. Copy config.example.yaml to config.yaml.",
                  store.config_path)
        return 1

    if args.tick:
        with only_one_tick(store.base / LOCK_FILE) as mine:
            if not mine:
                log.warning("A previous tick is still running; skipping this one.")
                return 0
            return tick(config, store)

    today = date.fromisoformat(args.date) if args.date else config_module.today_for(config)
    try:
        payload = run(config, store, today=today)
    except GenerationError as exc:
        # The previous dashboard is left in place rather than blanking the screen.
        log.error("%s", exc)
        log.error("Keeping the previous dashboard.")
        return 1

    report(payload)
    return 0


LOCK_FILE = ".tick.lock"


@contextmanager
def only_one_tick(path):
    """Hold an exclusive lock for the tick, or yield False and let it be skipped.

    Slow calendar feeds can outlive a cron slot, so overlapping refreshes are
    skipped and the next tick tries again.
    """
    if fcntl is None:
        yield True
        return
    handle = open(path, "a")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True
    finally:
        handle.close()  # releases the lock, and so does the process exiting


def tick(config, store, budget=None):
    """Do what the clock and the config say is owed, and no more.

    The optional budget object only checks whether this family may refresh.
    """
    now = datetime.now(timezone.utc)
    payload = store.load_payload(config)
    owed = due(config, payload, now)

    if not any(owed.values()):
        # With a */5 cron line this is the normal case, so it is logged below
        # the default level — otherwise it would be the whole of generate.log.
        log.debug("Nothing due")
        return 0

    try:
        if owed["refresh"]:
            refresh_calendars(config, store, now=now, budget=budget)
    except GenerationError as exc:
        log.error("%s", exc)
        log.error("Keeping the previous dashboard; the next tick will try again.")
        return 1
    return 0


def report(payload):
    log.info("Calendar refreshed: %d events", len(payload.get("events") or []))


if __name__ == "__main__":
    sys.exit(main())
