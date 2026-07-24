# WO-P2-025 — Control-lock + actor tag

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 2 · **Type:** harden · **Depends:** WO-P2-020
**Canon:** `canon/architecture/control-and-escalation.md`, `canon/architecture/session-engine.md`
(The Control-Lock as Keystroke Carrier), `canon/engine/trace-ledger.md` (Actor attribution)

**Goal:** Build the greenfield control-lock as an App/Human dual (no live `ai_pilot` drive mode) and
tag every send-time keystroke `{app, human}` at the choke point — the reborn actor model, not the
legacy `{ai, trainer, human}` enum this canon's own findings log (WO-P0-006) records as a
divergence to avoid re-introducing.

**Scope:** `tw2002_aiclient/session/control_lock.py` (new — mode state machine: `human`, `app`/`auto_loop` collapse
to App, `spectate`; no `ai_pilot`), `tw2002_aiclient/session/session.py` / `tw2002_aiclient/session/protocol.py` (send choke point
actor tag).

**Accept:**
- The control-lock's mode enum contains exactly `{human, app, spectate}` — no `ai_pilot` mode exists
  anywhere in the greenfield code.
- Every keystroke dispatched through the choke point is tagged `actor="app"` or `actor="human"` at
  send time — never `"ai"`.
- A ledger sample (once WO-P2-020's `ensure` and a manual `tw do` have both run) shows both actor
  values present and no third value.
- A second concurrent driver attempting to claim the lock while one is held is refused outright
  (never queued), naming why (`controller_locked_by_human` / `controller_busy` or equivalent).

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
grep -rn "ai_pilot" tw2002_aiclient/session/   # expect no match anywhere in greenfield code
.venv/bin/python -m tw2002_aiclient.session.cli do "1"
tail -5 state/ledger.jsonl | python3 -c "import sys,json; [print(json.loads(l)['actor']) for l in sys.stdin]"
# expect only app/human values
```
