# WO-BANNER-STAMP-SWEEP-317 — Stamp shipped READY banners after #316

**Status:** READY · EXECUTE · LOW · docs-only tip-honesty  
**Seat:** `impl-aiclient-cursor`  
**Branch:** `wo/BANNER-STAMP-SWEEP-317`  
**Depends:** main ≥ `2497c16` (#316)

## Why

Hub tip-check after FIND-STARDOCK: nearly every `Status: READY` banner in `workorders/`
already shipped on `main`. Stale READY poisons queue depth and IDLE-KICK targeting.

## Goal

Flip confirmed-shipped WO banners to `DONE · origin <SHA> (#N)` (verify-first — do not
stamp without `git log` / `gh pr` evidence).

## Scope (verify each before edit)

Stamp only after tip-check proves product on main. Candidate set (hub pre-check 2026-08-02):

- WO-FIND-STARDOCK-TOGGLE (#316) · WO-DEATH-RESPAWN (#308)
- WO-HUD-CARGO-BREAKDOWN (#305) · WO-HUD-CARGO-HOLDINGS (#306)
- WO-PLAY-HOST-SWITCH-DAEMON (#309) · WO-PLAY-STRIP-POLICY-AUTO (#297)
- WO-CONN-HEARTBEAT-GLYPH (#300) · WO-FOCUS-PTY-WAIT-FRAME (#301)
- WO-STRIP-HOTFIX-FIT-TRADE-LOGS (#299) · WO-TRADE-PARTIAL-BACKOFF (#302)
- WO-RETIRE-EXPLORE-OFFER (#304) · WO-LOOPS-POPUP-OVERLAY (#298)
- WO-AUTONOMY-HELP-VOCAB (#303) · WO-WIRE-AUTONOMY-HELP-LINES (#285)
- WO-GUARDED-RULE-KERNEL (#219) · WO-RULE-ENGINE-WIRE (#220)
- WO-REFLEX-CLIENT-REACH (#221) · WO-RULE-WRITER-DRAFTS (#222)
- WO-DRAFT-APPROVE-KERNEL-BRIDGE (#223) · WO-REFLEX-ARMED-RUN (#224)
- WO-WARP-CONFIRM-Y (#307) · WO-CURSOR-HOOK-RECOVERY-HARDENING (#289)
- WO-FOLD-EMPTY-DECISIONS-DOC (#287) · related BANNER-STAMP-* stampers if still READY
- Adapter / timeout IN-PROGRESS banners only if code proves DONE

Skip anything still genuinely open. No product code changes.

## Accept

1. Each edited banner cites real SHA/PR (or left READY with one-line "still open" note if tip-check fails).
2. Docs-only diff · suite untouched / n/a.
3. STATUS lists files stamped + skipped-with-reason.

## Proof

```bash
git diff --stat origin/main...HEAD   # workorders/ only
# optional: no pytest required for docs-only
```
