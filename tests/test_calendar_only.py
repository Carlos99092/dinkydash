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


def test_board_has_week_controls_and_requested_week(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('timezone: "Europe/Madrid"\n')
    (tmp_path / "dashboard_data.json").write_text('{"events": []}')
    page = client_for(create_app(FileStore(path))).get(
        "/?week=2026-10-05").get_data(as_text=True)
    assert "Octubre 2026" in page
    assert 'aria-label="Semana anterior"' in page
    assert 'aria-label="Semana siguiente"' in page
    assert ">Hoy</a>" in page


def test_board_uses_the_requested_inter_and_space_grotesk_fonts(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('timezone: "Europe/Madrid"\n')
    (tmp_path / "dashboard_data.json").write_text('{"events": []}')
    page = client_for(create_app(FileStore(path))).get("/").get_data(as_text=True)
    assert "family=Inter:wght@400;500;600" in page
    assert "family=Space+Grotesk:wght@300;600" in page
    assert "--font-sans: 'Inter'" in page
    assert "--font-display: 'Space Grotesk'" in page
