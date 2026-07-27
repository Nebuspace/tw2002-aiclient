# WO-PLAY-LADDER-LIVE-PROVE

**Status:** OPEN · **AMENDED 2026-07-27T04:18:15Z** — Max: create a **new** character on a **random** catalog server  
**Posted:** 2026-07-27T04:12:19Z · Max ask — CC must test Play ladder against a **live TWGS**  
**Seat:** `impl-claudecode-aiclient` (only)  
**Depends:** L1–L4 on `main` tip ≥ `3ec1928`  
**Plan:** `.samantha/plans/one-client-play-ladder-20260727.md`

## Goal

Prove the one-client Play ladder on a **real TradeWars server** by:

1. **Registering a brand-new sacrificial character** on a **randomly chosen** public catalog server  
2. Driving Play: ensure → offer → **E** → **y** → explore ≥5 sectors visible/proven  

Unit/pty mocks and reusing yesterday’s `proof_micro` RETURNING login are **not** Accept.

## Authorized config (this WO only)

Build a **fresh isolated** config dir (never under the git tree, never commit secrets):

```bash
CFG=/tmp/play-ladder-newchar-$(date -u +%Y%m%dT%H%MZ)
RUN=/tmp/play-ladder-newchar-run-$(date -u +%Y%m%dT%H%MZ)
mkdir -p "$CFG" "$RUN"
# catalog only — copy from repo tip (public, no secrets)
cp config/servers.toml "$CFG/servers.toml"
# empty secrets; ensure/register will save the generated password via daemon
printf '%s\n' '{}' > "$CFG/secrets.json"
export TW_CONFIG_DIR="$CFG"
export TW_RUN_DIR="$RUN"
```

**Do not** reuse `/tmp/tw2002-live-ensure-matrix-*` as the primary path (that was RETURNING).  
**Do not** invent Max’s bank. **Do not** use `127.0.0.1` fake harness.

## Create NEW character (required)

1. **Pick a random server** from `config/servers.toml` catalog keys (`random.choice` / `shuf` — record the key+host+port in the audit). Prefer port `2002` TWGS-shaped entries; skip obvious dead ones only after a connect failure (document the skip).
2. **Pick a game letter** at random from `A`–`C` (record it).
3. **Pick a fresh handle** — `Proof` + 8 hex chars (or similar throwaway). Must not collide with a known matrix handle if you can avoid it.
4. Write `$CFG/profiles.toml` **by hand** (do not rely on `create_profile()` — it hardcodes `allow_register = false`):

```toml
[<section>]
server = "<catalog_key>"
game_letter = "<A|B|C>"
handle = "<Proof…>"
ship_name = "ProofShip"
planet_name = "ProofWorld"
allow_register = true
crawl_sacrificial = true
autopilot = false
```

5. **Live ensure (NEW registration):**

```bash
./tw ensure --profile <section> --timeout 90 --no-auto-arm --run-dir "$RUN" --json
```

Accept gate: `"ok": true` and classification = `main_command`.  
If the server is full / registration refused / honest halt: **retry once** with a **different** random catalog server (max **3** server attempts total). Each failure goes in the audit with class/reason — do not silent-skip.

Password is generated + saved into `$CFG/secrets.json` by the daemon — **never** paste it into coord, git, or audit.

## Then: live Play path (required)

Same as before — against **this** new character’s live daemon:

1. Status offer: `explore ×5 available — press E` (after ensure @ `main_command`)
2. Drive product `_run_play` with **real** adapters: keys **`E`** then **`y`**, then idle ticks
3. Prove `run.distinct_sectors >= 5` and `run.outcome=completed` (fields under wire `run`) **and** prefer Play `status_line` `explore N/5…` / completed
4. `./tw explore start` alone does **not** Accept

## Cleanup

```bash
./tw explore stop --run-dir "$RUN" --json || true
./tw stop --run-dir "$RUN" --json || true
```

Leave throwaway character on the server (sacrificial). Do not delete remote accounts.

## Accept (falsifiable)

1. Profile was **created in this run** with `allow_register = true` (not a pre-existing RETURNING matrix profile)
2. Catalog server was **randomly selected** (RNG method + seed or entropy source named; chosen key+host recorded)
3. Live TWGS connection (not 127.0.0.1); ensure → `main_command` via **NEW** registration path
4. Play keys **E** then **y** against live adapters
5. Explore `distinct_sectors >= 5` · `outcome=completed` (or honest halt documented — not fake-green)
6. Audit committed: `audit/live-play-ladder-newchar-<tip>-<UTC>.md` — server key/host/port, game letter, handle (OK), tip SHA, ensure summary redacted, explore final wire, “Play keys driven: yes”, attempt count if retries

## Proof

STATUS with commands + tip SHA + audit PR. This is a **LIVE** prove — hub will not rubber-stamp `n/a`.

## Out of scope

- Product feature work unless live prove finds a real bug (then STATUS + ask before fix)
- New CLI verbs · Autopilot game_select · Max personal bank · committing `secrets.json`

## Refs

- Tip ≥ `3ec1928` · plan `one-client-play-ladder-20260727.md`
- Matrix profile shape (allow_register): `/tmp/tw2002-live-ensure-matrix-*/profiles.toml` as **example only**
- `login.py` NEW + `_fresh_password` / `save_password`
- `app.py` offer/arm/poll · `adapters.explore_*`
