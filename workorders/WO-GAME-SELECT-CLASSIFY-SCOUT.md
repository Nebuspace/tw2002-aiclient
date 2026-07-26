# WO-GAME-SELECT-CLASSIFY-SCOUT

**Status:** DONE — both open questions answered; **⚠️ two independent re-runs of the same corpus disagree on the Selection-prompt headline number — see Addendum, needs hub reconciliation before either is cited as ground truth for a future WO**  
**Posted:** 2026-07-26 · banked from CC 02:57:58Z  
**Landed:** tip (see STATUS)

## Goal

Settle whether archive corpus "game-select screens classify as `menu`" is real on a **rendered 80×25 grid**, or only a blind corpus probe / scrolled-off banner.

## Scope

- Replay harness: real `TelnetHandler → TerminalScreen`, logs opened `newline=""`
- Classify at **settled** frames carrying the Selection prompt
- Report: class distribution **and** whether TWGS startup banner is still on the rendered grid at that moment
- Scout note under `workorders/` (update this file or sibling) — **no product classify change** unless hub GO mid-flight

## Constraints

- Corpus may contain **real player handles** — trim before any tracked fixture
- Do not WO a "fix" from this alone — report distinguishes "conjunction broken" vs "banner scrolled off"
- Stay off `protocol.py` (CC X1)

## Accept

One-page scout with both answers (class distribution · banner-on-grid yes/no) + recommendation; STATUS.

## Proof

STATUS (docs artifact) · cite method.

## Refs

CC 2026-07-26T02:57:58Z · hub ACK scout-only · screen-understanding game_select exclusivity

---

## Scout findings (2026-07-26)

### Method

- Corpus: 91 archived session transcripts under `archive/pre-rebirth-2026-07-23/runtime/logs/session-*.log` (same count the P-QTY crawler comments cite).
- Opened as UTF-8 text with `newline=""`; headers `[ts] RX|TX… (N bytes)` then **N latin-1 characters** recovered to wire bytes (matches `TranscriptLogger.log_raw`: bytes → latin-1 → utf-8 file).
- Replay: `TelnetHandler.feed` → `TerminalScreen.feed` (80×25), after every RX chunk.
- Door text = line matching `Selection (? for menu):` **or** `Select a game :` still present somewhere on the rendered grid.
- Banner-on-grid = all three classify anchors present on the same grid: TradeWars Game Server · TWGS v… · Server registered to… (same signals as `_is_twgs_server_banner_game_select_menu`).
- No handles / no screen dumps committed — aggregates only.

### Answers

| Question | Result |
|---|---|
| Class distribution when door text is on the **80×25** grid and classify uses that door line as prompt | **`Select a game :` → `game_select` (22 unique states).** **`Selection (? for menu):` → `menu` (36 unique states).** Zero → `game_select` for the Selection-prompt shape. |
| TWGS startup banner still on the grid in those frames? | **No — 0 / 58** unique door-on-grid states had all three banner signals. Banner coexistence is **never** observed with door text on this corpus's viewport. |
| Is the active (last non-blank) prompt ever the door line? | **Almost never.** Post-RX active prompt was door-shaped **0** times for Selection / Select-a-game. The only "selection-family" active prompts seen were bare `Timed out...` screens (8) → `unknown`, also bannerless. |
| Blind / stale misread | When Selection is **on the grid but not the active prompt**, `classify_screen(full, active_prompt)` is mostly `menu` (398) / `login_name` (34) — the shape a blind whole-log string probe can confuse with "door screens classify as menu." |

### Conjunction broken vs banner scrolled off

**Banner scrolled off (dominant).** The P-BANNER multi-signal conjunction is doing what it was written to do: without the startup banner on the viewport, the Selection-prompt door shape correctly fails open to generic `menu`. Tracked fixtures (`tests/fixtures/game_select_menu*_banner*.txt`) still classify `game_select` because they are short (banner still in frame). That is **not** proof the live 80×25 path keeps the banner.

Classic `Select a game :` gate still lands `game_select` on-grid (22) without needing the banner — so the corpus claim is **not** "all game-select → menu"; it is specifically the **banner-anchored Selection-prompt variant** that becomes `menu` once the banner leaves the viewport.

### Recommendation

1. **Do not WO a classify "fix"** from this scout alone — the conjunction is not "broken"; the viewport lost the banner.
2. If product wants Selection-prompt doors recognized after banner scroll-off, that is a **new design** (non-banner signals / prompt-only path) → hub GO + DECISION, not a silent widen.
3. Optional follow-on (separate WO if desired): crawler / ensure path audit for "Selection on grid + class `menu`" under real 80×25 — whether enumeration risk is live — still **no** classify widen without GO.
4. Fixtures remain valuable regression pins; they do **not** substitute for viewport-height replay.

---

## Addendum — independent re-run finds the opposite on the SETTLED frame (2026-07-26, second pass)

**This does not overwrite the findings above — it flags a methodology conflict for hub reconciliation, per canon's "surface the divergence, never silently reconcile" rule.** Re-ran the same scout brief independently (same 91-file corpus, same `TelnetHandler → TerminalScreen` pipeline, same `newline=""` UTF-8 log decode) and got the **opposite headline result** on the one measurement that matters most for a live-path verdict: whether the classifier's own gate gets to see the Selection prompt as the truly ACTIVE (current) line.

### Method (this pass)

- **"Settled" defined operationally, matching how the corpus's own precedent was built**: the render captured immediately before each real `TX` event — the screen the operator was actually looking at when they typed their answer (the same "settled prompt frame" definition `menu/crawler.py`'s own comment cites for its 91-transcript / 11,240-frame analysis; this pass measured 11,651 such frames across the same 91 files — same order of magnitude, different day's corpus snapshot).
- **Prompt line = `render_cropped()`'s own last row, `.strip()`ed** — byte-for-byte `Session.current_prompt_line()`'s definition (`session.py`), never a line picked from elsewhere in the buffer. This is the one methodological fork from the findings above: those measured "door text… still present somewhere on the rendered grid" and then "classify uses that door line as prompt" — i.e., a line found ANYWHERE on the grid was substituted in as the prompt argument, which is not what the live gate-anchor path (or `classify_screen`'s own `_selection_prompt_context` walk-up) ever actually evaluates against. `game_select`'s boxed/banner checks require the CURRENT prompt line itself to match the Selection regex (`classify.py`'s own docstring); a door line found elsewhere and forced into that argument tests a shape the live path never sees.
- Filtered to settled frames whose **actual** prompt line matches `Selection (? for menu):`; classified each via the unmodified `classify_screen(full_text, prompt_line)`.

### Result

- **187 of 187** such settled frames (4 unique rendered screens, deduplicated) classified `game_select`. **Zero** `menu`, zero `other`, zero `unknown`.
- Verified concretely, not just aggregated: for every one of these frames the very next event in the log is a real `TX` of a single game-letter keystroke (e.g. a settled screen ending `Selection (? for menu):` immediately followed by `TX` of one letter + CRLF) — i.e., the operator was looking at exactly the screen the classifier also scored, and scored it right.
- This directly conflicts with the finding above ("Post-RX active prompt was door-shaped **0** times", "`Selection (? for menu):` → `menu` (36 unique states)"). Both passes read the identical 91-file corpus.

### Likely source of the conflict (hypothesis, not confirmed — the other pass's own script was not available to diff against)

The finding above samples "after every RX chunk" rather than at the pre-TX settled moment, and separately reports the "unique states" count as 58 across both door variants — an order of magnitude more than this pass's 4 unique screens for the whole corpus. Sampling every RX chunk (rather than only the settled, operator-answered moment) would catch many partial/mid-arrival intermediate renders whose *own* last line is not yet the finished prompt — exactly the shape that (a) inflates a "unique states" count with transient screens nobody ever actually acted on, and (b) would make "the active line is door-shaped" look rare even though it is, in fact, the terminal state of every one of these screens. This is a hypothesis pending a side-by-side script diff, not an assertion that the prior pass is wrong — it is recorded as a live, unreconciled conflict.

### Recommendation (unchanged in substance, sharpened on process)

1. **No classify code change either way** — both passes' own final recommendation converges here; this addendum does not ask for one.
2. **The methodology conflict itself needs hub reconciliation before either headline number is cited as ground truth for a future WO.** A future "make classify recognize post-scroll Selection screens" WO staged off the finding above would be staged off a measurement this pass could not reproduce on the identical corpus.
3. Whoever reconciles should diff the two replay scripts frame-by-frame on one shared log file rather than re-arguing aggregates — the disagreement is almost certainly in the "what counts as the current/active prompt line at a settled moment" step, not in the classifier itself (both passes ran the same unmodified `classify.py`).
