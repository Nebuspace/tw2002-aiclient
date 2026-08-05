"""Pins for WO-STATUS-CHAIN-SCALARS-COACH — the producer, and the coach wire.

Canon: `canon/engine/coaching-engine.md` I2/I3 ("it yields the pane to live
activity"), `canon/surfaces/trainer-cockpit.md` §"Panel states".

Two independent halves, kept in separate sections so a failure names which:

**A — the producer.** `cockpit/goals.py` reads ``status["chain_hops"]`` /
``["chain_unit"]``; until this WO nothing in the product wrote either, so the
GOALS Chain row could only ever render "unknown" on a live run while the suite
stayed green on values the tests themselves supplied. The load-bearing property
is not "the field gets written" — it is **which outcomes are allowed to write
it**. A search that was truncated, or ran against a world with no map, has
established nothing, and reporting "none yet" from either would be a fabricated
absence.

**B — the coach wire.** `cockpit/decisions.py` may now render authored coach
callouts, but only into a pane that would otherwise be empty, and only without
ever breaking its own never-raises contract.

The defects these are built to catch are listed at each section head.
"""

from __future__ import annotations

from tw2002_aiclient.cockpit import autonomy_keys

import pytest

from tw2002_aiclient import chain_search, chain_status, chains
from tw2002_aiclient.chain_status import ChainScalars, as_chain_like
from tw2002_aiclient.cockpit import decisions as decisions_mod
from tw2002_aiclient.cockpit.decisions import compose_decisions_lines
from tw2002_aiclient.cockpit.goals import compose_goals_lines


# ---------------------------------------------------------------------------
# Fixtures — REAL product objects, not hand-rolled look-alikes.
#
# This matters more than usual here: the first cut of the producer read
# ``.hops`` off the *result* (which has no such attribute) and passed a smoke
# test only because the smoke test's fake carried the attribute the code
# assumed. A fake shaped like the assumption cannot catch a wrong assumption.
# ---------------------------------------------------------------------------


def _hop(frm: int, to: int) -> chains.TradeHop:
    return chains.TradeHop(frm=frm, to=to, commodity="Fuel Ore", margin=50.0, turns=1)


def _chain(sectors: list[int]) -> chains.ProfitChain:
    hops = tuple(_hop(sectors[i], sectors[i + 1]) for i in range(len(sectors) - 1))
    return chains.ProfitChain(
        sectors=tuple(sectors),
        hops=hops,
        overall_profit=100.0,
        turns=len(hops),
        cr_per_turn=50.0,
        cr_per_execution=100.0,
    )


def _result(*, chains_=(), reason=None, search_note=None, adapter_note=None, world_id="w"):
    return chain_search.ProfitChainResult(
        world_id=world_id,
        chains=tuple(chains_),
        reason=reason,
        search_note=search_note,
        adapter_note=adapter_note,
    )


def _scalars(discovered) -> dict:
    cs = ChainScalars()
    cs.update(discovered)
    return cs.merge({})


def _goals_chain_row(status: dict) -> str:
    rows = [ln for ln in compose_goals_lines(status, width=40) if "Chain" in ln]
    assert len(rows) == 1, rows
    return rows[0]


# ===========================================================================
# A — PRODUCER
#
# Catches: reading .hops off the result (always None); marking a failed or
# truncated search as "looked and found nothing"; clobbering a fresher value;
# mutating the caller's dict; raising on the cockpit's per-draw path.
# ===========================================================================


def test_the_ranked_first_chain_is_what_reaches_status():
    # chains is ranked hop-count DESC, so chains[0] is the longest cycle --
    # what "Chain N hops" means. Reading .hops off the RESULT finds nothing
    # and reports None forever; that is the defect this pin exists for.
    result = _result(chains_=[_chain([1, 2, 3, 4, 1]), _chain([5, 6, 5])])
    assert _scalars(result) == {"chain_hops": 4, "chain_unit": "hops"}


def test_a_discovered_chain_moves_the_goals_row_off_unknown():
    # The end-to-end statement of the gap: same row, before and after.
    before = _goals_chain_row({})
    after = _goals_chain_row(_scalars(_result(chains_=[_chain([1, 2, 1])])))
    assert "—" in before  # UNKNOWN_DETAIL
    assert after != before
    assert "2 hops" in after


@pytest.mark.parametrize(
    "label,discovered",
    [
        ("finder raised / no world_id", None),
        ("not a result at all", object()),
        ("chains attribute is None", type("X", (), {"chains": None})()),
        (
            "never explored",
            _result(reason=chain_search.REASON_NO_WORLD_MODEL),
        ),
        (
            "empty but the search truncated",
            _result(reason=chain_search.REASON_NO_CLOSED_CYCLE, search_note="cut"),
        ),
        (
            "empty but the ADAPTER truncated",
            _result(reason=chain_search.REASON_NO_CLOSED_CYCLE, adapter_note="cut"),
        ),
    ],
)
def test_outcomes_that_establish_nothing_write_nothing(label, discovered):
    # Each of these must leave the GOALS row saying "unknown", NOT "none yet".
    # `truncated` is the subtle one: chain_search's own docstring says a
    # truncated search that found nothing "has not established that nothing
    # is there", and it is true if EITHER note is set.
    assert _scalars(discovered) == {}, label
    assert "—" in _goals_chain_row(_scalars(discovered)), label


def test_a_completed_search_over_a_known_world_may_say_none_yet():
    # The one case that IS an established absence -- withholding it would be
    # its own dishonesty, so this is pinned as firmly as the six above.
    status = _scalars(_result(reason=chain_search.REASON_NO_TRADEABLE_HOPS))
    assert status == {"chain_hops": 0, "chain_unit": "hops"}
    assert "none yet" in _goals_chain_row(status)


def test_the_no_world_model_reason_literal_matches_chain_search():
    # chain_status copies the literal rather than importing chain_search (a
    # ~40ms import the cockpit draw path must not carry). This is the pin that
    # keeps the copy from drifting -- without it the copy is a silent time bomb.
    from tw2002_aiclient import chain_detect

    assert chain_status._REASON_NO_WORLD_MODEL == chain_search.REASON_NO_WORLD_MODEL
    assert chain_status._REASON_NO_WORLD_MODEL == chain_detect.REASON_NO_WORLD_MODEL


def test_merge_does_not_mutate_the_caller_dict():
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([1, 2, 1])]))
    original = {"ok": True}
    merged = cs.merge(original)
    assert original == {"ok": True}
    assert merged is not original
    assert merged["chain_hops"] == 2


def test_merge_passes_a_non_dict_through_untouched():
    # The provider's "no status" signal is None; converting it to a dict here
    # would make a dead daemon look like a live one with no chain.
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([1, 2, 1])]))
    assert cs.merge(None) is None
    sentinel = object()
    assert cs.merge(sentinel) is sentinel


def test_merge_never_clobbers_a_value_the_caller_supplied():
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([1, 2, 3, 1])]))  # cached: 3
    supplied = {"chain_hops": 9, "chain_unit": "steps"}
    assert cs.merge(supplied) == supplied


def test_merge_fills_only_the_key_that_is_missing():
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([1, 2, 3, 1])]))
    assert cs.merge({"chain_unit": "steps"}) == {"chain_hops": 3, "chain_unit": "steps"}


class _RaisingChains:
    @property
    def chains(self):
        raise ZeroDivisionError("hostile")


class _RaisingTruncated:
    chains = ()

    @property
    def truncated(self):
        raise ZeroDivisionError("hostile")


class _RaisingSequence:
    def __len__(self):
        return 1

    def __getitem__(self, index):
        raise ZeroDivisionError("hostile")


class _RaisingIndex:
    chains = _RaisingSequence()


@pytest.mark.parametrize(
    "hostile",
    [_RaisingChains(), _RaisingTruncated(), _RaisingIndex()],
    ids=["chains-raises", "truncated-raises", "index-raises"],
)
def test_update_never_raises_on_a_hostile_shape(hostile):
    # `update` runs on the human's keypress in the play loop; a raise there
    # takes the cockpit down. An unreadable shape is an unknown, not a crash.
    cs = ChainScalars()
    cs.update(hostile)
    assert cs.merge({}) == {}



def test_best_chain_is_retained_alongside_scalars():
    """WO-PLAY-CHAIN-BUBBLE-VIZ: ranked-first cycle survives for bubble viz."""
    cs = ChainScalars()
    chain = _chain([10, 11, 12, 10])
    cs.update(_result(chains_=[chain, _chain([1, 2, 1])]))
    assert cs.best_chain is chain
    assert cs.merge({}) == {"chain_hops": 3, "chain_unit": "hops"}
    # Chain object must never land on status JSON.
    assert "chain_best" not in cs.merge({})
    assert "sectors" not in cs.merge({})


def test_failed_discovery_does_not_erase_best_chain():
    cs = ChainScalars()
    chain = _chain([10, 11, 12, 10])
    cs.update(_result(chains_=[chain]))
    cs.update(None)
    cs.update(_result(chains_=(), search_note="budget"))
    assert cs.best_chain is chain


def test_completed_empty_search_clears_best_chain_to_quiet_empty():
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([10, 11, 12, 10])]))
    cs.update(_result(chains_=(), reason="none"))
    assert cs.best_chain is None
    assert cs.merge({}) == {"chain_hops": 0, "chain_unit": "hops"}


def test_port_classes_enrich_from_world_model_on_successful_update(tmp_path):
    """WO-CHAIN-BUBBLE-PORT-CLASSES: real class labels, not perpetual '?'."""
    from tw2002_aiclient import world_model

    world_id = "bubble-ports"
    world_model.upsert_sector(
        world_id,
        {"sector_id": 10, "warps": [11], "port": {"class": "BSB"}},
        state_dir=tmp_path,
    )
    world_model.upsert_sector(
        world_id,
        {"sector_id": 11, "warps": [10], "port": {"class": "SSS"}},
        state_dir=tmp_path,
    )
    # Classless port still counts as known for the filter.
    world_model.upsert_sector(
        world_id,
        {"sector_id": 99, "warps": [10], "port": {}},
        state_dir=tmp_path,
    )
    cs = ChainScalars()
    cs.update(
        _result(chains_=[_chain([10, 11, 10])], world_id=world_id),
        state_dir=tmp_path,
    )
    assert cs.port_classes == {10: "BSB", 11: "SSS"}
    assert cs.known_ports == {10, 11, 99}
    # Never on status JSON.
    merged = cs.merge({})
    assert "port_classes" not in merged
    assert "known_ports" not in merged


def test_failed_update_retains_last_good_port_classes(tmp_path):
    from tw2002_aiclient import world_model

    world_id = "bubble-retain"
    world_model.upsert_sector(
        world_id,
        {"sector_id": 1, "port": {"class": "BBS"}},
        state_dir=tmp_path,
    )
    cs = ChainScalars()
    cs.update(
        _result(chains_=[_chain([1, 2, 1])], world_id=world_id),
        state_dir=tmp_path,
    )
    assert cs.port_classes == {1: "BBS"}
    cs.update(None)
    cs.update(_result(chains_=(), search_note="budget"))
    assert cs.port_classes == {1: "BBS"}
    assert 1 in cs.known_ports


def test_completed_empty_clears_port_class_cache(tmp_path):
    from tw2002_aiclient import world_model

    world_id = "bubble-clear"
    world_model.upsert_sector(
        world_id,
        {"sector_id": 5, "port": {"class": "SBB"}},
        state_dir=tmp_path,
    )
    cs = ChainScalars()
    cs.update(
        _result(chains_=[_chain([5, 6, 5])], world_id=world_id),
        state_dir=tmp_path,
    )
    cs.update(_result(chains_=(), reason="none", world_id=world_id))
    assert cs.port_classes == {}
    assert cs.known_ports == set()


def test_a_later_failed_discovery_does_not_erase_a_good_one():
    # A discovery that establishes nothing must not silently blank a value the
    # operator was already shown -- "unknown" replacing a real count reads as
    # the chain having gone away.
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([1, 2, 3, 1])]))
    cs.update(None)
    assert cs.merge({}) == {"chain_hops": 3, "chain_unit": "hops"}


def test_as_chain_like_round_trips_a_hop_count():
    assert as_chain_like(4, "hops") == {"source": "discovered", "steps": 4}
    assert as_chain_like(4, "steps") == {"source": "recorded", "steps": 4}


@pytest.mark.parametrize("bad", [None, True, False, 0, -1, "4", 4.0, object()])
def test_as_chain_like_refuses_anything_that_is_not_a_positive_int(bad):
    # `True` is the one worth naming: `isinstance(True, int)` holds, so without
    # the bool guard a stray flag becomes a 1-hop chain.
    assert as_chain_like(bad, "hops") is None


# ===========================================================================
# B — COACH WIRE
#
# Catches: the coach speaking over a live trace; a missing/broken KB taking the
# DECISIONS pane down or being re-read every frame; the empty-marker probe
# `cockpit/fold.py` depends on changing shape; a bool in fighters_aboard
# reading as a real count.
# ===========================================================================

_TRACE_STATUS = {
    "autopilot_trace": {
        "chosen": "trade",
        "candidates": [
            {
                "kind": "trade",
                "ev_cr_per_turn": 550.0,
                "rationale": "loop @1<->3",
            }
        ],
    },
    "chain_hops": 5,
    "chain_unit": "hops",
}


@pytest.fixture(autouse=True)
def _fresh_kb_cache():
    decisions_mod._reset_kb_cache_for_tests()
    yield
    decisions_mod._reset_kb_cache_for_tests()


def test_a_live_trace_wins_outright_over_the_coach():
    # Canon I3: "when a real autopilot trace ... owns the Decisions pane, the
    # coach steps back". The fixture carries a chain precisely so this cannot
    # pass by the coach having nothing to say.
    lines = compose_decisions_lines(_TRACE_STATUS, width=48)
    assert len(lines) == 1
    assert "loop @1<->3" in lines[0]


def test_the_coach_speaks_only_into_an_otherwise_empty_pane():
    no_trace = {"chain_hops": 5, "chain_unit": "hops"}
    lines = compose_decisions_lines(no_trace, width=48)
    assert lines != [line[:48] for line in autonomy_keys.compose_autonomy_help_lines()]
    assert lines[0].strip()  # authored card text, not a placeholder


def test_a_status_with_nothing_to_teach_still_shows_the_honest_empty_state():
    assert compose_decisions_lines({}, width=48) == [line[:48] for line in autonomy_keys.compose_autonomy_help_lines()]


def test_the_none_status_empty_marker_is_unchanged():
    # `cockpit/fold.py` probes the empty marker by calling this composer on
    # None at the same width, and collapses the whole pane when every section
    # matches its own marker. If the coach could ever fire on None, that probe
    # would silently stop matching and the pane would never collapse again.
    assert compose_decisions_lines(None, width=48) == [line[:48] for line in autonomy_keys.compose_autonomy_help_lines()]


def test_width_zero_still_yields_exactly_four_empty_lines():
    # Not cosmetic: at width<=0 every panel renders as empty strings, and a
    # coach callout would change the NUMBER of lines DECISIONS returns.
    rich = {"chain_hops": 5, "chain_unit": "hops"}
    assert compose_decisions_lines(rich, width=0) == [""] * len(autonomy_keys.compose_autonomy_help_lines())
    assert compose_decisions_lines(rich, width=-7) == [""] * len(autonomy_keys.compose_autonomy_help_lines())


def test_every_coach_line_respects_the_width_clip():
    rich = {"chain_hops": 5, "chain_unit": "hops"}
    for width in (1, 3, 12, 22, 60):
        lines = compose_decisions_lines(rich, width=width)
        assert all(len(ln) <= width for ln in lines), (width, lines)


def test_the_kb_is_loaded_at_most_once_per_process(monkeypatch):
    # Without the one-shot cache the cockpit does file I/O + json.loads on
    # every redraw of an idle pane.
    calls = []
    real = decisions_mod._coach_kb.load_coach_kb

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(decisions_mod._coach_kb, "load_coach_kb", counting)
    rich = {"chain_hops": 5, "chain_unit": "hops"}
    for _ in range(5):
        compose_decisions_lines(rich, width=48)
    assert len(calls) == 1


def test_a_failing_kb_load_is_cached_as_a_failure_not_retried(monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise OSError("no such file")

    monkeypatch.setattr(decisions_mod._coach_kb, "load_coach_kb", boom)
    rich = {"chain_hops": 5, "chain_unit": "hops"}
    for _ in range(5):
        assert compose_decisions_lines(rich, width=48) == [line[:48] for line in autonomy_keys.compose_autonomy_help_lines()]
    assert len(calls) == 1


def test_a_raising_coach_engine_degrades_to_the_empty_state(monkeypatch):
    # The module's contract is that it never raises regardless of `status`.
    # Coaching is survivable; a dead DECISIONS pane is not.
    def boom(*a, **k):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(decisions_mod._coach, "compose_decisions_coach", boom)
    rich = {"chain_hops": 5, "chain_unit": "hops"}
    assert compose_decisions_lines(rich, width=48) == [line[:48] for line in autonomy_keys.compose_autonomy_help_lines()]


@pytest.mark.parametrize(
    "status",
    [
        {"chain_hops": "five", "chain_unit": "hops"},
        {"chain_hops": True, "chain_unit": "hops"},
        {"chain_hops": 5, "chain_unit": object()},
        {"chain_hops": float("inf"), "chain_unit": "hops"},
        {"fighters_aboard": True},
        {"fighters_aboard": "many"},
    ],
)
def test_hostile_status_values_never_raise_and_never_invent_a_line(status):
    lines = compose_decisions_lines(status, width=48)
    assert isinstance(lines, list)
    assert all(isinstance(ln, str) for ln in lines)


def test_a_boolean_in_fighters_aboard_is_not_a_fighter_count():
    # `True == 1`, so an unguarded int check turns a stray flag into "1
    # fighter aboard" and can fire a combat-adjacent card off a boolean.
    assert decisions_mod._safe_int_or_none(True) is None
    assert decisions_mod._safe_int_or_none(False) is None
    assert decisions_mod._safe_int_or_none(0) == 0
    assert decisions_mod._safe_int_or_none(40) == 40


def test_the_coach_path_contains_no_send_or_arm(monkeypatch):
    # AI-never-live-drives, pinned structurally rather than by reading the
    # source: nothing the coach path touches may reach a sender.
    import ast
    import inspect

    src = inspect.getsource(decisions_mod)
    tree = ast.parse(src)
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not called & {"send", "send_raw", "arm", "acquire", "write"}


# ===========================================================================
# C — COST
#
# The cockpit draw path must stay import-cheap. `chain_search` pulls the
# finder + trade_adapter + world_model (~40ms) against a whole-process budget
# `tests/test_dead_terminal_spin.py` pins at 0.5s with roughly 50ms to spare.
# ===========================================================================


def test_the_decisions_import_graph_does_not_pull_the_finder():
    import subprocess
    import sys

    probe = (
        "import sys;"
        "import tw2002_aiclient.cockpit.decisions;"
        "bad=[m for m in ('tw2002_aiclient.chain_search',"
        "'tw2002_aiclient.trade_adapter','tw2002_aiclient.world_model')"
        " if m in sys.modules];"
        "print(','.join(bad))"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "", f"heavy modules pulled in: {out.stdout.strip()}"


def test_a_cim_report_classification_reaches_the_coach():
    """`classification` is on the real `status` verb response, so the
    docked-at-port card can fire. Pinned with the classification the REAL
    classifier produces (see the fixture pin below), not an invented one."""
    lines = compose_decisions_lines({"classification": "cim_report"}, width=60)
    assert lines != [line[:60] for line in autonomy_keys.compose_autonomy_help_lines()]


def test_the_cim_report_anchor_is_producible_by_the_real_classifier():
    """Guards the pin above against becoming a fiction. `infer_coach_triggers`
    anchors `docked_at_port` on ``port_trade`` and ``cim_report``; only the
    second is actually emitted by `classify_screen` today, so wiring
    `classification` buys exactly one reachable trigger, not four. If the
    classifier stops producing it, the wire above is silently dead and this
    is the pin that says so."""
    import pathlib

    from tw2002_aiclient.session.classify import classify_screen

    fixture = pathlib.Path(__file__).parent / "fixtures" / "cim_port_report.txt"
    text = fixture.read_text(errors="replace")
    prompt = text.splitlines()[-1].strip() if text.splitlines() else ""
    assert classify_screen(text, prompt) == "cim_report"


def test_the_prompt_field_is_never_read_by_the_coach():
    """`status["prompt"]` is deliberately absent from the status verb — on an
    echoing server that line is the operator's credential
    (`session/protocol.py::_status_response`). Reading it here would be a
    request for exactly the field the redaction fix removed, so the coach must
    never ask for it — pinned structurally, not by reading the comment."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(decisions_mod))
    asked = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert "prompt" not in asked


def test_wrap_overlays_any_provider_not_just_the_daemon_poller():
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([1, 2, 3, 1])]))
    wrapped = cs.wrap(lambda: {"ok": True, "credits": 7})
    assert wrapped() == {"ok": True, "credits": 7, "chain_hops": 3, "chain_unit": "hops"}


def test_wrap_leaves_a_none_returning_provider_returning_none():
    # A dead daemon must keep looking dead. Turning its None into a
    # chain-only dict would render a live-looking GOALS panel over nothing.
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([1, 2, 1])]))
    assert cs.wrap(lambda: None)() is None


def test_wrap_of_no_provider_is_no_provider():
    assert ChainScalars().wrap(None) is None


# ---------------------------------------------------------------------------
# WO-CHAIN-BUBBLE-PAIR-FALLBACK — best_pair retention + bubble preference
# ---------------------------------------------------------------------------


class _Pair:
    def __init__(self, a, b, turns=2):
        self.sector_a = a
        self.sector_b = b
        self.turns = turns
        # Deliberately no margin attribute — class pairs must not invent one.


class _PairResult:
    def __init__(self, pairs=(), reason=None, world_id="w"):
        self.pairs = tuple(pairs)
        self.reason = reason
        self.world_id = world_id


def test_best_pair_is_retained_and_never_on_status():
    cs = ChainScalars()
    pair = _Pair(10, 20)
    cs.update_pairs(_PairResult(pairs=[pair, _Pair(1, 2, turns=9)]))
    assert cs.best_pair is pair
    assert "best_pair" not in (cs.merge({"ok": True}) or {})
    assert not hasattr(cs.best_pair, "margin")


def test_failed_pair_update_does_not_erase_best_pair():
    cs = ChainScalars()
    pair = _Pair(10, 20)
    cs.update_pairs(_PairResult(pairs=[pair]))
    cs.update_pairs(None)
    cs.update_pairs(object())
    cs.update_pairs(_PairResult(pairs=(), reason=chain_search.REASON_NO_WORLD_MODEL))
    assert cs.best_pair is pair


def test_completed_empty_pair_result_clears_best_pair():
    cs = ChainScalars()
    cs.update_pairs(_PairResult(pairs=[_Pair(10, 20)]))
    cs.update_pairs(_PairResult(pairs=(), reason="no_compatible_pairs"))
    assert cs.best_pair is None


def test_bubble_subject_prefers_chain_over_pair():
    cs = ChainScalars()
    chain = _chain([10, 11, 12, 10])
    cs.update(_result(chains_=[chain]))
    cs.update_pairs(_PairResult(pairs=[_Pair(50, 60)]))
    subject, caption = cs.bubble_subject()
    assert subject is chain
    assert caption is None


def test_bubble_subject_falls_back_to_pair_when_chain_empty():
    from tw2002_aiclient.chain_status import pair_as_chain_like

    cs = ChainScalars()
    # Completed empty priced search (the live academy shape).
    cs.update(_result(chains_=(), reason="no_closed_cycle"))
    pair = _Pair(10, 20)
    cs.update_pairs(_PairResult(pairs=[pair]))
    subject, caption = cs.bubble_subject()
    assert subject == pair_as_chain_like(pair)
    assert caption == "class pair"
    assert cs.best_chain is None


def test_goals_hops_match_bubble_pair_fallback_not_none_yet():
    """WO-FIX-GOALS-CHAIN-ROW: bubble paints a class pair → GOALS must not say none yet."""
    from tw2002_aiclient.cockpit.goals import compose_goals_lines

    cs = ChainScalars()
    cs.update(_result(chains_=(), reason="no_closed_cycle"))
    cs.update_pairs(_PairResult(pairs=[_Pair(10, 20)]))
    merged = cs.merge({})
    assert merged["chain_hops"] == 2
    assert merged["chain_unit"] == "hops"
    row = compose_goals_lines(merged, width=40)[5]
    assert "none yet" not in row
    assert "2 hop" in row


def test_goals_hops_from_pair_only_without_priced_seen():
    """Pair refresh can land while priced half never established `_seen`."""
    cs = ChainScalars()
    cs.update_pairs(_PairResult(pairs=[_Pair(7, 8)]))
    assert cs.seen is False
    merged = cs.merge({})
    assert merged["chain_hops"] == 2
    assert cs.bubble_subject()[0] is not None


def test_bubble_subject_empty_when_both_absent():
    cs = ChainScalars()
    assert cs.bubble_subject() == (None, None)
    cs.update(_result(chains_=(), reason="no_closed_cycle"))
    cs.update_pairs(_PairResult(pairs=(), reason="no_compatible_pairs"))
    assert cs.bubble_subject() == (None, None)


def test_bubble_subject_truncated_empty_pair_caption_is_search_incomplete():
    """WO-CHAIN-BUBBLE-TRUNCATION-CAPTION Accept #1."""
    from tw2002_aiclient.chain_status import pair_as_chain_like

    cs = ChainScalars()
    cs.update(
        _result(
            chains_=(),
            reason=chain_search.REASON_NO_CLOSED_CYCLE,
            search_note="budget",
        )
    )
    pair = _Pair(10, 20)
    cs.update_pairs(_PairResult(pairs=[pair]))
    subject, caption = cs.bubble_subject()
    assert subject == pair_as_chain_like(pair)
    assert caption == "class pair · search incomplete"


def test_bubble_subject_completed_empty_keeps_bare_class_pair_caption():
    """WO-CHAIN-BUBBLE-TRUNCATION-CAPTION Accept #2."""
    cs = ChainScalars()
    cs.update(_result(chains_=(), reason="no_closed_cycle"))
    cs.update_pairs(_PairResult(pairs=[_Pair(10, 20)]))
    _subject, caption = cs.bubble_subject()
    assert caption == "class pair"


def test_bubble_subject_priced_chain_clears_incomplete_caption():
    """WO-CHAIN-BUBBLE-TRUNCATION-CAPTION Accept #3."""
    cs = ChainScalars()
    cs.update(
        _result(chains_=(), reason="no_closed_cycle", search_note="budget")
    )
    cs.update_pairs(_PairResult(pairs=[_Pair(10, 20)]))
    assert cs.bubble_subject()[1] == "class pair · search incomplete"
    chain = _chain([10, 11, 12, 10])
    cs.update(_result(chains_=[chain]))
    subject, caption = cs.bubble_subject()
    assert subject is chain
    assert caption is None


def test_bubble_subject_prefers_chain_including_current_sector():
    """WO-CHAIN-BUBBLE-PREFER-CURRENT Accept #1."""
    remote = _chain([1, 2, 3, 4, 5, 6, 7, 8, 9, 1])  # longer → ranked first
    local = _chain([50, 51, 52, 50])
    cs = ChainScalars()
    cs.update(_result(chains_=[remote, local]))
    assert cs.best_chain is remote  # GOALS still global longest
    subject, caption = cs.bubble_subject(current_sector=51)
    assert subject is local
    assert caption is None


def test_bubble_subject_falls_back_to_global_when_sector_absent():
    """WO-CHAIN-BUBBLE-PREFER-CURRENT Accept #2."""
    remote = _chain([1, 2, 3, 4, 5, 6, 7, 8, 9, 1])
    local = _chain([50, 51, 52, 50])
    cs = ChainScalars()
    cs.update(_result(chains_=[remote, local]))
    assert cs.bubble_subject()[0] is remote
    assert cs.bubble_subject(current_sector=999)[0] is remote


def test_bubble_subject_pair_fallback_unchanged_with_current_sector():
    """WO-CHAIN-BUBBLE-PREFER-CURRENT Accept #3 — class-pair path intact."""
    from tw2002_aiclient.chain_status import pair_as_chain_like

    cs = ChainScalars()
    cs.update(_result(chains_=(), reason="no_closed_cycle"))
    pair = _Pair(10, 20)
    cs.update_pairs(_PairResult(pairs=[pair]))
    subject, caption = cs.bubble_subject(current_sector=10)
    assert subject == pair_as_chain_like(pair)
    assert caption == "class pair"


def test_goals_hops_match_bubble_local_prefer():
    """WO-CHAIN-GOALS-MATCH-BUBBLE Accept #1."""
    remote = _chain([1, 2, 3, 4, 5, 6, 7, 8, 9, 1])  # 9 hops
    local = _chain([50, 51, 52, 50])  # 3 hops
    cs = ChainScalars()
    cs.update(_result(chains_=[remote, local]))
    assert cs.best_chain is remote
    subject, _caption = cs.bubble_subject(current_sector=51)
    assert subject is local
    merged = cs.merge(
        {"hud": {"sector": {"value": 51, "age_s": 0.0}}},
    )
    assert merged["chain_hops"] == 3
    assert merged["chain_unit"] == "hops"
    # Explicit kwarg matches HUD extraction.
    assert cs.merge({}, current_sector=51)["chain_hops"] == 3


def test_goals_hops_global_when_sector_absent_from_chains():
    """WO-CHAIN-GOALS-MATCH-BUBBLE Accept #2."""
    remote = _chain([1, 2, 3, 4, 5, 6, 7, 8, 9, 1])
    local = _chain([50, 51, 52, 50])
    cs = ChainScalars()
    cs.update(_result(chains_=[remote, local]))
    assert cs.merge({})["chain_hops"] == 9
    assert cs.merge({"hud": {"sector": {"value": 999}}})["chain_hops"] == 9
    assert cs.bubble_subject(current_sector=999)[0] is remote
