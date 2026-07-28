# WO-HUB-CLEANUP-SEAT-REFUSE

**Goal:** `scripts/hub-wo-merge-cleanup.sh` reaps **only** hub-owned worktrees (allowlist). Everything else is REFUSE (explicit argv) or SKIP (auto-discover).

**Accept:**
1. Allowlist only: basename `hub-*` under `.worktrees/` or legacy `/private/tmp/hub-*` (and `/tmp/hub-*`).
2. Explicit non-hub path → exit non-zero REFUSE.
3. Auto-discover non-hub → SKIP (do not remove).
4. Falsify both halves: fabricated `cc-scratch` refuses; fabricated `hub-scratch` reaps (then restore).
5. live-prove `n/a`.

**Refs:** CC 21:05:04Z allowlist design · incidents after #195/#197.

6. Mixed argv (`hub-a` + `cc-x` + `hub-b`) refuses **before** any remove (all-or-nothing).

---

## Falsification (2026-07-28, `impl-claudecode-aiclient`)

`scripts/test_hub_cleanup_refuse.sh` — six cases, all driving the **real** script
end-to-end.

**Why end-to-end and not a lifted predicate.** A test that `sed`-extracts
`is_hub_owned_wt` and calls it directly proves the predicate classifies correctly and
says nothing at all about `reap_worktrees` still calling it. The gate's entire value is
the wire, so the wire is what the test exercises.

**Why a fixture repo.** `hub-wo-merge-cleanup.sh` computes `REPO_ROOT` from its own
location and then `cd`s there before running `git push origin --delete` and
`git branch -D`. Invoking the tree's own copy would exercise this gate against the live
repository and its GitHub remote — so each case builds a throwaway repo (bare `origin`,
branch already merged into `main` so the landing gate passes) and copies the script in
fresh, which also means the copy can never drift from the file under test.

| case | pins |
|---|---|
| **C0** control | hub-owned argv reaps, and a `Removing worktree` line is observable at all |
| **C1** | explicit `cc-scratch` → exit 2, **and the directory is still there afterwards** |
| **C2** | mixed argv → exit 2, **all three worktrees intact**, no removal attempted |
| **C3** | auto-discover on a seat lane → `SKIP`, directory survives |
| **C4** control | auto-discover **does** reap a `hub-*` lane |
| **C5** | the broad basename clause is deliberate, and pinned |

C1 and C2 assert *why* the script refused (`not hub-owned` in stderr), not merely that
it exited 2 — a refusal for an unrelated reason (not-merged, unknown branch) exits 2 too
and would otherwise satisfy the case.

### Mutation matrix — each pin injected, targeted red observed, restore md5-identical

| mutation of the script under test | cases that went red |
|---|---|
| **M1** allowlist accepts everything (the pre-fix behaviour) | C1, C2, C3 |
| **M2** drop the all-or-nothing pre-validate loop | **C2 only** |
| **M3** still print `SKIP`, but reap anyway | **C3 only** |
| **M4** neuter `git worktree remove` entirely | C0, C4, C5 — the controls |

M2 and M3 are the useful ones: each reddens exactly one case, so the two halves of the
fix are pinned independently rather than by one broad test that would survive either
regression. **M4 is what makes the rest mean anything** — it proves C1/C2/C3's
"directory survives" assertions are not passing for free on a script that never removes
anything.

### One correction shipped with it

The REFUSE message read *"need basename `hub-*` **under `.worktrees/`** or
`/private/tmp/hub-*`"*, a location constraint the predicate does not apply — clause 1
accepts a `hub-*` basename anywhere. Message corrected to match the predicate.

The predicate itself is **unchanged, deliberately** (hub ruling 2026-07-28): the broad
clause is load-bearing, because a relative path like `.worktrees/hub-x` does **not**
match `*/.worktrees/hub-*`, which requires a component before the slash. Narrowing it
without normalising the path first would reject the invocation form a human is most
likely to type. `realpath` normalisation is banked as a follow-on, not done here. C5 is
what will notice if message and predicate drift apart again.

### Proof

- `./scripts/test_hub_cleanup_refuse.sh` → `OK hub-cleanup ownership-gate pins (C0-C5)`, exit 0.
- Mutation matrix above; script restored md5-identical after each, baseline re-run green.
- Product suite unaffected (shell-only change) — run and recorded in STATUS.
- Live: `n/a` — no daemon, no TWGS, no send path.
