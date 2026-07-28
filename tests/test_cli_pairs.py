"""``tw pairs`` CLI wire (WO-CHAIN-DETECT-WIRE Accept 5, re-scoped 2026-07-28
-- the thin product caller the WO's typed API requires).

The engine (`chain_detect.recompute` + `chain_detect_view.format_candidate_
pair_lines`) is proven by `test_chain_detect.py`/`test_chain_detect_view.py`/
`test_trade_adapter.py`. What is proven HERE is the thing only the wire can
get wrong: that the real verb, dispatched through the real parser, reads a
real on-disk world-model and prints the composer's report -- same discipline
`test_cli_loops.py` uses for its own sibling daemon-free read.

Every test drives ``cli.main([...])`` -- the whole dispatch path, not the
function in isolation -- against sectors this test wrote to disk via
`world_model.upsert_sector`. The world-model root is redirected by pointing
`world_model.WORLD_DIR` at `tmp_path`, the module's own documented injection
seam (mirrors `world_model._world_dir`'s `state_dir or WORLD_DIR` fallback).
"""

from __future__ import annotations

import datetime
import json

from tw2002_aiclient import world_model
from tw2002_aiclient.session import cli

WORLD = "hostA__F__ALPHA"
_CLOCK = lambda: datetime.datetime(2026, 7, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _at(monkeypatch, tmp_path):
    """Point the world-model's default root at this test's tmp tree --
    same seam `world_model._world_dir` itself falls back to when a
    caller (here, `cmd_pairs`) supplies no explicit `state_dir`."""
    monkeypatch.setattr(world_model, "WORLD_DIR", tmp_path)


def _upsert_class(sector_id, *, warps=(), klass=None, port_ts_clock=_CLOCK):
    record = {"sector_id": sector_id, "warps": list(warps)}
    if klass is not None:
        record["port"] = {"class": klass, "last_seen_ts": world_model._now_iso(port_ts_clock)}
    world_model.upsert_sector(WORLD, record, state_dir=None, now=port_ts_clock)


def _run(capsys, argv):
    rc = cli.main(argv)
    return rc, capsys.readouterr().out


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------


def test_pairs_verb_is_wired_with_only_world_id_and_json():
    """No ``--run-dir``: same daemon-free-read shape as ``loops``/``menumap``
    (`canon/architecture/cli-verbs.md`'s "daemon-free reads" carve-out) --
    the report cannot depend on which daemon is up because it never opens
    one."""
    parser = cli.build_parser()

    try:
        parser.parse_args(["pairs"])
        raise AssertionError("--world-id must be required")
    except SystemExit:
        pass

    args = parser.parse_args(["pairs", "--world-id", "hostA__F__ALPHA"])
    assert args.func is cli.cmd_pairs
    assert args.world_id == "hostA__F__ALPHA"
    assert args.json is False
    assert not hasattr(args, "run_dir")

    opted = parser.parse_args(["pairs", "--world-id", "hostA__F__ALPHA", "--json"])
    assert opted.json is True


def test_pairs_is_advertised_on_help_next_to_the_other_read_only_inspectors():
    help_text = cli.build_parser().format_help()
    assert "loops" in help_text  # control leg -- pins the render is real
    assert "pairs" in help_text


def test_the_pairs_help_strings_stay_ascii():
    """Same discipline `test_cli_loops.py` pins for its own verb --
    ``tw --help`` goes through the terminal's own codec."""
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if getattr(a, "choices", None) is not None)
    entry = next(a for a in sub._choices_actions if a.dest == "pairs")
    entry.help.encode("ascii")
    for action in sub.choices["pairs"]._actions:
        (action.help or "").encode("ascii")


def test_pairs_never_touches_the_daemon(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)

    def explode(*_a, **_kw):
        raise AssertionError("tw pairs must not touch the daemon")

    monkeypatch.setattr(cli, "send_request", explode)
    monkeypatch.setattr(cli, "daemon_alive", explode)

    rc, out = _run(capsys, ["pairs", "--world-id", WORLD])

    assert rc == 0
    assert "Discovered pair loops" in out


def test_pairs_verb_never_reaches_a_send_path():
    """Structural companion to `test_pairs_never_touches_the_daemon` --
    `cmd_pairs`'s own source names neither the socket adapter nor the
    protocol send verb, mirroring `test_cli_loops.py`-adjacent send-free
    pins elsewhere in this suite."""
    import inspect

    src = inspect.getsource(cli.cmd_pairs)
    assert "send_request" not in src
    assert "adapters" not in src


# --------------------------------------------------------------------------
# The five typed-empty outcomes, plus the populated case -- each proven by
# execution against a real on-disk world-model tree.
# --------------------------------------------------------------------------


def test_never_explored_world_exits_zero_and_explains_why(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)  # nothing written at all

    rc, out = _run(capsys, ["pairs", "--world-id", WORLD])

    assert rc == 0
    assert out.splitlines()[0] == "Discovered pair loops"
    assert "world not yet explored" in out


def test_fewer_than_two_ports_exits_zero_and_explains_why(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    _upsert_class(1, warps=(2,))  # known sector, no port
    _upsert_class(2, warps=(1,), klass="SBB")  # the only valid class port

    rc, out = _run(capsys, ["pairs", "--world-id", WORLD])

    assert rc == 0
    assert "fewer than 2 known ports" in out


def test_all_stale_exits_zero_and_explains_why(tmp_path, monkeypatch, capsys):
    """`PairLoopConfig` is not CLI-exposed (no test-only knob leaks into
    the wire), so this drives staleness the honest way: readings old
    enough to exceed even the class path's generous 30-day default."""
    _at(monkeypatch, tmp_path)
    ancient = lambda: datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    _upsert_class(10, warps=(11,), klass="SBB", port_ts_clock=ancient)
    _upsert_class(11, warps=(10,), klass="BSS", port_ts_clock=ancient)

    rc, out = _run(capsys, ["pairs", "--world-id", WORLD])

    assert rc == 0
    assert "class data too old" in out


def test_no_compatible_pairs_exits_zero_and_explains_why(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    _upsert_class(20, warps=(21,), klass="SSS")
    _upsert_class(21, warps=(20,), klass="SSS")

    rc, out = _run(capsys, ["pairs", "--world-id", WORLD])

    assert rc == 0
    assert "no compatible postures" in out


def test_compatible_but_unrouted_exits_zero_and_explains_why(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    _upsert_class(30, warps=(), klass="SBB")
    _upsert_class(31, warps=(), klass="BSS")

    rc, out = _run(capsys, ["pairs", "--world-id", WORLD])

    assert rc == 0
    assert "compatible pair, no known route yet" in out


def test_populated_world_exits_zero_and_lists_the_real_pair(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    _upsert_class(10, warps=(11,), klass="SBB")
    _upsert_class(11, warps=(10,), klass="BSS")

    rc, out = _run(capsys, ["pairs", "--world-id", WORLD])
    lines = out.splitlines()

    assert rc == 0
    assert lines[0] == "Discovered pair loops"
    assert len(lines) == 2  # TITLE + exactly one pair row
    assert "10<->11" in lines[1]
    assert "2t" in lines[1]
    assert "detected" in lines[1]
    assert "world not yet explored" not in out


# --------------------------------------------------------------------------
# --json: the scripted caller's view
# --------------------------------------------------------------------------


def test_json_reports_a_real_pair(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    _upsert_class(10, warps=(11,), klass="SBB")
    _upsert_class(11, warps=(10,), klass="BSS")

    rc, out = _run(capsys, ["pairs", "--world-id", WORLD, "--json"])
    payload = json.loads(out)

    assert rc == 0
    assert payload["world_id"] == WORLD
    assert payload["reason"] is None
    assert payload["detail"] is None
    assert len(payload["pairs"]) == 1
    pair = payload["pairs"][0]
    assert pair["sector_a"] == 10 and pair["sector_b"] == 11
    assert pair["commodities_a_sells"] == ["Fuel Ore"]
    assert pair["commodities_b_sells"] == ["Organics", "Equipment"]
    assert pair["turns"] == 2
    assert "margin" not in pair  # structurally absent on CandidatePair itself


def test_json_typed_empty_carries_the_reason_and_no_pairs(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    _upsert_class(20, warps=(21,), klass="SSS")
    _upsert_class(21, warps=(20,), klass="SSS")

    rc, out = _run(capsys, ["pairs", "--world-id", WORLD, "--json"])
    payload = json.loads(out)

    assert rc == 0
    assert payload["pairs"] == []
    assert payload["reason"] == "no_compatible_pairs"


def test_json_never_carries_a_nan_or_infinity_token(tmp_path, monkeypatch, capsys):
    """`observed_age_s` is a real computed float; confirm it always
    round-trips as strict JSON (same discipline `test_cli_loops.py` pins
    for a document-carried NaN, applied here to a COMPUTED figure this
    verb -- not a stored file -- is responsible for keeping finite)."""
    _at(monkeypatch, tmp_path)
    _upsert_class(10, warps=(11,), klass="SBB")
    _upsert_class(11, warps=(10,), klass="BSS")

    rc, out = _run(capsys, ["pairs", "--world-id", WORLD, "--json"])

    assert "NaN" not in out
    assert "Infinity" not in out
    json.loads(
        out, parse_constant=lambda token: (_ for _ in ()).throw(AssertionError(f"non-JSON constant {token!r}"))
    )
