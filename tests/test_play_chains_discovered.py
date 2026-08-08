"""ADR-003 — discovered chains require exact preview + confirm before execution.

The hub ruling this file pins (2026-07-28): discovered profit chains
`ChainsSession.discovered` stays separate from recorded macro `rows`.
`selected()` therefore remains recorded-only; `selected_discovered()` feeds
the exact semantic approval path. Enter raises a visible default-deny gate,
and only a later `y` may call the guarded trade adapter.

Both identities are pinned:

* `selected()` can never return a discovered chain, while
  `selected_discovered()` can feed only the separate exact-plan gate;
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
from tw2002_aiclient.chains import ProfitChain, TradeHop
from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient import world_model as world_model_mod
from tw2002_aiclient.cockpit import chains
from tw2002_aiclient.loops import store as _loop_store

# ---------------------------------------------------------------- payloads

RING = "10>11>12>"


def _chain(sectors=(10, 11, 12, 10), hops_n=3, turns=8, cr=120.0):
    sectors = tuple(sectors)
    commodities = ("Fuel Ore", "Organics", "Equipment")
    hops = tuple(
        TradeHop(
            frm=sectors[i],
            to=sectors[i + 1],
            commodity=commodities[i % len(commodities)],
            margin=10.0 + i,
            turns=1,
        )
        for i in range(hops_n)
    )
    return ProfitChain(
        sectors=sectors,
        hops=hops,
        overall_profit=sum(h.margin for h in hops),
        turns=turns,
        cr_per_turn=cr,
        cr_per_execution=sum(h.margin for h in hops),
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

# Distinct from every other number in this file so an assertion cannot pass on
# a coincidence, and not a count any real fixture here would produce.
SECTOR_COUNT = 812


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
        if sel is not None:
            assert any(sel is r for r in TAUGHT), f"selected() escaped the taught rows: {sel!r}"
            assert not hasattr(sel, "cr_per_turn"), "a chain-shaped object reached selected()"
    assert s.selected_discovered() is not None


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
        self.rows, self.cols = 40, 180

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


def _drive(monkeypatch, keys, *, store, recompute, sector_count=SECTOR_COUNT):
    """Run the real `_run_play`; return (arm_calls, explore_calls, screen).

    Both money-path spies are installed on every drive (the cross-
    contamination discipline `test_play_chains_arm.py` established), and
    `chain_search.recompute` is controlled so the discovered section is
    hermetic — no read of the real `state/world/` tree.

    `sector_count` controls the OTHER world-model read this branch now makes
    (`world_stats.refresh`), for the same hermetic reason and then some: left
    unpatched it would count sector files under the operator's real
    `state/world/`, so the assertions below would pass or fail according to
    how much the human had explored — a test that reddens exactly when the
    product is in use. Pass a `BaseException` to drive the raising-store case;
    `None` models a store that cannot be counted.
    """
    arm_calls: list = []
    trade_calls: list = []
    explore_calls: list = []

    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Result())

    def _read_store(**kw):
        # A `store` that IS an exception raises instead of returning, so a
        # caller can drive the unreadable-store branch. Patching
        # `read_loop_store` from the test body cannot do it: this line runs
        # after that patch and would overwrite it -- silently, leaving a test
        # named for one branch exercising the other.
        if isinstance(store, BaseException):
            raise store
        return store

    monkeypatch.setattr(_loop_store, "read_loop_store", _read_store)
    # `app.py` imports `chain_search` lazily inside the `chains_open`
    # branch (launcher-startup CPU budget), so the patch target is the
    # real module — the branch import resolves to the same object.
    monkeypatch.setattr(chain_search_mod, "recompute", recompute)

    def _count(world_id, **kw):
        if isinstance(sector_count, BaseException):
            raise sector_count
        if callable(sector_count):
            return sector_count(world_id, **kw)
        return sector_count

    # `world_stats.refresh` imports `world_model` lazily, so the patch target
    # is the real module -- the lazy import resolves to the same object.
    monkeypatch.setattr(world_model_mod, "known_sector_count", _count)

    def _arm(name=None, **kw):
        arm_calls.append((name, kw))
        return _AutoLoopResult()

    def _explore(profile, **kw):
        explore_calls.append(kw)
        return SimpleNamespace(ok=True, reason=None, detail=None, raw=None)

    monkeypatch.setattr(adapters, "autoloop_start", _arm, raising=False)
    def _trade(world_id, fingerprint, **kw):
        trade_calls.append((world_id, fingerprint, kw))
        return _AutoLoopResult()

    monkeypatch.setattr(adapters, "trade_chain_start", _trade, raising=False)
    monkeypatch.setattr(adapters, "explore_start_for_profile", _explore, raising=False)
    monkeypatch.setattr(
        adapters, "explore_stop",
        lambda **kw: SimpleNamespace(ok=True, reason=None), raising=False,
    )
    monkeypatch.setattr(
        adapters, "autoloop_stop",
        lambda **kw: _AutoLoopResult(), raising=False,
    )
    monkeypatch.setattr(
        adapters, "trade_chain_stop",
        lambda **kw: _AutoLoopResult(), raising=False,
    )

    seen: dict = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
            self.spectating = True  # no App-armed ensure explore kick
            self.port_trade_on = True
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
    screen = seen.get("screen")
    if screen is not None:
        screen.trade_calls = trade_calls
    return arm_calls, explore_calls, screen


def test_discovered_enter_arms_without_starting(monkeypatch):
    """Enter arms the L-selection; only T may start it."""
    arm, _explore, screen = _drive(
        monkeypatch, [L, ENTER], store=EMPTY_OK, recompute=lambda wid, **kw: DISCOVERED,
    )
    assert arm == []
    assert screen.trade_calls == []
    assert screen.gate_raises == []
    assert screen.trade_loop_arm is not None
    assert screen.trade_loop_arm["kind"] == "discovered"
    assert "10>11>12>10" in screen.trade_loop_arm["route"]
    assert "press T to run" in (screen.status_line or "")
    assert screen.chains_session.discovered is DISCOVERED


def test_discovered_t_starts_only_the_armed_fingerprint(monkeypatch):
    arm, explore, screen = _drive(
        monkeypatch,
        [L, ENTER, ord("T")],
        store=EMPTY_OK,
        recompute=lambda wid, **kw: DISCOVERED,
    )

    assert arm == []
    assert explore == []
    assert len(screen.trade_calls) == 1
    world_id, fingerprint, kwargs = screen.trade_calls[0]
    assert world_id
    assert len(fingerprint) == 64
    assert kwargs["cash_floor"] == 1000
    assert kwargs["turn_reserve"] == 10


def test_discovered_enter_alone_starts_no_money_path(monkeypatch):
    arm, explore, screen = _drive(
        monkeypatch,
        [L, ENTER, ord("n")],
        store=EMPTY_OK,
        recompute=lambda wid, **kw: DISCOVERED,
    )

    assert arm == []
    assert explore == []
    assert screen.trade_calls == []
    assert screen.trade_loop_arm is not None


def test_taught_arm_flow_unregressed_with_discovered_present(monkeypatch):
    """Taught path still wins when both sections exist: L Enter T starts taught."""
    arm, explore, screen = _drive(
        monkeypatch, [L, ENTER, ord("T")], store=TWO_LOOPS, recompute=lambda wid, **kw: DISCOVERED,
    )
    assert [name for (name, _kw) in arm] == ["ore-run-K7"]
    assert explore == []
    assert screen.trade_calls == []
    assert screen.trade_loop_arm == {
        "kind": "taught",
        "name": "ore-run-K7",
        "steps": 12,
    }


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
def test_discovered_rows_are_tagged_and_only_active_row_has_selection_marker(unicode_ok):
    s = _open(list(TAUGHT))
    for _pos in range(len(TAUGHT) + 1):  # every cursor position, incl. clamped end
        lines = chains.compose_chain_lines(s, unicode_ok=unicode_ok)
        disc = _discovered_slice(lines)
        tagged = [ln for ln in disc if V.SOURCE_TAG in ln]
        assert len(tagged) == len(DISCOVERED.chains), disc
        selected = [
            ln for ln in tagged
            if ln.startswith(chains.SELECTED_UNICODE)
            or ln.startswith(chains.SELECTED_ASCII)
        ]
        assert len(selected) == (1 if s.section == "discovered" else 0)
        # ...and the taught side never borrows the provenance tag.
        taught_side = lines[: lines.index(V.TITLE)]
        assert all(V.SOURCE_TAG not in ln for ln in taught_side), taught_side
        s.move(1)


# ------------------------------------------------ pin 4: truncation honesty


def test_partial_discovery_with_chains_remains_selectable():
    """RESOLVED-EXPLORE-VS-TRADE-LOOP-MODES: PARTIAL banner stays; rows stay armable."""
    partial = _payload(
        chains_=[_chain()],
        search_note="stopped at 100000 of 100000 steps",
        adapter_note="budget",
    )
    s = _open([], discovered=partial)
    assert s._selectable_discovered()
    assert s.selected_discovered() is not None


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


FULL_ROWS, FULL_COLS = 40, 180


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


# --------------------------------- pin 4: the chain-scalars producer wire
#
# WO-STATUS-CHAIN-SCALARS-COACH. `cockpit/goals.py` reads
# `status["chain_hops"]`/`["chain_unit"]`; the discovery that feeds them
# happens HERE, in this popup branch, because it is the one place a chain
# search already runs for its own reasons (importing `chain_search` on the
# draw path would blow the launcher's CPU budget outright).
#
# Unit tests for `ChainScalars` live in `tests/test_chain_status_coach_wire.py`.
# What is pinned below is only the thing those cannot see: that the real
# `_run_play` actually calls it, and that the scalars it caches reach the same
# `status_provider` closure the GOALS panel polls. A producer nobody wired is
# indistinguishable from no producer at all.


def _scalars_after(screen):
    return screen.chain_scalars.merge({})


def test_pressing_L_caches_the_discovered_hop_count(monkeypatch):
    # DISCOVERED is ranked hop-count desc: chains[0] carries 3 hops.
    _arm, _explore, screen = _drive(
        monkeypatch, [L], store=TWO_LOOPS, recompute=lambda wid, **kw: DISCOVERED,
    )
    assert _scalars_after(screen) == {"chain_hops": 3, "chain_unit": "hops"}


def test_the_cached_scalars_reach_the_real_status_provider(monkeypatch):
    """The wire, end to end: what the popup caches is what GOALS polls.

    Asserting on `screen.chain_scalars` alone would still pass if `_run_play`
    built its provider without them — that closure is the actual delivery
    path, so it is the thing worth reading.
    """
    from tw2002_aiclient.session import cli as session_cli

    monkeypatch.setattr(
        session_cli, "send_request",
        lambda verb, args=None, **kw: {"ok": True, "credits": 7},
    )
    _arm, _explore, screen = _drive(
        monkeypatch, [L], store=TWO_LOOPS, recompute=lambda wid, **kw: DISCOVERED,
    )
    got = screen.status_provider()
    # WO-PRIORITY-ENGINE-FOCUS-WIRE: outermost wrap adds focus.candidates;
    # assert the chain/world scalars delivery path separately from ranking.
    focus = got.pop("focus", None)
    assert isinstance(focus, dict)
    assert isinstance(focus.get("candidates"), list) and focus["candidates"]
    # WO-WIRE-SHIP-SPEC-CATALOG-INTO-UPGRADE-DECISIONS: FocusScalars.merge
    # also attaches upgrade_loop from the priced discovered chain — peel it
    # off so this pin stays about chain/world scalar delivery.
    upgrade_loop = got.pop("upgrade_loop", None)
    if upgrade_loop is not None:
        assert isinstance(upgrade_loop, dict)
        assert {"margin_per_hold", "turns_per_cycle", "stock_capacity"} <= set(
            upgrade_loop
        )
    assert got == {
        "ok": True, "credits": 7,
        "chain_hops": 3, "chain_unit": "hops",
        "known_sectors": SECTOR_COUNT,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
    }


def test_the_store_unreadable_branch_still_caches_the_scalars(monkeypatch):
    """Discovery and the taught-loop store are independent reads. A store
    that will not open says nothing about the chain search that already
    succeeded, so the GOALS row must not go dark with it."""
    _arm, _explore, screen = _drive(
        monkeypatch,
        [L],
        store=OSError("store gone"),
        recompute=lambda wid, **kw: DISCOVERED,
    )
    # Proof the intended branch was actually taken -- the first version of
    # this test patched `read_loop_store` from the body, `_drive` overwrote
    # the patch, and it passed for two runs while exercising the OK branch.
    assert "unreadable" in screen.status_line
    assert _scalars_after(screen) == {"chain_hops": 3, "chain_unit": "hops"}


def test_a_raising_finder_writes_no_scalars_at_all(monkeypatch):
    """The finder-unavailable payload is `None`, and the modal renders it as
    "discovery unavailable" rather than an absence. The GOALS row must make
    the same distinction: unknown, never "none yet"."""
    def _boom(wid, **kw):
        raise RuntimeError("finder exploded")

    _arm, _explore, screen = _drive(
        monkeypatch, [L], store=TWO_LOOPS, recompute=_boom,
    )
    assert _scalars_after(screen) == {}


def test_a_freshly_built_play_screen_always_has_chain_scalars(monkeypatch):
    """The popup branch calls `.update()` unconditionally, so the attribute
    must exist on every `PlayShellScreen` — including the many built directly
    by tests and never through `_run_play`."""
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    s = screens_mod.PlayShellScreen(_Win(), profile)
    assert s.chain_scalars.merge({"ok": True}) == {"ok": True}


def test_the_coach_callout_is_actually_PAINTED_not_merely_composed(monkeypatch):
    """Composer output is not a screen — the same discipline the discovered-rows
    pin above follows. `compose_decisions_lines` returning a card proves nothing
    about what the operator sees; this drives the real `PlayShellScreen.draw()`
    through a recording window and reads the pixels back."""
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    win = _Win()
    s = screens_mod.PlayShellScreen(win, profile)
    s.spectating = False
    s.attached = False
    # No autopilot_trace: DECISIONS would otherwise show its honest-empty state.
    s.status_provider = lambda: {"ok": True, "chain_hops": 4, "chain_unit": "hops"}
    s.draw()
    painted = "\n".join(text for (_y, _x, text, _a) in win.writes)
    assert "Exploring…" not in painted
    assert "profit chain" in painted.lower()


def test_the_empty_pane_still_paints_its_honest_state_without_a_chain(monkeypatch):
    """The negative control for the pin above: same screen, same draw, no chain
    — a coach callout that paints regardless would pass the positive test on its
    own."""
    from tw2002_aiclient.cockpit import autonomy_keys

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    win = _Win()
    s = screens_mod.PlayShellScreen(win, profile)
    s.spectating = False
    s.attached = False
    s.status_provider = lambda: {"ok": True}
    s.draw()
    painted = "\n".join(text for (_y, _x, text, _a) in win.writes)
    assert "profit chain" not in painted.lower()
    for help_line in autonomy_keys.compose_autonomy_help_lines():
        assert help_line[:12] in painted, (
            f"expected calm-empty HELP {help_line[:12]!r} in painted DECISIONS"
        )


# ------------------------------- WO-GOALS-STATUS-VOCABULARY T1: `known_sectors`
#
# The GOALS Map row's producer rides the same keypress and the same seam as the
# chain scalars above, for the same reason: `status_provider()` runs once per
# DRAW, and counting sector files is ~26ms at 5000 sectors against a budget
# already within ~50ms of its ceiling (`tests/test_dead_terminal_spin.py`).
#
# `WorldStats` unit behaviour is pinned in `tests/test_world_stats.py`. What is
# pinned HERE is only what those cannot see: that `_run_play` actually calls
# `refresh`, that it passes the profile's own world_id, and that the number
# reaches the closure GOALS polls.


def test_pressing_L_refreshes_the_known_sector_count(monkeypatch):
    from tw2002_aiclient.session import cli as session_cli

    monkeypatch.setattr(
        session_cli, "send_request", lambda verb, args=None, **kw: {"ok": True},
    )
    _arm, _explore, screen = _drive(
        monkeypatch, [L], store=TWO_LOOPS, recompute=lambda wid, **kw: DISCOVERED,
    )
    assert screen.status_provider().get("known_sectors") == SECTOR_COUNT


def test_the_count_is_absent_until_the_popup_runs(monkeypatch):
    """The negative control for the pin above.

    Without it, a `WorldStats` that fabricated a count at CONSTRUCTION time
    would pass every positive assertion in this file. The Map row must say
    "unknown" until we have actually looked, never a zero we did not measure.
    """
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    s = screens_mod.PlayShellScreen(_Win(), profile)
    assert s.world_stats.merge({"ok": True}) == {"ok": True}


def test_the_refresh_is_keyed_by_this_profiles_world_id(monkeypatch):
    """A count read against the wrong world is worse than no count: it would
    report another server's exploration as this one's progress."""
    from tw2002_aiclient import world_identity

    seen: list = []

    def _count(world_id, **kw):
        seen.append(world_id)
        return SECTOR_COUNT

    profile = app_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    expected = world_identity.world_id_from_profile(profile)

    # The spy is routed through the `sector_count` PARAMETER, not patched from
    # this body: `_drive` installs its own `known_sector_count` after the body
    # runs and would silently overwrite a patch made here, leaving this test
    # green while asserting nothing. The pin two sections up
    # (`..._store_unreadable_branch...`) exists because that already happened.
    _arm, _explore, _screen = _drive(
        monkeypatch, [L], store=TWO_LOOPS, recompute=lambda wid, **kw: DISCOVERED,
        sector_count=_count,
    )
    # world_stats.refresh + chain_detect/build_candidate_pairs both count
    # sectors for this profile's world_id (WO-CHAIN-BUBBLE-PAIR-FALLBACK).
    assert seen, f"never refreshed against any world"
    assert all(w == expected for w in seen), f"refreshed against the wrong world: {seen!r}"
    assert _screen.world_stats.merge({}) == {
        "known_sectors": SECTOR_COUNT,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
    }


def test_a_raising_world_model_costs_the_count_not_the_cockpit(monkeypatch):
    """The count and the chain search are independent reads on one keypress.
    A world model that will not open must not take the play loop down, and
    must not cost the discovered section that already succeeded."""
    _arm, _explore, screen = _drive(
        monkeypatch, [L], store=TWO_LOOPS,
        recompute=lambda wid, **kw: DISCOVERED,
        sector_count=OSError("world model gone"),
    )
    assert screen is not None
    assert screen.chains_session.status == "ok", "the popup never opened"
    # known_sectors refused; dead-end scan may still complete over [].
    assert screen.world_stats.merge({"ok": True}) == {
        "ok": True,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
    }, "fabricated a known_sectors count"
    assert _scalars_after(screen) == {"chain_hops": 3, "chain_unit": "hops"}


def test_the_map_row_paints_the_count(monkeypatch):
    """The delivery proof. `status` carrying the field and the operator SEEING
    a number are different claims, and this repo has shipped a composer with no
    wire to the screen before. Painted, not merely present in a dict."""
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    win = _Win()
    s = screens_mod.PlayShellScreen(win, profile)
    s.spectating = False
    s.attached = False
    s.status_provider = lambda: {"ok": True, "known_sectors": SECTOR_COUNT}
    s.draw()
    painted = "\n".join(text for (_y, _x, text, _a) in win.writes)
    assert f"{SECTOR_COUNT} sectors" in painted, f"Map row never painted the count:\n{painted}"


def test_the_map_row_paints_unknown_without_a_count(monkeypatch):
    """Negative control: a Map row that printed a number regardless would pass
    the pin above on its own."""
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    win = _Win()
    s = screens_mod.PlayShellScreen(win, profile)
    s.spectating = False
    s.attached = False
    s.status_provider = lambda: {"ok": True}
    s.draw()
    painted = "\n".join(text for (_y, _x, text, _a) in win.writes)
    assert "sectors" not in painted, f"a sector count appeared from nowhere:\n{painted}"
