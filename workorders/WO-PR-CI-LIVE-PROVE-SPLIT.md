# WO-PR-CI-LIVE-PROVE-SPLIT

**Status:** **DONE** · merged PR #1 → `main` @ `91a0561` · suite green · `live-prove` n/a (CI-infra, Commit Status) · `wo/PR-CI-LIVE-PROVE-SPLIT` deleted via cleanup ritual  

**Posted:** 2026-07-26 · Max rulings: PR return · GHA suite · secrets bank · laptop-default live · `live_login` · reconcile-before-resume · hub branch+WO seed · hub merge · **live-prove required check** · **no new HANDOFF until prior PR checks pass**  
**Supersedes:** [`WO-CI-GITHUB-ACTIONS-SUITE`](WO-CI-GITHUB-ACTIONS-SUITE.md) (folded here)  
**Repo:** `Nebuspace/tw2002-aiclient` (**PUBLIC**)  
**Scope:** project protocol + CI + merge gate for **this** product first; framework backport is a **separate** WO — [`WO-BACKPORT-PR-CI-COORD-TO-CLAUDE-SAMANTHA`](WO-BACKPORT-PR-CI-COORD-TO-CLAUDE-SAMANTHA.md) — on the heels of this one (Max-gated Claude_Samantha push).

---

## Goal

Change how work returns to the hub so that:

0. **Before any implementer resumes after restart:** reconcile, commit, and push **all outstanding** in-tree work to `main` (clean shared tip — no orphan HOLD WOs / fence WIP / docs sitting only on hub disk).
1. **Orchestrator creates the implementer branch**, commits the `workorders/WO-*.md` into that branch, then HANDOFFs — the seat never invents the branch or the WO file.
2. **Implementer builds only on that hub-created branch** and pushes commits there; midstream proof = targeted pytest only.
3. **PR encapsulates the entirety of the work:** WO markdown **and** implemented code (one reviewable unit).
4. **Orchestrator merges the PR to `main`** after GitHub Actions (offline suite) is green **and** any required laptop live prove — seats do not self-merge.
5. **Orchestrator does not hand out the next WO** to a seat until that seat's (or the shared pipeline's) **previous PR has passed required checks** — deliberate serialism; less laptop melt, acceptable implementer idle.
6. **Full offline suite** runs on **GitHub Actions** against the PR (and on `main` after merge).
7. Tests that **live-login to a real TWGS server** are segregated under `live_login` so hub runs them on the laptop and GHA excludes them by default.
8. **Live TWGS capacity** via Actions secrets exists (optional) — **default** live prove remains orchestrator laptop at merge; merge is blocked until a **`live-prove` certify check** is green (Environment approval and/or hub-posted status after laptop run).

No real passwords in git history. Public Actions logs never print secret values.

---

## Max rulings captured (this WO)

| # | Ruling |
|---|---|
| A | Implementer deliverable = **PR** we can run the full suite against. |
| B | Midstream = **targeted tests**; full suite = **PR GitHub Action**. |
| C | **Pre-populate GitHub secrets** with credentials; point the live job at whichever bank entry is in use — **not** commit passwords. |
| D | Need **some** GHA capacity for live real servers. |
| E | **Default** for that class of test: still run from **Max's laptop by the orchestrator** as part of **PR merging**. |
| F | **Label / rename** live-login-to-server tests so they are easy to segregate (orchestrator vs Actions). |
| G | **Reconcile + commit + push all outstanding code to `main` BEFORE any implementer gets back to work** after restart is done. |
| H | **Orchestrator creates the branch** the implementer works from, and **commits the workorders/ Markdown** into that branch before HANDOFF. |
| I | When done, **orchestrator merges the PR to `main`** after Actions complete; the PR contains **WO markdown + implementation** as one encapsulated unit. |
| J | Branch protection requires offline **`suite`** + **`live-prove`**. **`live-prove` turns green only when the orchestrator posts it** after a **multi-server / multi-character** laptop prove (≥3 hosts, NEW+RETURNING — see § What live-prove means); docs/CI-infra may post `n/a` with explicit reason. Not Max click-through; not an auto-green no-op job; not a single-host rubber stamp. |
| K | **No new HANDOFF** until the prior PR for that seat (or the single in-flight PR, if one-at-a-time globally) **has passed required checks** — serial dispatch; idle beats melting the laptop. |

---

## Hard gate — `live-prove` (orchestrator-owned certify)

**Problem:** GitHub cannot see the laptop. **Requirement:** merge to `main` must be impossible until someone who ran the live tests says so — and that someone is the **orchestrator**, not Max.

### What `live-prove` *means* (Max 2026-07-26 — multi-server / multi-character)

In the PR-coordinator rhythm, `live-prove` is **not** “one happy path on the server we always use.” It is a **diversity gate**: prove the change against **live TWGS** across **multiple servers** and **multiple characters**, so we do not silently design for a single banner / menu dialect / game-select shape.

**Default bar (product PRs that touch login · ensure · classify · play · session · reconnect):**

| Axis | Minimum | Notes |
|---|---|---|
| **Servers** | **≥ 3** distinct catalog hosts exercised | Hub picks/rotates. Prefer known-different stall/menu shapes (anet / rogue / micro / xeno / …). |
| **Characters (across the run)** | **≥ 1 NEW** and **≥ 1 RETURNING** *somewhere in the set* | Not “both on every host.” NEW only where registration can succeed; RETURNING only where a credential **already exists**. Untestable cells → list as `SKIP:reason` in the summary (not silent omit). |
| **Depth** | Exercise the WO's Accept path on each exercised host | Ensure-bar: push toward `main_command` where the cell allows. |
| **Evidence** | Summary lists host keys, NEW/RETURNING counts, skips, tip SHA — **no secrets** | Example: `hosts: gone_rogue(N+R), a_net_online(N), micro(SKIP:no-cred) · NEW:2 RETURNING:1 · tip abc1234`. |

**Hub picks the set** — Max’s intent is diversity (not one pet server), not an impossible 3×both matrix.

**When `n/a` is still honest:** docs / protocol / CI-infra / **product PRs that cannot affect live login/classify/ensure** (e.g. TUI dead-terminal CPU guard with offline exit+CPU proof). Summary must say why. **Do not** `n/a` a login/ensure/classify PR because “suite was green.”

**`n/a` vs `NOT-ATTEMPTED` (Max 2026-07-27 — #116):** `n/a` means live is *inapplicable*. `NOT-ATTEMPTED` means live *could* run and was skipped. **Never Accept or post hub `live-prove` as `n/a` when the truth is NOT-ATTEMPTED.** Unverified seat claims of “no TWGS / unreachable” without a probe (inventory · TCP sample · launchers) are **REVISE** — hub pushes back on the outbox; do **not** wait for Max to challenge. Safe halves (transport refusals / attach without arm) are hub GO; turn-spending arm still needs sacrificial Max GO. Cursor always-on: Nebuspace `.cursor/rules/live-prove-pushback.mdc`.

**Unmeetable ≠ lower the principle:** if ensure blockers leave fewer than 3 exercisable hosts, live-prove stays **failure/pending** with that stated — or Max temporarily narrows the floor. Do not invent RETURNING on hosts that never registered.

### Mechanism (hub has access; Max does not need to click)

1. **Ruleset / branch protection** on `main`: required status checks = `suite` (GHA) **and** `live-prove` (hub-posted Check Run or Commit Status).
2. **No workflow may mark `live-prove` success automatically** on every PR (that would be a rubber stamp). Do **not** use a Max-only Environment approval as the primary gate (Max is not running the live tests).
3. After the hub runs the multi-server / multi-character laptop prove (and/or `pytest -m live_login` cells that encode the same bar), the hub posts a check named exactly `live-prove` on the PR head SHA via `scripts/hub-live-prove-check.sh`, with:
   - `success` only if the diversity bar passed (or honest **`n/a`** — body must say why live was skipped),
   - `failure` if any required cell failed,
   - summary text: hosts, NEW/RETURNING counts, tip SHA, command lines — **no secrets**.
4. Example:

```bash
# after multi-server laptop prove on PR head $SHA
./scripts/hub-live-prove-check.sh "$SHA" success \
  "hosts: a_net_online, gone_rogue, microblaster_network · NEW:2 RETURNING:3 · tip ${SHA:0:7}"
```

5. **Hub merge ritual (ordered):** offline `suite` green → **code-scanning sweep** (step 0 below — does not block) → **multi-server live prove** (or honest docs/CI-infra `n/a`) → `scripts/hub-live-prove-check.sh` → `gh pr merge` → **`scripts/hub-wo-merge-cleanup.sh wo/<ID> [worktree…]`**. Never merge if `live-prove` is missing/pending/red. Never leave a merged `wo/*` branch on origin.

### Code-scanning sweep (step 0 — lagging indicator, not a gate)

GitHub code scanning alerts usually appear on **`main` after merge**, with scan lag. Waiting for them post-merge stalls the loop; checking the *current* PR's alerts pre-merge is usually empty. Instead:

1. At the **start** of each hub merge ritual (suite already green on the PR about to merge), run `scripts/hub-code-scanning-sweep.sh`.
2. **New** open alerts vs the last-seen set → treat as coming from **recently merged** work (~PR N−1 / N−2), **not** from the PR you are about to merge.
3. Bank remediation WO(s) / HANDOFF when a seat is free. **Do not block** the current merge.
4. State file (outside the public repo): orchestrator `.samantha/coord/code-scanning-seen.json` via `CODE_SCANNING_SEEN_FILE` or `NEBUSPACE_ROOT` (see script header).

Anti-patterns: required-check on alert count; holding merge for CodeQL to finish scanning the tip you just landed; pretending PR alert APIs are the gate unless Max enables true pre-merge alert publication.
6. **Auth:** Max provisions a credential the **orchestrator agent can use** (`gh auth` on the hub machine, or a fine-grained PAT / GitHub App with `checks:write` — **not** committed). Document name-only in the secret-bank map.
7. **Anti-cheat:** CI must not ship a job that always concludes `live-prove` success. Empty summary / single-host-only summary on a product PR is a **failed ritual** even if the API accepts it — hub must not post `success` in that case.

---

## Architecture (three lanes)

```
┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────────┐    ┌─────────────────────────────┐
│ Hub seeds branch     │    │ Midstream (seat)     │    │ PR CI (GitHub Actions)   │    │ Hub merge gate             │
│ wo/<ID> from main    │ →  │ targeted pytest -n0  │ →  │ offline: not live_login  │ →  │ laptop live_login / ensure │
│ commit WO-*.md       │    │ push to same branch  │    │ optional live (labeled)  │    │ hub merges PR → main       │
│ open/update PR +     │    │ STATUS (no self-     │    │                          │    │ PR = WO md + code          │
│ HANDOFF              │    │  merge)              │    │                          │    │                            │
└──────────────────────┘    └──────────────────────┘    └──────────────────────────┘    └─────────────────────────────┘
```

### Lane 1 — Offline suite (always on PR)

- Trigger: `pull_request` → `main` (and `push` to `main`).
- Command: `python -m pytest -m "not live_login"` (inherits `pytest.ini` `-n auto`; **excludes** live-login tests).
- **No network to TWGS.** Fail closed if an unmarked test opens real sockets (pin / audit in this WO).
- PTY/curses against FakeTWGS/local sockets: `xvfb-run` or skip with honest reason — no silent greenwash.
- Cache pip; upload junit + last-failed on red; reasonable timeout.

### Lane 2 — Live TWGS on Actions (capacity, not default)

- **Separate workflow or job**, **not** on every PR by default.
- Arm only when: `workflow_dispatch` **or** PR label e.g. `live-ensure` **or** hub explicitly requests in HANDOFF.
- Selects **only** `@pytest.mark.live_login` (and/or the dedicated live runner script) — never the offline suite job.
- Credentials: **GitHub Actions secrets** only, e.g.:
  - `TW_LIVE_BANK_ROGUE_USER` / `TW_LIVE_BANK_ROGUE_PASS` / host+port+game_letter as needed, **or**
  - one JSON secret `TW_LIVE_BANK` mapping profile keys → fields (prefer structured; never echo).
- Job checks out PR SHA, writes an **ephemeral** isolated `TW_CONFIG_DIR` + secrets file in the runner workspace (never committed), runs a **narrow** live script (`ensure` NEW and/or RETURNING for named hosts), uploads **redacted** artifacts only (no frame dumps with passwords).
- Hard ceiling: sacrificial profiles only; max N hosts / M attempts named in the workflow; fail loud on leak scanners.
- **This lane proves capacity.** It does **not** replace Lane 3 as the default Accept path for live.

### Lane 3 — Orchestrator laptop live prove (DEFAULT at merge)

- After PR offline CI is green + seat STATUS + hub design Accept (cipher/mack when required):
  - Hub runs the **diversity gate**: ≥3 live catalog servers, ≥1 NEW + ≥1 RETURNING characters (hub picks/rotates), exercising the WO Accept path (plus `pytest -m live_login` cells when they encode the same bar). Existing discipline: `--run-dir`, no default-daemon footgun.
  - Results → Accept note / matrix row / `hub-live-prove-check.sh` summary → merge GO.
- Live fails on laptop ⇒ **do not merge** on CI-green alone for ensure-bar / login / play WOs.
- Optional later: hub may *also* arm Lane 2 for a second opinion — never the only gate for M1–M3 until Max re-rules.

---

## Coordination protocol changes (project)

Record in Nebuspace `CLAUDE.md` (tw2002 section) + `.cursor/rules/workorders-required.mdc` + short `💡 PROCESS-NOTE` on `orchestrator.md` for seat ACK (unanimous when both seats up). Framework backport to Claude_Samantha = **optional later**, Max-gated.

### Branch + WO seed lifecycle (rulings H · I) — **hub owns**

```
main (clean tip)
  │
  ├─ hub: git checkout -b wo/<WO-ID>          # hub creates branch — seat does not
  ├─ hub: write workorders/WO-<ID>.md
  ├─ hub: git commit -- workorders/WO-<ID>.md # WO lands on the branch first
  ├─ hub: git push -u origin wo/<WO-ID>
  ├─ hub: gh pr create (or draft) → main      # PR exists early; encapsulates WO from commit 1
  ├─ hub: 🤝 HANDOFF with branch name + PR URL + Accept
  │
  ├─ seat: fetch + worktree/checkout hub branch only
  ├─ seat: implement + targeted pytest -n0
  ├─ seat: push commits to same wo/<WO-ID>    # updates the same PR
  ├─ seat: 📋 STATUS DONE (PR URL + head SHA) — does NOT merge
  │
  ├─ GHA: offline suite on the PR
  ├─ hub: laptop live prove if required
  └─ hub: merge PR → main                     # hub only; WO md + code ship together
```

**Branch naming:** `wo/<WO-ID>` preferred (matches file stem, e.g. `wo/PLAY-GAME-LETTER-AUTOSELECT` or `wo/WO-PLAY-GAME-LETTER-AUTOSELECT` — pick one convention in CLAUDE.md and stick to it). Parallel seats = parallel hub-created branches (disjoint paths as today).

**PR body:** link `workorders/WO-<ID>.md`; state Accept criteria; no secrets.

**Encapsulation rule:** the merged PR **must** contain the WO markdown that authorized the work **and** the implementation. Do not merge code-only PRs that orphan the WO on another branch, and do not leave the WO only on `main` while code lives elsewhere.

### Implementer contract

1. **Never create the work branch or the WO file** — checkout/fetch only the branch named in the HANDOFF.
2. Midstream proof = **targeted** `pytest <paths> -n0` (+ injections for safety WOs). **No full suite** midstream.
3. Push only to the hub-created branch; **do not** push finished product straight to `main`; **do not** self-merge the PR.
4. STATUS cites **PR URL** + head SHA + targeted proof + "full suite = CI"; ask hub for merge.
5. Rebase/update when hub says origin moved; **no** `pull --rebase --autostash` on shared dirty trees; no bare stash (existing Rule 1).
6. After hub merge: prune worktrees; no idle full-suite runs. While waiting for CI / hub merge / next HANDOFF: **stand by** (IDLE-KICK does not invent new product work — queue empty until hub seeds the next branch).

### Hub contract

1. For every implementer HANDOFF: **create branch → commit WO md → push → open/ensure PR → then HANDOFF** (order is load-bearing).
2. **Serial dispatch (ruling K):** do **not** HANDOFF a new WO to a seat while that seat still has an open return PR whose required checks (`suite`, and `live-prove` when applicable) have not passed. Prefer **one in-flight PR per seat**; if both seats share conflicting paths, one global in-flight PR until merge. Idle standing-by under HOLD/pace-down rules is correct — better than full-suite laptop grind.
3. Watch PR CI (offline) — red ⇒ REVISE, not merge.
4. For WOs with live Accept: run Lane 3 on laptop; then **post `live-prove` Check Run** via `gh`/API (success only if live passed; docs-only `n/a` with reason). **Never** Approve/`n/a` dishonestly on ensure-bar WOs. **Never** merge without a green `live-prove` on the head SHA.
5. **Hub merges** the PR to `main` only when required checks are green — seats never merge their own return PRs.
6. Branch protection: require `suite` + `live-prove`; no force-push to `main`. No auto-green `live-prove` workflow.
7. After merge (or PR closed failed): next HANDOFF may fire for that seat (ruling K).
### Accept STATUS shape (new)

```
📋 STATUS DONE [WO-…]
Branch: wo/<WO-ID>   (hub-created)
PR: https://github.com/Nebuspace/tw2002-aiclient/pull/N
Head: <sha>
WO path: workorders/WO-<ID>.md   (present on branch from hub seed commit)
Targeted: pytest … -n0 → green
CI offline: pending | green <url>
Live (hub): n/a | laptop <summary> | Actions live <url> (only if labeled)
Merge: awaiting orchestrator
```
---

## Secrets bank (Max ops + hub doc)

| Hub action | Detail |
|---|---|
| Create secrets in repo Settings | Named bank entries for sacrificial profiles only (rogue/micro/anet/… as Max chooses) |
| Document mapping (no values) | `canon/` or `workorders/LIVE-SECRET-BANK.md` — **names only**, which host each secret feeds |
| Rotation | Max rotates; hub never writes secret values into coord files or public docs |
| Pointing | Live job / laptop script selects profile key → reads from env injected by Actions or local keychain/`TW_CONFIG_DIR` |

**Forbidden:** committing `secrets.json` with live passwords; printing secrets in Actions logs; using Max's primary non-sacrificial account in CI.

---

## Pytest segregation — `live_login` (ruling F)

**Canonical mark (required for any test that logs into a real TWGS server):**

```python
@pytest.mark.live_login
def test_…():
    ...
```

| Surface | Rule |
|---|---|
| **Mark name** | `live_login` — not bare `live` (too vague; collides with “live daemon sock” / spectate PTY language already in `pytest.ini` comments). |
| **Register** | `pytest.ini` `markers =` one-liner: `live_login: requires real TWGS login + credentials (orchestrator laptop default; excluded from GHA offline suite)`. |
| **Filename convention (preferred for new files)** | `tests/test_*_live_login.py` so `rg live_login` / path globs find them without opening every file. Existing tests: **mark first**, rename optional in same tip if cheap. |
| **GHA offline (`suite.yml`)** | `pytest -m "not live_login"` — must never collect/run live-login cases. |
| **Orchestrator laptop (default)** | `pytest -m live_login` and/or matrix/`ensure` scripts that are the real Accept path. |
| **GHA live (optional capacity)** | Same `-m live_login` (or dedicated runner) only when labeled / dispatched. |
| **Unmarked tests** | Must be offline-safe (FakeTWGS / unit). Add a pin or audit script in this WO that fails if an unmarked test module imports a “must hit WAN” helper without the mark. |

**Not `live_login`:** FakeTWGS, unit classify/login automaton, PTY against local fakes, “daemon sock exists” spectate skips — keep those in the offline suite (or existing skip logic).

Ignored rehab files stay ignored until intentionally un-ignored.

---

## Phase 0 — Reconcile to `main` BEFORE seats resume (ruling G)

**Hard gate:** after Max’s local restart is done and the pace-down HOLD is ready to lift, **hub reconciles and lands everything outstanding onto `origin/main` before any 🤝 HANDOFF / IDLE-KICK work resumes.**

### In scope for the reconcile

1. **Hub-authored untracked / dirty tree** — at minimum the banked HOLD WOs and stamps currently only on disk (as of authoring: `WO-PR-CI-LIVE-PROVE-SPLIT`, `WO-CI-GITHUB-ACTIONS-SUITE` supersede, `WO-PLAY-*`, `WO-EXPLORE-SECTOR-FRONTIER`, and any other uncommitted hub docs). Commit with explicit paths (Rule 1 — never `git add -A`).
2. **CC in-flight fence tip** — if `WO-CONTROL-LOCK-AUTOLOOP-FENCE` is Accept-ready (cipher+mack clear): land via scoped commit/PR-or-push per then-current return path; if still open: either finish under HOLD **or** park on a named branch/`preserve/` and record SHA on coord — **do not** leave the only copy in an unpushed worktree while seats resume.
3. **Cursor leftovers** — prune or push any accepted-but-unpruned worktrees; no silent dirty shared tree.
4. **Fetch + verify** — `origin/main` contains the reconcile tip; both seats `git fetch` before next HANDOFF.
5. **Coord HEADS-UP** — hub posts `✅ RECONCILE-TO-MAIN DONE` with tip SHA, then lifts pace-down / posts next HANDOFF. Until that post, seats stay STANDING DOWN.

### Out of scope for Phase 0

- Implementing the full CI workflows (Phase 1+) — reconcile can land **WO files + fence product** first; workflows may follow in the same hub burst or the next tip.
- Live matrix prove (that stays Lane 3 when ensure WOs run).

---

## Multi-seat / PR pitfalls (call out in protocol)

- Two PRs touching same files → hub sequences merge; second rebases.
- Fence / login / classify lanes stay file-disjoint as today.
- Hot-deploy Rule 6 unchanged — PR merge ≠ deploy window by itself.
- Public PR descriptions: no credentials, no coord chatter with secrets.

---

## Implementation checklist (hub after restart · HOLD lift)

### Phase 0 — before any implementer resumes

0. Inventory dirty/untracked + in-flight worktrees/branches (CC fence, Cursor prune, hub WO files).
1. Commit + push outstanding hub artifacts to `main` (explicit paths).
2. Land or preserve+record CC fence; Cursor prune.
3. Verify `origin/main`; post `✅ RECONCILE-TO-MAIN DONE` + tip SHA; **then** allow seat work.

### Phase 1 — protocol + segregation + CI

4. **Docs / protocol** — Nebuspace CLAUDE.md tw2002: hub creates `wo/<ID>` · seeds WO md · opens PR · HANDOFF; seat builds on that branch only; **hub merges** after checks; **no next HANDOFF until prior PR checks pass** (ruling K). PROCESS-NOTE; seat ACK. Update `.cursor/rules/workorders-required.mdc` for branch seed + serial dispatch.  
5. **`live_login` mark** — `pytest.ini` + migrate/mark existing live-login tests; prefer `test_*_live_login.py` for new files; pin unmarked ≠ WAN.  
6. **`.github/workflows/suite.yml`** — PR + main; `pytest -m "not live_login"`; xvfb as needed; artifacts.  
7. **`live-prove` gate** — ruleset requires check name `live-prove`. Hub posts Check Run via `gh` after laptop live (not Max Environment click; not auto-green job). Optional separate `live-ensure.yml` for labeled cloud live capacity.  
8. **Branch protection / ruleset** — require checks `suite` + `live-prove` on `main`; Max enables UI + grants hub `gh` token with `checks:write`.  
9. **Secret bank** — Max populates live TWGS secrets; hub writes name-only map doc (include hub checks token name-only).  
10. **Pilot** — hub seeds branch+WO, PR, `suite` green, hub runs or skips live with honest `live-prove` post, hub merges — proves cannot merge without the check.  
11. **Stamp** this WO DONE + keep supersede banner on `WO-CI-GITHUB-ACTIONS-SUITE`.
12. **Unblock follow-on:** [`WO-BACKPORT-PR-CI-COORD-TO-CLAUDE-SAMANTHA`](WO-BACKPORT-PR-CI-COORD-TO-CLAUDE-SAMANTHA.md) (HOLD until this Accept; then hub drafts framework PR; Max GO to push).

Cursor may draft Phase 1 workflows under hub HANDOFF **after** Phase 0; Max does secrets + branch protection UI; hub owns branch-seed ritual, Accept, laptop live prove, and **every merge to main**.

---

## Accept

1. **Phase 0:** `origin/main` holds all outstanding reconcile work; coord `RECONCILE-TO-MAIN DONE` posted **before** the next implementer HANDOFF.
2. Protocol docs state: **hub creates branch + commits WO md + opens PR + merges**; seat never creates the work branch or merges the return PR; **hub does not HANDOFF the next WO until the prior PR's required checks have passed** (ruling K).
3. Offline suite workflow green on a PR and on `main` using `-m "not live_login"`.
4. Ruleset requires **`suite` + `live-prove`**; **`live-prove` is only set green by the orchestrator** after laptop live tests (or explicit docs `n/a`) via Check Run API — pilot proves merge is blocked without it.
5. Every test that live-logs into TWGS carries `@pytest.mark.live_login` (and new files follow `*_live_login.py` where practical); unmarked suite does not require WAN.
6. Live cloud workflow exists, secrets-driven, **manual/label-armed only**; one dry-run STATUS (hub or Max) without leaking secrets.
7. Pilot (or first real) PR contains **both** `workorders/WO-*.md` (from hub seed commit) **and** implementation commits; merged by hub after required checks green.
8. No passwords in git; secret-scan clean on the tip.

## Proof

```text
# Phase 0
git -C tw2002-aiclient fetch origin && git -C tw2002-aiclient status -sb   # clean vs origin/main
# hub seed ritual (pilot)
git log --oneline main..wo/<ID>   # first commit includes workorders/WO-*.md
gh pr view <N> --json files       # WO md + code paths both present
# offline CI
gh run list --workflow suite.yml
rg -n 'live_login' pytest.ini tests/
pytest -m live_login --collect-only
pytest -m "not live_login" --collect-only
# protocol
rg -n 'hub creates|wo/<|live_login|RECONCILE-TO-MAIN' CLAUDE.md .cursor/rules/workorders-required.mdc workorders/WO-PR-CI-LIVE-PROVE-SPLIT.md
```

## Out of bounds

- Committing live credentials.
- Making Actions live the **default** merge gate (contradicts Max ruling E).
- Replacing cipher/mack / design Accept with CI green alone.
- Resuming implementer HANDOFFs before Phase 0 reconcile lands on `origin/main`.
- Seat-created work branches or seat self-merge of return PRs (contradicts H · I).
- Framework-wide Samantha default (unless Max later GO's backport).

## Refs

- Max session 2026-07-26 (PR return · secrets · laptop live · `live_login` · reconcile-before-resume · **hub branch + WO seed + hub merge**)
- `pytest.ini` (`-n auto`) · `WO-SUITE-PARALLEL-FLAKE` · `WO-TEST-PARALLEL-DEFAULT`
- `.cursor/rules/workorders-required.mdc`
- Sprint plan `.samantha/plans/ensure-game-explore-sprint-20260726.md`
- Ensure bar / live matrix discipline (isolated `--run-dir`)
