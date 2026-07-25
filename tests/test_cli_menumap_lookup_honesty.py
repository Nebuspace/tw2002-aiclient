"""F4 — ``tw menumap`` must stop claiming "here off-map" when it never looked.

``cmd_menumap`` left ``current_sig = None`` on FOUR different failure-to-look
paths, and ``format_menu_map_lines`` has exactly one rendering for a None
``current``. So a genuine off-map result and a failed lookup were **byte-for-
byte identical** to the operator, rc 0 either way.

That matters because the two demand opposite responses. Canon reserves
off-map for ``localize()``'s own None -- "STOP, escalate, never navigate
blind" (canon/engine/menu-map-and-introspection.md:298-302) -- so an operator
reading ``here off-map`` believes a lookup ran and placed them nowhere on the
map. When the truth is "the daemon is not running", nothing was established
at all, and the fix is to start the daemon, not to escalate.

The four paths, all confirmed by execution against the pre-fix tree before
any of this was written (they produced identical five-line output and rc 0):

1. daemon not alive
2. the ``screen`` verb answered not-ok
3. ``localize()`` raised
4. the screen came back blank -- ``localize`` was never called at all

Path 4 was NOT in the original finding; it was found by running the grid
rather than reading the source, and it is the quietest of the four.
"""

from __future__ import annotations

import json
from argparse import Namespace

import pytest

from tw2002_aiclient.menu import knowledge as menu_knowledge
from tw2002_aiclient.menu import nav as menu_nav
from tw2002_aiclient.session import cli

SCREEN = "=== Computer ===\n(1) Status\n(2) Ship\n"


@pytest.fixture
def store(tmp_path):
    """A small real map, so the coverage lines below are real output."""
    path = tmp_path / "game_knowledge.json"
    menu_knowledge.upsert_menu_node(path, "sig-a", label="Computer")
    menu_knowledge.upsert_menu_node(path, "sig-b", label="Ship")
    menu_knowledge.upsert_menu_edge(path, "sig-a", "2", "sig-b", kind="nav")
    return path


def _args(store, tmp_path, *, as_json=False):
    return Namespace(
        path=str(store), world_id=None, run_dir=str(tmp_path), json=as_json
    )


def _run(monkeypatch, store, tmp_path, capsys, *, alive, screen_resp=None,
         localize=None, as_json=False):
    """Drive the real ``cmd_menumap`` with one of the five conditions wired."""
    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: alive)
    monkeypatch.setattr(
        cli, "send_request",
        lambda verb, payload, **kw: screen_resp,
    )
    if localize is not None:
        monkeypatch.setattr(menu_nav, "localize", localize)
    rc = cli.cmd_menumap(_args(store, tmp_path, as_json=as_json))
    return rc, capsys.readouterr().out


def _located(*_a, **_k):
    return {"signature": "sig-a", "label": "Computer"}


def _off_map(*_a, **_k):
    return None


def _raises(*_a, **_k):
    raise ValueError("knowledge store is unreadable")


OK_SCREEN = {"ok": True, "screen": SCREEN.splitlines()}
BLANK_SCREEN = {"ok": True, "screen": ["", "   ", ""]}
BAD_SCREEN = {"ok": False, "error": "not_connected"}


# -- each failure path must be distinguishable from a genuine off-map --------

def test_genuine_off_map_still_says_off_map(monkeypatch, store, tmp_path, capsys):
    """The one case entitled to the claim: localize ran and answered None.
    This must NOT change -- canon's escalate signal depends on it."""
    rc, out = _run(monkeypatch, store, tmp_path, capsys,
                   alive=True, screen_resp=OK_SCREEN, localize=_off_map)

    assert rc == 0
    assert "here off-map" in out, out
    assert "here ?" not in out


def test_daemon_down_does_not_claim_off_map(monkeypatch, store, tmp_path, capsys):
    rc, out = _run(monkeypatch, store, tmp_path, capsys, alive=False)

    assert rc == 0
    assert "here off-map" not in out, out
    assert "here ?" in out and "daemon" in out, out


def test_unusable_screen_response_does_not_claim_off_map(
    monkeypatch, store, tmp_path, capsys
):
    rc, out = _run(monkeypatch, store, tmp_path, capsys,
                   alive=True, screen_resp=BAD_SCREEN)

    assert rc == 0
    assert "here off-map" not in out, out
    assert "here ?" in out, out
    assert "not_connected" in out, "the daemon's own reason must reach the operator"


def test_raised_lookup_does_not_claim_off_map(monkeypatch, store, tmp_path, capsys):
    rc, out = _run(monkeypatch, store, tmp_path, capsys,
                   alive=True, screen_resp=OK_SCREEN, localize=_raises)

    assert rc == 0
    assert "here off-map" not in out, out
    assert "here ?" in out and "ValueError" in out, out


def test_blank_screen_does_not_claim_off_map(monkeypatch, store, tmp_path, capsys):
    """The 4th path -- localize is never even called, so it never said
    anything, let alone off-map."""
    called = []

    def _tracking(*a, **k):
        called.append(a)
        return None

    rc, out = _run(monkeypatch, store, tmp_path, capsys,
                   alive=True, screen_resp=BLANK_SCREEN, localize=_tracking)

    assert rc == 0
    assert called == [], "a blank screen must not be handed to localize at all"
    assert "here off-map" not in out, out
    assert "here ?" in out and "blank" in out, out


def test_localized_still_wins_with_a_star(monkeypatch, store, tmp_path, capsys):
    """Regression guard on the happy path: a real localization is unchanged."""
    rc, out = _run(monkeypatch, store, tmp_path, capsys,
                   alive=True, screen_resp=OK_SCREEN, localize=_located)

    assert rc == 0
    assert "here ★ Computer" in out, out
    assert "here ?" not in out and "off-map" not in out


# -- the collapse itself: no two conditions may render the same --------------

def test_all_five_conditions_render_five_distinct_you_are_here_lines(
    monkeypatch, store, tmp_path, capsys
):
    """The finding in one assertion. Pre-fix, all five of these produced the
    IDENTICAL line; the test is written on the you-are-here line specifically
    rather than whole-output, so it stays honest if the coverage lines ever
    legitimately differ between runs."""
    conditions = {
        "daemon-down": dict(alive=False),
        "screen-not-ok": dict(alive=True, screen_resp=BAD_SCREEN),
        "localize-raised": dict(alive=True, screen_resp=OK_SCREEN, localize=_raises),
        "screen-blank": dict(alive=True, screen_resp=BLANK_SCREEN, localize=_off_map),
        "genuine-off-map": dict(alive=True, screen_resp=OK_SCREEN, localize=_off_map),
    }

    here_lines = {}
    for label, kwargs in conditions.items():
        _rc, out = _run(monkeypatch, store, tmp_path, capsys, **kwargs)
        here = [ln for ln in out.splitlines() if ln.startswith("here")]
        assert len(here) == 1, (label, out)
        here_lines[label] = here[0]

    assert len(set(here_lines.values())) == 5, (
        "two conditions still render identically:\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in sorted(here_lines.items()))
    )
    # ...and specifically, only the genuine one may claim off-map.
    assert here_lines["genuine-off-map"] == "here off-map"
    for label, line in here_lines.items():
        if label != "genuine-off-map":
            assert "off-map" not in line, (label, line)


# -- the machine-readable surface carries it too -----------------------------

def test_json_output_distinguishes_the_reason(monkeypatch, store, tmp_path, capsys):
    rc, out = _run(monkeypatch, store, tmp_path, capsys, alive=False, as_json=True)
    payload = json.loads(out)

    assert rc == 0
    assert payload["current"] is None
    assert payload["here_unknown"], "a scripted caller must be able to branch on it"
    assert "daemon" in payload["here_unknown"]


def test_json_genuine_off_map_carries_no_reason(monkeypatch, store, tmp_path, capsys):
    """The distinction has to be readable BOTH ways: absence of a reason is
    what marks the genuine off-map result, so it must really be absent."""
    rc, out = _run(monkeypatch, store, tmp_path, capsys,
                   alive=True, screen_resp=OK_SCREEN, localize=_off_map,
                   as_json=True)
    payload = json.loads(out)

    assert rc == 0
    assert payload["current"] is None
    assert payload["here_unknown"] is None


def test_json_localized_carries_no_reason(monkeypatch, store, tmp_path, capsys):
    rc, out = _run(monkeypatch, store, tmp_path, capsys,
                   alive=True, screen_resp=OK_SCREEN, localize=_located,
                   as_json=True)
    payload = json.loads(out)

    assert rc == 0
    assert payload["current"]["signature"] == "sig-a"
    assert payload["here_unknown"] is None


# -- the rest of the report is untouched ------------------------------------

def test_the_map_report_itself_is_unchanged_on_a_failed_lookup(
    monkeypatch, store, tmp_path, capsys
):
    """Only the you-are-here line changes. Counts, coverage, dead-ends and
    orphans are all real store facts and must still print -- the verb's value
    when the daemon is down is precisely that it still shows the map."""
    rc, out = _run(monkeypatch, store, tmp_path, capsys, alive=False)

    assert rc == 0
    assert "MAP 2n·1e" in out
    assert "0/2 reachable" in out
    assert "dead-ends: sig-b" in out
    assert "orphans: (none)" in out
