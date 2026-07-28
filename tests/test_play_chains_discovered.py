"""WO-CHAINS-TUI-FULL — discovered chains in `L)chains`: displayed, NEVER armable.

The hub ruling this file pins (2026-07-28): discovered profit chains
(`chain_search.recompute` results) are DISPLAY-ONLY in the `L)chains`
modal — visually distinct, structurally non-armable. Taught rows arm
unchanged through the confirm gate. The design is structural, not a
guard: `ChainsSession.discovered` is a separate field, never merged into
`rows`, so `move()` cannot put a discovered chain under the cursor and
`selected()` cannot return one — an absent path, not a deletable `if`.

Both directions are pinned:

* the arm side can never see a discovered chain (cursor sweep, and the
  real `_run_play` arm wire with zero taught loops but discovered rows
  present);
* the display side is honest — the discovered section renders even with
  zero taught loops (the old taught-empty early-return would have
  swallowed it), a truncated-and-empty search renders the hedge and never
  the established-absence wording, and an UNAVAILABLE payload (finder
  raised / junk shape) renders "unavailable", never a fabricated absence.

Payloads are duck-typed `SimpleNamespace`s, same rule as
`tests/test_chain_search_view.py`: the composer reads by `getattr` and
must never need the real `ProfitChainResult`.

App-level drives reuse the `tests/test_play_chains_arm.py` harness shape
(real `_run_play`, fake stdscr, spied money-path adapter calls); the
draw-level test reuses `tests/test_play_chains_visible.py`'s recording
`_Win`, because a composer with no wire to the screen is the failure that
file exists to prevent.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tw2002_aiclient import adapters, app as app_mod
from tw2002_aiclient import chain_search as chain_search_mod
from tw2002_aiclient import chain_search_view as V
from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient.cockpit import chains
from tw2002_aiclient.loops import store as _loop_store

# ---------------------------------------------------------------- payloads

RING = "10>11>12>"


def _chain(sectors=(10, 11, 12, 10), hops_n=3, turns=8, cr=120.0):
    return SimpleNamespace(
        sectors=tuple(sectors),
        hops=tuple(object() for _ in range(hops_n)),
        turns=turns,
        cr_per_turn=cr,
    )


def _payload(chains_=(), reason=None, detail=None, adapter_note=None, search_note=None):
    return SimpleNamespace(
        chains=tuple(chains_),
        reason=reason,
        detail=detail,
        adapter_note=adapter_note,
        search_note=search_note,
    )


TAUGHT = [
    {"name": "ore-run-K7", "steps": 12},
    {"name": "fuel-shuttle", "steps": 8},
]

DISCOVERED = _payload([_chain(), _chain((20, 21, 20), hops_n=2, turns=6, cr=90.0)])


def _open(rows, status="ok", discovered=DISCOVERED):
    s = chains.ChainsSession()
    s.open(rows, status, discovered=discovered)
    return s


def _body(session, **kw) -> str:
    return "\n".join(chains.compose_chain_lines(session, **kw))


# ------------------------------------------------- pin 1: selected() is taught-only


def _sweep_selected(session):
    """Every value `selected()` yields while the cursor is driven across
    (and past) its full range, including hostile jumps."""
    seen = [session.selected()]
    for delta in [1] * 6 + [-1] * 6 + [3, -7, 100, -100, 1, 1]:
        session.move(delta)
        seen.append(session.selected())
    return seen


def test_selected_can_never_return_a_discovered_chain_with_taught_present():
    """The oracle is the ORIGIN taught list by identity, deliberately not
    `s.rows` — a mutation that merges discovered chains INTO `rows` would
    leave a rows-based assertion green (the merged rows are, by then, "in
    rows"). Only the list the operator's store actually produced counts."""
    s = _open(list(TAUGHT))
    for sel in _sweep_selected(s):
        assert sel is not None
        assert any(sel is r for r in TAUGHT), f"selected() escaped the taught rows: {sel!r}"
        assert not hasattr(sel, "cr_per_turn"), "a chain-shaped object reached selected()"


@pytest.mark.parametrize("rows", [None, []], ids=["taught-absent", "taught-empty"])
def test_selected_is_always_none_when_only_discovered_rows_exist(rows):
    """Zero taught loops + a full discovered section: the cursor has nothing
    to stand on, so every position yields None — the value that makes the
    app's arm branch refuse."""
    s = _open(rows)
    assert all(sel is None for sel in _sweep_selected(s))


def test_open_keeps_discovered_out_of_rows_entirely():
    """The structural half stated directly: the payload is not row-shaped
    and `rows` contains only the taught Mappings that were passed in."""
    s = _open(list(TAUGHT))
    assert len(s.rows) == len(TAUGHT)
    assert s.discovered is DISCOVERED
    assert all(not hasattr(r, "chains") for r in s.rows)


# ------------------------------------------- pin 2: the arm wire (real _run_play)


class _Result:
    def __init__(self, ok=True, classification="main_command", reason=None, detail=None):
        self.ok, self.classification, self.reason, self.detail = ok, classification, reason, detail


class _AutoLoopResult:
    def __init__(self, ok=True, reason=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, None


class _Stdscr:
    """Feeds a scripted key sequence, then Esc to leave the loop."""

    def __init__(self, keys):
        self._keys = list(keys) + [27, 27]
        self.rows, self.cols = 40, 160

    def getmaxyx(self): return (self.rows, self.cols)
    def getch(self): return self._keys.pop(0) if self._keys else 27
    def timeout(self, ms): pass
    def erase(self): pass
    def refresh(self): pass
    def addstr(self, *a, **k): pass
    def addnstr(self, *a, **k): pass
    def attron(self, a): pass
    def attroff(self, a): pass
    def hline(self, *a, **k): pass
    def vline(self, *a, **k): pass
    def border(self, *a, **k): pass
    def chgat(self, *a, **k): pass
    def keypad(self, flag): pass
    def nodelay(self, flag): pass


TWO_LOOPS = {
    "status": "ok",
    "loops": [
        {"name": "ore-run-K7", "steps": 12, "draft": False},
        {"name": "fuel-shuttle", "steps": 8, "draft": False},
    ],
}
EMPTY_OK = {"status": "ok", "loops": []}

L = ord("L")
ENTER = 10


def _drive(monkeypatch, keys, *, store, recompute):
    """Run the real `_run_play`; return (arm_calls, explore_calls, screen).

    Both money-path spies are installed on every drive (the cross-
    contamination discipline `test_play_chains_arm.py` established), and
    `chain_search.recompute` is controlled so the discovered section is
    hermetic — no read of the real `state/world/` tree.
    """
    arm_calls: list = []
    explore_calls: list = []

    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Result())
    monkeypatch.setattr(_loop_store, "read_loop_store", lambda **kw: store)
    # `app.py` imports `chain_search` lazily inside the `chains_open`
    # branch (launcher-startup CPU budget), so the patch target is the
    # real module — the branch import resolves to the same object.
    monkeypatch.setattr(chain_search_mod, "recompute", recompute)

    def _arm(name=None, **kw):
        arm_calls.append((name, kw))
        return _AutoLoopResult()

    def _explore(profile, **kw):
        explore_calls.append(kw)
        return SimpleNamespace(ok=True, reason=None, detail=None, raw=None)

    monkeypatch.setattr(adapters, "autoloop_start", _arm, raising=False)
    monkeypatch.setattr(adapters, "explore_start_for_profile", _explore, raising=False)

    seen: dict = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
            seen["screen"] = self

        def begin_arm_confirm(self, action=None, *, cycles=None):
            self.gate_raises.append((action, cycles))
            return super().begin_arm_confirm(action, cycles=cycles)

        def draw(self):  # keep the fake stdscr out of real curses paint paths
            pass

    monkeypatch.setattr(app_mod, "PlayShellScreen", _Spy)
    monkeypatch.setattr(app_mod.curses, "has_colors", lambda: False, raising=False)

    profile = app_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    try:
        app_mod._run_play(_Stdscr(keys), profile)
    except Exception:
        pass
    return arm_calls, explore_calls, seen.get("screen")


def test_the_arm_wire_cannot_receive_a_discovered_chain(monkeypatch):
    """Zero taught loops, discovered chains on screen, Enter pressed: no
    gate may rise and no adapter call may happen — there is no row for the
    arm path to hold, because discovered chains never became rows."""
    arm, _explore, screen = _drive(
        monkeypatch, [L, ENTER], store=EMPTY_OK, recompute=lambda wid, **kw: DISCOVERED,
    )
    assert arm == [], f"a discovered chain reached the money path: {arm}"
    assert screen.gate_raises == [], (
        f"a confirm gate rose with nothing taught to arm: {screen.gate_raises}"
    )
    assert "nothing to arm" in (screen.status_line or "")
    assert screen.chains_session.discovered is DISCOVERED


def test_taught_arm_flow_unregressed_with_discovered_present(monkeypatch):
    """The other direction: the taught path must not lose its arm to the
    new section. `L` Enter `y` still starts exactly the taught macro."""
    arm, explore, screen = _drive(
        monkeypatch, [L, ENTER, ord("y")], store=TWO_LOOPS, recompute=lambda wid, **kw: DISCOVERED,
    )
    assert [name for (name, _kw) in arm] == ["ore-run-K7"]
    assert explore == []
    assert "ore-run-K7" in screen.gate_raises[0][0]


def test_a_raising_finder_does_not_take_down_the_play_loop(monkeypatch):
    """`recompute` blowing up (or a profile that cannot form a world_id)
    costs the operator the discovered section, never the cockpit."""
    def _boom(wid, **kw):
        raise RuntimeError("finder down")

    _arm, _explore, screen = _drive(monkeypatch, [L], store=TWO_LOOPS, recompute=_boom)
    assert screen is not None
    # The harness's trailing Esc closes the popup again, so `is_open` is
    # False by return; the proof the popup OPENED (i.e. the loop survived
    # the raise and reached `open()`) is the store status it recorded —
    # the session's own default is "unreadable", never "ok".
    assert screen.chains_session.status == "ok", "the popup never opened"
    assert screen.chains_session.discovered is None


# --------------------------------- pin 3: visually distinct, never the marker


def _discovered_slice(lines):
    assert V.TITLE in lines, f"no discovered section in {lines!r}"
    return lines[lines.index(V.TITLE):]


@pytest.mark.parametrize("unicode_ok", [True, False], ids=["unicode", "ascii"])
def test_discovered_rows_are_tagged_and_never_carry_the_selected_marker(unicode_ok):
    s = _open(list(TAUGHT))
    for _pos in range(len(TAUGHT) + 1):  # every cursor position, incl. clamped end
        lines = chains.compose_chain_lines(s, unicode_ok=unicode_ok)
        disc = _discovered_slice(lines)
        tagged = [ln for ln in disc if V.SOURCE_TAG in ln]
        assert len(tagged) == len(DISCOVERED.chains), disc
        for ln in tagged:
            assert not ln.startswith(chains.SELECTED_UNICODE), ln
            assert not ln.startswith(chains.SELECTED_ASCII), ln
        # ...and the taught side never borrows the provenance tag.
        taught_side = lines[: lines.index(V.TITLE)]
        assert all(V.SOURCE_TAG not in ln for ln in taught_side), taught_side
        s.move(1)


# ------------------------------------------------ pin 4: truncation honesty


def test_truncated_and_empty_renders_the_hedge_never_established_absence():
    """`chain_search`'s sharpest fact must survive INTO the modal: a
    truncated search that found nothing has not established that nothing
    is there. The wording comes from `chain_search_view`, not a re-derived
    copy here."""
    truncated_empty = _payload(
        reason="no_closed_cycle",
        detail="search truncated before completion -- absence is not established",
        search_note="stopped at 100000 of 100000 steps",
    )
    body = _body(_open([], discovered=truncated_empty))
    assert V._EMPTY_BUT_TRUNCATED_TEXT in body
    assert V.PARTIAL_UNICODE in body
    assert V._REASON_TEXT["no_closed_cycle"] not in body, (
        "a truncated-empty search rendered as an ESTABLISHED absence"
    )


def test_untruncated_empty_renders_the_reason_never_the_hedge():
    clean_empty = _payload(reason="no_closed_cycle")
    body = _body(_open([], discovered=clean_empty))
    assert V._REASON_TEXT["no_closed_cycle"] in body
    assert V._EMPTY_BUT_TRUNCATED_TEXT not in body, (
        "an exhaustive empty hedged as if the search had been cut short"
    )
    assert V.PARTIAL_UNICODE not in body


# ------------------------------------- pin 5: the taught-empty-branch trap


def test_zero_taught_plus_discovered_still_renders_the_discovered_section():
    """The early-return trap: with no taught loops the old composer
    returned before any discovered section could render. Both sections are
    independent now — and the taught placeholder keeps its ok/unreadable
    split rather than flattening."""
    body_ok = _body(_open([], "ok"))
    assert chains.EMPTY_TEXT in body_ok            # "none taught" — established
    assert V.TITLE in body_ok
    assert RING in body_ok

    body_bad = _body(_open([], "unreadable"))
    assert chains.UNREADABLE_TEXT in body_bad      # "could not establish"
    assert chains.EMPTY_TEXT not in body_bad
    assert RING in body_bad


# ------------------------------- pin 7: unavailable is not an established absence


@pytest.mark.parametrize("bogus", [None, 7, "chains", object()], ids=["none", "int", "str", "object"])
def test_unavailable_discovery_never_renders_as_established_absence(bogus):
    """No payload (finder raised) or a junk shape must render the modal's
    own "unavailable" line — `chain_search_view`'s default empty text
    claims an absence nobody established and must be unreachable from
    garbage."""
    body = _body(_open(list(TAUGHT), discovered=bogus))
    assert chains.DISCOVERY_UNAVAILABLE_TEXT in body
    assert V._DEFAULT_EMPTY_TEXT not in body
    assert V.TITLE in body  # the section itself is still announced


# ---------------------------------------- pin 9: the section reaches the screen


FULL_ROWS, FULL_COLS = 40, 160


class _Win:
    def __init__(self, rows=FULL_ROWS, cols=FULL_COLS):
        self._rows, self._cols = rows, cols
        self.writes: list[tuple[int, int, str, int]] = []

    def getmaxyx(self): return (self._rows, self._cols)
    def erase(self): pass
    def refresh(self): pass
    def addstr(self, y, x, s, attr=0): self.writes.append((y, x, s, attr))
    def addnstr(self, y, x, s, n, attr=0): self.writes.append((y, x, s[:n], attr))
    def attron(self, a): pass
    def attroff(self, a): pass
    def hline(self, *a, **k): pass
    def vline(self, *a, **k): pass
    def border(self, *a, **k): pass
    def chgat(self, *a, **k): pass


def test_discovered_rows_reach_the_screen(monkeypatch):
    """Composer output is not a screen. Same recording-`_Win` discipline as
    `test_play_chains_visible.py`: the ring, the provenance tag, and the
    section title must actually be painted."""
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    win = _Win()
    s = screens_mod.PlayShellScreen(win, profile)
    s.spectating = False
    s.attached = False
    s.status_provider = lambda: None
    s.chains_session.open(list(TAUGHT), "ok", discovered=DISCOVERED)
    s.draw()
    painted = "\n".join(text for (_y, _x, text, _a) in win.writes)
    assert V.TITLE in painted
    assert RING in painted
    assert V.SOURCE_TAG in painted
