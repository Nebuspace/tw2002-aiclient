"""Pure bubble composer pins (WO-PLAY-CHAIN-BUBBLE-VIZ)."""

from __future__ import annotations

import pytest

from tw2002_aiclient.cockpit import chain_bubbles


class _Chain:
    def __init__(self, sectors):
        self.sectors = tuple(sectors)


def test_empty_chain_is_quiet_placeholder():
    lines = chain_bubbles.compose_chain_bubbles(None, width=40)
    assert len(lines) == chain_bubbles.CHAIN_VIZ_H
    assert any("no trade loop yet" in ln for ln in lines)


def test_closed_cycle_drops_repeated_closing_sector():
    assert chain_bubbles.chain_bubble_sectors(_Chain([10, 11, 12, 10])) == [10, 11, 12]


def test_current_sector_is_star_marked():
    lines = chain_bubbles.compose_chain_bubbles(
        _Chain([100, 101, 100]),
        current_sector=100,
        port_classes={100: "BSB", 101: "SSS"},
        width=80,
    )
    assert any("★" in ln for ln in lines)
    assert any("100" in ln for ln in lines)
    assert any("BSB" in ln for ln in lines)


def test_unknown_port_class_renders_question_mark():
    lines = chain_bubbles.compose_chain_bubbles(
        _Chain([5, 6, 5]),
        port_classes={5: "BSB"},
        width=80,
    )
    joined = "\n".join(lines)
    assert "?" in joined


def test_known_ports_filter_drops_non_port_warps():
    sectors = chain_bubbles.filter_port_only_sectors([10, 99, 11], known_ports={10, 11})
    assert sectors == [10, 11]
    lines = chain_bubbles.compose_chain_bubbles(
        _Chain([10, 99, 11, 10]),
        known_ports={10, 11},
        port_classes={10: "BSB", 11: "SSS"},
        width=80,
    )
    joined = "\n".join(lines)
    assert "99" not in joined


def test_truncation_suffix_is_deterministic():
    sectors = list(range(1, 20)) + [1]
    lines = chain_bubbles.compose_chain_bubbles(_Chain(sectors), width=30)
    joined = "\n".join(lines)
    assert "…" in joined
    assert "h" in joined


@pytest.mark.parametrize("hostile", [None, object(), {"sectors": "x"}, "nope"])
def test_composer_never_raises(hostile):
    lines = chain_bubbles.compose_chain_bubbles(hostile, width="bad")
    assert len(lines) == chain_bubbles.CHAIN_VIZ_H


def test_caption_marks_class_pair_when_no_star():
    """WO-CHAIN-BUBBLE-PAIR-FALLBACK — honest unpriced chrome."""
    lines = chain_bubbles.compose_chain_bubbles(
        _Chain([10, 20, 10]),
        port_classes={10: "BSB", 20: "SBS"},
        width=80,
        caption="class pair",
    )
    joined = "\n".join(lines)
    assert "class pair" in joined
    assert "no trade loop yet" not in joined


def test_star_wins_over_caption():
    lines = chain_bubbles.compose_chain_bubbles(
        _Chain([10, 20, 10]),
        current_sector=10,
        port_classes={10: "BSB", 20: "SBS"},
        width=80,
        caption="class pair",
    )
    joined = "\n".join(lines)
    assert "★" in joined
    assert "class pair" not in joined
