"""WO-CHAIN-NPORT-WIRE — the pure N-port chain formatter.

Payloads here are deliberately duck-typed `SimpleNamespace`s, never real
`chain_search.ProfitChainResult`s: `format_profit_chain_lines` reads
everything by `getattr` and must never import or isinstance-check the
result type. If a test needed the real class, the view had grown a
coupling it is not allowed to have.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tw2002_aiclient import chain_search_view as V


def _chain(sectors, hops_n, turns, cr):
    return SimpleNamespace(
        sectors=tuple(sectors),
        hops=tuple(object() for _ in range(hops_n)),
        turns=turns,
        cr_per_turn=cr,
    )


def _payload(chains=(), reason=None, detail=None, adapter_note=None, search_note=None):
    return SimpleNamespace(
        chains=tuple(chains),
        reason=reason,
        detail=detail,
        adapter_note=adapter_note,
        search_note=search_note,
    )


# -- rows -------------------------------------------------------------------


def test_renders_a_cycle_row_with_counts_and_provenance():
    lines = V.format_profit_chain_lines(_payload([_chain((10, 12, 11, 10), 3, 3, 30.0)]))
    assert lines[0] == V.TITLE
    row = lines[1]
    assert "10>12>11>" in row       # closed ring, duplicate tail dropped
    assert "3h" in row and "3t" in row and "30/t" in row
    assert V.SOURCE_TAG in row      # never "recorded"/"mined"


def test_best_marker_only_on_row_zero():
    lines = V.format_profit_chain_lines(
        _payload([_chain((1, 2, 3, 1), 3, 3, 30.0), _chain((4, 5, 4), 2, 2, 10.0)])
    )
    assert lines[1].startswith(V.BEST_UNICODE)
    assert not lines[2].startswith(V.BEST_UNICODE)


def test_ascii_twin_when_unicode_is_unavailable():
    lines = V.format_profit_chain_lines(
        _payload([_chain((1, 2, 3, 1), 3, 3, 30.0)]), unicode_ok=False
    )
    assert lines[1].startswith(V.BEST_ASCII)
    assert V.BEST_UNICODE not in "\n".join(lines)


def test_source_tag_stays_within_its_reserved_width():
    """The tag column is reserved and never truncated; a rename that blows
    the ceiling must fail here rather than silently eat another column."""
    assert len(V.SOURCE_TAG) <= V._SOURCE_TAG_MAX_W


def test_below_floor_chain_row_marked_discovery():
    """WO-WIRE-EXECUTABLE-CHAIN-VIEW Accept #1 — 1-hop is discovery-only."""
    lines = V.format_profit_chain_lines(
        _payload([_chain((10, 12, 10), 1, 1, 50.0)])
    )
    row = lines[1]
    assert V.DISCOVERY_TAG in row
    assert "1h" in row
    assert V.SOURCE_TAG in row


def test_executable_chain_row_has_no_discovery_tag():
    """WO-WIRE-EXECUTABLE-CHAIN-VIEW Accept #1 — ≥ floor is not discovery."""
    lines = V.format_profit_chain_lines(
        _payload([_chain((10, 12, 11, 10), 3, 3, 30.0)])
    )
    row = lines[1]
    assert V.DISCOVERY_TAG not in row
    assert V.SOURCE_TAG in row


# -- honest empties ---------------------------------------------------------


def test_empty_renders_the_typed_reason():
    lines = V.format_profit_chain_lines(_payload(reason="no_tradeable_hops"))
    assert lines[0] == V.TITLE
    assert V._REASON_TEXT["no_tradeable_hops"] in lines[-1]


def test_unknown_reason_degrades_to_the_default_text():
    lines = V.format_profit_chain_lines(_payload(reason="something_new"))
    assert V._DEFAULT_EMPTY_TEXT in lines[-1]


# -- truncation is part of the rendering ------------------------------------


def test_truncated_result_gets_a_partial_banner():
    lines = V.format_profit_chain_lines(
        _payload([_chain((1, 2, 3, 1), 3, 3, 30.0)], search_note="budget exhausted")
    )
    assert any(V.PARTIAL_UNICODE in ln for ln in lines), lines


def test_adapter_truncation_alone_also_banners():
    """Either stage. A caller that only checked the search budget would
    render an edge-capped result as exhaustive."""
    lines = V.format_profit_chain_lines(
        _payload([_chain((1, 2, 3, 1), 3, 3, 30.0)], adapter_note="dropped 40 hops")
    )
    assert any(V.PARTIAL_UNICODE in ln for ln in lines)


def test_partial_banner_has_an_ascii_twin():
    lines = V.format_profit_chain_lines(
        _payload([_chain((1, 2, 3, 1), 3, 3, 30.0)], search_note="x"), unicode_ok=False
    )
    assert any(V.PARTIAL_ASCII in ln for ln in lines)
    assert V.PARTIAL_UNICODE not in "\n".join(lines)


def test_truncated_EMPTY_never_claims_absence():
    """The sharpest pin in this module. A truncated empty must NOT render
    the `no_closed_cycle` wording -- that is a claim about the world, and
    the search never finished making it."""
    lines = V.format_profit_chain_lines(
        _payload(reason="no_closed_cycle", search_note="budget exhausted")
    )
    body = "\n".join(lines)
    assert V._EMPTY_BUT_TRUNCATED_TEXT in body
    assert V._REASON_TEXT["no_closed_cycle"] not in body


def test_untruncated_empty_DOES_state_the_reason():
    """The other half of the asymmetry -- when the search really did
    complete, the honest answer is the reason, not a hedge."""
    lines = V.format_profit_chain_lines(_payload(reason="no_closed_cycle"))
    body = "\n".join(lines)
    assert V._REASON_TEXT["no_closed_cycle"] in body
    assert V._EMPTY_BUT_TRUNCATED_TEXT not in body


# -- hardening: never raises ------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        None,
        object(),
        SimpleNamespace(),
        SimpleNamespace(chains="not-a-sequence"),
        SimpleNamespace(chains=[SimpleNamespace()]),
        SimpleNamespace(chains=[_chain((), 0, None, None)]),
        SimpleNamespace(chains=[SimpleNamespace(sectors=None, hops=None, turns=True, cr_per_turn=True)]),
    ],
)
def test_never_raises_on_a_malformed_payload(payload):
    lines = V.format_profit_chain_lines(payload)
    assert isinstance(lines, list) and lines and lines[0] == V.TITLE


def test_bools_are_not_rendered_as_numbers():
    """`isinstance(True, int)` is True in Python -- an unguarded render
    would print `1t` / `1/t` for a boolean and look like real data."""
    lines = V.format_profit_chain_lines(
        _payload([SimpleNamespace(sectors=(1, 2, 1), hops=(1, 2), turns=True, cr_per_turn=True)])
    )
    assert f"{V.UNKNOWN}t" in lines[1]
    assert f"{V.UNKNOWN}/t" in lines[1]


@pytest.mark.parametrize("width", [0, -5, 1, 8, 200, "nonsense"])
def test_absurd_widths_do_not_raise(width):
    lines = V.format_profit_chain_lines(
        _payload([_chain((1, 2, 3, 1), 3, 3, 30.0)]), width=width
    )
    assert isinstance(lines, list) and len(lines) >= 2


# -- viewport windowing (WO-FIX-CHAINS-POPUP-DISCOVERED-PAGINATION) ----------


def _many_chains(n: int):
    return [
        _chain((i, i + 1, i), 2, 2, float(i + 1))
        for i in range(1, n + 1)
    ]


def test_window_size_bounds_formatted_rows_and_shows_n_of_m():
    """Only the visible slice is formatted; indicator names the viewport."""
    lines = V.format_profit_chain_lines(
        _payload(_many_chains(200)),
        window_start=0,
        window_size=10,
        selected_index=0,
    )
    body = [ln for ln in lines if ln != V.TITLE and "showing" not in ln]
    assert any(ln.startswith("showing 10 of 200") for ln in lines), lines
    assert len(body) == 10
    assert lines[0] == V.TITLE


def test_window_tracks_selected_index_past_the_fold():
    lines = V.format_profit_chain_lines(
        _payload(_many_chains(200)),
        window_start=40,
        window_size=10,
        selected_index=45,
    )
    assert any(ln.startswith("showing 10 of 200") for ln in lines)
    # Selected glyph on the in-window absolute index 45 (= offset 5).
    chain_rows = [ln for ln in lines if V.SOURCE_TAG in ln]
    assert len(chain_rows) == 10
    assert any(ln.startswith(V.SELECTED_UNICODE) for ln in chain_rows)


def test_small_set_below_window_unchanged_no_indicator():
    chains = _many_chains(3)
    lines = V.format_profit_chain_lines(
        _payload(chains), window_start=0, window_size=10
    )
    assert not any("showing" in ln for ln in lines)
    assert sum(1 for ln in lines if V.SOURCE_TAG in ln) == 3



def test_hold_scaled_display_multiplies_cr_per_turn_and_banners():
    """Unit 3.5 × 100 holds → 350/t with explicit banner."""
    lines = V.format_profit_chain_lines(
        _payload([_chain((10, 12, 11, 10), 3, 3, 3.5)]),
        hold_count=100,
    )
    body = "\n".join(lines)
    assert "hold-scaled ×100" in body
    assert "350/t" in body
    assert "4/t" not in body  # would be unit 3.5 rounded


def test_hold_scaled_omitted_keeps_unit_cr_per_turn():
    lines = V.format_profit_chain_lines(
        _payload([_chain((10, 12, 11, 10), 3, 3, 30.0)]),
    )
    body = "\n".join(lines)
    assert "hold-scaled" not in body
    assert "30/t" in body


def test_hold_scaled_junk_hold_count_keeps_unit():
    lines = V.format_profit_chain_lines(
        _payload([_chain((10, 12, 11, 10), 3, 3, 30.0)]),
        hold_count=0,
    )
    assert "hold-scaled" not in "\n".join(lines)
    assert "30/t" in "\n".join(lines)
