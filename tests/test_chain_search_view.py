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
