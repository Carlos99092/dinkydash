"""The product exposes calendar configuration only."""

import re

from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app


def test_settings_home_contains_only_calendar_features(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('family_name: "Casa"\ntimezone: "Europe/Madrid"\ncalendars:\n  - label: "Familia"\n    url: "https://example.com/family.ics"\n    enabled: true\n')
    page = client_for(create_app(FileStore(path))).get("/settings/").get_data(as_text=True)
    assert "Calendarios conectados" in page
    visible = re.sub(r"<(style|script).*?</\1>|<!--.*?-->", "", page,
                     flags=re.DOTALL)
    for removed in ("People", "Pets", "Chores", "Special dates", "daily message"):
        assert removed not in visible


def test_removed_feature_routes_are_not_available(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('timezone: "Europe/Madrid"\n')
    client = client_for(create_app(FileStore(path)))
    for section in ("people", "pets", "recurring", "special_dates"):
        assert client.get(f"/settings/{section}").status_code == 404
