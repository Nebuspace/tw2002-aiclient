"""Pins for the rebirth-ported coaching engine (WO-COACH-ENGINE-PORT).

Canon: `canon/engine/coaching-engine.md` I1–I4.

The load-bearing properties, in the order they can actually hurt:

1. ``default_kb_paths`` resolves to the repo's REAL data dir. The pre-rebirth
   expression was a bare ``parent.parent`` that silently encoded how deep the
   module sat; moving the file breaks it with no error until a load runs.
2. ``infer_coach_triggers`` is fail-closed — an unreadable input omits its
   trigger rather than guessing one.
3. ``compose_decisions_coach`` renders ONLY authored card text. Card prose is
   canon's single-source rule; a second source is the thing being prevented.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tw2002_aiclient import coach_kb
from tw2002_aiclient.chain_units import (
    chain_hop_count_and_unit,
    hop_count_from_sectors,
    unit_for_source,
)
from tw2002_aiclient.coach_engine import (
    compose_decisions_coach,
    compose_decisions_placeholder,
    infer_coach_triggers,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# -- 1. data location -------------------------------------------------------


def test_default_kb_paths_resolve_to_the_repo_data_dir_that_actually_exists():
    """The placement trap: a relative ``__file__`` walk must land on real files.

    Asserting the files EXIST (not merely that the string looks right) is the
    point -- a wrong-depth resolution produces a perfectly plausible path.
    """
    strategies, params = coach_kb.default_kb_paths()
    assert strategies == REPO_ROOT / "data" / "coach" / "strategies.json"
    assert params == REPO_ROOT / "data" / "coach" / "params.json"
    assert strategies.is_file(), f"resolved to a non-existent file: {strategies}"
    assert params.is_file(), f"resolved to a non-existent file: {params}"


def test_default_kb_paths_honors_an_explicit_root():
    s, p = coach_kb.default_kb_paths(Path("/tmp/elsewhere"))
    assert s == Path("/tmp/elsewhere/strategies.json")
    assert p == Path("/tmp/elsewhere/params.json")


def test_the_shipped_kb_loads_and_is_the_only_card_source():
    """Loads tip data. Also pins that no card text originates in code."""
    kb = coach_kb.load_coach_kb(*coach_kb.default_kb_paths())
    assert kb.strategies, "shipped strategies.json produced no cards"
    raw = json.loads((REPO_ROOT / "data" / "coach" / "strategies.json").read_text())
    assert {c.id for c in kb.strategies} == {s["id"] for s in raw["strategies"]}
    assert {c.title for c in kb.strategies} == {s["title"] for s in raw["strategies"]}


# -- 2. schema validation ---------------------------------------------------


def test_missing_required_strategy_field_is_rejected():
    with pytest.raises(ValueError, match="missing fields"):
        coach_kb.validate_strategy({"id": "x", "title": "t"})


def test_duplicate_strategy_id_is_rejected(tmp_path):
    doc = {
        "version": 1,
        "strategies": [_row("dup"), _row("dup")],
    }
    p = tmp_path / "s.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate strategy id"):
        coach_kb.load_coach_kb(p)


def test_non_object_root_is_rejected(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        coach_kb.load_coach_kb(p)


def test_scalar_where_a_list_belongs_is_rejected():
    row = _row("x")
    row["steps"] = "not-a-list"
    with pytest.raises(ValueError, match="steps must be a list"):
        coach_kb.validate_strategy(row)


def _row(card_id: str) -> dict:
    return {
        "id": card_id,
        "title": "T",
        "what": "W",
        "when_trigger": "docked_at_port",
        "tradeoffs": [],
        "steps": [],
        "okf_refs": [],
        "hypothesis_flags": [],
    }


# -- 3. trigger inference (canon I2, fail-closed) ---------------------------


def test_no_input_yields_no_triggers():
    """Fail-closed: nothing known -> nothing advised."""
    assert infer_coach_triggers() == []


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"has_port": True}, "docked_at_port"),
        ({"classification": "port_trade"}, "docked_at_port"),
        ({"classification": "cim_report"}, "docked_at_port"),
        ({"fighters_aboard": 0}, "at_shipyard"),
        ({"prompt": "Welcome to StarDock"}, "at_shipyard"),
        ({"genesis_count": 1}, "at_dead_end"),
        ({"dead_end_count": 1}, "at_dead_end"),
        ({"explore_mode": "auto"}, "exploring_frontier"),
        ({"prompt": "Option? "}, "toll_or_gate"),
        ({"prompt": "How many fighters to use?"}, "toll_or_gate"),
        ({"classification": "fighter_encounter"}, "toll_or_gate"),
        ({"chain": {"source": "discovered", "steps": 3}}, "chain_opportunity"),
        ({"loop_depleting": True}, "loop_depleting"),
    ],
)
def test_each_trigger_fires_on_its_own_signal(kwargs, expected):
    assert expected in infer_coach_triggers(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fighters_aboard": 3},        # has fighters -> not shipyard
        {"explore_mode": "off"},       # explicitly off -> not exploring
        {"genesis_count": 0, "dead_end_count": 0},
        {"chain": {"source": "discovered", "steps": 1}},  # single leg, not a loop
        {"chain": None},
        {"classification": "unknown"},
        {"prompt": ""},
        # WO-COACH-LOOP-DEPLETING-TRIGGER: identity-true only — truthy junk
        # and False/absent must not fire.
        {"loop_depleting": False},
        {"loop_depleting": 1},
        {"loop_depleting": "yes"},
        {"loop_depleting": "True"},
    ],
)
def test_negative_signals_produce_no_trigger(kwargs):
    """Each of these is the near-miss of a real trigger -- none may fire."""
    assert infer_coach_triggers(**kwargs) == []


def test_triggers_are_unique_and_order_is_stable():
    kwargs = dict(
        has_port=True,
        classification="port_trade",   # same trigger by a second route
        fighters_aboard=0,
        prompt="stardock option?",     # at_shipyard AND toll_or_gate
        chain={"source": "discovered", "steps": 4},
        loop_depleting=True,
        genesis_count=2,
        explore_mode="auto",
    )
    got = infer_coach_triggers(**kwargs)
    assert len(got) == len(set(got)), f"duplicate triggers: {got}"
    assert got == infer_coach_triggers(**kwargs)
    assert got == [
        "docked_at_port",
        "at_shipyard",
        "chain_opportunity",
        "loop_depleting",
        "at_dead_end",
        "exploring_frontier",
        "toll_or_gate",
    ]


def test_the_reachable_trigger_set_is_pinned_against_the_shipped_cards():
    """Enumerate the CLOSED side: which authored cards can never fire.

    ``infer_coach_triggers`` emits seven ids. ``strategies.json`` authors eight
    cards. The one whose trigger is never produced is unreachable through
    this engine -- pinned here so the gap is a stated fact rather than a
    surprise, and so closing it has to update this list deliberately.
    """
    emitted = {
        "docked_at_port",
        "at_shipyard",
        "chain_opportunity",
        "loop_depleting",
        "at_dead_end",
        "exploring_frontier",
        "toll_or_gate",
    }
    kb = coach_kb.load_coach_kb(*coach_kb.default_kb_paths())
    authored = {c.when_trigger for c in kb.strategies}
    assert authored - emitted == {"planet_management"}
    assert emitted - authored == set()


# -- 4. compose (canon I3, authored text only) ------------------------------


def test_none_kb_and_empty_triggers_give_the_honest_placeholder():
    assert compose_decisions_coach(None, ["docked_at_port"]) == compose_decisions_placeholder()
    kb = coach_kb.load_coach_kb(*coach_kb.default_kb_paths())
    assert compose_decisions_coach(kb, []) == compose_decisions_placeholder()
    assert compose_decisions_coach(kb, None) == compose_decisions_placeholder()


def test_unmatched_trigger_gives_the_placeholder_not_an_invented_card():
    kb = coach_kb.load_coach_kb(*coach_kb.default_kb_paths())
    assert compose_decisions_coach(kb, ["no_such_trigger"]) == compose_decisions_placeholder()


def test_rendered_lines_come_from_the_authored_card():
    kb = coach_kb.load_coach_kb(*coach_kb.default_kb_paths())
    card = next(c for c in kb.strategies if c.when_trigger == "chain_opportunity")
    lines = compose_decisions_coach(kb, ["chain_opportunity"], width=200)
    assert lines[0].startswith(card.title)
    joined = " ".join(lines)
    assert card.what[:20] in joined
    if card.steps:
        assert card.steps[0][:20] in joined


def test_hypothesis_flagged_card_is_marked_unverified():
    """An unproven number must never be presented as fact."""
    kb = coach_kb.load_coach_kb(*coach_kb.default_kb_paths())
    flagged = next(c for c in kb.strategies if c.hypothesis_flags)
    lines = compose_decisions_coach(kb, [flagged.when_trigger], width=200)
    assert "(unverified)" in lines[0]


def test_unflagged_card_is_not_marked_unverified():
    """The converse -- otherwise the marker could be unconditional."""
    kb = coach_kb.load_coach_kb(*coach_kb.default_kb_paths())
    clean = next(c for c in kb.strategies if not c.hypothesis_flags)
    lines = compose_decisions_coach(kb, [clean.when_trigger], width=200)
    assert "(unverified)" not in lines[0]


def test_cards_are_ordered_by_priority_then_id():
    kb = coach_kb.load_coach_kb(*coach_kb.default_kb_paths())
    lines = compose_decisions_coach(
        kb, ["at_dead_end", "chain_opportunity"], width=200, max_cards=2
    )
    chain_card = next(c for c in kb.strategies if c.when_trigger == "chain_opportunity")
    # chain_opportunity card has priority 12, at_dead_end has 40 -> chain first
    assert lines[0].startswith(chain_card.title)


def test_max_cards_and_width_are_honored():
    kb = coach_kb.load_coach_kb(*coach_kb.default_kb_paths())
    triggers = ["docked_at_port", "at_dead_end", "exploring_frontier", "at_shipyard"]
    lines = compose_decisions_coach(kb, triggers, width=12, max_cards=1)
    assert all(len(ln) <= 12 for ln in lines), lines
    # one card -> at most title + body + first step
    assert len(lines) <= 3


def test_a_duplicate_trigger_does_not_duplicate_a_card():
    kb = coach_kb.load_coach_kb(*coach_kb.default_kb_paths())
    once = compose_decisions_coach(kb, ["at_dead_end"], width=200)
    twice = compose_decisions_coach(kb, ["at_dead_end", "at_dead_end"], width=200)
    assert once == twice


# -- 5. chain hop/step arithmetic -------------------------------------------


def test_hops_and_steps_are_not_conflated():
    """A macro's step count must never be labelled 'hops'."""
    assert unit_for_source("discovered") == "hops"
    assert unit_for_source("presence_seed") == "hops"
    assert unit_for_source("recorded") == "steps"
    assert unit_for_source(None) == "steps"


def test_hop_count_from_sectors_counts_edges_not_nodes():
    assert hop_count_from_sectors([1, 2, 3]) == 2
    assert hop_count_from_sectors([1, 2, 3, 1]) == 3   # closed cycle keeps return hop
    assert hop_count_from_sectors([1]) is None
    assert hop_count_from_sectors([]) is None
    assert hop_count_from_sectors(None) is None
    assert hop_count_from_sectors(["a", "b"]) is None  # unparseable -> None, not 1


def test_chain_hop_count_and_unit_across_the_shapes():
    class _Obj:
        hops = [1, 2, 3]

    assert chain_hop_count_and_unit(_Obj()) == (3, "hops")
    assert chain_hop_count_and_unit(None) == (None, "hops")
    assert chain_hop_count_and_unit({"source": "discovered", "steps": 4}) == (4, "hops")
    assert chain_hop_count_and_unit({"source": "recorded", "steps": 4}) == (4, "steps")
    # presence seed: no steps, derive from the path
    assert chain_hop_count_and_unit(
        {"source": "presence_seed", "sectors": [1, 2, 3]}
    ) == (2, "hops")
    # a dict with nothing usable
    assert chain_hop_count_and_unit({"source": "recorded"}) == (None, "hops")


def test_zero_steps_is_treated_as_no_chain():
    assert chain_hop_count_and_unit({"source": "discovered", "steps": 0})[0] is None
