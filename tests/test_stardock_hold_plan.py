from pathlib import Path

from tw2002_aiclient.stardock_hold_plan import (
    compose_confirm_action,
    compute_auto_max_qty,
    parse_hold_qty_range,
    plan_from_evidence,
    plan_from_status,
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


def test_compute_auto_max_qty_fills_toward_empty_and_cash():
    assert compute_auto_max_qty(
        empty_holds=20, hold_price=1000, credits=50_000, cash_floor=1000
    ) == 20
    assert compute_auto_max_qty(
        empty_holds=20, hold_price=1000, credits=5500, cash_floor=1000
    ) == 4
    assert (
        compute_auto_max_qty(
            empty_holds=20, hold_price=1000, credits=1500, cash_floor=1000
        )
        is None
    )


def test_plan_from_status_auto_max_uses_toward_max_qty():
    status = {
        "stardock_sectors": [751],
        "hud": {
            "cargo": {"value": 10},
            "credits": {"value": 50_000},
        },
        "hold_price_label": "1,000cr",
    }
    one = plan_from_status("world-a", status)
    assert one is not None and one.qty == 1
    filled = plan_from_status(
        "world-a", status, auto_max=True, cash_floor=1000
    )
    assert filled is not None and filled.qty == 10


def test_plan_from_status_auto_max_parses_empty_holds_string():
    status = {
        "stardock_found": True,
        "stardock_sector": 751,
        "credits": 20_000,
        "hud": {"cargo": {"value": "5 empty / 40"}},
        "hold_price": 2000,
    }
    plan = plan_from_status(
        "world-a", status, auto_max=True, cash_floor=0
    )
    assert plan is not None
    assert plan.qty == 5
    assert plan.empty_holds == 5
