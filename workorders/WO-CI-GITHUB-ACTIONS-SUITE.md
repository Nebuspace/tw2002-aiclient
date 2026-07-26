# WO-CI-GITHUB-ACTIONS-SUITE

**Status:** **SUPERSEDED** by [`WO-PR-CI-LIVE-PROVE-SPLIT`](WO-PR-CI-LIVE-PROVE-SPLIT.md) (Max 2026-07-26 — PR return path · secrets bank · laptop-default live prove)  
**Posted:** 2026-07-26 · Max ask: move suite off local machine; tests bog down under `-n auto` mid AI-coding  
**Do not implement this file** — use the superseding WO.

## Goal

Run the **full offline unit/FakeTWGS suite on GitHub Actions** on every push to `main` (and optionally every PR), so implementers and Max are not forced to burn a local machine on ~3k parallel pytest workers mid-coding.

Local midstream proof becomes **targeted** (`pytest path/to/tests -n0`), not the full suite.

## Why now

- Default is already `-n auto` (`WO-TEST-PARALLEL-DEFAULT` / `pytest.ini`) — correct for CI machines, brutal on a laptop during agent build-waves.
- Seats today often run full suite as Accept proof → fan-out workers saturate Max's box.
- **Zero** `.github/workflows/` today — greenfield, no migration of a broken pipeline.

## Proposed shape (Max can trim)

| Trigger | What runs |
|---|---|
| `push` to `main` | Full suite: `python -m pytest` (inherits `-n auto`) |
| `pull_request` → `main` | Same (optional but recommended — catches before merge) |
| Local / agent midstream | **Targeted only** — touched tests + `-n0`; document in CLAUDE.md / seat brief |

### Required CI hygiene

1. **No live TWGS / no secrets** — unit + FakeTWGS only; fail the job if any test tries real network (pin or marker).
2. **PTY / curses** — use `xvfb-run` or mark and skip on CI if headless fails; do not silently greenwash.
3. **Cache** `.venv` / pip for speed.
4. **Timeout** + artifact upload of junit/last-failed on red.
5. **Flake policy** — suite must be green under `-n auto` on GHA (we just fixed parallel flake `f6432a1`); if CI flakes, fix tests — do not default CI to `-n0` without Max GO.
6. **Public logs** — redaction already product-side; never echo profile secrets in workflow env.

### Explicitly out of scope

- Replacing live ensure matrix / sacrificial host proof (stays human/hub-gated).
- Making CI the *only* Accept proof for safety WOs (cipher/mack + targeted pins still local/fast).
- Running ignored banked rehab files until un-ignored on purpose.

## Local / agent contract change (docs in same tip)

Document standing rule:

> Midstream (AI coding): run **narrow** pytest on files you touched (`-n0`).  
> Full suite: **CI on main** (or explicit `pytest` when you mean to pay the cost).  
> Accept STATUS may cite CI green URL **or** targeted pins + “full suite deferred to CI” when hub allows.

Hub may still demand a local full run for safety-critical Accept until CI has a clean track record (N green mains).

## Accept

1. Workflow file(s) under `.github/workflows/` run on `main` push; job installs deps from `pyproject.toml` / lock and runs pytest.
2. README or CLAUDE.md one-liner: local midstream = targeted; full = CI.
3. One documented green CI run on `main` (or a dry-run PR) posted in STATUS.
4. No secrets / live host credentials in workflow YAML.

## Proof

```text
# after land: open Actions tab — green "suite" workflow on tip SHA
# local still: pytest tests/test_<touched>.py -n0
```

## Refs

- `pytest.ini` (`-n auto` default)
- `WO-TEST-PARALLEL-DEFAULT.md` · `WO-SUITE-PARALLEL-FLAKE.md` (`f6432a1`)
- Max ask 2026-07-26 (machine bog-down mid AI coding)
