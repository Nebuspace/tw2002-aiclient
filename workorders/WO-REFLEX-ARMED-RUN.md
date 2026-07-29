# WO-REFLEX-ARMED-RUN — approved reflex proposal → confirmed macro run

**Status:** READY · visible automation (follow-on #223)
**Seat:** `impl-claudecode-aiclient`
**Branch:** `wo/REFLEX-ARMED-RUN`
**Depends:** `main` ≥ `84ad771` (reflex stack #219–#223)

## Goal

Turn the visible `tw reflex` proposal into a deliberately armed run through the
existing macro player: preview the exact approved rule/macro, require a human
`y/N`, revalidate the proposal at launch, then enter the existing
`autoloop_start → AutoLoopRunner → replay_loop` path.

Default `tw reflex` remains read-only.

## Scope

- Add an explicit `tw reflex --arm` flow (or equivalently narrow syntax):
  1. request and render the current reflex proposal;
  2. if there is no macro / a typed STOP, do not raise a confirm and send zero;
  3. show `Arm <macro> LIVE?  y/N` with rule id + screen classification;
  4. only literal `y`/`Y`, resolved through the existing default-deny
     arm-confirm policy, may launch;
  5. cancel / EOF / non-interactive unavailable input sends zero.
- Add a narrow daemon/adapter launch operation that receives the proposal
  identity the human saw (`rule_id`, `macro`, `classification`), takes one fresh
  status snapshot, re-runs `propose_macro`, and refuses unless all three still
  match exactly.
- On exact match, delegate to the existing `_dispatch_autoloop_start` /
  `AutoLoopRunner.start(name)` path. No second player, no direct send.
- Surface typed proposal-drift / no-candidate / unreadable-store / start
  refusals honestly.
- Focused tests + mutation controls.

## Constraints

- **Approved ≠ armed.** Approval makes a rule eligible; only the human's
  explicit `y` in this flow arms the run.
- No `--yes`, environment auto-confirm, default-yes, bare Enter, or caller
  boolean that can bypass the prompt.
- **Revalidate after confirmation.** Never launch from a stale preview or
  silently substitute a different rule/macro/classification.
- `NEVER_AUTO_ACTION_CLASSES` remains unconditional at `replay_loop`
  boundaries. The §A.2 money-prompt exemption remains out of scope.
- One pass only; no cycles/repetition expansion.
- Preserve start-anchor, send-and-confirm, control-lock, stop/fence, credit
  floor, and operator-stop behavior unchanged.
- No line-cap / #218 hygiene work in this slice.
- No new external dependency.

## Accept

1. Plain `tw reflex` is still read-only and behavior-compatible.
2. `tw reflex --arm` with no candidate / typed STOP / transport failure performs
   zero launch calls and prints the reason.
3. Enter, `n`, EOF, malformed input, and every key except literal `y`/`Y`
   perform zero launch calls.
4. On `y`, the daemon freshly reselects; exact same
   `(rule_id, macro, classification)` delegates once to the existing
   autoloop-start path.
5. Any change between preview and launch (rule, macro, classification, store
   status, no candidate) refuses with zero player start; no substitution.
6. The existing player rails remain the send choke-point: no direct
   `session.send*` / socket write in reflex launch code.
7. Full offline suite green; focused mutation proves prompt bypass, stale
   preview, and direct-start substitutions are caught.

## Proof

- Focused offline tests: preview/cancel; preview/EOF; exact confirm/start;
  proposal drift in each identity field; no-candidate; unreadable store;
  autoloop-start refusal propagation; structural no-direct-send pin.
- Full offline suite.
- **Live-prove split:** Cursor executor after suite. Safe half (no-candidate /
  drift/refusal) is hub-GO. A successful arm spends turns and requires a
  separate Max sacrificial GO; until then report `NOT-ATTEMPTED`, never `n/a`.

## Refs

- `canon/architecture/app-autopilot-model.md` — external human arm + re-read
- `canon/doctrine/action-safety-guards.md` — approval spine, arm-confirm rails
- `canon/architecture/rule-macro-engine.md` — one-cycle selector
- `tw2002_aiclient/session/protocol.py` — `_dispatch_reflex`,
  `_dispatch_autoloop_start`
- `tw2002_aiclient/session/autoloop.py` — existing armed runner
- `tw2002_aiclient/loops/player.py` — existing send choke-point
- `tw2002_aiclient/cockpit/armconfirm.py` — default-deny confirmation policy
- Max GO 2026-07-29T16:49Z — continue visible automation
