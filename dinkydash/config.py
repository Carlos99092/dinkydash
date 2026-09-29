"""Reading and writing config.yaml.

The settings UI writes this file back, so loads and saves go through ruamel's
round-trip mode: your comments and key order survive an edit made from a phone.
"""

import logging
import os
import secrets
import tempfile
from datetime import datetime
from pathlib import Path

from ruamel.yaml import YAML

from .calendars import addresses, zone
from .clock import CLOCKS, DEFAULT_CLOCK

log = logging.getLogger(__name__)

DEFAULTS = {
    "family_name": "Our family",
    "timezone": "UTC",
    # Beside the timezone because the two are read together: one decides what a
    # time *is*, the other how it is written.
    "clock": DEFAULT_CLOCK,
    "theme": "light",
    "calendars": [],
    "calendar_days_ahead": 14,
    # Read by `generate.py --tick` to decide when to fetch again.
    "refresh_minutes": 60,
    # Storage-layer keys, read only by dinkydash.store.FileStore. They say
    # where a self-hoster's generated files go and mean nothing in cloud mode,
    # where the same two things are rows.
    "data_file": "dashboard_data.json",
}

THEMES = ("light", "dark")

# The lists the settings UI edits. Every item in them carries a stable `id`.
LIST_KEYS = ("calendars",)

# Ids are short and typed by nobody, but they end up in URLs and get read aloud
# when something goes wrong, so leave out the characters that look like others.
ID_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
ID_LENGTH = 8

# A screen URL is read off a television and typed on a remote, so it uses the
# same unambiguous alphabet — 12 characters of it is about 59 bits, and the
# route rate-limits misses. The column allows 10 to 32.
SCREEN_TOKEN_LENGTH = 12


def _yaml():
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # don't rewrap long iCal URLs onto continuation lines
    # Indent list items under their key, the way the example file is written —
    # otherwise the first save from the UI re-indents the whole file and every
    # later diff is noise.
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def config_path():
    """Where config.yaml lives. Override with DINKYDASH_CONFIG."""
    return Path(os.environ.get("DINKYDASH_CONFIG", "config.yaml")).expanduser()


def load_config(path=None):
    """Load config.yaml, applying defaults and migrating old shapes."""
    path = Path(path) if path else config_path()
    with open(path) as f:
        raw = _yaml().load(f) or {}
    return with_defaults(raw)


def save_config(config, path=None):
    """Write config.yaml atomically, preserving comments and key order."""
    path = Path(path) if path else config_path()
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            _yaml().dump(config, f)
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    log.info("Wrote %s", path)


def with_defaults(raw):
    """Fill in defaults and migrate pre-multi-calendar config in place."""
    config = raw
    for key, value in DEFAULTS.items():
        if config.get(key) is None:
            config[key] = [] if isinstance(value, list) else value

    # A single calendar_url becomes the first entry in `calendars`, and the
    # global calendar_filter_emails that went with it becomes that entry's
    # `shared_with`. The old key meant what the new one means — show me the
    # events my partner is on — but it was one filter for the one URL, so it
    # only has a home when that URL is what is being migrated.
    legacy_url = config.pop("calendar_url", None)
    legacy_filter = addresses(config.pop("calendar_filter_emails", None))
    if legacy_url and not config["calendars"]:
        feed = {"label": "Calendar", "url": legacy_url, "enabled": True}
        if legacy_filter:
            feed["shared_with"] = legacy_filter
        config["calendars"] = [feed]
        log.info("Migrated calendar_url into calendars[]")
    elif legacy_filter:
        log.warning(
            "Ignoring calendar_filter_emails: it was one filter for one calendar_url. "
            "Put the addresses under `shared_with` on the calendar they were meant for."
        )

    if config.get("theme") not in THEMES:
        config["theme"] = "light"
    # Coerced rather than trusted for the same reason as the theme: this value
    # arrives from a hand-edited file or a jsonb column, and an unrecognised
    # one should fall back to the default rather than reach a formatter.
    if config.get("clock") not in CLOCKS:
        config["clock"] = DEFAULT_CLOCK

    return config


def new_id(taken=()):
    """A short id for a list item, avoiding any already in `taken`."""
    taken = set(taken)
    while True:
        value = "".join(secrets.choice(ID_ALPHABET) for _ in range(ID_LENGTH))
        if value not in taken:
            return value


def new_screen_token():
    """The unguessable part of a family's dashboard URL.

    A bearer credential: whoever holds it sees the dashboard, which is the whole
    point — a wall panel cannot sign in. Rotatable from the settings page, so
    this is called again rather than once per family for ever.
    """
    return "".join(secrets.choice(ID_ALPHABET)
                   for _ in range(SCREEN_TOKEN_LENGTH))


def starter_config():
    """A blank calendar configuration with no invented household data."""
    config = with_defaults({"family_name": "Mi calendario"})
    for key in ("data_file",):
        config.pop(key, None)
    return config


def ensure_ids(config):
    """Give every list item an id. True if any were added.

    A position is not an identity: calendar ids keep edit URLs stable when
    feeds are reordered or removed.

    Deliberately not part of load_config — loading must not rewrite the file,
    and the engine never looks at ids. The settings UI calls this and saves.
    """
    added = False
    for key in LIST_KEYS:
        items = config.get(key) or []
        taken = {item.get("id") for item in items if isinstance(item, dict)}
        for item in items:
            if not isinstance(item, dict) or item.get("id"):
                continue
            _add_id(item, new_id(taken))
            taken.add(item["id"])
            added = True
    return added


def _add_id(item, value):
    """Put the id first in the mapping.

    Appending looks tidier but breaks the file: ruamel hangs the blank line and
    comment that introduce the *next* section off the last item of this one, so
    an appended key lands underneath somebody else's heading. First is safe
    everywhere, and it is where a database would put it anyway.
    """
    insert = getattr(item, "insert", None)  # ruamel's CommentedMap has one
    if callable(insert):
        insert(0, "id", value)
    else:
        item["id"] = value


def find_item(items, item_id):
    """(index, item) for the item with this id, or (None, None)."""
    for index, item in enumerate(items or []):
        if isinstance(item, dict) and item.get("id") == item_id:
            return index, item
    return None, None


def tzinfo_for(config):
    return zone(config.get("timezone") or "UTC")


def now_for(config):
    """This moment on the family's own clock, not the server's."""
    return datetime.now(tzinfo_for(config))


def today_for(config):
    """Today's date in the family's own timezone, not the server's."""
    return now_for(config).date()


def timezone_is_set(config):
    """False while the timezone is still the default.

    The default is UTC; choosing a named zone determines the displayed day and
    appointment times.
    """
    return (config.get("timezone") or DEFAULTS["timezone"]) != DEFAULTS["timezone"]


def is_set_up(config):
    """A calendar is ready once its timezone and at least one feed are set."""
    return timezone_is_set(config) and any(
        isinstance(item, dict) and item.get("enabled", True) and item.get("url")
        for item in config.get("calendars") or []
    )
