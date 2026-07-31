from pathlib import Path

from tw2002_aiclient.stardock_hold_driver import run_hold_purchase
from tw2002_aiclient.stardock_hold_plan import StardockHoldPlan, plan_from_evidence

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stardock_cargo_hold_quote.txt"


class FakeSession:
    def __init__(self, text: str):
        self.text = text
        self.sent: list[str] = []

    def rendered_text(self):
        return self.text

    def send(self, payload: str) -> None:
        self.sent.append(payload)


def _plan(**over):
    kwargs = dict(
        stardock_sector=751,
        empty_holds=20,
        hold_price=1468,
        credits=50_000,
        qty=1,
    )
    kwargs.update(over)
    return plan_from_evidence("world-a", **kwargs)


def test_armed_buy_sends_qty_from_quote_fixture():
    session = FakeSession(_FIXTURE.read_text(encoding="utf-8"))
    plan = _plan(qty=3)

    result = run_hold_purchase(
        session,
        plan,
        should_abort=lambda: False,
        is_armed=lambda: True,
    )

    assert result.ok is True
    assert result.outcome == "completed"
    assert result.sends_issued == 1
    assert result.qty_sent == 3
    assert session.sent == ["3"]


def test_abort_or_disarm_halts_before_send():
    session = FakeSession(_FIXTURE.read_text(encoding="utf-8"))
    plan = _plan()

    aborted = run_hold_purchase(
        session,
        plan,
        should_abort=lambda: True,
        is_armed=lambda: True,
    )
    disarmed = run_hold_purchase(
        session,
        plan,
        should_abort=lambda: False,
        is_armed=lambda: False,
    )

    assert aborted.outcome == "halted"
    assert aborted.reason == "aborted"
    assert aborted.sends_issued == 0
    assert disarmed.outcome == "halted"
    assert disarmed.sends_issued == 0
    assert session.sent == []


def test_unknown_qty_range_refused():
    session = FakeSession("How many holds would you like to buy ?")
    plan = _plan()

    result = run_hold_purchase(
        session,
        plan,
        should_abort=lambda: False,
        is_armed=lambda: True,
    )

    assert result.ok is False
    assert result.outcome == "refused"
    assert result.reason == "unknown_qty_range"
    assert session.sent == []


def test_price_mismatch_refused():
    session = FakeSession(_FIXTURE.read_text(encoding="utf-8"))
    plan = _plan(hold_price=999)

    result = run_hold_purchase(
        session,
        plan,
        should_abort=lambda: False,
        is_armed=lambda: True,
    )

    assert result.ok is False
    assert result.outcome == "refused"
    assert result.reason == "hold_price_mismatch"
    assert session.sent == []


def test_qty_out_of_range_refused():
    session = FakeSession(_FIXTURE.read_text(encoding="utf-8"))
    base = _plan()
    plan = StardockHoldPlan(
        world_id=base.world_id,
        fingerprint=base.fingerprint,
        stardock_sector=base.stardock_sector,
        empty_holds=base.empty_holds,
        hold_price=base.hold_price,
        credits=base.credits,
        qty=25,
    )

    result = run_hold_purchase(
        session,
        plan,
        should_abort=lambda: False,
        is_armed=lambda: True,
    )

    assert result.ok is False
    assert result.outcome == "refused"
    assert result.reason == "qty_out_of_range"
    assert session.sent == []
