Goal:        Add the third `VALID_SENDERS` value (`"dev"`) and a `crawl_sacrificial`
             runtime gate, per canon/doctrine/dev-drive-exception.md's own
             "Code divergence" residual.
Scope:       tw2002_aiclient/session/session.py — `VALID_SENDERS`, `send()`,
             `send_raw()`, new `_require_dev_sender_authorized()` helper.
             tw2002_aiclient/session/credentials.py — new `is_crawl_sacrificial()`.
             tw2002_aiclient/cockpit/covermeter.py — stale tuple citation.
             tests/test_actor_attribution.py, tests/test_session.py — updated pins.
             tests/test_is_crawl_sacrificial.py (new).
Out-of-scope: No autopilot/taught-rule/macro path constructs a Session with
             sender="dev" — none was added, none should be. `_record_ledger`'s
             `actor not in ("app", "human")` refusal in protocol.py is
             deliberately left untouched (fails closed on "dev" by skipping
             ledger attribution rather than mis-recording it) — wiring "dev"
             into ledger attribution is the doc's own named residual, not
             this WO. No MODE_AI_PILOT / control_lock.py change.
Constraints: Fail-closed twice over, mirroring menu/crawl_driver.py's
             `_SACRIFICIAL_FLAG` precedent: missing profile, missing store,
             absent flag, or any non-`True` truthy stand-in all refuse.
             Checked fresh on every send call, never cached.
Accept:      `VALID_SENDERS == ("app", "human", "dev")`. `send()`/`send_raw()`
             refuse `sender="dev"` unless `auto_login_profile` is marked and
             `is_crawl_sacrificial(profile) is True`. No regression in the
             existing `{app, human}` legacy-rejection tests.
Proof:       `.venv/bin/python -m pytest tests/test_is_crawl_sacrificial.py
             tests/test_actor_attribution.py tests/test_session.py -n0 -q`
             + full suite diffed against clean main to confirm no new
             failures (3 pre-existing unrelated failures reproduce
             identically on main without this diff: test_play_chains_arm,
             test_play_chains_discovered, test_cockpit_viewport_pty,
             test_cockpit_attach — plus the known 2 PTY covermeter flakes).
Refs:        canon/doctrine/dev-drive-exception.md, tw2002_aiclient/menu/crawl_driver.py.
