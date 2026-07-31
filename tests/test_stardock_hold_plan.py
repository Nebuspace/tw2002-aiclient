from pathlib import Path

from tw2002_aiclient.stardock_hold_plan import (
    compose_confirm_action,
    parse_hold_qty_range,
    plan_from_evidence,
)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stardock_cargo_hold_quote.txt"


def test_plan_stable_fingerprint_and_fields():
    first = plan_from_evidence(
        "world-a",
        stardock_sector=751,
        empty_holds=20,
        hold_price=1468,
        credits=50_000,
        qty=1,
    )
    second = plan_from_evidence(
        "world-a",
        stardock_sector=751,
        empty_holds=20,
        hold_price=1468,
        credits=50_000,
        qty=1,
    )

    assert first == second
    assert first.stardock_sector == 751
    assert first.empty_holds == 20
    assert first.hold_price == 1468
    assert first.credits == 50_000
    assert first.qty == 1
    assert len(first.fingerprint) == 64


def test_incomplete_or_hostile_evidence_refuses():
    valid = dict(
        stardock_sector=751,
        empty_holds=20,
        hold_price=1468,
        credits=50_000,
        qty=1,
    )
    assert plan_from_evidence("", **valid) is None
    assert plan_from_evidence("world-a", stardock_sector=0, **{k: v for k, v in valid.items() if k != "stardock_sector"}) is None
    assert plan_from_evidence("world-a", hold_price=-1, **{k: v for k, v in valid.items() if k != "hold_price"}) is None
    assert plan_from_evidence("world-a", credits=True, **{k: v for k, v in valid.items() if k != "credits"}) is None
    assert plan_from_evidence("world-a", qty=0, **{k: v for k, v in valid.items() if k != "qty"}) is None
    assert plan_from_evidence("world-a", **{**valid, "qty": 25}) is None
    assert plan_from_evidence("world-a", qty=2, hold_price=500, credits=500, stardock_sector=751, empty_holds=20) is None


def test_compose_confirm_action_names_one_pass_and_floor():
    plan = plan_from_evidence(
        "world-a",
        stardock_sector=751,
        empty_holds=20,
        hold_price=1468,
        credits=50_000,
        qty=1,
    )
    action = compose_confirm_action(plan, cash_floor=1_000)

    assert action == (
        "Buy 1 cargo hold(s) @ StarDock 751 — 1468cr each, floor 1000cr"
    )
    assert compose_confirm_action(plan, cash_floor=None) is None
    assert compose_confirm_action(plan, cash_floor=True) is None
    assert compose_confirm_action(plan, cash_floor=50_001) is None


def test_parse_hold_qty_range_from_fixture():
    text = _FIXTURE.read_text(encoding="utf-8")
    assert parse_hold_qty_range(text) == (0, 20)


def test_parse_hold_qty_range_refuses_unknown_shapes():
    assert parse_hold_qty_range("") is None
    assert parse_hold_qty_range("How many holds would you like?") is None
    assert parse_hold_qty_range("How many holds would you like to buy [20-0] ?") is None
    assert parse_hold_qty_range("How many holds would you like to buy [x-y] ?") is None
