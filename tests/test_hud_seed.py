"""WO-HUD-CREDITS-TURNS-JOIN — cold-join I-probe + sticky turns."""

from twclient.hud_seed import seed_hud_after_join


class _FakeSession:
    def __init__(self, screens):
        self._screens = list(screens)
        self._i = 0
        self.last_credits = None
        self.last_credits_ts = None
        self.last_turns = None
        self.last_turns_ts = None
        self.lock = __import__("threading").Lock()
        self.sends = []

    def render(self):
        text = self._screens[min(self._i, len(self._screens) - 1)]
        return text.split("\n")

    def render_text(self, rows):
        return "\n".join(rows)

    def observe_credits(self, text):
        from twclient.state_parser import credits_balance
        bal = credits_balance(text)
        if bal is not None:
            self.last_credits = bal
            self.last_credits_ts = 1.0

    def observe_turns(self, text):
        from twclient.state_parser import parse_state
        turns = parse_state(text).get("turns_left")
        if turns is not None:
            self.last_turns = turns
            self.last_turns_ts = 1.0

    def credits_snapshot(self):
        return self.last_credits, self.last_credits_ts

    def turns_snapshot(self):
        return self.last_turns, self.last_turns_ts

    def send(self, text, enter=True, secret=False):
        self.sends.append(text)
        self._i = min(self._i + 1, len(self._screens) - 1)

    def wait_settle(self, **kwargs):
        return "idle", 0.01


def test_seed_hud_skips_probe_when_already_known(monkeypatch):
    info = (
        "Current Sector : 10\n"
        "Turns left     : 99\n"
        "Credits        : 500\n"
    )
    session = _FakeSession([info])
    # Bypass send_and_confirm — seed should not send when values present.
    monkeypatch.setattr(
        "twclient.hud_seed.send_and_confirm",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not probe")),
    )
    out = seed_hud_after_join(session)
    assert out["hud_seed_probed"] is False
    assert out["credits"] == 500
    assert out["turns_left"] == 99


def test_seed_hud_defers_i_on_fighter_option_even_when_stats_unknown(monkeypatch):
    """I on Option? is Info (not ship-info) and can scroll the vs-line off —
    defer the probe; ensure/autopilot clear Attack/Retreat first."""
    toll = (
        "You have to destroy the fighters\n"
        "Your fighters: 30 vs. theirs: 1\n"
        "Option? (A,D,I,R,S,?):?"
    )
    session = _FakeSession([toll])
    monkeypatch.setattr(
        "twclient.hud_seed.send_and_confirm",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not I-probe Option?")),
    )
    out = seed_hud_after_join(session)
    assert out["hud_seed_probed"] is False
    assert out["hud_seed_deferred"] == "fighter_option"
    assert session.sends == []
