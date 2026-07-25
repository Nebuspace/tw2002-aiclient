"""Tests for ``screens.py``'s ``_SharedPairs`` -- the ONE process-lifetime
curses color-pair allocator (WO-P3-040 REVISE, Mack CRITICAL finding;
widened to a ``(fg_name, bg_name)`` cache key at the WO-P4-053 draw-seam
merge so GAME viewport cell colors and chrome colors share it, rather than
GAME cells getting a second, independently-counting allocator -- see the
class's own docstring for why that would reopen the exact pair-number-
collision bug this class exists to eliminate).

Pure allocator tests: monkeypatch the shared ``curses`` module (``screens.
curses`` and ``cockpit.viewport_color.curses`` are the SAME module object,
both a plain ``import curses`` -- patching one patches every reference to
it, same pattern ``tests/test_play_chrome_nav.py`` already uses for
``screens.py``'s own curses references), never a real terminal.

This file absorbs the real allocation / pair-exhaustion / cache-on-failure
coverage that used to live in ``tests/test_cockpit_viewport_color.py``
against that module's own (now-deleted) ``GameCellPairs`` reference
implementation -- see that file's own docstring. It ADDS the one proof
that implementation could never make on its own: that a SINGLE shared
allocator instance keeps chrome's already-cached pair untouched once GAME
cells start allocating theirs (the regression class Mack originally
caught, reproduced here between chrome and game cells rather than between
two screen instances).
"""

from __future__ import annotations

import curses

import pytest

from tw2002_aiclient import screens as screens_mod


class _FakeCurses:
    """Records init_pair/color_pair/start_color calls; lets tests drive
    has_colors()/COLOR_PAIRS/exhaustion without a real terminal."""

    def __init__(self, *, has_colors=True, color_pairs_limit=None, init_pair_raises=False):
        self._has_colors = has_colors
        self.color_pairs_limit = color_pairs_limit
        self.init_pair_raises = init_pair_raises
        self.init_pair_calls: list[tuple[int, int, int]] = []
        self.start_color_calls = 0
        self.use_default_colors_calls = 0
        self.has_colors_calls = 0

    def has_colors(self):
        self.has_colors_calls += 1
        return self._has_colors

    def start_color(self):
        self.start_color_calls += 1

    def use_default_colors(self):
        self.use_default_colors_calls += 1

    def init_pair(self, n, fg, bg):
        if self.init_pair_raises:
            raise curses.error("simulated exhaustion")
        self.init_pair_calls.append((n, fg, bg))

    def color_pair(self, n):
        # A plain int -- NOT a tuple: callers OR curses.A_BOLD into
        # whatever attr_for() returns, and a tuple doesn't support `|`.
        # Small values here never collide with curses.A_BOLD's own bit.
        return n


def _patch_curses(monkeypatch, fake, *, limit_attr=True):
    monkeypatch.setattr(screens_mod.curses, "has_colors", fake.has_colors)
    monkeypatch.setattr(screens_mod.curses, "start_color", fake.start_color)
    monkeypatch.setattr(screens_mod.curses, "use_default_colors", fake.use_default_colors)
    monkeypatch.setattr(screens_mod.curses, "init_pair", fake.init_pair)
    monkeypatch.setattr(screens_mod.curses, "color_pair", fake.color_pair)
    if fake.color_pairs_limit is not None:
        monkeypatch.setattr(screens_mod.curses, "COLOR_PAIRS", fake.color_pairs_limit, raising=False)
    elif limit_attr and hasattr(screens_mod.curses, "COLOR_PAIRS"):
        monkeypatch.delattr(screens_mod.curses, "COLOR_PAIRS", raising=False)


# ---------------------------------------------------------------------------
# Basic allocation contract (mirrors the deleted GameCellPairs suite)
# ---------------------------------------------------------------------------


def test_no_color_support_short_circuits_to_normal_without_touching_curses(monkeypatch):
    fake = _FakeCurses(has_colors=False)
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    assert pairs.attr_for("red", "default") == curses.A_NORMAL
    assert fake.start_color_calls == 0
    assert fake.init_pair_calls == []


def test_both_default_never_allocates_a_pair(monkeypatch):
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    assert pairs.attr_for("default", "default") == curses.A_NORMAL
    assert fake.init_pair_calls == []


def test_default_fg_with_real_bg_allocates_a_pair_with_minus_one_fg(monkeypatch):
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    attr = pairs.attr_for("default", "red")
    assert attr == 1
    assert fake.init_pair_calls == [(1, -1, curses.COLOR_RED)]


def test_real_fg_with_default_bg_allocates_a_pair_with_minus_one_bg(monkeypatch):
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    attr = pairs.attr_for("green", "default")
    assert attr == 1
    assert fake.init_pair_calls == [(1, curses.COLOR_GREEN, -1)]


def test_single_arg_call_defaults_bg_to_default_zero_behavior_change(monkeypatch):
    # Every existing chrome caller uses the single-arg form (attr_for(fg))
    # -- this must be byte-for-byte the same allocation as the old
    # hardcoded `curses.init_pair(pair_n, fg, -1)`.
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    attr = pairs.attr_for("cyan")
    assert attr == 1
    assert fake.init_pair_calls == [(1, curses.COLOR_CYAN, -1)]
    # And it shares a cache key with the equivalent explicit two-arg call.
    attr2 = pairs.attr_for("cyan", "default")
    assert attr2 == attr
    assert len(fake.init_pair_calls) == 1


def test_same_combo_reuses_the_cached_pair_number(monkeypatch):
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    first = pairs.attr_for("red", "blue")
    second = pairs.attr_for("red", "blue")
    assert first == second == 1
    assert fake.init_pair_calls == [(1, curses.COLOR_RED, curses.COLOR_BLUE)]  # only ONE init_pair call


def test_distinct_combos_get_distinct_pair_numbers(monkeypatch):
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    a = pairs.attr_for("red", "default")
    b = pairs.attr_for("green", "default")
    c = pairs.attr_for("red", "blue")
    assert len({a, b, c}) == 3
    assert [call[0] for call in fake.init_pair_calls] == [1, 2, 3]


def test_pyte_only_names_resolve_through_the_merged_table(monkeypatch):
    # brown/magenta/white/black are GAME-cell (pyte) vocabulary, absent
    # from the old chrome-only table -- must resolve through the same
    # allocator now that the two tables are merged.
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    pairs.attr_for("brown", "black")
    pairs.attr_for("magenta", "white")
    assert fake.init_pair_calls == [
        (1, curses.COLOR_YELLOW, curses.COLOR_BLACK),  # pyte's own ANSI-yellow quirk
        (2, curses.COLOR_MAGENTA, curses.COLOR_WHITE),
    ]


def test_hostile_unhashable_fg_name_does_not_crash(monkeypatch):
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    # fg_name is a list (unhashable) -- must degrade to "default" for both
    # color resolution AND the cache key, never raise TypeError on a dict-
    # key hash attempt.
    attr = pairs.attr_for(["red"], "green")
    assert attr == 1
    assert fake.init_pair_calls == [(1, -1, curses.COLOR_GREEN)]
    # Repeating the exact same hostile input reuses the cached pair.
    attr2 = pairs.attr_for(["red"], "green")
    assert attr2 == attr
    assert len(fake.init_pair_calls) == 1


# --- pair-table exhaustion degrades without crashing -----------------------


def test_proactive_color_pairs_limit_degrades_without_crash(monkeypatch):
    fake = _FakeCurses(color_pairs_limit=2)  # room for pair 1 only (pair 0 reserved)
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    first = pairs.attr_for("red", "default")  # allocates pair 1
    assert first == 1
    second = pairs.attr_for("green", "default")  # next_pair(2) >= limit(2) -> exhausted
    assert second == curses.A_NORMAL
    assert len(fake.init_pair_calls) == 1  # init_pair never even attempted for the 2nd


def test_exhaustion_is_cached_not_retried_every_call(monkeypatch):
    fake = _FakeCurses(color_pairs_limit=1)  # pair 0 reserved -- nothing allocatable
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    first = pairs.attr_for("red", "default")
    second = pairs.attr_for("red", "default")
    third = pairs.attr_for("blue", "default")  # a DIFFERENT combo, still exhausted
    assert first == second == third == curses.A_NORMAL
    assert fake.init_pair_calls == []


def test_reactive_curses_error_from_init_pair_degrades_without_crash(monkeypatch):
    fake = _FakeCurses(init_pair_raises=True)
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    attr = pairs.attr_for("red", "default")  # init_pair raises curses.error internally
    assert attr == curses.A_NORMAL

    # Cached as a known failure -- a second call for the SAME combo must
    # not attempt init_pair again (curses.error would raise every time if
    # it did).
    attr2 = pairs.attr_for("red", "default")
    assert attr2 == curses.A_NORMAL


def test_color_pairs_attribute_missing_falls_back_to_reactive_check_only(monkeypatch):
    # Mirrors real pre-initscr() curses: curses.COLOR_PAIRS raises
    # AttributeError until a terminal session exists. getattr(..., None)
    # must absorb that rather than crashing the proactive check.
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)  # no color_pairs_limit -> attribute stays absent
    pairs = screens_mod._SharedPairs()

    attr = pairs.attr_for("red", "default")
    assert attr == 1


# ---------------------------------------------------------------------------
# WO-P4-053: chrome colors survive GAME-cell allocation on the SAME shared
# allocator -- the regression class Mack originally caught (two independent
# allocators colliding on pair numbers), reproduced here between chrome and
# game cells sharing ONE allocator instead of between two screen instances.
# ---------------------------------------------------------------------------


def test_chrome_pair_is_init_paired_exactly_once_even_as_game_cells_allocate(monkeypatch):
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    # Chrome allocates first, single-arg style (info tone, cyan-on-default)
    # -- mirrors PlayShellScreen._init_colors' own `_shared_pairs.attr_for
    # (info_fg_name)` call.
    chrome_attr = pairs.attr_for("cyan")
    assert chrome_attr == 1
    assert fake.init_pair_calls == [(1, curses.COLOR_CYAN, -1)]

    # A wave of distinct GAME-cell (fg, bg) combinations allocate next --
    # each MUST get its own new pair number, never pair 1 (chrome's).
    game_attrs = [
        pairs.attr_for("red", "default"),
        pairs.attr_for("green", "black"),
        pairs.attr_for("brown", "blue"),  # pyte's own yellow-quirk name
        pairs.attr_for("magenta", "white"),
        pairs.attr_for("default", "cyan"),
    ]
    assert sorted(set(game_attrs)) == [2, 3, 4, 5, 6]

    # THE regression proof: chrome's own pair number (1) was init_pair'd
    # EXACTLY ONCE across the whole sequence -- no game-cell allocation
    # ever re-initialized it with a different color, which is exactly the
    # corruption Mack's PoC reproduced against two independent allocators.
    pair_1_calls = [c for c in fake.init_pair_calls if c[0] == 1]
    assert pair_1_calls == [(1, curses.COLOR_CYAN, -1)]

    # And re-querying the SAME chrome combo after all that game-cell
    # allocation returns the identical cached attr -- still pair 1, still
    # cyan-on-default -- with no additional init_pair call at all.
    chrome_attr_again = pairs.attr_for("cyan")
    assert chrome_attr_again == chrome_attr == 1
    assert len(fake.init_pair_calls) == 1 + len(game_attrs)  # no extra call for the re-query


def test_start_color_and_use_default_colors_called_exactly_once_total(monkeypatch):
    # A second, independent allocator's own lazy start_color()/
    # use_default_colors() would double-call these -- with one shared
    # allocator serving both chrome and game cells, they fire exactly
    # once for the whole process regardless of how many distinct combos
    # (chrome or game) are subsequently resolved.
    fake = _FakeCurses()
    _patch_curses(monkeypatch, fake)
    pairs = screens_mod._SharedPairs()

    pairs.attr_for("cyan")  # chrome-style
    pairs.attr_for("red", "blue")  # game-style
    pairs.attr_for("green", "black")  # game-style

    assert fake.start_color_calls == 1
    assert fake.use_default_colors_calls == 1
