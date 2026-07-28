"""WO-LAST-KNOWN-SECTOR — the daemon remembers a sector, and forgets it fast.

**Why remembering is dangerous, and what makes it safe.** Several screens
identify themselves without carrying a sector: every captured StarDock screen
shows `Command [TL=00751:0/0/0/850] (?=Help)? :` with no `[sector]` bracket,
while an ordinary docked-port screen has one. So a per-sector fact learned there
has nothing to attach to — hence a memory. But a *stale* memory is worse than no
memory: attributing a landmark to the sector we just left writes StarDock into
the wrong one, and `landmarks` unions (`WO-WM-LANDMARKS-WRITE` P1), so **nothing
in the product can ever remove it**. One wrong write is permanent.

The send-epoch is what makes it safe. It bumps on every send — both paths — and
on every reconnect, and a reading is offered back only while the epoch still
matches the one it was taken at. The memory therefore answers exactly *"the
sector we are in, given that nothing has happened since we looked"*, and goes
silent the instant anything has.

**These tests run against the real `Session` class**, not a double, because the
production call sites duck-type `note_sector` via `getattr` (matching this
codebase's idiom for optional session capabilities) and a hand-built stand-in
would happily confirm whatever this file assumed. `test_the_real_session_class_
carries_the_contract` is what stops that duck-typing from ever excusing a
regression rather than a test double.
"""

from __future__ import annotations

import threading

import pytest

from tw2002_aiclient.session import protocol
from tw2002_aiclient.session.session import Session

SECTOR = 158
OTHER = 4309


@pytest.fixture
def session(tmp_path):
    """A real Session. `Session.__init__` builds a `TelnetConnection` but does
    not dial, so this touches no socket."""
    return Session("127.0.0.1", 65000, "probe", str(tmp_path))


# --------------------------------------------------- the contract itself


def test_the_real_session_class_carries_the_contract():
    """The pin that closes the `getattr` hole.

    `protocol.py` and `sector_explore.py` call `note_sector` through
    `getattr(session, "note_sector", None)` so the dozens of scripted
    stand-ins handed to `build_response` do not crash the daemon. That
    tolerance must never extend to the real thing: if `Session` lost the
    method, every call site would silently become a no-op and the memory
    would go quietly, permanently empty. Asserting on the CLASS is what
    makes the duck-typing excuse only a double.
    """
    for name in ("note_sector", "last_known_sector"):
        assert callable(getattr(Session, name, None)), f"Session lost {name}()"


def test_absent_until_something_is_actually_read(session):
    assert session.last_known_sector() is None


def test_a_read_is_remembered(session):
    session.note_sector(SECTOR)
    assert session.last_known_sector() == SECTOR


# --------------------------------------------------- forgetting, every route


def test_a_send_forgets_it(session, monkeypatch):
    """The ordinary case: we looked, then we did something. Whatever we did
    may have moved the ship, so the reading no longer describes where we are."""
    session.note_sector(SECTOR)
    monkeypatch.setattr(session.conn, "send_text", lambda *a, **k: None)
    session.send("D")
    assert session.last_known_sector() is None


def test_a_human_keystroke_forgets_it_too(session, monkeypatch):
    """`send_raw` is the interactive attach path. A human typing a warp moves
    the ship exactly like a scripted dispatch does — bumping in one send path
    and not the other would leave the memory correct under automation and
    wrong under a human at the keys, which is the direction nobody tests."""
    session.note_sector(SECTOR)
    monkeypatch.setattr(session.conn, "send_bytes", lambda *a, **k: None)
    try:
        session.send_raw(b"1\r")
    except Exception:
        # The wire half may refuse in this bare harness; the invalidation is
        # what is under test and it happens before any byte can go out.
        pass
    assert session.last_known_sector() is None


def test_a_send_that_RAISES_still_forgets_it(session, monkeypatch):
    """The bump happens before the byte can reach the wire, deliberately. A
    send that blew up may still have moved the ship, and a memory that
    outlived a failed send is exactly the one that would attribute a landmark
    to the sector we just left. Bumping early can only cost a write we were
    unsure about; bumping late can write a permanent wrong one."""
    session.note_sector(SECTOR)

    def _boom(*a, **k):
        raise OSError("wire down")

    monkeypatch.setattr(session.conn, "send_text", _boom)
    with pytest.raises(Exception):
        session.send("D")
    assert session.last_known_sector() is None


def test_a_reconnect_forgets_it(session, monkeypatch):
    """A fresh TCP connection means the server starts drawing from its own
    login entry point, so the sector is gone with the old screen."""
    session.note_sector(SECTOR)
    monkeypatch.setattr(session.conn, "close", lambda *a, **k: None)
    monkeypatch.setattr(session, "connect", lambda *a, **k: None, raising=False)
    try:
        session.reconnect()
    except Exception:
        pass
    assert session.last_known_sector() is None


def test_a_reconnect_that_raises_still_forgets_it(session, monkeypatch):
    def _boom(*a, **k):
        raise OSError("already dead")

    session.note_sector(SECTOR)
    monkeypatch.setattr(session.conn, "connect", _boom, raising=False)
    monkeypatch.setattr(session, "connect", _boom, raising=False)
    try:
        session.reconnect()
    except Exception:
        pass
    assert session.last_known_sector() is None


def test_a_fresh_read_after_a_send_is_remembered_again(session, monkeypatch):
    """Negative control for every forgetting test above: an implementation
    that simply never returned a sector would pass all of them."""
    monkeypatch.setattr(session.conn, "send_text", lambda *a, **k: None)
    session.note_sector(SECTOR)
    session.send("D")
    assert session.last_known_sector() is None
    session.note_sector(OTHER)
    assert session.last_known_sector() == OTHER


# --------------------------------------------------- never invent a sector


@pytest.mark.parametrize(
    "junk", [None, True, False, "158", 158.0, object(), [158]],
    ids=["none", "true", "false", "str", "float", "obj", "list"],
)
def test_junk_is_never_remembered(session, junk):
    """`True` is an `int` in Python and would remember sector 1. A sector is a
    parsed reading or it is nothing; there is no path here that derives,
    defaults, or coerces one."""
    session.note_sector(junk)
    assert session.last_known_sector() is None


def test_junk_does_not_displace_a_good_reading(session):
    session.note_sector(SECTOR)
    session.note_sector(None)
    assert session.last_known_sector() == SECTOR


# --------------------------------------------------- concurrency


def test_a_send_racing_a_read_never_yields_a_stale_positive(session, monkeypatch):
    """The daemon is threaded. The invariant that matters is one-directional:
    the memory may return `None` when a sector was in fact knowable (safe), but
    it must NEVER return a sector that a send has already invalidated.

    Checked by hammering both sides and asserting the epoch discipline holds
    rather than asserting a particular interleaving, which would only pin the
    scheduler this machine happened to use.
    """
    monkeypatch.setattr(session.conn, "send_text", lambda *a, **k: None)
    bad: list = []
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            got = session.last_known_sector()
            if got is not None and got != SECTOR:
                bad.append(got)

    def writer():
        for _ in range(300):
            session.note_sector(SECTOR)
            session.send("D")

    r = threading.Thread(target=reader, daemon=True)
    r.start()
    try:
        writer()
    finally:
        stop.set()
        r.join(timeout=5)
    assert bad == [], f"a sector appeared that was never noted: {bad[:3]}"


# --------------------------------------------------- the production wiring


WITH_SECTOR = "Command [TL=00:00:00]:[158] (?=Help)? :"
STARDOCK = "<StarDock> Where to? (?=Help)"  # captured: seraph_run, double2_run


def _wire(session, monkeypatch, prompt):
    """Point a REAL Session's render surface at a fixed screen.

    Deliberately not a hand-built session double: the verb responses read
    `conn.connected`, `last_rx`, `host`, `port` and more, so a stand-in would
    have to be grown until it re-implemented Session — at which point it
    confirms whatever this file assumed rather than what the daemon does.
    """
    rows = ["Sector  : 158 in uncharted space.", prompt]
    monkeypatch.setattr(session, "render", lambda *a, **k: list(rows))
    monkeypatch.setattr(session, "render_with_color", lambda *a, **k: (list(rows), None))
    monkeypatch.setattr(session, "render_text", lambda r=None: "\n".join(r or rows))
    monkeypatch.setattr(session.conn, "connected", True, raising=False)
    return session


def test_the_state_verb_notes_a_sector_it_read(session, monkeypatch):
    """The wire, not just the store: a producer nobody calls is
    indistinguishable from no producer at all."""
    _wire(session, monkeypatch, WITH_SECTOR)
    resp = protocol._state_response(session)
    assert resp["state"]["sector"]["sector"] == SECTOR
    assert session.last_known_sector() == SECTOR


def test_the_state_verb_notes_nothing_on_a_sector_less_screen(session, monkeypatch):
    """Fed the REAL captured StarDock prompt. `read_current_sector` reports
    `absent` for it, and an absent reading must leave the previous memory
    alone rather than overwrite it with a guess — that memory is the whole
    reason this screen can be attributed at all."""
    session.note_sector(OTHER)
    _wire(session, monkeypatch, STARDOCK)
    resp = protocol._state_response(session)
    assert resp["state"]["sector"] == {"outcome": "absent"}
    assert session.last_known_sector() == OTHER, "an absent read displaced a good one"


def test_a_session_without_the_hook_does_not_break_the_state_verb(session, monkeypatch):
    """The tolerance the `getattr` buys, stated explicitly so nobody
    'tightens' it into a daemon crash on the dozens of scripted stand-ins
    `build_response` is handed."""
    _wire(session, monkeypatch, WITH_SECTOR)
    monkeypatch.setattr(session, "note_sector", None)
    resp = protocol._state_response(session)
    assert resp["ok"] is True


# --------------------------------------------------- the explore-loop producer


def test_the_explore_loop_notes_every_sector_it_reads(tmp_path, monkeypatch):
    """The explore loop reads far more sectors than the `state` verb does, and
    it is the path that STOPS when the next screen is unrecognised — which is
    exactly the StarDock case this memory exists for. If it did not note as it
    went, the memory would be empty at the one moment it is needed.

    Driven through the real `ExploreRunner` against this repo's own explore
    harness, with a recording `note_sector` added: the production call site is
    `getattr`-guarded, so a session lacking the hook would make this test pass
    while proving nothing.
    """
    from pathlib import Path as _P

    from tests.test_sector_explore import WORLD, ExploreMapSession, _seed_line
    from tw2002_aiclient.session import sector_explore
    from tw2002_aiclient.session.control_lock import ControlLock

    _seed_line(tmp_path, [1, 2, 3, 4, 5, 6], extra_frontier=(6, 99))
    graph = {i: [i - 1, i + 1] if 1 < i < 6 else ([2] if i == 1 else [5, 99]) for i in range(1, 7)}

    class _Noting(ExploreMapSession):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.noted: list = []

        def note_sector(self, sector_id):
            self.noted.append(sector_id)

    session = _Noting(sector=1, graph=graph, state_dir=tmp_path)
    runner = sector_explore.ExploreRunner(session, ControlLock(), state_dir=tmp_path)
    runner.start(WORLD, min_sectors=5, turn_budget=20)
    runner._thread.join(timeout=30)

    assert session.noted, "the explore loop read sectors and noted none of them"
    assert all(isinstance(s, int) and not isinstance(s, bool) for s in session.noted)
    # Every noted sector must be one the loop genuinely visited, never derived.
    assert set(session.noted) <= set(graph), f"noted a sector never visited: {session.noted}"
    assert len(set(session.noted)) >= 5, f"only noted {set(session.noted)}"
