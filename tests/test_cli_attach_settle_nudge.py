"""MT-09 / SESSION-F1-MICRO-SETTLE-NUDGE -- CORRECTED (WO-ENSURE-SPAWN-READINESS).

**This file's original ruling was wrong, and is corrected here rather than
silently rewritten.** Commit `9110a95` pinned `ensure_raw` discarding a
failed post-spawn `read` as *benign* -- the reasoning at the time (MT-09's
own row: "Benign today; silent if nudge starts mattering") was that the
`read` is a cosmetic settle nudge, not a readiness proof, so its failure
should never affect the real `ensure` round trip's own, independently
decisive result.

**Live evidence proved the opposite.** `twgs.microblaster.net`'s post-stop
re-ensure produced exactly the failure mode MT-09 named as the risk: the
discarded `read`'s not-ready answer (`empty_response`) was immediately
followed by the SAME not-ready daemon answering the real `ensure` call with
the identical `empty_response` -- which rode straight through as
`ensure_raw`'s own top-level result, misreporting a purely local startup
race as though a *remote* game server had failed
(`REASON_CONNECT_FAILED` in `adapters.py`). "The nudge doesn't matter" was
false in exactly the case a nudge exists to catch.

`ensure_raw` (`session/cli.py`) now RETRIES the settle `read` -- checking,
not discarding, its result -- until it succeeds or the shared `deadline`
budget runs out (see `tests/test_ensure_spawn_readiness.py` for the PIN
tests on that mechanism and on the "never becomes ready" failure mode).

**What survives from the original test, unchanged in spirit:** a single
TRANSIENT nudge hiccup -- the daemon settles a moment later, same as it
always does in the real startup race -- must still not "poison" the result
or invent a failure where none exists. That is what this test proves now:
retrying past one failed `read` still reaches a decisive, successful
`ensure`. It does NOT prove (and no longer claims) that a nudge failure is
inconsequential -- a nudge that never resolves is exactly the case
`tests/test_ensure_spawn_readiness.py::
test_ensure_raw_never_reports_empty_response_for_a_daemon_that_just_never_answers`
now pins as a genuine, distinguishable `spawn_failed`.
"""

from __future__ import annotations

from tw2002_aiclient.session import cli


def test_ensure_raw_settle_nudge_failure_does_not_flip_ensure_result(
    tmp_path, monkeypatch
):
    """Pin: ONE transient post-spawn `read` hiccup, followed by a real
    settle, does not poison an otherwise-decisive `ensure` result -- the
    retry added for WO-ENSURE-SPAWN-READINESS must not turn a normal,
    single-beat startup race into a false failure."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    sock = run_dir / "twd.sock"
    # Pre-plant so wait-for-exists can exit without a real daemon. Product
    # WO-ENSURE-STALE-SOCK-RECOVER unlinks orphan sock before Popen when
    # daemon_alive is False — FakePopen must recreate the node (same as a
    # real daemon bind) or the wait loop never sees a socket.
    sock.write_text("")
    (tmp_path / "logs").mkdir()

    calls = []

    def fake_send_request(verb, args_payload, *, timeout=15.0, run_dir=None):
        calls.append(verb)
        if verb == "read":
            # Not-ready exactly once -- the daemon settles on the very next
            # probe, same as the ordinary (non-racy) startup case.
            if calls.count("read") == 1:
                return {"ok": False, "error": "connect_failed:nudge"}
            return {"ok": True, "classification": "settled"}
        if verb == "ensure":
            return {"ok": True, "classification": "main_command"}
        return {"ok": False, "error": f"unexpected:{verb}"}

    monkeypatch.setattr(cli, "_resolve_profile_connection", lambda name: ("127.0.0.1", 23))
    monkeypatch.setattr(cli, "daemon_alive", lambda run_dir=None: False)
    monkeypatch.setattr(cli, "send_request", fake_send_request)
    monkeypatch.setattr(cli.env, "socket_path", lambda run_dir=None: sock)
    monkeypatch.setattr(cli.env, "resolve_run_dir", lambda: run_dir)
    monkeypatch.setattr(cli.env, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(cli.env, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli.env, "RUN_DIR_VAR", "TW_RUN_DIR")

    class _FakePopen:
        def __init__(self, *a, **k):
            sock.write_text("")  # recreate after product orphan unlink

    monkeypatch.setattr(cli.subprocess, "Popen", _FakePopen)

    resp = cli.ensure_raw("demo", timeout=5.0, run_dir=run_dir)
    assert resp == {"ok": True, "classification": "main_command"}
    assert calls == ["read", "read", "ensure"]
