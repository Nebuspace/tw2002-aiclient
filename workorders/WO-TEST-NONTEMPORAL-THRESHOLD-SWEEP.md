# WO-TEST-NONTEMPORAL-THRESHOLD-SWEEP

**Goal:** Finish the non-temporal half of the budget-window audit: find count/size/ratio/retry thresholds whose **measured quantity is wider than the name/message claims** (cardinality-for-identity, vacuous floors, etc.).

**Context:** Temporal axis checked clean (#185). One measured non-temporal hit already fixed (#186 badge `len > 10`). CC stopped at first hit rather than expanding GO'd scope — this WO is the rest of that pass.

**Deliverable:** Findings with evidence per site (measure what the control can/cannot catch). Bank fix WOs for real defects; record checked-clean sites. **No product code** in this WO unless a one-line test fix is obviously Accept-complete — prefer bank-then-HANDOFF for fixes.

**Accept:**
1. Sweep report (STATUS or `workorders/` appendix) covering non-temporal thresholds in `tests/`.
2. Each suspect: what it measures, what the message claims, what a realistic silent miss looks like, disposition (KEEP / BANK-FIX / FIXED-inline if trivial).
3. live-prove `n/a`.

**Refs:** CC 19:28:37Z / 19:32:59Z / 19:47:13Z · #186 exemplar.

---

## Findings — sweep report (impl-claudecode-aiclient, 2026-07-28)

### Population

AST enumeration over `tests/` (207 `test_*.py` parsed, 0 syntax failures):

| | count |
|---|---|
| non-temporal numeric-threshold asserts | **827** |
| …of which inequality bounds (the slack-prone family) | **83** |
| …of which equality pins (cannot be vacuous this way) | 744 |
| non-temporal **floors** measured individually | **57** |

Wall-clock / CPU sites are excluded here — that axis is #185's, and its 27 excluded
rows were enumerated and eyeballed rather than assumed (26 genuine `elapsed`; 1,
`test_loop_player.py:1014 CREDITS_STALE_MS > 0`, was misfiled by the units token and
pulled back into scope — it is a constant-sanity pin, KEEP).

### Method, and why the numbers are trustworthy

A floor cannot be judged from its constant: `>= 5` is tight when the true value is 5
and vacuous when it is 500. So each of the 57 floors was **mutated to an unreachable
bound (1e9) on a throwaway copy of the tree, its own test run in isolation, and the
real quantity read out of the failure** pytest's assertion rewriting prints. Every file
was restored and **md5-verified byte-identical**; the lane itself was never mutated.

Two instrument defects were found and fixed *before* the numbers were believed. Both
would have produced a confident, wrong report:

1. The first exclusion pass matched the **substring** `sec`, which matches **`sector`** —
   the most common noun in this repo. Token-boundary matching surfaced **84 further
   asserts (743 → 827)**. The clean-looking first run was hiding work.
2. Consecutive mutations of the same file collided with pytest's `(size, mtime)`
   bytecode / assertion-rewrite cache, so a run could execute the *previous* site's
   rewritten module. This reported **5 live asserts as "never executes"**. Purging
   `__pycache__` + `.pytest_cache` per run and setting `PYTHONDONTWRITEBYTECODE`
   **flipped 13 verdicts**. Post-fix there are **zero dead asserts** — the five were an
   artefact of my harness, not defects in the suite.

One site remains unmeasured and is declared, not hidden: `test_loops_store.py:444`
(`all(row["steps"] > 0 …)`) **skips** in a worktree — *"archived store not present in
this tree"*. It is unmeasured here, not clean here.

### Findings

**F1 — `tests/test_status_vocabulary_guard.py:169` · BANK-FIX (low)**
`assert len(emitted_keys()) >= 10, "producer scan found suspiciously few keys"`
*Measures* the producer-scan population (**29** today). *Claims* the scan is healthy.
*Silent miss:* dropping each producer file in turn, the worst single-file loss is
`session/protocol.py` (14 keys) which leaves **15 — still above the floor**. **No
single-file producer regression can make this control fire**, including losing the
largest producer outright. Its consumed-side sibling at `:166` is *not* vacuous by the
same measure (dropping `goals.py` leaves 13 vs a floor of 20) **and** carries identity
anchors naming real files — the right pattern already exists in the same file; the
emitted half just never got it.
*Severity is genuinely lower than #186's, because a sibling catches it:* running the
whole file with the producer scan broken, `test_starved_status_keys_match_the_allowlist_exactly`
goes **RED** (the 9 lost keys read as newly starved). The floor is not load-bearing —
it is a redundant weak tripwire, not the only guard.
*Fix to bank:* anchor the emitted side on identity (name `session/protocol.py` and
`world_model.py` among the scanned producers), mirroring `:167`. Do **not** merely
raise the number — that repeats #185's "widening keeps the wrong instrument".

**F2 — `tests/test_watchfeed.py:323` · BANK-FIX (trivial)**
`assert last_count > 0  # actually observed real growth, not a no-op loop`
*Measures* that at least one event arrived (**109** today). *Claims*, in its own
comment, that **growth** was observed. *Silent miss:* a feed delivering exactly one
event and then stalling satisfies `> 0` while the loop above it (monotonic
non-decrease) is trivially satisfied too — the "no-op loop" the comment exists to rule
out passes. *Fix to bank:* compare against the count at loop entry, or require ≥2.

**F3 — `tests/test_cockpit_teachband_pty.py:144` · BANK-FIX**
`assert row.index(band) > 0, "band is hard-left; canon right-aligns it"`
*Measures* that the band is not at column 0 (**index 115** today). *Claims* — in the
message **and** the docstring (*"Canon places the hint band on the control strip,
right-aligned"*) — right-alignment. *Silent miss:* with `FULL_COLS=160` and a 36-char
band, **124 distinct positions pass**, of which about one is right-aligned. A band
moved to **column 1** — hard-left in every practical sense — passes the very assert
whose message is *"band is hard-left"*. *Corroboration:* the non-PTY twin
`test_cockpit_teachband.py:136` already pins both edges with spacing identity
(`idx >= 1 and line[idx-1] == " "` plus the matching right-edge check), so the stronger
pattern exists in the sibling module. *Fix to bank:* assert the band's right edge sits
at the row's right edge (allowing the documented yield to other content), not `> 0`.

**None fixed inline.** Each of the three requires a judgment about the intended
contract — what "right-aligned" means when the band yields to other content, whether
the feed guarantees ≥2 events. A wrong tightening converts a weak test into a flaky
one, which is worse than the weakness.

### Checked clean (recorded, per Deliverable)

**24 of the 57 floors sit at slack 0–1** — the bound equals the measured quantity
(`test_last_known_sector.py:346` 5/5 · `test_menu_crawler.py:1230` 6/6 ·
`test_crawl_driver.py:680` 3/3 · `test_sector_explore.py` 130/198/266 5/5, 131 4/4,
237 2/2 · `test_ensure_spawn_readiness.py:104` 3/3 · `test_conn_toggle.py:446` 2/2 ·
`test_wedged_send_fence.py:96` 1/1 · `test_cli_chains.py:110` 1/1 · others).
That is the signature of bounds chosen *from* the real quantity, and it is the
suite's dominant pattern.

**High-ratio but correct — not defects.** A large actual/bound ratio is only a defect
when the bound is a *population proxy*. Where the bound **is** the requirement, the
ratio is irrelevant:
- `test_cockpit_layout.py:340/341/400/401/472/473` — `x/y/w/h >= 1` means "inside the
  frame, non-degenerate". True at 1, true at 36.
- `test_cockpit_fold.py:358` — `len(result_wide) > 2` distinguishes real output from
  the pane's own two-line empty marker. Exactly 2 is the thing being excluded.
- `test_haggle.py:127/358` — `> 2214` / `> 800` **are** the domain baselines
  (`fair_value = 2214`); `test_analyze.py:69` `>= 2` is the `min_support=2` passed in.
- `test_autoloop.py:414` — `len(samples) > 10, "the poller never actually sampled"`
  (actual ~154k). The bound is *stricter* than its own message ("never" = 0), and the
  next line pins the semantic content (`any(sample is True …)`). Weak as a health
  gauge, but no claim/mechanism mismatch.
- `test_tx_record_honesty.py:166`, `test_server_inventory.py:21`, `test_chains.py:310`
  — `> 0` floors each paired with an identity assert on the following line.

### Scope not covered

Ceilings (`<=`) were enumerated but not individually measured; the failure mode there
is the mirror image (a ceiling too generous to catch growth) and is a smaller family.
`test_loops_store.py:444` is worktree-skipped, as declared above.
