# WO-PLAY-LADDER-LIVE-PROVE

**Status:** OPEN  
**Posted:** 2026-07-27T04:12:19Z · Max ask — CC must test Play ladder against a **live TWGS**  
**Seat:** `impl-claudecode-aiclient` (only)  
**Depends:** L1–L4 on `main` tip `3ec1928` (or newer)  
**Plan:** `.samantha/plans/one-client-play-ladder-20260727.md`

## Goal

Prove the one-client Play ladder on a **real TradeWars server** — not unit mocks talking to themselves. Max wants explicit live-server evidence for ensure → offer → E → y → explore progress.

## Authorized bank (this WO only)

Hub ephemeral sacrificial bank (already used for M4 / ensure matrix — **not** Max’s personal bank):

```text
TW_CONFIG_DIR=/tmp/tw2002-live-ensure-matrix-20260726T0801Z
```

- Profile: **`proof_micro`** (host microblaster · game letter B · handle in that bank)
- Secrets live in that dir’s `secrets.json` — **do not** copy secrets into git, coord, or audit prose
- Isolation rule: when `TW_CONFIG_DIR` is set you **must** pass an isolated run-dir:

```text
RUN=/tmp/play-ladder-live-prove-$(date -u +%Y%m%dT%H%MZ)
mkdir -p "$RUN"
export TW_CONFIG_DIR=/tmp/tw2002-live-ensure-matrix-20260726T0801Z
export TW_RUN_DIR="$RUN"
```

If that bank is missing on your machine: **STOP** and `❓ DECISION-NEEDED` — do not invent credentials, do not scrape Max’s bank, do not stand up a fake TWGS and call it live.

## Scope (owned)

- Live exercise only + audit write-up under `audit/`
- Optional tiny **test harness script** under `scripts/` **only if** needed to drive Play keys against the live daemon without a human TTY — delete or keep under `scripts/` with clear “live-prove helper” name; no product behavior change
- **No** product feature work unless live prove surfaces a **real** bug (then STATUS with REVISE ask before fixing)

## Out of scope

- New CLI verbs
- Autopilot `game_select` changes
- Xeno / Max personal bank
- Claiming “demoed for Max” without the Accept below

## Procedure (do in order)

### 1. Tip + isolation

```bash
cd <repo> && git fetch origin && git checkout main && git pull --ff-only
git rev-parse --short HEAD   # expect 3ec1928 or descendant
# export TW_CONFIG_DIR / TW_RUN_DIR / RUN as above
```

### 2. Live ensure → `main_command`

```bash
./tw ensure --profile proof_micro --timeout 45 --no-auto-arm --run-dir "$RUN" --json
```

Accept gate: `"ok": true` and classification/`class` = `main_command`. Save JSON to `/tmp/…` (not git) and summarize hosts/outcome in the audit (no secrets).

### 3. Live Play-path drive (required)

Drive the **product Play path** against that live daemon (real `adapters.explore_*`, not mocked):

1. After ensure, session sits at `main_command`.
2. Invoke `_run_play` (or equivalent product entry) with a fake/scripted stdscr that sends, in order:
   - **`E`** (raise confirm gate — offer must already be on status_line from ensure success)
   - **`y`** (confirm explore ×5)
   - idle ticks (`-1`) long enough for explore to finish or ≥15s
3. Assert at least one of:
   - `status_line` matched `explore \d+/5` (or `explore completed`) during/after the run, **or**
   - after the key sequence, `adapters.explore_status(run_dir=…)` (or `./tw explore status --run-dir "$RUN" --json`) shows `run.outcome=completed` and `run.distinct_sectors >= 5`

**Prefer both.** Wire nests under `run` — read `raw["run"]["distinct_sectors"]`, not top-level.

Do **not** satisfy Accept by only running `tw explore start` from the CLI while skipping the Play E→y path. CLI explore may be a **secondary** corroboration after Play keys.

### 4. Cleanup

```bash
./tw explore stop --run-dir "$RUN" --json || true
./tw stop --run-dir "$RUN" --json || true
```

Do not leave a connected daemon holding the sacrificial character mid-run without STATUS note.

## Accept (falsifiable)

1. Live TWGS host was **microblaster** (or named in STATUS if bank profile differs) — connection refused / fake 127.0.0.1 harness = **FAIL**
2. Ensure reached `main_command` for `proof_micro`
3. Play path keys **E** then **y** were exercised against the **live** adapter (proof: call log, or status_line transition `explore ×5 available — press E` → confirm → started/progress)
4. Explore reached **`distinct_sectors >= 5`** with **`outcome=completed`** (or honest halt with reason + screen class — still a live prove, mark HALTED not fake-green)
5. Audit file committed: `audit/live-play-ladder-<tip>-<UTC>.md` — hosts, tip SHA, ensure JSON summary (redacted), explore final wire, whether status_line was observed, **explicit** “Play TUI interactive Max-try: not done / done”

## Proof

- Commands + exit codes in STATUS
- Audit markdown on a branch/PR (docs-only OK) or same PR as any harness script
- live-prove check: hub posts after review; your STATUS must say LIVE not n/a

## Refs

- Tip `3ec1928` · plan `one-client-play-ladder-20260727.md`
- Hub earlier engine-only prove (ensure+adapter, **not** Play E→y): orchestrator 2026-07-27T04:11:11Z — this WO **closes that gap**
- `app.py` offer/arm/poll · `adapters.explore_*` · `workorders/WO-PLAY-EXPLORE-ARM.md` · `WO-PLAY-EXPLORE-VISIBLE.md`
