# WO-BACKPORT-PR-CI-COORD-TO-CLAUDE-SAMANTHA

**Status:** **HOLD** · blocked on [`WO-PR-CI-LIVE-PROVE-SPLIT`](WO-PR-CI-LIVE-PROVE-SPLIT.md) **DONE** (landed + proven in Nebuspace/tw2002-aiclient) · then **orchestrator-owned** · **Max-gated push** to Claude_Samantha  
**Posted:** 2026-07-26 · Max ask: on the heels of the PR/CI/live-prove protocol, backport the reusable kernel to the framework  
**Depends:** `WO-PR-CI-LIVE-PROVE-SPLIT` Accept (Phase 0–1 proven in-instance)  
**Target repo:** `~/github/Claude_Samantha/` (generic Samantha coordinator/orchestrator/implementer framework)  
**Seat:** orchestrator (hub) — may dispatch Monk for file edits; **push to Claude_Samantha requires Max GO** (shared public framework)

---

## Goal

Backport the **framework-generic** coordination + return-path changes forged in Nebuspace/tw2002 into **Claude_Samantha**, so future Samantha deployments inherit them without re-deriving from this instance.

**Test (from Nebuspace CLAUDE.md):** *"would any orchestrator/implementer project want this?"* → yes ⇒ backport. Strip instance names (tw2002, TWGS hosts, heimdall, seat ids) — keep the principle.

---

## Source of truth (instance → extract kernel)

Primary: `tw2002-aiclient/workorders/WO-PR-CI-LIVE-PROVE-SPLIT.md` (rulings A–K)  
Also: Nebuspace `.cursor/rules/workorders-required.mdc` (hub branch seed + serial dispatch + hub merge + hub `live-prove` Check Run)

### Kernel to backport (keep)

| Kernel | Instance wording → framework wording |
|---|---|
| Hub creates work branch | Orchestrator creates `wo/<ID>` (or project-conventional prefix) from main before HANDOFF |
| Hub seeds WO file on that branch | `workorders/WO-<ID>.md` committed on the branch **before** HANDOFF |
| PR encapsulates WO + code | Return path is a PR containing both; not silent tip-push to main |
| Hub merges | Orchestrator merges after required checks; implementer does not self-merge |
| Midstream targeted tests | Implementers run narrow tests only; full suite on CI |
| Offline CI on PR | GitHub Actions (or project CI) runs full offline suite on PRs |
| Live/integration segregation | Project-defined pytest mark (instance: `live_login`) excluded from default CI |
| Default live prove = hub machine | Orchestrator runs live/integration Accept on its machine at merge time |
| Hard `live-prove` gate | Required check; **only orchestrator** posts success via Check Run API after live prove (or explicit docs `n/a`) — not human rubber-stamp Environment, not auto-green job |
| Serial HANDOFF | No next HANDOFF to a seat until prior return PR required checks pass |
| Reconcile before resume | After a pace-down/restart HOLD: land outstanding work on main before new HANDOFFs |
| Secrets for optional cloud live | Credentials in CI secrets / secret store — never committed |

### Strip / do not backport as-is

- TWGS hostnames, sacrificial profile names, `TW_LIVE_BANK_*` secret name literals (document as *examples*).
- tw2002-specific file paths (`session/login.py`, ensure matrix).
- Nebuspace-only audit paths.
- Assumption that every project uses pytest-xdist `-n auto` (say “full offline suite as configured”).
- Force-adopting GitHub if a deployment uses GitLab — phrase as “PR + required status checks on the host forge.”

---

## Likely edit surfaces in Claude_Samantha

Confirm against tip at execute time; expected:

- `CLAUDE.md` — orchestrator/implementer return path, HANDOFF prerequisites, serial dispatch, merge ritual  
- `.samantha/references/coordination-protocol/` — README and/or WORK-ORDER-template / MAILBOX notes  
- `.samantha/specs/samantha-prime-spec.md` (or equivalent) if return-path is normative there  
- `.samantha/DEPLOYMENTS.md` — note Nebuspace as donor instance + date  
- Optional: framework `.cursor/rules/` or documented rule recipe for “WO on hub-created branch”  
- Optional: template workflow stub under `references/` or `templates/` for `suite` + hub-posted `live-prove` (not a copy of tw2002 secrets)

**Do not** invent product CI for Claude_Samantha itself unless the framework repo already runs tests that way — prefer protocol docs + optional template.

---

## Ordering

```
WO-PR-CI-LIVE-PROVE-SPLIT (Nebuspace) DONE
        │
        ▼
WO-BACKPORT-PR-CI-COORD-TO-CLAUDE-SAMANTHA  (this WO)
        │  draft PR on Claude_Samantha
        ▼
Max GO → merge/push framework
        │
        ▼
Update Nebuspace audit/QUEUE.md backport queue + Claude_Samantha DEPLOYMENTS.md
```

---

## Accept

1. Claude_Samantha documents the kernel (branch seed · PR encapsulation · hub merge · midstream targeted · CI offline · live mark excluded from default CI · hub-posted live-prove check · serial HANDOFF · reconcile-before-resume) **without** tw2002-only nouns.
2. Cross-links to Nebuspace donor WO / date for provenance.
3. `DEPLOYMENTS.md` (or equivalent) notes the backport.
4. Nebuspace `audit/QUEUE.md` backport queue row marked done / SHA.
5. **No push to Claude_Samantha `main` without Max explicit GO** for that push.
6. Diff review: zero live credentials; zero Nebuspace machine-local paths.

## Proof

```text
rg -n 'hub-created|live-prove|serial HANDOFF|workorders/WO' ~/github/Claude_Samantha/CLAUDE.md ~/github/Claude_Samantha/.samantha/references/coordination-protocol/
# PR URL on Claude_Samantha + Max GO recorded on coord before merge
```

## Out of bounds

- Pushing framework changes without Max GO.
- Copy-pasting tw2002 workflow YAML wholesale (adapt to templates or prose).
- Changing Nebuspace instance protocol again in this WO (instance already owned by WO-PR-CI-LIVE-PROVE-SPLIT).
- Backporting other pending QUEUE items in the same tip unless Max expands scope.

## Refs

- Donor: `tw2002-aiclient/workorders/WO-PR-CI-LIVE-PROVE-SPLIT.md`
- Nebuspace `CLAUDE.md` § Canon stewardship / framework backport discipline (Max 2026-07-18)
- `audit/QUEUE.md` ⏳ BACKPORT QUEUE
- `Claude_Samantha/.samantha/DEPLOYMENTS.md`
