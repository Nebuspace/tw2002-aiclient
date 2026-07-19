"""Profit-miner tests (DESIGN-v2 §3 v2.1 item 11c, C10) -- no network,
operates on hand-built ledger-entry-shaped dicts (the exact shape
twclient.ledger.LedgerWriter.record_do() produces: `input`,
`settled_class`, `reward`)."""

import json

import pytest

from twclient import miner


def _entry(input_text, settled_class, d_credits=0, d_turns=0):
    reward = {}
    if d_credits is not None:
        reward["d_credits"] = d_credits
    if d_turns is not None:
        reward["d_turns"] = d_turns
    return {"input": input_text, "settled_class": settled_class, "reward": reward}


def _build_trade_loop_ledger():
    """Three repeats of a profitable buy-then-sell 2-step loop (B: -100
    credits/-1 turn, S: +400 credits/-1 turn -- net +300cr over 2 turns =
    150 cr/turn), each preceded by a distinct single noise action (so no
    OTHER 2-window signature recurs -- N_lead/N0/N1/N2 are all distinct
    inputs, only ("B","S") ever repeats)."""
    entries = [_entry("N_lead", "sector_display", d_credits=-10, d_turns=-1)]
    for i in range(3):
        entries.append(_entry("B", "port_trade", d_credits=-100, d_turns=-1))
        entries.append(_entry("S", "port_trade", d_credits=400, d_turns=-1))
        entries.append(_entry(f"N{i}", "sector_display", d_credits=-10, d_turns=-1))
    return entries


def test_mine_patterns_surfaces_the_recurring_trade_loop():
    entries = _build_trade_loop_ledger()
    patterns = miner.mine_patterns(entries=entries, min_support=2)
    trade_loop = next(p for p in patterns if p["inputs"] == ["B", "S"])
    assert trade_loop["pre_class"] == "sector_display"
    assert trade_loop["post_class"] == "port_trade"
    assert trade_loop["support"] == 3
    assert trade_loop["cr_per_turn"] == 150.0
    assert trade_loop["cr_per_action"] == 150.0


def test_mine_patterns_filters_out_unsupported_one_off_windows():
    entries = _build_trade_loop_ledger()
    patterns = miner.mine_patterns(entries=entries, min_support=2)
    # the lead-in noise ("N_lead", "B") only ever happens once -- must
    # never surface no matter how it's window-sliced.
    assert not any(p["inputs"] == ["N_lead", "B"] for p in patterns)
    assert not any(p["inputs"] == ["S", "N0"] for p in patterns)


def test_mine_patterns_ranks_higher_profit_pattern_first():
    """Two independently-recurring 2-step patterns at different profit
    rates ("A","B") @ 250 cr/turn, ("C","D") @ 5 cr/turn -- the miner
    must rank the richer one first regardless of ledger order."""
    entries = (
        [_entry("lead1", "sector_display"), _entry("A", "menu", 500, -1), _entry("B", "menu", 0, -1)]
        + [_entry("mid1", "sector_display"), _entry("A", "menu", 500, -1), _entry("B", "menu", 0, -1)]
        + [_entry("lead2", "port_trade"), _entry("C", "computer", 10, -1), _entry("D", "computer", 0, -1)]
        + [_entry("mid2", "port_trade"), _entry("C", "computer", 10, -1), _entry("D", "computer", 0, -1)]
    )
    patterns = miner.mine_patterns(entries=entries, min_support=2, min_window=2, max_window=2)
    rich = next(p for p in patterns if p["inputs"] == ["A", "B"])
    poor = next(p for p in patterns if p["inputs"] == ["C", "D"])
    assert rich["cr_per_turn"] == 250.0
    assert poor["cr_per_turn"] == 5.0
    assert patterns.index(rich) < patterns.index(poor)
    assert patterns[0] is rich


def test_mine_patterns_never_surfaces_a_pattern_built_on_redacted_input():
    # Without the redaction guard this ("<redacted>", "Q") 2-window would
    # legitimately reach support=2 (same pre_class both times) -- the
    # guard must still drop it.
    entries = (
        [_entry("lead", "sector_display"), _entry("<redacted>", "main_command", 0, 0), _entry("Q", "main_command", 0, -1)]
        + [_entry("mid", "sector_display"), _entry("<redacted>", "main_command", 0, 0), _entry("Q", "main_command", 0, -1)]
    )
    patterns = miner.mine_patterns(entries=entries, min_support=2)
    assert all("<redacted>" not in p["inputs"] for p in patterns)


def test_mine_patterns_falls_back_to_credits_per_action_when_no_turn_spent():
    # A window that never touches turns_left (e.g. pure menu navigation,
    # d_turns simply absent from reward -- the real ledger's "omit
    # what's unknown" convention) still ranks by credits-per-action
    # instead of vanishing.
    def e(input_text, d_credits):
        return {"input": input_text, "settled_class": "menu", "reward": {"d_credits": d_credits}}

    entries = [e("lead", 0), e("X", 50), e("Y", 0), e("mid", 0), e("X", 50), e("Y", 0)]
    patterns = miner.mine_patterns(entries=entries, min_support=2, min_window=2, max_window=2)
    match = next(p for p in patterns if p["inputs"] == ["X", "Y"])
    assert match["cr_per_turn"] is None
    assert match["cr_per_action"] == 25.0


def test_mine_patterns_empty_ledger_returns_empty_list():
    assert miner.mine_patterns(entries=[]) == []


def test_mine_patterns_normalizes_haggled_numerals_so_the_loop_still_recurs():
    """Live-caught: a real port haggles, so the offer amount differs
    every round (146 one trip, 158 the next) -- a literal-match miner
    would never see the profit-bearing step recur. Numeric inputs must
    be wildcarded for grouping while the real credits/turns math (which
    comes from `reward`, never from the input text) still sums
    correctly."""
    entries = (
        [_entry("lead1", "sector_display"), _entry("B", "port_trade", 0, -1), _entry("146", "menu", -146, 0), _entry("S", "port_trade", 0, -1), _entry("370", "menu", 370, 0)]
        + [_entry("lead2", "sector_display"), _entry("B", "port_trade", 0, -1), _entry("158", "menu", -158, 0), _entry("S", "port_trade", 0, -1), _entry("369", "menu", 369, 0)]
    )
    patterns = miner.mine_patterns(entries=entries, min_support=2, min_window=4, max_window=4)
    loop = next(p for p in patterns if p["inputs"] == ["B", "<NUM>", "S", "<NUM>"])
    assert loop["support"] == 2
    # occurrence 1: -146+370=224 over 2 turns=112/turn; occurrence 2: -158+369=211/2=105.5/turn; avg=108.75
    assert loop["cr_per_turn"] == pytest.approx(108.75)
    # sample_steps preserves the REAL literal values from one occurrence, not the "<NUM>" wildcard.
    assert [s["input"] for s in loop["sample_steps"]] == ["B", "146", "S", "370"]


def test_propose_drafts_writes_only_profitable_top_k(tmp_path):
    entries = _build_trade_loop_ledger()
    patterns = miner.mine_patterns(entries=entries, min_support=2)
    drafts = miner.propose_drafts(patterns, top_k=3, drafts_dir=tmp_path)
    assert len(drafts) >= 1
    assert all((d["cr_per_turn"] or 0) > 0 or (d["cr_per_action"] or 0) > 0 for d in drafts)
    for d in drafts:
        assert (tmp_path / f"{d['name']}.json").exists()


def test_mine_ledger_end_to_end_reads_the_given_entries_and_proposes(tmp_path):
    entries = _build_trade_loop_ledger()
    result = miner.mine_ledger(min_support=2, entries=entries, drafts_dir=tmp_path)
    assert result["patterns"][0]["inputs"] == ["B", "S"]
    assert len(result["drafts"]) >= 1
    top_draft = result["drafts"][0]
    saved = json.loads((tmp_path / f"{top_draft['name']}.json").read_text(encoding="utf-8"))
    assert saved["source"] == "mined"
    assert saved["mined_stats"]["support"] == 3
    assert [s["input"] for s in saved["steps"]] == ["B", "S"]
