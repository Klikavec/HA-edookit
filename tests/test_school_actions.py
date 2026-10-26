"""Only a deliberate, verified item action may write to the portal."""

from urllib.parse import urlparse

import pytest

from custom_components.edookit.api import EdookitClient, EdookitError
from custom_components.edookit.parsers import parse_assignments

from .test_api import BASE, FakeSession


def homework_page(done=False):
    progress = (
        '<div class="finished_assignment"></div>'
        '<input name="assignments[u90001]" type="submit" value="Zrušit označení">'
        if done
        else """
        <input type="checkbox" name="assignments[90001]">
        <input type="hidden" name="assignments[h90001]" value="">
        <input type="submit" name="assignments[s90001]" value="Označit jako hotové">"""
    )
    return f"""<div class="assignmentsContainer"><form method="post" action="/assignments/">
      <input type="hidden" name="_do" value="assignmentsGrid-finishAssignment-submit">
      <input type="hidden" name="_token_" value="synthetic-csrf-token">
      <input type="hidden" name="fragment" value="">
      <input type="hidden" name="assignments[h90002]" value="untouched">
      <ul class="table_row"><li class="c1"><p><b>26. 10. 2026 8:00</b></p>
      <p>Matematika<span class="link_info">M - X</span></p></li>
      <li class="c2"><a href="/assignments/detail?assignment=90001">Synthetic homework</a><p>Page 3</p></li>
      <li class="c3">{progress}</li></ul></form></div>"""


def test_finished_assignment_marker_without_checkbox_is_done():
    assert parse_assignments(homework_page(True))[0]["done"] is True
    assert (
        parse_assignments(homework_page(True).replace('<div class="finished_assignment"></div>', ""))[0]["done"] is True
    )
    assert parse_assignments(homework_page(False))[0]["done"] is False


async def test_completion_posts_only_selected_item_and_confirms_server_state():
    finished = False
    posted = []

    def handler(method, url, **kwargs):
        nonlocal finished
        assert urlparse(url).path == "/assignments/"
        if method == "POST":
            posted.append(kwargs["data"])
            assert kwargs["headers"]["Origin"] == BASE
            finished = True
        return 200, {}, homework_page(finished)

    session = FakeSession(handler)
    client = EdookitClient(session, "skola", "parent@example.com", "synthetic")
    client.logged_in = True
    assert await client.async_complete_assignment("/assignments/detail?assignment=90001") is True
    assert len(posted) == 1
    assert posted[0]["assignments[90001]"] == "on"
    assert posted[0]["_token_"] == "synthetic-csrf-token"
    assert "assignments[s90001]" in posted[0]
    assert not any(key.startswith("assignments[u") or "90002" in key for key in posted[0])


async def test_completed_item_is_idempotent_and_never_unchecked():
    session = FakeSession(lambda method, url, **kw: (200, {}, homework_page(True)))
    client = EdookitClient(session, "skola", "parent@example.com", "synthetic")
    client.logged_in = True
    assert await client.async_complete_assignment("/assignments/detail?assignment=90001") is False
    assert all(method == "GET" for method, _, _ in session.calls)


async def test_actions_reject_unknown_or_external_targets():
    session = FakeSession(lambda method, url, **kw: (200, {}, homework_page()))
    client = EdookitClient(session, "skola", "parent@example.com", "synthetic")
    client.logged_in = True
    for target in (
        "https://evil.example/assignments/detail?assignment=90001",
        "/payments/detail?assignment=90001",
        "/assignments/detail?assignment=not-an-id",
    ):
        with pytest.raises(EdookitError):
            await client.async_complete_assignment(target)
    assert session.calls == []
    with pytest.raises(EdookitError):
        await client.async_complete_assignment("/assignments/detail?assignment=99999")
    assert all(method == "GET" for method, _, _ in session.calls)
