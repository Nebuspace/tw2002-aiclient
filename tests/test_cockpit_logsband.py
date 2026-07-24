"""Pure LOGS-band composer tests (WO-P3-041, Layer-A).

No curses/terminal involved — asserts the composed strings and pure
flash-timing decisions directly, per the ``tests/test_cockpit_hud.py`` /
``test_cockpit_liveness.py`` / ``test_cockpit_goals.py`` pure-function
convention this mirrors.
"""

import pytest

from tw2002_aiclient.cockpit.logsband import (
    LOGS_EMPTY,
    TICKER_FLASH_DURATION_S,
    compose_logs_lines,
    flash_active,
    newest_tail_entry,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_logs_empty_marker_matches_canon_honest_empty_text():
    assert LOGS_EMPTY == "(none yet)"


def test_ticker_flash_duration_is_one_point_zero_per_canon():
    # Canon `trainer-cockpit.md` "Liveness & motion": "ticker flash | newest
    # LOG row bold, TICKER_FLASH_DURATION_S = 1.0" -- distinct from the
    # CREDITS delta-chip's own CREDIT_FLASH_DURATION_S (1.5).
    assert TICKER_FLASH_DURATION_S == 1.0


# ---------------------------------------------------------------------------
# compose_logs_lines — honest-empty
# ---------------------------------------------------------------------------


def test_none_status_is_honest_empty():
    assert compose_logs_lines(None, width=40, height=3) == [LOGS_EMPTY]


def test_non_dict_status_is_honest_empty():
    assert compose_logs_lines("nope", width=40, height=3) == [LOGS_EMPTY]
    assert compose_logs_lines(42, width=40, height=3) == [LOGS_EMPTY]
    assert compose_logs_lines(object(), width=40, height=3) == [LOGS_EMPTY]


def test_missing_log_tail_key_is_honest_empty():
    assert compose_logs_lines({}, width=40, height=3) == [LOGS_EMPTY]


def test_log_tail_not_a_list_is_honest_empty():
    assert compose_logs_lines({"log_tail": "nope"}, width=40, height=3) == [LOGS_EMPTY]
    assert compose_logs_lines({"log_tail": None}, width=40, height=3) == [LOGS_EMPTY]
    assert compose_logs_lines({"log_tail": {}}, width=40, height=3) == [LOGS_EMPTY]
    assert compose_logs_lines({"log_tail": 5}, width=40, height=3) == [LOGS_EMPTY]


def test_empty_log_tail_list_is_honest_empty():
    assert compose_logs_lines({"log_tail": []}, width=40, height=3) == [LOGS_EMPTY]


def test_log_tail_of_only_hostile_entries_is_honest_empty():
    class HostileStr:
        def __str__(self):
            raise RuntimeError("boom")

    assert compose_logs_lines({"log_tail": [None, HostileStr()]}, width=40, height=3) == [LOGS_EMPTY]


# ---------------------------------------------------------------------------
# compose_logs_lines — real tail: newest-last, fit/clip, oldest-drop-first
# ---------------------------------------------------------------------------


def test_real_tail_fits_within_height_renders_all_in_order():
    tail = ["first line", "second line"]
    assert compose_logs_lines({"log_tail": tail}, width=40, height=5) == tail


def test_real_tail_exceeding_height_drops_oldest_first_newest_last():
    tail = ["oldest", "middle", "newer", "newest"]
    # height=2 -> only the last 2 entries survive, in original order, so
    # the bottom line is always the newest.
    assert compose_logs_lines({"log_tail": tail}, width=40, height=2) == ["newer", "newest"]


def test_real_tail_exactly_matching_height_keeps_all():
    tail = ["a", "b", "c"]
    assert compose_logs_lines({"log_tail": tail}, width=40, height=3) == tail


def test_single_line_height_shows_only_the_newest_entry():
    tail = ["oldest", "middle", "newest"]
    assert compose_logs_lines({"log_tail": tail}, width=40, height=1) == ["newest"]


def test_shorter_tail_than_height_is_not_blank_padded():
    tail = ["only line"]
    assert compose_logs_lines({"log_tail": tail}, width=40, height=5) == ["only line"]


# ---------------------------------------------------------------------------
# compose_logs_lines — hostile-entry hardening (coerce / drop, never raise)
# ---------------------------------------------------------------------------


def test_non_str_entries_are_coerced_via_str():
    tail = [42, 3.5, True]
    assert compose_logs_lines({"log_tail": tail}, width=40, height=5) == ["42", "3.5", "True"]


def test_none_entries_are_dropped_not_rendered_as_literal_none():
    tail = ["real line", None, "another line"]
    assert compose_logs_lines({"log_tail": tail}, width=40, height=5) == ["real line", "another line"]


def test_hostile_str_dunder_entry_is_dropped_not_raised():
    class HostileStr:
        def __str__(self):
            raise RuntimeError("boom")

    tail = ["before", HostileStr(), "after"]
    assert compose_logs_lines({"log_tail": tail}, width=40, height=5) == ["before", "after"]


def test_hostile_dict_subclass_entry_is_contained():
    class HostileDict(dict):
        def __repr__(self):
            raise RuntimeError("boom")

        def __str__(self):
            raise RuntimeError("boom")

    tail = ["before", HostileDict(), "after"]
    assert compose_logs_lines({"log_tail": tail}, width=40, height=5) == ["before", "after"]


def test_log_tail_tuple_is_accepted_same_as_list():
    tail = ("a", "b")
    assert compose_logs_lines({"log_tail": tail}, width=40, height=5) == ["a", "b"]


# ---------------------------------------------------------------------------
# compose_logs_lines — width/height edges
# ---------------------------------------------------------------------------


def test_height_zero_returns_empty_list_even_with_real_tail():
    assert compose_logs_lines({"log_tail": ["a"]}, width=40, height=0) == []


def test_height_negative_returns_empty_list():
    assert compose_logs_lines({"log_tail": ["a"]}, width=40, height=-3) == []


def test_height_non_int_never_raises_and_returns_empty_list():
    assert compose_logs_lines({"log_tail": ["a"]}, width=40, height=None) == []
    assert compose_logs_lines({"log_tail": ["a"]}, width=40, height="tall") == []


def test_width_zero_or_negative_empties_lines_but_preserves_count():
    tail = ["one", "two"]
    assert compose_logs_lines({"log_tail": tail}, width=0, height=5) == ["", ""]
    assert compose_logs_lines({"log_tail": tail}, width=-5, height=5) == ["", ""]


def test_width_zero_preserves_honest_empty_line_count():
    assert compose_logs_lines({}, width=0, height=3) == [""]


def test_width_clips_each_line():
    tail = ["hello world", "goodbye world"]
    assert compose_logs_lines({"log_tail": tail}, width=5, height=5) == ["hello", "goodb"]


def test_width_non_int_never_raises_and_empties():
    tail = ["one"]
    assert compose_logs_lines({"log_tail": tail}, width=None, height=5) == [""]
    assert compose_logs_lines({"log_tail": tail}, width="wide", height=5) == [""]


def test_width_overflow_error_never_raises_and_empties():
    # int(float("inf")) raises OverflowError, not TypeError/ValueError; and
    # json.loads() accepts a bare Infinity literal by default, so this is a
    # realistic hostile wire payload.
    tail = ["one"]
    assert compose_logs_lines({"log_tail": tail}, width=float("inf"), height=5) == [""]


def test_height_overflow_error_never_raises():
    tail = ["one"]
    assert compose_logs_lines({"log_tail": tail}, width=40, height=float("inf")) == []


# ---------------------------------------------------------------------------
# newest_tail_entry
# ---------------------------------------------------------------------------


def test_newest_tail_entry_none_status_is_none():
    assert newest_tail_entry(None) is None


def test_newest_tail_entry_no_real_tail_is_none():
    assert newest_tail_entry({}) is None
    assert newest_tail_entry({"log_tail": []}) is None
    assert newest_tail_entry({"log_tail": "nope"}) is None


def test_newest_tail_entry_returns_last_coerced_entry():
    assert newest_tail_entry({"log_tail": ["a", "b", "c"]}) == "c"


def test_newest_tail_entry_coerces_non_str_newest():
    assert newest_tail_entry({"log_tail": ["a", 42]}) == "42"


def test_newest_tail_entry_skips_trailing_hostile_entry_to_last_survivor():
    class HostileStr:
        def __str__(self):
            raise RuntimeError("boom")

    # The hostile entry is DROPPED entirely (not rendered as a placeholder),
    # so the newest surviving entry is "b", not the hostile one.
    assert newest_tail_entry({"log_tail": ["a", "b", HostileStr()]}) == "b"


# ---------------------------------------------------------------------------
# flash_active — age-vs-duration decision
# ---------------------------------------------------------------------------


def test_flash_active_none_arrival_never_flashes():
    assert flash_active(None, now=0.0) is False
    assert flash_active(None, now=100.0) is False


def test_flash_active_at_the_moment_of_arrival():
    assert flash_active(10.0, now=10.0) is True


def test_flash_active_just_under_duration():
    assert flash_active(10.0, now=10.0 + TICKER_FLASH_DURATION_S - 0.01) is True


def test_flash_active_at_exact_duration_boundary_is_false():
    # age < duration_s -- the boundary itself is NOT flashing (matches the
    # sibling family's own inclusive/exclusive stale-boundary convention:
    # exactly-at-the-edge tips to the "no longer recent" side).
    assert flash_active(10.0, now=10.0 + TICKER_FLASH_DURATION_S) is False


def test_flash_active_past_duration_is_false():
    assert flash_active(10.0, now=10.0 + TICKER_FLASH_DURATION_S + 1.0) is False


def test_flash_active_custom_duration_s():
    assert flash_active(0.0, now=4.9, duration_s=5.0) is True
    assert flash_active(0.0, now=5.0, duration_s=5.0) is False


def test_flash_active_now_before_arrival_is_false_not_negative_flash():
    # A clock that moved backward between draws -- must not compute a
    # negative age and treat it as "very fresh".
    assert flash_active(10.0, now=5.0) is False


@pytest.mark.parametrize("bad_arrival", ["text", object(), [], {}, float("inf"), float("-inf"), float("nan")])
def test_flash_active_hostile_arrival_never_raises_and_is_false(bad_arrival):
    assert flash_active(bad_arrival, now=0.0) is False


@pytest.mark.parametrize("bad_now", ["text", object(), [], {}, float("inf"), float("-inf"), float("nan")])
def test_flash_active_hostile_now_never_raises_and_is_false(bad_now):
    assert flash_active(0.0, now=bad_now) is False


def test_flash_active_hostile_duration_s_falls_back_to_module_default():
    # A hostile duration_s degrades to TICKER_FLASH_DURATION_S rather than
    # comparing against garbage or raising.
    assert flash_active(10.0, now=10.5, duration_s=float("nan")) is True  # 0.5 < 1.0 default
    assert flash_active(10.0, now=10.5, duration_s="not-a-number") is True


def test_flash_active_raising_float_dunder_never_raises():
    class HostileFloat:
        def __float__(self):
            raise RuntimeError("boom")

    assert flash_active(HostileFloat(), now=0.0) is False
    assert flash_active(0.0, now=HostileFloat()) is False


# ---------------------------------------------------------------------------
# Never-raises sweep across every public function
# ---------------------------------------------------------------------------


_HOSTILE_INPUTS = [
    None,
    True,
    False,
    0,
    -1,
    3.5,
    float("inf"),
    float("-inf"),
    float("nan"),
    "",
    "text",
    [],
    {},
    object(),
]


@pytest.mark.parametrize("bad", _HOSTILE_INPUTS)
def test_compose_logs_lines_never_raises_sweep(bad):
    compose_logs_lines(bad, width=bad, height=bad)


@pytest.mark.parametrize("bad", _HOSTILE_INPUTS)
def test_newest_tail_entry_never_raises_sweep(bad):
    newest_tail_entry(bad)


@pytest.mark.parametrize("bad", _HOSTILE_INPUTS)
def test_flash_active_never_raises_sweep(bad):
    flash_active(bad, now=bad, duration_s=bad)


def test_compose_logs_lines_hostile_log_tail_entries_mixed_bag_never_raises():
    class HostileStr:
        def __str__(self):
            raise RuntimeError("boom")

    class HostileDict(dict):
        def __repr__(self):
            raise RuntimeError("boom")

    tail = [None, HostileStr(), HostileDict(), 1, 2.0, True, "ok", [], {}]
    result = compose_logs_lines({"log_tail": tail}, width=40, height=10)
    assert isinstance(result, list)
    assert all(isinstance(line, str) for line in result)
