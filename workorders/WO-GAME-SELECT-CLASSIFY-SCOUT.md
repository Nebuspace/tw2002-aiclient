# WO-GAME-SELECT-CLASSIFY-SCOUT

**Status:** DONE  
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
