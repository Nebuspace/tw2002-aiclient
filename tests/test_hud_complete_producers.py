"""Cold-join seed, cargo, and session-profit HUD producers."""

from pathlib import Path

from tw2002_aiclient.session import hud_seed, hud_tracking, protocol
from tw2002_aiclient.session.session import Session
from tw2002_aiclient.session.state_parser import OUTCOME_ABSENT, OUTCOME_READ

FIXTURE = Path("tests/fixtures/ship_info_screen.txt")


class _Server:
    watch_hub = None
    control_lock = None
    autoloop = None


def _session(tmp_path) -> Session:
    session = Session("127.0.0.1", 65000, "hud", str(tmp_path))
    session.conn.connected = True
    return session


def _screen(session, monkeypatch, rows):
    current = {"rows": list(rows)}
    monkeypatch.setattr(session, "render", lambda *a, **k: list(current["rows"]))
    monkeypatch.setattr(
        session,
        "render_with_color",
        lambda *a, **k: (list(current["rows"]), None),
    )
    monkeypatch.setattr(
        session,
        "render_text",
        lambda rows=None: "\n".join(rows or current["rows"]),
    )
    return current


def test_strict_cargo_reader_accepts_live_ship_info_and_port_report():
    ship_info = hud_tracking.read_empty_cargo_holds(FIXTURE.read_text())
    assert ship_info.outcome == OUTCOME_READ
    assert ship_info.empty_holds == 60
    assert ship_info.total_holds == 60

    port = hud_tracking.read_empty_cargo_holds(
        "You have 99,000 credits and 40 empty cargo holds."
    )
    assert port.outcome == OUTCOME_READ
    assert port.empty_holds == 40
    assert port.total_holds is None


def test_cargo_reader_refuses_commodity_rows_and_impossible_ship_arithmetic():
    assert (
        hud_tracking.read_empty_cargo_holds("Fuel Ore Buying 2030 100% 17").outcome
        == OUTCOME_ABSENT
    )
    assert (
        hud_tracking.read_empty_cargo_holds("Total Holds : 20 - Empty=21").outcome
        == OUTCOME_ABSENT
    )


def test_session_tracks_empty_holds_and_profit_from_first_strict_balance(tmp_path):
    session = _session(tmp_path)
    text = FIXTURE.read_text()
    session.observe_cargo(text)
    session.observe_credits(text)

    snap = session.cargo_snapshot()
    assert snap.cargo == 60
    assert snap.total_holds == 60
    assert session.profit_snapshot().profit == 0

    session.observe_credits("You have 101,250 credits.")
    assert session.credits_snapshot().balance == 101250
    assert session.profit_snapshot().profit == 1250


def test_live_ship_info_populates_all_five_status_cells(tmp_path, monkeypatch):
    session = _session(tmp_path)
    rows = FIXTURE.read_text().splitlines()
    _screen(session, monkeypatch, rows)

    response = protocol._status_response(session, _Server())

    assert response["hud"]["credits"]["value"] == 100000
    assert response["hud"]["sector"]["value"] == 15450
    assert response["hud"]["turns"]["value"] == 25000
    assert response["hud"]["cargo"]["value"] == "60 empty / 60"
    assert response["hud"]["profit"]["value"] == 0
    for cell in response["hud"].values():
        assert cell["age_s"] is not None


def test_seed_sends_one_i_and_observes_the_confirmed_ship_info(tmp_path, monkeypatch):
    session = _session(tmp_path)
    current = _screen(
        session,
        monkeypatch,
        ["Sector : 15450", "Command [TL=07:58:26]:[15450] (?=Help)? :"],
    )
    sent = []

    def fake_send_and_confirm(target, text, **kwargs):
        sent.append((target, text, kwargs))
        current["rows"] = FIXTURE.read_text().splitlines()
        return "prompt", 0.1, True

    monkeypatch.setattr(hud_seed, "send_and_confirm", fake_send_and_confirm)

    result = hud_seed.seed_hud_after_join(session)

    assert len(sent) == 1
    assert sent[0][1] == "I"
    assert result == {
        "hud_seed_probed": True,
        "hud_seed_reason": "seeded",
        "credits": 100000,
        "turns_left": 25000,
        "cargo": 60,
    }
    assert session.profit_snapshot().profit == 0


def test_seed_is_no_send_when_already_seeded_or_not_at_main_command(tmp_path, monkeypatch):
    session = _session(tmp_path)
    current = _screen(session, monkeypatch, FIXTURE.read_text().splitlines())
    monkeypatch.setattr(
        hud_seed,
        "send_and_confirm",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected send")),
    )

    assert hud_seed.seed_hud_after_join(session)["hud_seed_reason"] == "already_seeded"

    fresh = _session(tmp_path)
    current = _screen(fresh, monkeypatch, ["Your fighters: 3 vs. theirs: 5", "Option? (A,D,I,R)"])
    assert current["rows"][-1].startswith("Option?")
    assert hud_seed.seed_hud_after_join(fresh)["hud_seed_reason"] == "unsafe_screen"


def test_seed_failure_never_raises_or_invents_values(tmp_path, monkeypatch):
    session = _session(tmp_path)
    _screen(
        session,
        monkeypatch,
        ["Sector : 15450", "Command [TL=07:58:26]:[15450] (?=Help)? :"],
    )
    monkeypatch.setattr(
        hud_seed,
        "send_and_confirm",
        lambda *a, **k: (_ for _ in ()).throw(OSError("transport down")),
    )

    result = hud_seed.seed_hud_after_join(session)

    assert result["hud_seed_reason"] == "probe_error"
    assert result["hud_seed_error"] == "OSError"
    assert session.cargo_snapshot().outcome == OUTCOME_ABSENT


_UNLIMITED_SHIP_INFO = [
    "Trader Name    : Gunnery Sergeant Sextant",
    "Current Sector : 9193",
    "Total Holds    : 50 - Empty=50",
    "Credits        : 99,000",
    "Command [TL=00:00:00]:[9193] (?=Help)? :",
]


def test_seed_confirms_ship_info_that_omits_turns_left(tmp_path, monkeypatch):
    """Unlimited-turn variants omit Turns left; Credits+cargo still seed."""
    session = _session(tmp_path)
    current = _screen(
        session,
        monkeypatch,
        ["Sector : 9193", "Command [TL=00:00:00]:[9193] (?=Help)? :"],
    )
    sent = []

    def fake_send_and_confirm(target, text, **kwargs):
        sent.append(kwargs.get("confirm_prompt"))
        current["rows"] = list(_UNLIMITED_SHIP_INFO)
        return "prompt", 0.1, True

    monkeypatch.setattr(hud_seed, "send_and_confirm", fake_send_and_confirm)

    result = hud_seed.seed_hud_after_join(session)

    assert len(sent) == 1
    assert "Credits" in sent[0]
    assert "Turns" not in sent[0]
    assert result == {
        "hud_seed_probed": True,
        "hud_seed_reason": "seeded",
        "credits": 99000,
        "turns_left": None,
        "cargo": 50,
    }
    assert session.turns_snapshot().outcome == OUTCOME_ABSENT


def test_credits_and_cargo_known_without_turns_is_already_seeded(tmp_path, monkeypatch):
    session = _session(tmp_path)
    _screen(session, monkeypatch, _UNLIMITED_SHIP_INFO)
    monkeypatch.setattr(
        hud_seed,
        "send_and_confirm",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected send")),
    )

    assert hud_seed.seed_hud_after_join(session)["hud_seed_reason"] == "already_seeded"


def test_port_empty_keeps_sticky_total_and_hud_breakdown(tmp_path, monkeypatch):
    """Port updates empty only; ship-info total sticks; HUD paints breakdown."""
    session = _session(tmp_path)
    session.observe_cargo(FIXTURE.read_text())
    assert session.cargo_snapshot().total_holds == 60

    session.observe_cargo("You have 99,000 credits and 40 empty cargo holds.")
    snap = session.cargo_snapshot()
    assert snap.cargo == 40
    assert snap.total_holds == 60

    rows = [
        "You have 99,000 credits and 40 empty cargo holds.",
        "Command [TL=00:00:08]:[1] (?=Help)? :",
    ]
    _screen(session, monkeypatch, rows)
    # Re-observe via status path uses last sticky (already observed).
    response = protocol._status_response(session, _Server())
    assert response["hud"]["cargo"]["value"] == "40 empty / 60"


def test_cargo_hud_value_without_total_cues_empty_holds():
    assert hud_tracking.format_cargo_hud_value(50, None) == "50 empty"
    assert hud_tracking.format_cargo_hud_value(50, 60) == "50 empty / 60"


def test_port_only_hud_shows_empty_cue_not_bare_int(tmp_path, monkeypatch):
    session = _session(tmp_path)
    rows = [
        "You have 99,000 credits and 40 empty cargo holds.",
        "Command [TL=00:00:08]:[1] (?=Help)? :",
    ]
    _screen(session, monkeypatch, rows)
    session.observe_cargo("\n".join(rows))
    response = protocol._status_response(session, _Server())
    assert response["hud"]["cargo"]["value"] == "40 empty"

def test_holdings_buy_equ_sticky_on_hud(tmp_path, monkeypatch):
    """After verified Equ buy, HUD CARGO shows Equ N with empty/total."""
    session = _session(tmp_path)
    session.observe_cargo(FIXTURE.read_text())
    session.adjust_holdings("Equipment", 50)
    # Port empty update after buy: 10 empty of 60 with Equ 50 aboard.
    session.observe_cargo("You have 99,000 credits and 10 empty cargo holds.")
    snap = session.cargo_snapshot()
    assert snap.cargo == 10
    assert snap.total_holds == 60
    assert snap.holdings is not None
    assert snap.holdings.equipment == 50
    assert hud_tracking.format_cargo_hud_value(
        snap.cargo, snap.total_holds, snap.holdings
    ) == "10 empty / 60 · Equ 50"

    rows = [
        "You have 99,000 credits and 10 empty cargo holds.",
        "Command [TL=00:00:08]:[1] (?=Help)? :",
    ]
    _screen(session, monkeypatch, rows)
    response = protocol._status_response(session, _Server())
    assert response["hud"]["cargo"]["value"] == "10 empty / 60 · Equ 50"


def test_holdings_sell_reduces_and_clears(tmp_path):
    session = _session(tmp_path)
    session.observe_cargo(FIXTURE.read_text())
    session.adjust_holdings("Equipment", 50)
    session.adjust_holdings("Equipment", -30)
    assert session.cargo_snapshot().holdings.equipment == 20
    session.adjust_holdings("Equipment", -20)
    assert session.cargo_snapshot().holdings.equipment == 0
    assert hud_tracking.format_cargo_hud_value(
        60, 60, session.cargo_snapshot().holdings
    ) == "60 empty / 60"
    # Oversell clamps at zero — never negative.
    session.adjust_holdings("Equipment", -5)
    assert session.cargo_snapshot().holdings.equipment == 0


def test_holdings_never_from_market_rows_or_observe_holdings(tmp_path):
    session = _session(tmp_path)
    session.observe_cargo(FIXTURE.read_text())
    assert session.last_cargo_holdings is None
    # Market / port commodity rows do not invent holdings via cargo reader.
    market = (
        "Fuel Ore Buying 2030 100% 17\n"
        "Organics Selling 500 80% 42\n"
        "Equipment Buying 100 50% 99"
    )
    session.observe_cargo(market)
    session.observe_holdings(market)
    assert session.last_cargo_holdings is None
    assert session.cargo_snapshot().holdings is None


def test_trade_driver_buy_sell_updates_session_holdings(tmp_path):
    """Thin session: adjust_holdings called with +qty on buy, -qty on sell."""
    from tw2002_aiclient.trade_driver import _apply_holdings_delta

    class _Sess:
        def __init__(self):
            self.calls = []

        def adjust_holdings(self, commodity, delta):
            self.calls.append((commodity, delta))

    s = _Sess()
    _apply_holdings_delta(s, "Equipment", 50)
    _apply_holdings_delta(s, "Equipment", -50)
    assert s.calls == [("Equipment", 50), ("Equipment", -50)]
    # Missing API is quiet.
    _apply_holdings_delta(object(), "Equipment", 1)


def test_format_cargo_hud_holdings_multi_and_unknown_until_write():
    assert hud_tracking.format_cargo_hud_value(10, 60, None) == "10 empty / 60"
    h = hud_tracking.CargoHoldings(fuel_ore=5, organics=0, equipment=50)
    assert hud_tracking.format_cargo_hud_value(5, 60, h) == "5 empty / 60 · Ore 5 · Equ 50"
    assert hud_tracking.holdings_field_for_commodity("Fuel Ore") == "fuel_ore"
    assert hud_tracking.holdings_field_for_commodity("nope") is None

