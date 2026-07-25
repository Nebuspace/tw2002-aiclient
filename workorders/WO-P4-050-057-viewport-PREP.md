# WO-P4-050…057 — Game viewport & watch surfaces · PREP

> Status: **PREP** 2026-07-24 · tip `6391bb7` · seat `impl-aiclient-cursor`  
> Phase: 4 · Type: PREP (inventory + tightened Accept/Proof) · Execute: Fable on `impl-claudecode-aiclient` after Accept  
> Canon: `canon/surfaces/trainer-cockpit.md` · `spectate-and-attach.md` · `visual-language.md` · `control-and-escalation.md`  
> Refs: `ULTRACODE-WO-INVENTORY.md` Phase-4 rows · `WO-P2-OPS-VERB-F-PREP.md` · WatchHub tip · F2 HOLD

**No product edited in this WO.** Live-state below is **committed tip `6391bb7`** only.

---

## 0. Strategic framing

- **Phase 3 CLOSED** — panels 034–041 on tip (`6391bb7` LOGS). Play shell chrome is live; **center GAME is still a placeholder string**.
- **Play-critical path:** **050 → 051 → 052 → 053 → 054** (subscribe → empty shell → pyte paint → color parity → disconnect chrome). **055–057** after the viewport paints (spectate mode / attach / detach).
- **Ops ≠ product:** `WatchHub` + daemon `subscribe` + `tw watch` CLI are **LIVE** (P2). Product cockpit must **subscribe as a client** into the play shell — that is **not** shipping `tw spectate` (F2 HOLD). Do not invent an F2 lift.
- **F2 HOLD** — full curses `tw spectate` CLI remains Max-gated. PWO-055 (product spectate *mode* inside cockpit) may overlap F2 conceptually — **flag in execute**: implement as cockpit mode only; do not open the ops `spectate` CLI lane without Max GO.
- **G2–G4 HOLD** unchanged (menu crawler / loops / autoloop).
- **AI never live-drives.** Viewport is display of daemon pyte / settle stream; live senders remain `{app, human}` only. Attach (056) takes Human lock — still not AI.
- **Archive** is reference-only for `spectate_app` / `spectate_layout` / `terminal.color_map` patterns — never `import twclient`.
- **D1 harness:** `tests/pty_helpers.py` · `tests/fake_client.py`. Prefer Layer-A pure compose + FakeClient; Layer-B pty for geometry/color; never `run/twd.sock` in Accept.

---

## 1. Tip inventory (vs archive)

| Piece | Tip `eb59274` (`tw2002_aiclient`) | Notes |
|---|---|---|
| WatchHub / daemon `subscribe` | **LIVE** — `session/watch.py` · `daemon._handle_subscribe` | Settle-edge push stream |
| `tw watch` CLI | **LIVE** — ops consumer of `subscribe` | **≠** product cockpit subscribe |
| Session pyte terminal | **LIVE** — `session/terminal.py` (`color_map`, glyphs) · bare `build_response` emits color | One-lock `render_with_color` |
| Play shell center GAME | **LIVE** — glyph + per-cell color paint 80×25 (PWO-051…053) | Disconnect chrome = 054 |
| Viewport border STATE flip | **LIVE** (P3-040) — cyan → red non-bold / mono underline on `connected: False` | 054 extends semantics already partially shipped |
| Product watch-stream client | **LIVE** — `watchfeed.py` + play-shell snapshot→paint | 050+052+053 |
| Product spectate mode | **MISSING** | 055; F2 HOLD for *ops* spectate CLI |
| Cockpit attach / detach keys | **MISSING** (Esc→launcher only; no `h` / Ctrl-] attach path) | 056–057; daemon attach protocol **LIVE** for `tw attach` ops |
| Archive `spectate_app` / layout | gitignored archive | Port patterns only under execute WO |

---

## 2. Per-PWO Accept + Proof

### PWO-050 — Watch-stream subscribe (BUILD) — **DONE 2026-07-24** (impl-claudecode-aiclient · Fable · product `WatchFeed` lifetime-subscribe client (`watchfeed.py`) — protocol-shaped, structural no-send API (sole wire write is the one subscribe line, hostile write-log-capture proven across repeated `snapshot()`/`stop()` calls); latest-wins `WatchFeedSnapshot` (`events_received`/`latest_event`/`running`); per-line containment (malformed/non-dict JSON dropped, reader never raises); `shutdown(SHUT_RDWR)`-before-`close()` unblock mirroring `session/attach_client.py`'s own idiom, giving a bounded (~2s join) idempotent `stop()` safe before/mid-stream/twice; `app.py` wire scoped to the play binding only — feed started before the frame loop, released in a `try`/`finally` covering Esc/quit/exception exits; 051's center-viewport placeholder untouched (this WO owns subscribe only, never paint); one redraw owner preserved — nothing reads the feed into UI yet, so no TOCTOU with the existing status-poll redraw; AST tripwire adjudication — the pre-existing `test_run_play_source_never_calls_stop` bare-identifier guard flagged `feed.stop()`, resolved with a precise single-site allowlist (`_is_allowlisted_watchfeed_stop`) rather than a loosened guard, so the guard's actual behavioral intent (no daemon teardown verb reachable from Esc, proven separately by `test_run_play_esc_issues_no_daemon_stop_verb`) is unchanged. Known follow-on: `WatchFeedSnapshot` has no error-detail field — any connect/write/read failure collapses to `running=False` alone; candidate for a future contract-extension WO (**not** this doc's own PWO-054, an unrelated disconnect-viewport-chrome item — flagging the numbering ambiguity from the dispatch for hub to assign a real slot).)
- **Depends-on:** 020 (daemon) · WatchHub live
- **Live state:** **LIVE** — `tw2002_aiclient/watchfeed.py` (`WatchFeed` client) · `tw2002_aiclient/app.py` play-binding wire · `tests/test_watchfeed.py` (Layer-A) · `tests/test_watchfeed_wire.py` (wiring).
- **Accept:** Play shell (or a thin adapter it owns) opens a lifetime `subscribe` connection (or in-process hub hook if same process — prefer protocol-shaped FakeClient first); settle-edge events arrive; **no game sends** on that channel; disconnect/unsubscribe clean on Esc/back.
- **Proof:** Layer-A — FakeClient / fake hub pushes N settle events → adapter records N. Layer-B optional — never sock. Assert no `do`/`send` from subscribe path.
- **Hazards:** Do not conflate with `tw watch` CLI. Do not take control_lock. TOCTOU if status poll + subscribe both mutate UI — one redraw owner.

### PWO-051 — Center 80×24 viewport shell (BUILD) — **DONE 2026-07-24** (impl-claudecode-aiclient · Fable · own commit, first past `b211be2` — `_GAME_PLACEHOLDER` removed from `PlayShellScreen.draw()`'s center block: bordered tiers draw the double-line border + `GAME` title only, zero interior content (blankness is `stdscr.erase()`'s own leftover, never a positive draw call); the `no_border` tier draws nothing into `center` at all — the region stays reserved but unpainted, the same convention the tall-terminal gap band already uses. Layer-A: `tests/test_cockpit_layout.py`'s new PWO-051 section pins the exact 80×24 interior budget at every bordered tier and re-derives the `no_border`/`minimal` clip-ceiling formulas from `layout.py`'s own named constants (never a hand-typed literal); `tests/test_cockpit_viewport.py` (new) proves via a fake-stdscr `addstr` recorder that `draw()` never writes into the GAME interior and the placeholder string never reaches any `addstr` call anywhere in a full draw pass. Layer-B: `tests/test_cockpit_frame_pty.py`'s committed placeholder-present assert flipped to placeholder-absent grid-wide plus a positive blank-interior cell scan at the full tier; sibling lane B's `tests/test_cockpit_viewport_pty.py` independently covers the full/minimal/no_border tier pty proofs. Also caught and fixed a blast-radius regression the placeholder-kill exposed: `tests/test_play_chrome_nav.py`'s daemon-survival test carried a dead `OR` assertion whose only live disjunct was the now-retired placeholder text.) **History:** the 80×24 interior budget in this DONE narrative is what 051 shipped; GAME grew to **80×25** / bordered **82×27** in `bb780e0` (Accept/Proof lines below carry current contract).
- **Depends-on:** 033 · 050 (or 050 stub that yields empty frames)
- **Live state:** **LIVE** — `tw2002_aiclient/screens.py` (`PlayShellScreen.draw()` center block, no interior content drawn) · `tests/test_cockpit_frame_pty.py` (Layer-B) · `tests/test_cockpit_layout.py` (Layer-A) · `tests/test_cockpit_viewport.py` (Layer-A) · `tests/test_cockpit_viewport_pty.py` (Layer-B, lane B).
- **Accept:** Bordered `GAME` box shows empty 80×25 (or honest blank grid), **zero inset**, double-line border per visual-language; geometry matches `VIEWPORT_W/H` / `GAME_W/H`; placeholder string **gone**.
- **Proof:** Layer-A — layout regions + content cell budget 80×25. Layer-B — pty: no placeholder text; title `GAME` present; narrow/no_border tiers still sane.
- **Hazards:** Don't paint real pyte yet (052). Don't break Esc→launcher / ADR-001.

### PWO-052 — Viewport render grid (BUILD) — **DONE 2026-07-24** (impl-claudecode-aiclient · tip `de47a26` — mono glyph paint into 80×25 GAME via WatchFeed snapshot; top-drop under height pressure; per-cell color deferred to 053)
- **Depends-on:** 051 · session terminal / settle payload
- **Accept:** pyte (or settle snapshot grid) cells drawn into center; updates on settle-edge (050); ASCII/unicode glyph twin policy honored where chrome meets game edge.
- **Proof:** Layer-A — fixture grid → exact drawn lines (clip/sanitize via `cockpit/draw`). Layer-B — pty `_find_text` for a known fixture glyph/string; side-by-side note vs archive spectate if useful.
- **Hazards:** Don't reinterpret server palette here — that's 053. Hostility: CSI/OSC in cells must hit draw choke.

### PWO-053 — Viewport color parity (HARDEN) — **DONE 2026-07-25** (impl-claudecode-aiclient · tip `eb59274` — one-lock `render_with_color` on bare `build_response`; `draw_runs`; process-global `_SharedPairs (fg,bg)`; pair exhaustion → A_NORMAL)
- **Depends-on:** 052
- **Accept:** Per-cell fg/bg/bold from `terminal.color_map()` (or equivalent) matches ops spectate contract / visual-language "server CP437 palette"; pair exhaustion degrades without crash.
- **Proof:** Layer-A — color_map fixture → attr pairs. Layer-B — pty cell `.fg`/`.bold` vs fixture (not ANSI-regex).
- **Hazards:** Semantic 7-tone table is **chrome only** — never recolor game cells with `ok`/`danger`.

### PWO-054 — Disconnect viewport chrome (BUILD / VERIFY)
- **Depends-on:** 051 · P3-040 tones
- **Live state:** `_viewport_border_attr` already flips danger non-bold on `connected: False`.
- **Accept:** Documented + proven: disconnect → danger border (non-bold / mono underline interim); reconnect → cyan chrome; honest-unknown stays cyan. Any additional "reconnecting" copy stays outside game cells.
- **Proof:** Existing tones/pty pins + one dedicated kill-sock or FakeClient `connected: False` leg if not already covered.
- **Hazards:** Don't invent a second STATE convention. Height policy / fold unchanged.

### PWO-055 — Product spectate mode (read-only) (BUILD)
- **Depends-on:** 050 · preferably 052
- **Accept:** Cockpit can enter a read-only spectate *mode* (watch without lock); **no sends**; badge/muted per visual-language Spectate. **Does not** ship `tw spectate` CLI.
- **Proof:** Static assert no send path; FakeClient subscribe-only; TTY mode indicator if N5 not ready — honest muted/`—` OK.
- **Hazards:** **F2 HOLD** — if execute would require lifting ops spectate CLI, **STOP and ❓**; stay cockpit-only.

### PWO-056 — Attach from cockpit (VERIFY/BUILD)
- **Depends-on:** 020 attach protocol · preferably 052
- **Live state:** Daemon attach + `tw attach` CLI LIVE; cockpit keybind **MISSING**.
- **Accept:** Documented hotkey (canon `h` / mode-line — confirm against mode-line doc at execute) takes Human lock; Human badge path (may stub badge until P5-060); keystrokes go attach channel with secret redaction.
- **Proof:** FakeClient control_lock transitions; redaction sentinel; Esc/detach interaction owned by 057.
- **Hazards:** Don't bypass control_lock. Secrets doctrine / prompt-echo DOC-GAP is separate (canon only until a harden WO).

### PWO-057 — Detach returns App path (VERIFY)
- **Depends-on:** 056
- **Accept:** Detach (canon Ctrl-] / documented key) releases lock; returns App-capable path without zombie lock; viewport keeps updating if subscribe still up.
- **Proof:** Lock released assert; no send after detach; Esc→launcher still clean.
- **Hazards:** Double-detach / mid-settle detach.

---

## 3. Depends-on graph (execute order)

```
020/WatchHub ─► 050 (product subscribe)
033 frame    ─┬─► 051 (empty GAME shell) ─► 052 (paint) ─► 053 (color)
              │                              └─► 054 (disconnect chrome; may verify-early w/ 040)
050 ──────────┴─► 055 (product spectate mode)   [after paint preferred]
020 attach   ────► 056 ─► 057
```

**Hard gate:** no 051+ product paint until 050 Accept path is clear (even a FakeClient hub).  
**F2:** blocks ops `tw spectate` only — not 050–054.

---

## 4. Hazards / mid-frame collision

1. **CC Phase-4 execute** — once CC ACKs 050, Cursor stays off `screens.py` / cockpit paint paths CC owns.
2. **F2 / G2–G4 HOLDs** — do not invent spectate CLI or menu crawler work.
3. **Ops vs product WatchHub** — two consumers OK; one lock owner for Human.
4. **Secrets** — viewport/RX may show echoed secrets (see DOC-GAP status-prompt); no code "fix" in Phase-4 PREP.
5. **Pty mid-flush** — prefer shared `settle_drain` when migrating new pty drivers (`WO-PTY-SETTLE-HYGIENE-PREP.md`); KEY_RESIZE still separate.
6. **Placeholder deletion** — 051 must remove `_GAME_PLACEHOLDER` entirely (no dual-path).

---

## 5. Execute readiness

All of **050–057 = PREP only** on this seat. First CC execute: **PWO-050**. Cursor idle under F2·G2–G4 after this PREP CLOSES unless hub feeds docs WOs.
