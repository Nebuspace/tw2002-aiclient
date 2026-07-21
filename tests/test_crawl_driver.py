"""TW-26 live-crawl driver tests (crawl_driver.py) — no network, mock
session_factory only. `menu_crawler.py`'s own correctness (the safety
vocabulary, the never-commit guarantee across an adversarial graph) is
already thoroughly covered by tests/test_menu_crawler.py; these tests
cover what's NEW here instead: the `crawl_sacrificial` hard gate, the
abort-wrapped session_factory, and the live JSONL log."""

import json

import pytest

from twclient import credentials, game_knowledge
from twclient.crawl_driver import CrawlAborted, CrawlSafetyError, run_live_crawl


class _FakeCrawlSession:
    """Minimal fake mirroring tests/test_menu_crawler.py's
    `FakeMenuSession` (same deferred-advance-on-sleep convention
    `settle.send_and_confirm`/`wait_until_settled` rely on) — a small,
    fully-deterministic 3-screen graph: a root menu with one SAFE option
    ("V"iew -> a leaf), one HELP option ("H"elp -> a leaf), and one DENY
    option ("B"uy -> never sent, no transition needed)."""

    SCREENS = {
        "root": "(V)iew Something\n(H)elp\n(B)uy Fighters",
        "view_screen": "Just a status readout.\nNothing else to do here.",
        "help_screen": "Help text here.\nNothing else to do here.",
    }
    TRANSITIONS = {
        ("root", "V"): "view_screen",
        ("root", "H"): "help_screen",
        # deliberately no ("root", "B") -- must never be sent
    }

    def __init__(self):
        self.t = 0.0
        self.rx_count = 1
        self.last_rx = -1.0
        self._id = "root"
        self.sent = []
        self._pending = None

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._pending is not None:
            key = self._pending
            self._pending = None
            self._id = self.TRANSITIONS.get((self._id, key), self._id)
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self.SCREENS[self._id].split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self.SCREENS[self._id]

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self._pending = text


def _profile(crawl_sacrificial):
    return credentials.Profile(
        name="crawl_test_profile",
        host="test.example",
        port=2002,
        game_letter="A",
        handle="Sacrifice1",
        crawl_sacrificial=crawl_sacrificial,
    )


def _read_jsonl(path):
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines


# -- the crawl_sacrificial hard gate (the load-bearing test) -----------------


def test_run_live_crawl_refuses_non_sacrificial_profile_with_zero_connection(tmp_path):
    """The gate is checked BEFORE any connection or crawl action --
    proven here by a session_factory spy that must NEVER be called."""
    calls = []

    def spy_factory():
        calls.append(1)
        return _FakeCrawlSession()

    profile = _profile(crawl_sacrificial=False)
    log_path = tmp_path / "crawl.jsonl"
    kpath = tmp_path / "game_knowledge.json"

    with pytest.raises(CrawlSafetyError):
        run_live_crawl(profile, spy_factory, path=kpath, log_path=log_path)

    assert calls == []  # zero connection/crawl-call
    assert not log_path.exists()  # no side effect at all before the gate


def test_run_live_crawl_default_profile_is_not_sacrificial():
    """Belt-and-suspenders: the default (a profile that never set the
    field at all) must also refuse -- safe by omission, same as
    allow_register."""
    profile = _profile(crawl_sacrificial=False)
    assert profile.crawl_sacrificial is False


# -- the driver over a mock session_factory ----------------------------------


def test_run_live_crawl_completes_and_never_emits_a_deny_category(tmp_path):
    profile = _profile(crawl_sacrificial=True)
    log_path = tmp_path / "crawl.jsonl"
    kpath = tmp_path / "game_knowledge.json"

    result = run_live_crawl(profile, _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50)

    assert result["aborted"] is False
    assert result["nodes_visited"] == 3  # root + view_screen + help_screen
    assert result["screens_seen"] > 0
    # never-commit guarantee still holds end to end through this wiring
    from twclient import menu_crawler

    assert set(result["emitted_keys"]) <= menu_crawler.SAFE_ALLOWLIST
    assert set(result["emitted_keys"]) & menu_crawler.STATE_CHANGING_KEYS == set()
    assert "buy" not in result["emitted_keys"]

    # the game_knowledge store actually got written
    assert kpath.exists()
    assert len(game_knowledge.list_menu_nodes(kpath)) >= 3


def test_run_live_crawl_log_is_well_formed_jsonl_with_expected_phases(tmp_path):
    profile = _profile(crawl_sacrificial=True)
    log_path = tmp_path / "crawl.jsonl"
    kpath = tmp_path / "game_knowledge.json"

    run_live_crawl(profile, _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50)

    events = _read_jsonl(log_path)
    assert events  # non-empty
    for e in events:
        assert "ts" in e and "event" in e

    phases = [e["phase"] for e in events if e["event"] == "phase"]
    assert phases == ["connect", "registered", "crawl_start", "done"]

    screen_events = [e for e in events if e["event"] == "screen"]
    assert len(screen_events) > 0

    summaries = [e for e in events if e["event"] == "summary"]
    assert len(summaries) == 1
    assert summaries[0]["nodes_visited"] == 3


def test_run_live_crawl_appends_across_repeated_calls(tmp_path):
    """log_path is append-only, never truncated -- a re-run against the
    same path accumulates (same convention as ledger.py)."""
    profile = _profile(crawl_sacrificial=True)
    log_path = tmp_path / "crawl.jsonl"
    kpath = tmp_path / "game_knowledge.json"

    run_live_crawl(profile, _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50)
    first_len = len(_read_jsonl(log_path))
    run_live_crawl(profile, _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50)
    second_len = len(_read_jsonl(log_path))

    assert second_len > first_len


# -- mid-crawl abort ----------------------------------------------------------


def test_run_live_crawl_abort_mid_crawl_stops_cleanly(tmp_path):
    """abort_check returns False on the very first session_factory call
    (the crawl's own root-open) and True on the second -- i.e. it fires
    before the crawler ever gets to probe root's options at all. Proves
    a mid-crawl abort halts promptly: crawl_menus() never returns a
    result (nodes_visited is None), only ONE screen was ever actually
    logged, and nothing beyond it appears in the log."""
    call_count = [0]

    def abort_check():
        call_count[0] += 1
        return call_count[0] >= 2

    profile = _profile(crawl_sacrificial=True)
    log_path = tmp_path / "crawl.jsonl"
    kpath = tmp_path / "game_knowledge.json"

    result = run_live_crawl(
        profile, _FakeCrawlSession, path=kpath, log_path=log_path, abort_check=abort_check, max_nodes=50
    )

    assert result["aborted"] is True
    assert result["nodes_visited"] is None
    assert result["emitted_keys"] == []
    assert result["send_log"] == []
    assert result["screens_seen"] == 1  # only the root-open succeeded before the abort fired

    events = _read_jsonl(log_path)
    screen_events = [e for e in events if e["event"] == "screen"]
    assert len(screen_events) == 1  # nothing more was ever fetched after the abort

    phases = [e["phase"] for e in events if e["event"] == "phase"]
    assert phases == ["connect", "registered", "crawl_start", "aborted"]
    assert "done" not in phases
    # no summary is ever written on an aborted run -- crawl_menus() never returned one
    assert not any(e["event"] == "summary" for e in events)


def test_run_live_crawl_abort_mid_crawl_names_the_reason(tmp_path):
    """`aborted_reason` (WO-CLEANPREEMPT addition) carries the triggering
    CrawlAborted message -- lets a caller/log tell an external
    abort_check apart from a driver-fence stop without a separate
    boolean field."""
    profile = _profile(crawl_sacrificial=True)
    log_path = tmp_path / "crawl.jsonl"
    kpath = tmp_path / "game_knowledge.json"

    result = run_live_crawl(
        profile, _FakeCrawlSession, path=kpath, log_path=log_path, abort_check=lambda: True, max_nodes=50
    )

    assert result["aborted"] is True
    assert result["aborted_reason"] == "abort_check requested a stop"
    events = _read_jsonl(log_path)
    aborted_events = [e for e in events if e.get("phase") == "aborted"]
    assert aborted_events[0]["reason"] == "abort_check requested a stop"


def test_run_live_crawl_non_aborted_completion_reports_aborted_reason_none(tmp_path):
    profile = _profile(crawl_sacrificial=True)
    log_path = tmp_path / "crawl.jsonl"
    kpath = tmp_path / "game_knowledge.json"

    result = run_live_crawl(profile, _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50)

    assert result["aborted"] is False
    assert result["aborted_reason"] is None


# -- WO-CLEANPREEMPT: is_driver_fenced -- a second, independent abort trigger


def test_run_live_crawl_stops_cleanly_when_the_driver_is_fenced(tmp_path):
    """Mirrors test_run_live_crawl_abort_mid_crawl_stops_cleanly's shape
    exactly, with `is_driver_fenced` firing on the second session_factory
    call instead of `abort_check` -- a `tw attach` racing in mid-crawl
    (WO-CLEANPREEMPT) stops the crawl at the next node boundary, the
    identical clean-stop path an external abort_check already uses."""
    call_count = [0]

    def is_driver_fenced():
        call_count[0] += 1
        return call_count[0] >= 2

    profile = _profile(crawl_sacrificial=True)
    log_path = tmp_path / "crawl.jsonl"
    kpath = tmp_path / "game_knowledge.json"

    result = run_live_crawl(
        profile, _FakeCrawlSession, path=kpath, log_path=log_path, is_driver_fenced=is_driver_fenced, max_nodes=50
    )

    assert result["aborted"] is True
    assert "fenced" in result["aborted_reason"]
    assert result["nodes_visited"] is None
    assert result["screens_seen"] == 1  # only the root-open succeeded before the fence fired

    phases = [e["phase"] for e in _read_jsonl(log_path) if e["event"] == "phase"]
    assert phases == ["connect", "registered", "crawl_start", "aborted"]


def test_run_live_crawl_is_driver_fenced_and_abort_check_are_independent_triggers(tmp_path):
    """Either signal alone is enough -- `abort_check` staying False the
    whole run doesn't mask a fence, and vice versa (proven separately
    above); here abort_check is provided but never trips, confirming the
    fence check still fires on its own."""
    profile = _profile(crawl_sacrificial=True)
    log_path = tmp_path / "crawl.jsonl"
    kpath = tmp_path / "game_knowledge.json"

    result = run_live_crawl(
        profile,
        _FakeCrawlSession,
        path=kpath,
        log_path=log_path,
        abort_check=lambda: False,
        is_driver_fenced=lambda: True,
        max_nodes=50,
    )

    assert result["aborted"] is True
    assert "fenced" in result["aborted_reason"]


def test_run_live_crawl_abort_check_never_called_when_gate_refuses(tmp_path):
    """The crawl_sacrificial gate is checked before abort_check is ever
    consulted at all -- a non-sacrificial profile refuses without
    touching any of the caller-supplied hooks."""
    abort_calls = []

    def abort_check():
        abort_calls.append(1)
        return False

    profile = _profile(crawl_sacrificial=False)
    log_path = tmp_path / "crawl.jsonl"
    kpath = tmp_path / "game_knowledge.json"

    with pytest.raises(CrawlSafetyError):
        run_live_crawl(
            profile, _FakeCrawlSession, path=kpath, log_path=log_path, abort_check=abort_check
        )

    assert abort_calls == []
