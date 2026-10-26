"""Contract regressions use synthetic data, never private portal captures."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.edookit import parsers
from custom_components.edookit.coordinator import validate_list_page
from custom_components.edookit.school import poll_delay, safe_url, school_payload, stable_items

TZ = ZoneInfo("Europe/Prague")


def test_identity_survives_description_change_and_deduplicates():
    item = {"id": "123", "title": "Procvičování", "description": "Původní"}
    first = stable_items([item, item], "homework", "student-a")
    edited = stable_items([{**item, "description": "Opravený rozsah"}], "homework", "student-a")
    assert len(first) == 1
    assert first[0]["id"] == edited[0]["id"]
    assert first[0]["id"] != stable_items([item], "homework", "student-b")[0]["id"]


@pytest.mark.parametrize(
    ("stamp", "school_day", "minutes"),
    [
        ("2026-10-26T08:00:00", True, 45),
        ("2026-10-26T17:00:00", True, 180),
        ("2026-10-28T10:00:00", False, 180),
        ("2026-10-26T23:00:00", True, 420),
        ("2026-10-25T01:00:00", False, 360),  # fall DST adds an hour before 06:00
        ("2026-03-29T01:00:00", False, 240),  # spring DST removes one
    ],
)
def test_school_and_quiet_schedules(stamp, school_day, minutes):
    assert poll_delay(datetime.fromisoformat(stamp).replace(tzinfo=TZ), school_day) == timedelta(minutes=minutes)


def test_missing_next_week_is_not_projected():
    now = datetime(2026, 10, 26, 8, tzinfo=TZ)
    payload = school_payload(
        "s",
        {"lessons": [{"date": "2026-10-26"}], "sync_status": "ok", "updated": now.isoformat()},
        {"assignments": [], "exams": [], "section_status": {"assignments": "ok", "exams": "error"}},
        "https://school.edookit.net",
        now,
    )
    assert [w["status"] for w in payload["timetable"]["weeks"]] == ["available", "unavailable"]
    assert payload["sections"]["exams"] == "error"
    assert payload["sync_status"] != "ok"


def test_empty_and_broken_pages_are_different():
    validate_list_page("<main>Domácí úkoly: žádné úkoly</main>", [], "assignments")
    with pytest.raises(ValueError):
        validate_list_page("<main>Server maintenance</main>", [], "assignments")
    with pytest.raises(ValueError):
        validate_list_page("<main>Domácí úkoly</main>", [], "assignments")


def test_nested_portal_homework_rows():
    # The shape was observed on a portal; all text, IDs and dates here are synthetic.
    html = """<div class="assignmentsContainer"><ul class="anyCourse incomplete table_row">
      <li class="c1"><h3>Termín odevzdání</h3><p><b>do 26. 10., <span>7:45</span></b></p>
        <p>Matematika<span class="link_info">M - IV.X</span></p></li>
      <li class="c2"><h3>Popis</h3><div class="bold">
        <a href="/assignments/detail?assignment=90001">Procvičování</a></div>
        <p>Sešit strana 12</p></li><li class="c3">0 %<input type="checkbox"></li>
      <li class="c4"><div class="smaller"><p><b>Test Teacher</b></p><p>23. 10. 2026, 8:31</p></div></li>
    </ul></div>"""
    item = parsers.parse_assignments(html, datetime(2026, 10, 26).date())[0]
    assert item["id"] == "90001"
    assert item["subject"] == "Matematika"
    assert item["title"] == "Procvičování"
    assert item["description"] == "Sešit strana 12"
    assert item["due"] == "2026-10-26T07:45:00"
    assert item["assigned"] == "2026-10-23T08:31:00"
    assert item["done"] is False


def test_nested_portal_exam_rows():
    html = """<div id="content"><div class="homeworks_table"><ul class="table_row">
      <li class="c1"><p><b>10. 11., od <span>7:45</span> do <span>8:30</span></b></p>
        <p>Matematika<span class="link_info">M - IV.X</span></p></li>
      <li class="c2"><a href="/exams/detail?assignment=90002">Zlomky</a><p>Kapitola 2</p></li>
      <li class="c4"><div class="smaller"><p><b>Test Teacher</b></p><p>26. 10. 2026</p></div></li>
    </ul></div></div>"""
    item = parsers.parse_exams(html, datetime(2026, 10, 26).date())[0]
    assert item["subject"] == "Matematika"
    assert item["title"] == "Zlomky"
    assert item["date"] == "2026-11-10T07:45:00"
    assert item["description"] == "Kapitola 2"


def test_portal_links_cannot_leave_school():
    base = "https://school.edookit.net"
    assert safe_url("/assignments/detail?assignment=1", base) == base + "/assignments/detail?assignment=1"
    for url in ("javascript:alert(1)", "https://evil.example/", "//evil.example/"):
        assert safe_url(url, base) is None
