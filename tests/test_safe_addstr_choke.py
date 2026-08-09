"""Proof lane for ``WO-AUDIT-SAFE-ADDSTR-DEDUPE``: ``screens.py``'s launcher/
bank/create-profile-form ``_safe_addstr`` now delegates onto
``cockpit.draw.safe_write`` -- the SAME hardened choke every cockpit panel
writes through -- instead of carrying its own separate, less-hardened local
clip. Four proof legs:

1. Hostile echo matrix -- control-char neutralization (this is the path that
   renders the operator's own live-typed ``edit_buf`` field echo at the
   create-profile form, so it doubles as that field's injection guard)
   pinned against ``_sanitize_controls``'s documented mapping (every C0
   ``\\x00-\\x1f`` and C1 ``\\x7f-\\x9f`` control collapses to a single
   space, alignment-preserving, no run-collapse).
2. Cell-width clip parity -- a CJK string straddling the width boundary
   drops the wide char whole (never split), matching ``_clip_cells``
   semantics exactly -- asserted against the choke's own primitive for
   identical inputs (parity by construction).
3. Last-column parity change, red-first -- the pre-fix ``screens.py`` blob
   (loaded from a SHA-pinned ``git show <sha>:...``, per
   ``.claude/agent-memory/monk/red-first-via-git-blob-not-live-revert.md``;
   the live working tree is never reverted) stopped one column short of a
   window's true last column unconditionally; the new delegate reaches it.
   The blob is pinned to an explicit SHA, never bare ``HEAD`` -- see
   ``_PRE_FIX_TIP`` below for why.
4. Delegation pin -- ``_safe_addstr`` IS the choke, not a lookalike:
   monkeypatching ``cockpit_draw.safe_write`` must intercept every call, and
   an exception raised by the patched choke must propagate through
   ``_safe_addstr`` un-caught (proving no local ``try/except`` reimplements
   anything around it any more).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from tw2002_aiclient import screens
from tw2002_aiclient.cockpit import draw as cockpit_draw
from tw2002_aiclient.cockpit import strip as cockpit_strip

REPO_ROOT = Path(__file__).resolve().parents[1]


class _RecordingWindow:
    """Minimal addstr-only curses double -- mirrors
    ``tests/test_cockpit_draw_runs.py``'s ``_RecordingWindow`` (this
    project's established fake-window idiom; ``draw.safe_write`` never calls
    ``addnstr``, per the "curses test doubles are addstr-only" convention)."""

    def __init__(self, rows: int = 10, cols: int = 20) -> None:
        self._rows, self._cols = rows, cols
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self._rows, self._cols

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))


# ---------------------------------------------------------------------------
# 1. Hostile echo matrix -- operator-typed edit_buf live-echo protection
# ---------------------------------------------------------------------------


def test_c0_and_c1_controls_neutralize_to_space_per_sanitize_controls_mapping():
    """Every C0 (\\x00-\\x1f) and C1 (\\x7f-\\x9f) control byte in text
    reaching ``_safe_addstr`` becomes a single plain space -- the exact
    documented mapping in ``cockpit.draw._sanitize_controls`` -- with
    surrounding literal characters preserved and NOT run-collapsed."""
    win = _RecordingWindow()
    text = "A\x00B\x07C\x1bD\x7fE\x9bF"  # NUL, BEL, ESC, DEL, a mid-C1 byte
    screens._safe_addstr(win, 0, 0, text, 3)

    assert len(win.calls) == 1
    _, _, written, attr = win.calls[0]
    assert written == "A B C D E F"  # each control -> exactly one space
    assert attr == 3


def test_injected_escape_sequence_marker_present_absent_pair():
    """The operator-typed ``edit_buf`` echo protection: an injected CSI
    escape sequence's ESC byte never reaches the window raw (ABSENT), while
    the surrounding literal payload the operator typed stays intact and
    findable at its expected position (PRESENT) -- proving the sequence is
    neutralized in place, not dropped or reordered."""
    win = _RecordingWindow(rows=5, cols=60)
    # A cursor-move + color-change CSI pair straddling a literal marker --
    # if this reached a real terminal's addstr raw, \x1b[2K would erase the
    # line and \x1b[31m would recolor it out from under the caller.
    text = "PRE\x1b[2K\x1b[31mMARKER\x1b[0mPOST"
    screens._safe_addstr(win, 0, 0, text, 0)

    written = win.calls[0][2]
    assert "\x1b" not in written  # marker ABSENT: no raw ESC byte reaches the window
    assert "MARKER" in written  # marker PRESENT: literal payload survives intact
    assert written.index("MARKER") == text.index("MARKER")  # position unchanged
    # The bracket/digit bytes around the neutralized ESC are plain
    # printable text, not control chars, so they are untouched -- only the
    # ESC lead-in itself collapses to a space, structurally breaking the
    # sequence rather than deleting it wholesale (alignment-preserving).
    assert written == "PRE [2K [31mMARKER [0mPOST"


# ---------------------------------------------------------------------------
# 2. Cell-width clip parity -- CJK wide-char boundary straddle
# ---------------------------------------------------------------------------


def test_wide_char_straddling_width_boundary_drops_whole_not_split():
    """A CJK string whose wide (2-cell) characters straddle the available
    budget drops the straddling character WHOLE, matching
    ``cockpit.draw._clip_cells`` exactly -- asserted against the choke's own
    primitive for the identical (sanitized) input, so this can't drift from
    what the choke itself does (parity by construction)."""
    win = _RecordingWindow(rows=5, cols=10)
    text = "永永永"  # 3 chars, 2 cells each == 6 cells total
    x = 5  # budget = max_x - x = 5 cells -- straddles the 3rd wide char
    screens._safe_addstr(win, 1, x, text, 0)

    assert len(win.calls) == 1
    written = win.calls[0][2]

    expected = cockpit_draw._clip_cells(cockpit_draw._sanitize_controls(text), 5)
    assert written == expected
    assert written == "永永"  # 4 cells used; the 3rd wide char (would need a 5th+6th
    # cell but only 1 remains) is dropped whole, not half-rendered


def test_narrow_ascii_is_unaffected_by_cell_width_accounting():
    """Sanity twin: plain ASCII is 1 cell per char, so the clip boundary is
    just a character count -- confirms the cell-width machinery doesn't
    over- or under-clip when nothing wide is present."""
    win = _RecordingWindow(rows=5, cols=10)
    screens._safe_addstr(win, 1, 5, "ABCDEFGH", 0)
    written = win.calls[0][2]
    expected = cockpit_draw._clip_cells(cockpit_draw._sanitize_controls("ABCDEFGH"), 5)
    assert written == expected == "ABCDE"


# ---------------------------------------------------------------------------
# 3. Last-column parity change -- red-first via pre-fix git blob
# ---------------------------------------------------------------------------


# The last commit BEFORE WO-AUDIT-SAFE-ADDSTR-DEDUPE's fix -- i.e. the tip
# whose tw2002_aiclient/screens.py still carries the old, un-hardened local
# ``_safe_addstr`` clip. Pinned to this exact SHA and NEVER bare ``HEAD``:
# at development time HEAD *was* this pre-fix tip, but the moment the fix
# landed as its own commit, HEAD moved onto the fix itself -- a committed
# test using bare ``HEAD:`` would then load the NEW code and its "old
# behavior" assertion would fail forever after. A red-first git-blob loader
# in COMMITTED test code must always pin the specific pre-fix SHA, not a
# moving ref (team-lead correction, WO-AUDIT-SAFE-ADDSTR-DEDUPE review,
# 2026-07-25 -- see the same rule now added to
# ``.claude/agent-memory/monk/red-first-via-git-blob-not-live-revert.md``).
_PRE_FIX_TIP = "7cd9ea9"


def _load_prefix_screens_module(tmp_path: Path):
    """Load the pre-``WO-AUDIT-SAFE-ADDSTR-DEDUPE`` ``screens.py`` blob from
    the pinned ``_PRE_FIX_TIP`` SHA into a throwaway module -- never reverts
    the live working file (see
    ``.claude/agent-memory/monk/red-first-via-git-blob-not-live-revert.md``).
    ``screens.py`` uses only absolute ``tw2002_aiclient.*`` imports (no
    package-relative ``from .x import y``), so no ``__package__`` shim is
    needed -- the blob's imports resolve against the real installed
    siblings, same as the memory note's relative-import wrinkle achieves for
    packages that DO need one.

    The pinned blob still imports the retired
    ``compose_profile_strip_from_row`` helper at module load time even though
    these choke tests only exercise ``_safe_addstr``. Stub that symbol on
    the live ``strip`` module only for the duration of the load so the blob
    can import without reviving product dead code or leaving the live module
    mutated for later tests."""
    added_stub = False
    if not hasattr(cockpit_strip, "compose_profile_strip_from_row"):

        def _legacy_compose_profile_strip_from_row(
            row: object, *, width: int, unicode_ok: bool = True
        ) -> str:
            host = getattr(row, "host", None) or getattr(row, "server", None)
            return cockpit_strip.compose_profile_strip(
                host=host,
                game_letter=getattr(row, "game_letter", None),
                handle=getattr(row, "handle", None),
                width=width,
                unicode_ok=unicode_ok,
            )

        cockpit_strip.compose_profile_strip_from_row = _legacy_compose_profile_strip_from_row
        added_stub = True

    try:
        blob = subprocess.run(
            ["git", "show", f"{_PRE_FIX_TIP}:tw2002_aiclient/screens.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
            text=True,
        ).stdout
        module_path = tmp_path / "prefix_screens.py"
        module_path.write_text(blob, encoding="utf-8")

        spec = importlib.util.spec_from_file_location(
            "tw2002_aiclient._prefix_screens_addstr_dedupe", module_path
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            del sys.modules[spec.name]
        return module
    finally:
        if added_stub:
            del cockpit_strip.compose_profile_strip_from_row


def test_old_safe_addstr_stopped_one_column_short_of_window_edge(tmp_path):
    """RED baseline: prove the pre-fix limitation actually existed. The old
    local clip was ``text[: max(0, max_x - x - 1)]`` -- unconditionally one
    column short of the window's true last column, regardless of content."""
    prefix = _load_prefix_screens_module(tmp_path)
    win = _RecordingWindow(rows=3, cols=10)
    text = "ABCDEFGHIJ"  # 10 chars -- longer than the window is wide
    prefix._safe_addstr(win, 1, 0, text, 0)

    assert len(win.calls) == 1
    _, x, written, _ = win.calls[0]
    assert written == "ABCDEFGHI"  # 9 chars: columns 0..8 only
    last_col_written = x + len(written) - 1
    assert last_col_written == 8  # max_x - 2 -- the true last column (9) untouched


def test_new_safe_addstr_reaches_the_window_true_last_column():
    """GREEN: the live delegate, same window/content, now reaches column
    ``max_x - 1`` -- a deliberate hardening-parity change cited in
    ``_safe_addstr``'s own docstring (WO-AUDIT-SAFE-ADDSTR-DEDUPE), not a
    regression -- see ``cockpit.draw``'s module docstring for the
    already-proven bottom-right-cell-``curses.error``-catch rationale."""
    win = _RecordingWindow(rows=3, cols=10)
    text = "ABCDEFGHIJ"
    screens._safe_addstr(win, 1, 0, text, 0)

    assert len(win.calls) == 1
    _, x, written, _ = win.calls[0]
    assert written == "ABCDEFGHIJ"  # all 10 chars: columns 0..9
    last_col_written = x + len(written) - 1
    assert last_col_written == 9  # max_x - 1 -- the true last column, now reached


# ---------------------------------------------------------------------------
# 4. Delegation pin -- _safe_addstr IS the choke, not a lookalike
# ---------------------------------------------------------------------------


def test_safe_addstr_delegates_every_call_onto_cockpit_draw_safe_write(monkeypatch):
    """Monkeypatching ``cockpit_draw.safe_write`` must intercept every
    ``screens._safe_addstr`` call with the exact args, unmodified -- so a
    future edit can't silently regrow a second, un-hardened local
    implementation without this test catching it."""
    calls: list[tuple] = []

    def _fake_safe_write(win, y, x, text, attr=0):
        calls.append((win, y, x, text, attr))

    monkeypatch.setattr(cockpit_draw, "safe_write", _fake_safe_write)

    win = _RecordingWindow()
    screens._safe_addstr(win, 4, 7, "hello", 9)

    assert calls == [(win, 4, 7, "hello", 9)]
    assert win.calls == []  # the fake intercepted it -- nothing reached the window


def test_safe_addstr_propagates_choke_exceptions_uncaught(monkeypatch):
    """No local ``try/except`` remains in ``screens._safe_addstr`` -- an
    exception raised by the (patched) choke propagates straight through,
    proving this is a pure delegate rather than a reimplementation with its
    own error-swallowing wrapped around a call to the choke."""

    def _boom(win, y, x, text, attr=0):
        raise RuntimeError("choke exploded")

    monkeypatch.setattr(cockpit_draw, "safe_write", _boom)

    with pytest.raises(RuntimeError, match="choke exploded"):
        screens._safe_addstr(_RecordingWindow(), 0, 0, "x", 0)
