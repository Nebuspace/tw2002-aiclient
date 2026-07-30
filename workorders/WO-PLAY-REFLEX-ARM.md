# WO-PLAY-REFLEX-ARM — Play can preview + confirm-arm a reflex proposal

**Status:** OPEN · EXECUTE · HIGH · visible client automation · Cursor-only  
**Posted / seeded:** 2026-07-30T03:50Z · hub (Max priority: automation in the client)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `6ea3dcd` / tip with `reflex` + `reflex_arm` + Analyze→rule-store bridge  
**Refs:** `WO-REFLEX-ARMED-RUN` · `WO-REFLEX-CLIENT-REACH` · `WO-DRAFT-APPROVE-KERNEL-BRIDGE` · `canon/architecture/app-autopilot-model.md`

## Goal

From **Play** (the client Max sits in), an operator can:

1. ask what the taught rule library proposes for the live screen,
2. see the proposal (macro + rule id + classification) in the cockpit,
3. confirm with the existing default-deny `y/N` arm gate,
4. launch **only** through the existing fresh-revalidating `reflex_arm → autoloop_start` path.

Today that path is CLI-only (`tw reflex` / `tw reflex --arm`). Play can Explore / L)chains / Analyze, but cannot reach reflex — automation stays outside the client.

## Scope

- **`adapters.py`:** typed `reflex_arm(...)` (or equivalent) wrapping daemon `reflex_arm` — never-raises transport, structured result. Mirror `reflex_propose` / `autoloop_start` honesty. CLI may keep its direct `send_request` call; do not invent a second launch semantics.
- **`app.py` + `screens.py` / thin `cockpit/` helper:** a free Play key (recommend **`V`/`v`** — not in {A,R,T,L,E,D,F,G,P,Q,Space}) that:
  - calls `reflex_propose`,
  - if no candidate / STOP / transport fail → status_line reason, **zero** arm gate, **zero** launch,
  - if macro proposed → `begin_arm_confirm` with an honest label (`Arm <macro> LIVE?` / rule id visible in status or confirm line),
  - on `y` only (`pending_confirm_action == "reflex"`) → `reflex_arm` with the **exact** identity the human saw (`rule_id`, `macro`, `classification`),
  - cancel / non-`y` → zero launch.
- **Tests:** FakeClient / Play intent pins: no-candidate; cancel; exact confirm→adapter; drift/refusal surfaces; structural no-direct-send from Play path; key not colliding with E/L/A/R/T/D/F/G/P.
- Hint/status affordance text may mention the key once (keep minimal; no new chrome mega-panel).

## Constraints

- **Approved ≠ armed.** Proposal is a suggestion until explicit `y`.
- **Revalidate on launch.** Pass the preview identity into `reflex_arm`; daemon re-derives — never launch a stale or substituted macro from Play.
- Reuse existing `begin_arm_confirm` / `resolve_arm_confirm_key` (default-deny). No `--yes`, bare Enter, env auto-confirm, or caller boolean bypass.
- **No second player / no direct `session.send*`** from the Play reflex path.
- One pass only (daemon already refuses `cycles` on `reflex_arm`). No repeating/unattended expansion in this WO.
- `NEVER_AUTO_ACTION_CLASSES` stays unconditional; §A.2 money-prompt exemption **out of scope / Max-gated**.
- `#218` `app.py` **split** stays frozen — this WO may edit `app.py` for the Play wire only (smallest possible), not the line-cap split.
- No new external deps. No tooling/hygiene riders.

## Accept

1. Free Play key (named in STATUS) proposes via adapter; status shows macro+rule or STOP reason.
2. No candidate / STOP / transport fail → no arm gate, zero launch calls.
3. `y` after confirm launches once through `reflex_arm` with matching identity; non-`y` → zero launch.
4. Explicit `pending_confirm_action == "reflex"` (not bare `arm_confirm` default); explore/loop/relaunch branches unchanged.
5. Focused tests + full offline suite green.
6. Live prove: **safe half** (no-candidate / cancel / refusal) hub-GO offline is enough for Accept. Successful live arm spends turns → report `NOT-ATTEMPTED` until Max sacrificial GO — **never** costume as `n/a`.

## Proof

```text
pytest -q tests/test_*reflex* tests/test_play_*  # + any new focused file
pytest -q tests
```

STATUS names: key binding · adapter entrypoint · confirm label · live vocabulary (`n/a` vs `NOT-ATTEMPTED`).

## Follow-on (not this WO)

- Repeating / cycle semantics for armed reflex runs (core-mechanics; separate review).
- Auto-offer reflex on STOP / idle (needs product ruling).
