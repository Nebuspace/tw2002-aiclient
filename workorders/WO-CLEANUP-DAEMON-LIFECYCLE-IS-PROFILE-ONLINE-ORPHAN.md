# WO-CLEANUP-DAEMON-LIFECYCLE-IS-PROFILE-ONLINE-ORPHAN

**Status:** OPEN (in PR)  
**Priority:** MED  
**Claimed-by:** impl-aiclient-cursor  
**Source:** Cycle-39 / queue-aiclient.md · 6-lens aiclient audit 2026-08-05

## Goal

Resolve the apparent orphan of `daemon_lifecycle.is_profile_online` (product callers = 0 outside its unit test).

## Tip-verify (2026-08-06 @ main `b6f1be3`)

| Check | Result |
|---|---|
| Def site | `tw2002_aiclient/daemon_lifecycle.py:125` |
| Product callers | **0** (grep) — only `tests/test_daemon_lifecycle.py` |
| Sibling API | `online_profile_name` **is** used by `app._apply_presence` + `quit_profile_label` |
| Duplicated logic | `_apply_presence` inlined `active is not None and row.name == active` — identical to `is_profile_online` |

## Decision

**Wire, do not retire.** The helper is the named exact-match ONLINE predicate; the launcher already needed that predicate and duplicated it. Route `_apply_presence` through `is_profile_online` so the exact-match / no-case-fold contract lives in one place.

Not a feature gap: daemon health/status already flows through `read_presence` → `online_profile_name` / `presence_note`. No new health-check path required.

## Accept

- [ ] `app._apply_presence` uses `daemon_lifecycle.is_profile_online`
- [ ] Existing `test_apply_presence_exact_match_only` still green
- [ ] No behavior change (exact name match only; still at most one ONLINE row)

## Proof

```bash
.venv/bin/python -m pytest tests/test_daemon_lifecycle.py -q -n0
```

## live-prove

`n/a` — launcher presence overlay only; no TWGS session path.
