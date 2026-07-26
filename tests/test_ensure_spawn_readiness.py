"""WO-ENSURE-SPAWN-READINESS -- `ensure_raw`'s post-spawn settle `read` must
be a CHECKED readiness probe, not a discarded one.

`cli.py::ensure_raw`'s spawn branch used to prove readiness two ways, only
one of which is real:

1. `sock_path.exists()` -- a unix socket FILE can exist as soon as `bind()`
   runs, well before anything is `accept()`-ing on it. File presence is not
   listener readiness.
2. The post-spawn settle `read` round trip -- this one WOULD have caught a
   not-ready daemon (`empty_response` / a connect refusal), but its return
   value was never assigned or checked. The real `ensure` round trip right
   below it then met the exact same not-ready daemon and surfaced
   `empty_response` to the operator as though a *remote* game server had
   failed.

These tests never spawn a real daemon subprocess or touch a real socket --
`subprocess.Popen`, `daemon_alive`, `env.socket_path`, and `send_request` are
all faked (same idiom as `tests/test_ensure_no_auto_arm.py` /
`tests/test_cli_run_dir.py`), so the not-ready window is produced by a plain
call counter, deterministically, on every machine -- never a sleep-based
race. `env.socket_path(...).exists()` is faked to return `True` from the
very FIRST check, so the OLD `Path.exists()` gate is satisfied instantly and
cannot be the thing that saves either test -- only a checked, retried round
trip can.
"""

from __future__ import annotations

from types import SimpleNamespace

from tw2002_aiclient.session import cli


class _AlwaysExistsSockPath:
    """Simulates the real race: the socket FILE is already present (as it
    would be the instant `bind()` returns) before anything behind it is
    ready to answer. `cli.ensure_raw`'s `sock_path.exists()` spin-wait
    (`:270-277`) is satisfied on its very first check -- this fixture never
    becomes the guard that determines the test's outcome."""

    def exists(self):
        return True


def _wire_spawn_branch(monkeypatch, *, popen_side_effect=None):
    """Common harness routing `ensure_raw` into its spawn branch without a
    real daemon process, real profile, or real socket."""
    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: False)
    monkeypatch.setattr(cli, "_resolve_profile_connection", lambda _p: ("127.0.0.1", 23))
    monkeypatch.setattr(cli.env, "socket_path", lambda _rd=None: _AlwaysExistsSockPath())

    def fake_popen(cmd, **kwargs):
        return SimpleNamespace(pid=999999)

    monkeypatch.setattr(cli.subprocess, "Popen", popen_side_effect or fake_popen)


def test_ensure_raw_retries_the_settle_probe_until_a_real_round_trip_succeeds(
    monkeypatch, tmp_path
):
    """PIN (crux assertions, not gate-only): a not-ready daemon (deterministic
    `empty_response` on the first two round trips) must be RETRIED, never
    silently accepted-and-discarded. Two independent things are checked, both
    of which flip red the instant the probe's result goes back to being
    ignored:

    * `read_calls["n"] >= 3` -- proves the mechanism: the settle probe was
      actually re-sent after a not-ready answer. Under the discarded-probe
      defect, `ensure_raw` sends exactly ONE `read` (whose answer it never
      looks at) before falling straight through to the `ensure` verb -- this
      would freeze at `1`.
    * `resp["ok"] is True` -- proves the user-visible Accept criterion: once
      the daemon genuinely becomes ready, `ensure_raw` reaches it rather than
      reporting a stale not-ready answer.

    Neither assertion is satisfied by any OTHER guard in `ensure_raw` --
    `daemon_alive`, `_resolve_profile_connection`, `subprocess.Popen`, and
    the `sock_path.exists()` gate are all faked to pass trivially and
    immediately, so only the readiness-retry code under test can produce
    this result.
    """
    _wire_spawn_branch(monkeypatch)

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    read_calls = {"n": 0}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        if verb == "read":
            read_calls["n"] += 1
            if read_calls["n"] < 3:
                return {"ok": False, "error": "empty_response"}
            return {"ok": True, "class": "settled"}
        if verb == "ensure":
            return {"ok": True, "class": "main_command"}
        raise AssertionError(f"unexpected verb {verb!r} sent by ensure_raw")

    monkeypatch.setattr(cli, "send_request", fake_send)

    resp = cli.ensure_raw("scratch", timeout=5.0, run_dir=run_dir)

    assert read_calls["n"] >= 3, (
        f"settle probe was sent only {read_calls['n']} time(s) -- its "
        "not-ready answer was not actually retried/checked"
    )
    assert resp == {"ok": True, "class": "main_command"}


def test_ensure_raw_never_reports_empty_response_for_a_daemon_that_just_never_answers(
    monkeypatch, tmp_path
):
    """PIN (crux assertions): a freshly-spawned daemon that NEVER produces a
    successful round trip within budget must fail as a distinguishable
    `spawn_failed`, never as the raw `empty_response`/`connect_failed*` wire
    error (Accept #2: "empty_response is no longer reachable purely because
    the client was faster than daemon startup"). Every probe here returns
    the exact not-ready shape reported live against `twgs.microblaster.net`'s
    post-stop re-ensure.

    `resp["error"] == "spawn_failed"` is the crux -- under the
    discarded-probe defect, `ensure_raw` sends one `read` (ignored) then
    immediately sends the real `ensure` verb against the same never-ready
    daemon, which returns this test's `empty_response` verbatim as the
    function's own top-level answer. That is the exact defect this WO
    describes ("a false claim about someone else's service, with a real
    defect of ours buried underneath it").
    """
    _wire_spawn_branch(monkeypatch)

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        # Deterministically never ready, on ANY verb, at ANY call count --
        # models a daemon that is up (the socket file exists) but never
        # produces a successful round trip.
        return {"ok": False, "error": "empty_response"}

    monkeypatch.setattr(cli, "send_request", fake_send)

    # Short budget -- the point under test is the FAILURE MODE (what error
    # code surfaces), not how long a real budget takes to exhaust.
    resp = cli.ensure_raw("scratch", timeout=1.0, run_dir=run_dir)

    assert resp["ok"] is False
    assert resp["error"] == "spawn_failed", (
        f"expected a distinguishable spawn_failed, got {resp!r} -- "
        "empty_response leaked through to the top-level ensure answer"
    )
    assert resp["error"] != "empty_response"


def test_ensure_raw_first_probe_success_sends_exactly_one_settle_read(monkeypatch, tmp_path):
    """Gate-only sanity check (NOT a pin for this defect): the retry loop
    must not become a gratuitous poll when the daemon is ready on the very
    first attempt -- the common, non-racy case. This passes identically
    whether or not the probe's result is checked (a discarded-probe
    implementation also sends exactly one `read` here, since there is
    nothing to retry against), so it proves the fix adds no needless
    overhead on the fast path -- it does NOT, by itself, prove the defect is
    fixed. Kept alongside the two PIN tests above, not in place of them.
    """
    _wire_spawn_branch(monkeypatch)

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    read_calls = {"n": 0}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        if verb == "read":
            read_calls["n"] += 1
            return {"ok": True, "class": "settled"}
        if verb == "ensure":
            return {"ok": True, "class": "main_command"}
        raise AssertionError(f"unexpected verb {verb!r} sent by ensure_raw")

    monkeypatch.setattr(cli, "send_request", fake_send)

    resp = cli.ensure_raw("scratch", timeout=5.0, run_dir=run_dir)

    assert read_calls["n"] == 1
    assert resp == {"ok": True, "class": "main_command"}
