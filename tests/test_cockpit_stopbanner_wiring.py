"""WO-P5-064 Layer-B -- the STOP banner's REGION geometry (``cockpit.
layout.frame_layout``) and its DRAW wiring (``screens.PlayShellScreen.
draw()``).

Layer-A (the pure composer and the reason-code catalog) lives in
``tests/test_cockpit_stopbanner.py``; this file proves the two things a
pure composer test cannot: that the banner gets real rows on a real
frame without starving the panels around it, and that those rows actually
carry the composed text on screen, at the warn-bold weight canon calls
for.

Harness: the headless fake-stdscr idiom every sibling cockpit-panel suite
uses (``tests/test_cockpit_spectate.py``'s ``_RecordingWin``) -- real
``draw()``, real ``frame_layout``, no pty, no daemon, no network.
"""

from __future__ import annotations

import curses

import pytest

from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient.cockpit import layout as layout_mod
from tw2002_aiclient.cockpit import stopbanner
from tw2002_aiclient.cockpit.layout import frame_layout

FULL_ROWS, FULL_COLS = 40, 180
HANDLE = "Alpha"

# Every region key that existed before this WO -- the parity set below
# asserts the banner changes NONE of them while no halt is raised.
_PRE_WO_KEYS = (
    "mode", "message", "outer", "strip", "goals", "left_gutter",
    "center", "right_gutter", "decisions", "logs", "control_strip",
)


class _RecordingWin:
    def __init__(self, rows: int, cols: int) -> None:
        self._rows, self._cols = rows, cols
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self):
        return (self._rows, self._cols)

    def erase(self):
        return None

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))

    def refresh(self):
        return None


def _halt_status(*codes, mode=None, needs=True):
    status = {"intervention": {"needs_attention": needs,
                               "reasons": [{"code": c} for c in codes]}}
    if mode is not None:
        status["mode"] = mode
    return status


def _screen(monkeypatch, win, status=None, *, count=None):
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(win, profile)
    if status is not None or count is not None:
        def _provider():
            if count is not None:
                count.append(1)
            return status
        screen.status_provider = _provider
    return screen


def _row_calls(win, y: int, region: dict):
    """Every write landing on row ``y`` INSIDE ``region``'s own column
    span, sorted left-to-right.

    Bounding BOTH edges against the region is load-bearing, not tidiness:
    the outer double-line frame draws its own ``║`` border cells on this
    very row, at ``x = 0`` and ``x = cols - 1``. An unbounded reader
    silently returns ``"║! STOP — …║"`` and every ``startswith`` on it
    fails for a reason that has nothing to do with the banner (observed
    exactly once while writing this file -- the same trap
    ``tests/test_cockpit_spectate.py``'s own row reader documents)."""
    left, right = region["x"], region["x"] + region["w"]
    calls = [(x, text, a) for (yy, x, text, a) in win.calls if yy == y and left <= x < right]
    calls.sort(key=lambda c: c[0])
    return calls


def _row_text(win, y: int, region: dict) -> str:
    return "".join(text for _x, text, _a in _row_calls(win, y, region))


def _row_attrs(win, y: int, region: dict) -> set[int]:
    return {a for _x, text, a in _row_calls(win, y, region) if text.strip()}


# ---------------------------------------------------------------------------
# 1. Geometry -- no halt, nothing moves.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lines,cols", [
    (24, 80), (30, 100), (34, 130), (40, 180), (50, 200), (20, 60), (19, 60),
])
def test_no_halt_leaves_every_pre_wo_region_untouched(lines, cols):
    """The banner is opt-in: with ``needs_attention`` unset (the default,
    and the only thing today's daemon can report -- the ``intervention``
    block is still a WO-P2-020 Wave-3 CUT), ``frame_layout`` returns
    exactly what it returned before this WO."""
    default = frame_layout(lines, cols)
    explicit = frame_layout(lines, cols, needs_attention=False)
    assert default["intervention"] is None
    for key in _PRE_WO_KEYS:
        assert default[key] == explicit[key]


def test_too_small_still_refuses_and_allocates_no_banner():
    regions = frame_layout(10, 40, needs_attention=True)
    assert regions["mode"] == "too_small"
    assert regions["intervention"] is None
    assert regions["logs"] is None


# ---------------------------------------------------------------------------
# 2. Geometry -- at a halt the banner gets real rows, and LOGS keeps its own.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lines,cols", [
    (20, 60), (24, 80), (30, 100), (34, 130), (40, 180), (60, 200),
])
def test_banner_claims_rows_without_ever_shrinking_logs(lines, cols):
    """The hazard this WO was warned about, pinned: LOGS must never lose a
    row to the banner. ``layout.py`` computes LOGS' height with the exact
    same expression whether or not a halt is raised, so this holds by
    construction -- this test is what proves the construction."""
    calm = frame_layout(lines, cols)
    halt = frame_layout(lines, cols, needs_attention=True)
    assert halt["intervention"] is not None
    assert halt["logs"]["h"] == calm["logs"]["h"]
    assert halt["logs"]["w"] == calm["logs"]["w"]


@pytest.mark.parametrize("lines,cols", [(20, 60), (30, 100), (40, 180), (60, 200)])
def test_banner_is_full_inner_width_directly_above_the_control_strip(lines, cols):
    regions = frame_layout(lines, cols, needs_attention=True)
    banner = regions["intervention"]
    logs = regions["logs"]
    control = regions["control_strip"]
    assert banner["x"] == logs["x"]
    assert banner["w"] == logs["w"]
    # Stacked bottom-up: LOGS, then the banner, then the control strip --
    # the reborn analogue of the archive's LOG / intervention / control /
    # status stack.
    assert banner["y"] == logs["y"] + logs["h"]
    assert control["y"] == banner["y"] + banner["h"]


@pytest.mark.parametrize("lines,cols", [(20, 60), (24, 100), (40, 180), (60, 200)])
def test_no_region_overlaps_or_escapes_the_frame_at_a_halt(lines, cols):
    regions = frame_layout(lines, cols, needs_attention=True)
    outer = regions["outer"]
    spans = []
    for key in ("strip", "goals", "left_gutter", "center", "right_gutter",
                "decisions", "logs", "intervention", "control_strip"):
        region = regions[key]
        if region is None:
            continue
        assert region["y"] >= outer["y"]
        assert region["x"] >= outer["x"]
        assert region["y"] + region["h"] <= outer["y"] + outer["h"]
        assert region["x"] + region["w"] <= outer["x"] + outer["w"]
        spans.append((key, region))
    for i, (name_a, a) in enumerate(spans):
        for name_b, b in spans[i + 1:]:
            overlap_y = a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]
            overlap_x = a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
            assert not (overlap_y and overlap_x), f"{name_a} overlaps {name_b}"


def test_banner_height_is_the_three_band_constant_when_there_is_room():
    regions = frame_layout(FULL_ROWS, FULL_COLS, needs_attention=True)
    assert regions["intervention"]["h"] == layout_mod.INTERVENTION_H
    assert layout_mod.INTERVENTION_H == stopbanner.BANNER_H


def test_the_banner_costs_the_center_viewport_rows_only_below_37_lines():
    """Honest statement of what the banner DOES take, so a future change
    that widens the cost fails here rather than passing unnoticed. At and
    above 37 lines the column band has enough slack that the viewport
    still reaches its full VIEWPORT_H; below that the banner's rows come
    out of the viewport's already-clipped height (reported as a finding,
    not silently absorbed)."""
    for lines in (37, 40, 60):
        calm = frame_layout(lines, FULL_COLS)
        halt = frame_layout(lines, FULL_COLS, needs_attention=True)
        assert calm["center"]["h"] == halt["center"]["h"] == layout_mod.VIEWPORT_H
    for lines in (34, 35, 36):
        calm = frame_layout(lines, FULL_COLS)
        halt = frame_layout(lines, FULL_COLS, needs_attention=True)
        assert halt["center"]["h"] < calm["center"]["h"]


def test_the_banner_outranks_the_control_strip_under_height_pressure(monkeypatch):
    """Canon's safety-legibility invariant (``mode-line-and-teach-
    controls.md``: the strip "claims leftover height first -- before the
    control strip, before the ticker"; frame-PREP geometry guard #6).

    Below today's real ``MIN_LINES`` floor there is always room for both,
    so this probes the ordering with the floor lowered -- the same
    latent-guard shape ``layout.py``'s own ``LOGS_MIN_H`` clamp documents
    for a future floor change. Without the lowered floor the assertion
    would be unreachable, and an ordering regression would ship
    unnoticed."""
    monkeypatch.setattr(layout_mod, "MIN_LINES", 8)
    regions = frame_layout(8, 60, needs_attention=True)
    assert regions["mode"] != "too_small"
    assert regions["intervention"] is not None and regions["intervention"]["h"] >= 1
    assert regions["control_strip"] is None  # yielded so the halt could surface
    assert regions["logs"]["h"] >= 1  # and LOGS still never paid for it


# ---------------------------------------------------------------------------
# 3. Draw wiring -- the composed bands actually reach the screen.
# ---------------------------------------------------------------------------


def test_halt_paints_all_three_bands_on_the_banner_rows(monkeypatch):
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _halt_status("autopilot_no_candidates", mode="human"))
    screen.draw()

    banner = frame_layout(FULL_ROWS, FULL_COLS, needs_attention=True)["intervention"]
    assert _row_text(win, banner["y"], banner) == "! STOP — autopilot no candidates"
    assert _row_text(win, banner["y"] + 1, banner) == stopbanner.HANDOFF_MARKER
    assert _row_text(win, banner["y"] + 2, banner) == stopbanner.TEACH_LINE


@pytest.mark.parametrize("token", ["A)nalyze", "R)ecord", "T)assign"])
def test_teach_affordances_are_visible_on_screen_at_a_halt(monkeypatch, token):
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _halt_status("autopilot_halted"))
    screen.draw()
    drawn = "\n".join(text for (_y, _x, text, _a) in win.calls)
    assert token in drawn


def test_unknown_code_reaches_the_screen_raw_with_no_invented_prose(monkeypatch):
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _halt_status("singularity_encountered"))
    screen.draw()
    banner = frame_layout(FULL_ROWS, FULL_COLS, needs_attention=True)["intervention"]
    reason_row = _row_text(win, banner["y"], banner)
    assert "singularity_encountered" in reason_row
    for label in stopbanner.INTERVENTION_REASON_LABELS.values():
        assert label not in reason_row


def test_banner_rows_carry_the_warn_bold_weight(monkeypatch):
    """Canon: the strip is painted warn-tone AND bold. Colors are off in
    this harness (``has_colors`` False), so the honest remainder of that
    attr is A_BOLD -- never plain, and never A_REVERSE (reserved as the
    one selection/badge signal)."""
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _halt_status("autopilot_halted", mode="human"))
    screen.draw()
    banner = frame_layout(FULL_ROWS, FULL_COLS, needs_attention=True)["intervention"]
    for row in range(banner["y"], banner["y"] + banner["h"]):
        attrs = _row_attrs(win, row, banner)
        assert attrs, f"expected drawn content on banner row {row}"
        for attr in attrs:
            assert attr & curses.A_BOLD
            assert not attr & curses.A_REVERSE


def test_no_halt_paints_no_banner_and_leaves_the_bottom_stack_where_it_was(monkeypatch):
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, {"connected": True, "mode": "app"})
    screen.draw()
    drawn = "\n".join(text for (_y, _x, text, _a) in win.calls)
    assert "! STOP" not in drawn
    assert stopbanner.TEACH_LINE not in drawn
    # LOGS and the control strip stay exactly where the calm layout puts
    # them -- the banner's absence is a real absence, not a blank region.
    calm = frame_layout(FULL_ROWS, FULL_COLS)
    assert "LOGS" in _row_text(win, calm["logs"]["y"], calm["logs"])


def test_a_raising_banner_composer_never_crashes_the_draw_pass(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("composer exploded")

    monkeypatch.setattr(screens_mod.cockpit_stopbanner, "compose_stop_banner_lines", _boom)
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _halt_status("autopilot_halted"))
    screen.draw()  # must not raise
    assert win.calls  # the rest of the frame still painted


def test_a_raising_needs_attention_gate_degrades_to_the_calm_layout(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("gate exploded")

    monkeypatch.setattr(screens_mod.cockpit_stopbanner, "needs_attention", _boom)
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _halt_status("autopilot_halted"))
    screen.draw()
    drawn = "\n".join(text for (_y, _x, text, _a) in win.calls)
    assert "! STOP" not in drawn


# ---------------------------------------------------------------------------
# 4. The poll-guard invariant -- still exactly ONE status read per draw,
#    even though a halt makes the frame layout resolve twice.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [
    {"connected": True},
    {"intervention": {"needs_attention": True, "reasons": [{"code": "autopilot_halted"}]}},
])
def test_exactly_one_status_poll_per_draw_halt_or_not(monkeypatch, status):
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    count: list[int] = []
    screen = _screen(monkeypatch, win, status, count=count)
    screen.draw()
    assert len(count) == 1
    count.clear()
    screen.draw()
    assert len(count) == 1


def test_a_raising_status_provider_still_draws_the_calm_frame(monkeypatch):
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(win, profile)

    def _boom():
        raise RuntimeError("provider exploded")

    screen.status_provider = _boom
    screen.draw()
    drawn = "\n".join(text for (_y, _x, text, _a) in win.calls)
    assert "! STOP" not in drawn
    assert "LOGS" in drawn
