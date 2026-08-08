"""WO-CHAIN-NPORT-WIRE — the `tw chains` verb.

Daemon-free: no socket, no `--run-dir`, no sends. Same family as
`tests/test_cli_pairs.py`.
"""

from __future__ import annotations

import datetime
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from tw2002_aiclient import world_model
from tw2002_aiclient.session import cli

NOW = datetime.datetime(2026, 7, 28, 4, 0, tzinfo=datetime.timezone.utc)
CLOCK = lambda: NOW  # noqa: E731
W = "test+cli-nport"


def _row(name, status, pct, amount=1000):
    return {"name": name, "status": status, "amount": amount, "pct": pct}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """A three-port cycle, with `world_model.WORLD_DIR` pointed at tmp so
    `cmd_chains` (which takes no `--state-dir`) reads it.

    `cmd_chains` → `chain_search.recompute` omits `now=`, so
    `trade_adapter.build_trade_hops` falls back to wall-clock UTC. Ports
    stamped at a fixed NOW go stale after ``max_age_s`` (1h) and the suite
    flips to ``no_tradeable_hops`` — a CI time-bomb (green before the hour,
    red after). Pin the adapter clock to CLOCK for this fixture.
    """
    from tw2002_aiclient import trade_adapter

    monkeypatch.setattr(world_model, "WORLD_DIR", tmp_path)
    _orig_build = trade_adapter.build_trade_hops

    def _build_pinned(world_id, *, state_dir=None, config=None, now=None):
        return _orig_build(
            world_id, state_dir=state_dir, config=config, now=now or CLOCK
        )

    monkeypatch.setattr(trade_adapter, "build_trade_hops", _build_pinned)
    for sid, warps, comm in (
        (10, (11, 12), [_row("Equipment", "selling", 100), _row("Fuel Ore", "buying", 0)]),
        (11, (10, 12), [_row("Fuel Ore", "selling", 100), _row("Organics", "buying", 0)]),
        (12, (10, 11), [_row("Organics", "selling", 100), _row("Equipment", "buying", 0)]),
    ):
        world_model.upsert_sector(
            W,
            {
                "sector_id": sid,
                "warps": list(warps),
                "port": {"commodities": comm, "last_seen_ts": world_model._now_iso(CLOCK)},
            },
            state_dir=tmp_path,
            now=CLOCK,
        )
    return tmp_path


def _run(argv):
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = cli.main(argv)
    except SystemExit as exc:  # argparse
        rc = exc.code
    return rc, buf.getvalue()


# -- wiring ----------------------------------------------------------------


def test_verb_is_registered_and_bound_to_cmd_chains():
    args = cli.build_parser().parse_args(["chains", "--world-id", "w"])
    assert args.func is cli.cmd_chains
    assert args.world_id == "w"


def test_world_id_is_required():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["chains"])


# -- behaviour -------------------------------------------------------------


def test_text_output_lists_the_three_port_cycle(world):
    rc, out = _run(["chains", "--world-id", W])
    assert rc == 0
    assert "Discovered profit chains" in out
    assert "10>" in out and "detected" in out
    assert "3h" in out, out


def test_json_output_carries_the_cycle(world):
    rc, out = _run(["chains", "--world-id", W, "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["world_id"] == W
    assert payload["reason"] is None
    assert len(payload["chains"]) >= 1
    assert len(payload["chains"][0]["hops"]) == 3


def test_cmd_chains_requests_yield_rank(world, monkeypatch):
    """Earn CLI surface must ask recompute for yield-first ordering."""
    from tw2002_aiclient import chain_search

    seen: dict = {}
    real = chain_search.recompute

    def _capture(world_id, **kwargs):
        seen["rank"] = kwargs.get("rank")
        return real(world_id, **kwargs)

    monkeypatch.setattr(chain_search, "recompute", _capture)
    rc, _ = _run(["chains", "--world-id", W, "--json"])
    assert rc == 0
    assert seen.get("rank") == chain_search.RANK_YIELD


def test_cmd_chains_json_lists_yield_first_when_short_rich_and_long_thin(
    world, monkeypatch
):
    """Pin #523: CLI JSON tops 2-hop@3.5 over 9-hop@1.0."""
    from tw2002_aiclient import chain_search, chains

    short_rich = chains.ProfitChain(
        sectors=(100, 101, 100),
        hops=(
            chains.TradeHop(100, 101, "A", 3.5, 1),
            chains.TradeHop(101, 100, "B", 3.5, 1),
        ),
        overall_profit=7.0,
        turns=2,
        cr_per_turn=3.5,
        cr_per_execution=7.0,
    )
    long_thin = chains.ProfitChain(
        sectors=tuple(range(1, 10)) + (1,),
        hops=tuple(
            chains.TradeHop(i, i + 1 if i < 9 else 1, "X", 1.0, 1) for i in range(1, 10)
        ),
        overall_profit=9.0,
        turns=9,
        cr_per_turn=1.0,
        cr_per_execution=9.0,
    )

    def _yield_payload(world_id, **kwargs):
        assert kwargs.get("rank") == chain_search.RANK_YIELD
        ranked = chains.rank_chains_by_yield([long_thin, short_rich])
        return chain_search.ProfitChainResult(
            world_id=world_id, chains=tuple(ranked), reason=None
        )

    monkeypatch.setattr(chain_search, "recompute", _yield_payload)
    rc, out = _run(["chains", "--world-id", W, "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["chains"][0]["cr_per_turn"] == 3.5
    assert len(payload["chains"][0]["hops"]) == 2


def test_json_carries_the_two_truncation_notes_as_SEPARATE_fields(world):
    """A machine consumer must be able to tell 'I did not consider every
    hop' from 'I did not finish searching the hops I had'. One merged
    string would make that impossible."""
    rc, out = _run(["chains", "--world-id", W, "--json"])
    payload = json.loads(out)
    assert "adapter_note" in payload
    assert "search_note" in payload
    assert "truncated" in payload
    assert payload["truncated"] is False


def test_unexplored_world_exits_zero_with_an_honest_reason(monkeypatch, tmp_path):
    """Exit 0: a typed empty reason is a successfully established fact
    about the world, never a failure to read anything."""
    monkeypatch.setattr(world_model, "WORLD_DIR", tmp_path)
    rc, out = _run(["chains", "--world-id", "test+nothing-here"])
    assert rc == 0
    assert "world not yet explored" in out


def test_unexplored_world_json_reports_the_typed_reason(monkeypatch, tmp_path):
    monkeypatch.setattr(world_model, "WORLD_DIR", tmp_path)
    rc, out = _run(["chains", "--world-id", "test+nothing-here", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["chains"] == []
    assert payload["reason"] == "no_world_model"


# -- the surface separation this WO must not violate -----------------------


def test_cmd_chains_never_touches_the_taught_arm_list():
    """`cockpit/chains.py`'s `rows` are the ARM surface (-> `begin_arm_confirm`
    -> `autoloop_start`, the money-spending call). Since WO-CHAINS-TUI-FULL
    the `L)chains` modal displays discovered cycles and ADR-003 gives that
    surface a separate exact-fingerprint approval path, never through the
    recorded arm list. This CLI verb must still not touch either arm path:
    no cockpit import, no autoloop reference, nothing that could put a
    discovered cycle where `selected()` could return it.

    Checked by **AST**, not by text search. A `"cockpit" not in source`
    grep fails on this very function, whose docstring names the arm list
    precisely in order to disclaim it -- a prose mention and a code
    reference are different facts, and only one of them is a defect."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(cli.cmd_chains).lstrip())

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)

    # Every NAME this function actually references in code (docstrings are
    # ast.Constant and are invisible here -- which is the whole point).
    referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    referenced |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}

    forbidden = ("cockpit", "autoloop", "begin_arm_confirm", "arm_confirm")
    for bad in forbidden:
        assert not any(bad in mod for mod in imported), f"imports {bad}: {imported}"
        assert not any(bad in ref for ref in referenced), f"references {bad}: {referenced}"

    # And the positive half: it reaches the discovery modules, not the taught ones.
    assert any("chain_search" in m for m in imported), imported
