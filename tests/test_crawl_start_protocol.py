"""protocol.py's `crawl_start` verb dispatch -- no network, same bare
dispatch-harness convention as tests/test_protocol_haggle.py/
test_actor_attribution.py. `credentials.PROFILES_PATH` is monkeypatched
to a tmp_path profiles.toml rather than touching the real gitignored
config/profiles.toml (mirrors tests/test_credentials.py's own
profiles_path= convention, adapted for a call site -- _dispatch_ensure's
-- that has no such override parameter of its own)."""

import json

import pytest

from twclient import credentials, protocol
from twclient.control_lock import ControlLock


class FakeSession:
    """A single, non-menu leaf screen -- no bracket options at all, so a
    real crawl_menus() run completes in exactly one node with zero
    sends. Same minimal surface as test_menu_crawler.py's
    FakeMenuSession (clock/sleep/rx_count/last_rx/render/render_text/
    send)."""

    def __init__(self):
        self.t = 0.0
        self.rx_count = 1
        self.last_rx = -1.0
        self.sent = []

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds

    def render(self):
        return ["Command [TL=00753:0/0/0/850] (?=Help)? : "]

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self.render()[0]

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))


class FakeServer:
    """Deliberately bare by default -- no `.control_lock`, matching
    protocol.py's documented bare-dispatch-harness convention
    (`_driving_dispatch` treats a missing control_lock as
    unrestricted)."""


@pytest.fixture
def profiles_toml(tmp_path, monkeypatch):
    p = tmp_path / "profiles.toml"
    p.write_text(
        "[sacrificial]\n"
        'host = "test.example"\n'
        "port = 2002\n"
        'game_letter = "A"\n'
        'handle = "Sacrifice1"\n'
        "crawl_sacrificial = true\n"
        "\n"
        "[ordinary]\n"
        'host = "test.example"\n'
        "port = 2002\n"
        'game_letter = "A"\n'
        'handle = "Regular1"\n'
    )
    monkeypatch.setattr(credentials, "PROFILES_PATH", p)
    return p


def _paths(tmp_path):
    return {"path": str(tmp_path / "gk.json"), "log_path": str(tmp_path / "crawl.jsonl")}


# -- fast, up-front refusals --------------------------------------------------


def test_crawl_start_missing_profile_arg():
    resp = protocol.dispatch(FakeSession(), "crawl_start", {}, FakeServer())
    assert resp == {"ok": False, "error": "missing_profile"}


def test_crawl_start_unknown_profile_name(profiles_toml, tmp_path):
    resp = protocol.dispatch(
        FakeSession(), "crawl_start", {"profile": "nope", **_paths(tmp_path)}, FakeServer()
    )
    assert resp["ok"] is False
    assert resp["error"].startswith("profile_not_found")


def test_crawl_start_refuses_non_sacrificial_profile(profiles_toml, tmp_path):
    resp = protocol.dispatch(
        FakeSession(), "crawl_start", {"profile": "ordinary", **_paths(tmp_path)}, FakeServer()
    )
    assert resp == {"ok": False, "error": "not_crawl_sacrificial:ordinary"}


def test_crawl_start_missing_path_or_log_path(profiles_toml, tmp_path):
    resp = protocol.dispatch(
        FakeSession(), "crawl_start", {"profile": "sacrificial"}, FakeServer()
    )
    assert resp == {"ok": False, "error": "missing_path_or_log_path"}


# -- control-lock gating (same guard do/send/replay/play/haggle share) ------


def test_crawl_start_refused_while_human_is_attached(profiles_toml, tmp_path):
    server = FakeServer()
    server.control_lock = ControlLock()
    server.control_lock.take_human()

    resp = protocol.dispatch(
        FakeSession(), "crawl_start", {"profile": "sacrificial", **_paths(tmp_path)}, server
    )
    assert resp == {"ok": False, "error": "controller_locked_by_human"}


# -- the happy path over a mock (non-network) session ------------------------


def test_crawl_start_dispatches_and_returns_the_crawl_summary(profiles_toml, tmp_path):
    resp = protocol.dispatch(
        FakeSession(), "crawl_start", {"profile": "sacrificial", **_paths(tmp_path)}, FakeServer()
    )
    assert resp["ok"] is True
    assert resp["aborted"] is False
    assert resp["nodes_visited"] == 1  # a single non-menu leaf screen
    assert resp["emitted_keys"] == []

    log_path = tmp_path / "crawl.jsonl"
    assert log_path.exists()
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    phases = [e["phase"] for e in events if e["event"] == "phase"]
    assert phases == ["connect", "registered", "crawl_start", "done"]
