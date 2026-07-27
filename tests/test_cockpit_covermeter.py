"""Coverage meter -- App-vs-Human live share (WO-P5-072).

The pins here are chosen so that reintroducing the archive's retired
formula, its `AI` live slice, or a fabricated `0%` for an empty window
turns one of them red. Several are written as *properties over a grid*
rather than single examples, because the defects they guard against
(rounding drift, an `AI` token appearing only at some widths) hide easily
between hand-picked cases.
"""

from __future__ import annotations

import inspect

import pytest

from tw2002_aiclient.cockpit import covermeter


# --------------------------------------------------------------------------
# The canon formula -- and the archive formula it replaced
# --------------------------------------------------------------------------

def test_canon_worked_example():
    """`coverage-metrics.md`'s own example: 3 app + 1 human -> 75% / 25%."""
    assert covermeter.coverage_percentages(app=3, human=1) == (75, 25)


def test_human_is_inside_the_denominator():
    """The load-bearing recast: `app / (app + human)`, human INCLUDED.

    This is the single pin that kills the archived formula. The archive
    computed `trainer / (ai + trainer)` with human EXCLUDED, so for these
    inputs it returned 3/3 = 100%. Any regression back toward that shape --
    dropping the human term, or reviving an `ai` term in the denominator --
    lands on 100 here, not 75.
    """
    app_pct, _ = covermeter.coverage_percentages(app=3, human=1)
    assert app_pct == 75, "human dropped from the denominator (archive formula)"
    assert app_pct != 100


def test_escalation_is_the_exact_complement():
    for app, human in [(1, 0), (0, 1), (3, 1), (7, 13), (999, 1)]:
        app_pct, human_pct = covermeter.coverage_percentages(app=app, human=human)
        assert app_pct + human_pct == 100


@pytest.mark.parametrize("app", range(0, 25))
@pytest.mark.parametrize("human", range(0, 25))
def test_percentages_always_total_100_over_a_grid(app, human):
    """The pair are complements, so they total 100 for every window.

    Scope of this pin, stated honestly because it is narrower than it looks:
    the composer derives `human_pct` as `100 - app_pct`, so under the current
    implementation this sum is 100 *by construction* and no change to the
    rounding function alone can make it fail. Verified by mutation rather
    than assumed -- swapping `round(x)` for `int(x + 0.5)` leaves this grid
    fully green.

    What it does catch is the regression where someone rounds the two
    percentages independently *and* uses `int(x + 0.5)`: `1 app / 7 human`
    then yields `App 13% · Hum 88%` = 101. That mutation was run and this
    grid goes red on it.
    """
    pcts = covermeter.coverage_percentages(app=app, human=human)
    if app + human == 0:
        assert pcts is None
    else:
        assert sum(pcts) == 100


def test_complement_is_derived_not_recomputed():
    """The structural reason the sum holds -- pinned directly rather than
    inferred from the arithmetic, since the arithmetic agrees either way at
    most inputs. `1/7` is a `.5`-boundary window: `app_pct` is whatever the
    rounding yields, and `human_pct` must be exactly its complement."""
    app_pct, human_pct = covermeter.coverage_percentages(app=1, human=7)
    assert human_pct == 100 - app_pct


# --------------------------------------------------------------------------
# Honest `?` -- never invent a share
# --------------------------------------------------------------------------

def test_empty_window_is_unknown_not_zero_percent():
    """`0 / 0` is undefined. `COV 0%` would assert the app carried none of a
    session that never happened."""
    assert covermeter.coverage_percentages(app=0, human=0) is None
    line = covermeter.compose_coverage_meter(app=0, human=0)
    assert "0%" not in line
    assert covermeter.UNKNOWN in line


def test_empty_window_still_reports_the_counts_it_knows():
    """Counts known, share undefined -- report the counts, `?` the share."""
    line = covermeter.compose_coverage_meter(app=0, human=0)
    assert line == "COV ? · App 0 · Hum 0"


def test_absent_counts_render_bare_unknown():
    """No ledger on tip -> this is what the live product actually shows."""
    assert covermeter.compose_coverage_meter() == "COV ?"
    assert covermeter.compose_coverage_meter(app=None, human=None) == "COV ?"


def test_one_missing_count_is_unknown_not_half_a_meter():
    """A known app count with an unknown human count cannot yield a share --
    reporting `App 5` beside a `?` share would invite reading 5 as 100%."""
    assert covermeter.compose_coverage_meter(app=5, human=None) == "COV ?"
    assert covermeter.compose_coverage_meter(app=None, human=5) == "COV ?"


def test_known_counts_render_the_share():
    assert covermeter.compose_coverage_meter(app=3, human=1) == "COV 75% · App 3 · Hum 1"


# --------------------------------------------------------------------------
# No live AI slice -- the WO's grep pin, widened to a property
# --------------------------------------------------------------------------

@pytest.mark.parametrize("app", [None, 0, 1, 3, 7, 100, 99999])
@pytest.mark.parametrize("human", [None, 0, 1, 3, 7, 100, 99999])
@pytest.mark.parametrize("width", [None, 0, 5, 20, 40, 200])
def test_no_ai_term_in_any_rendered_meter(app, human, width):
    """Canon J1: the AI's live share is definitionally zero, and printing an
    `AI 0` slice would reassert a third live driver.

    Swept over the full input cross-product rather than one example, because
    an `AI` token added to only one branch (say, the unknown case) would
    survive a single-input grep pin.
    """
    line = covermeter.compose_coverage_meter(app=app, human=human, width=width)
    assert "AI" not in line
    assert "ai" not in line.lower().replace("human", "")


def test_composer_exposes_no_ai_parameter():
    """Structural companion to the string pin: the `ai` term must not be
    re-admitted through the API even if nothing renders it today."""
    for fn in (covermeter.compose_coverage_meter, covermeter.coverage_percentages):
        params = set(inspect.signature(fn).parameters)
        assert "ai" not in params
        assert "trainer" not in params, "legacy actor name re-admitted"


def test_module_declares_no_ai_or_trainer_constant():
    """The archive's `format_autonomy_counts` rendered `App N / AI N · Hum N`
    from module-level pieces; no such constant may exist here."""
    for name, value in vars(covermeter).items():
        if name.startswith("_") or not isinstance(value, str):
            continue
        assert "AI" not in value, f"{name} carries an AI term: {value!r}"


# --------------------------------------------------------------------------
# Width: dropped whole, never truncated into a wrong number
# --------------------------------------------------------------------------

def test_meter_drops_whole_rather_than_truncating_a_percentage():
    """`COV 75%` clipped to `COV 7` reads as seven percent -- a readable lie.
    The meter leaves the row instead."""
    full = covermeter.compose_coverage_meter(app=3, human=1)
    for width in range(1, len(full)):
        assert covermeter.compose_coverage_meter(app=3, human=1, width=width) == ""
    assert covermeter.compose_coverage_meter(app=3, human=1, width=len(full)) == full


def test_exact_fit_is_kept():
    line = covermeter.compose_coverage_meter(app=0, human=0)
    assert covermeter.compose_coverage_meter(app=0, human=0, width=len(line)) == line


def test_no_width_budget_returns_full_string():
    assert covermeter.compose_coverage_meter(app=3, human=1, width=None) != ""


# --------------------------------------------------------------------------
# Hardening -- never raises, never guesses
# --------------------------------------------------------------------------

def test_bool_counts_are_rejected_not_read_as_one():
    """`isinstance(True, int)` holds; a `True` in a count slot is a type error
    upstream and must not silently become the count 1."""
    assert covermeter.coverage_percentages(app=True, human=False) is None
    assert covermeter.compose_coverage_meter(app=True, human=1) == "COV ?"


def test_negative_counts_are_unknown():
    assert covermeter.coverage_percentages(app=-1, human=5) is None


def test_float_counts_are_unknown():
    """Row counts are whole; a float means someone computed a rate upstream."""
    assert covermeter.coverage_percentages(app=3.0, human=1) is None


@pytest.mark.parametrize(
    "hostile",
    [object(), "3", b"3", [], {}, float("nan"), float("inf"), complex(1, 2)],
)
def test_never_raises_on_hostile_input(hostile):
    covermeter.compose_coverage_meter(app=hostile, human=hostile, width=hostile)
    covermeter.coverage_percentages(app=hostile, human=hostile)


def test_tone_is_plain_not_a_badge():
    """The meter is a data readout like liveness, not an ok/warn/danger chip
    and not the teach band's chrome -- `screens.py::_control_strip_segment_attr`
    gives everything else plain `A_NORMAL`, which is what this asserts."""
    assert covermeter.METER_TONE is None


def test_label_is_cov_not_the_retired_auto():
    """`AUTO %` carried the retired "crossing 50% = flies itself" graduation
    framing (`coverage-metrics.md`); hub-approved 2026-07-27."""
    assert covermeter.METER_LABEL == "COV"
