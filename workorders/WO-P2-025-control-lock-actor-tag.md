# WO-P2-025 — Control-lock + actor tag

> Status: **DONE** · origin `190bd09` (hub Accept stamp 2026-07-26 · was EXECUTE DONE awaiting Accept)
**Phase:** 2 · **Type:** harden · **Depends:** WO-P2-020 · **Preferred after:** WO-P2-024 (login/fake_twgs exclusive until Accept)
**Canon:** `canon/architecture/control-and-escalation.md`, `canon/architecture/session-engine.md`
(The Control-Lock as Keystroke Carrier), `canon/engine/trace-ledger.md` (Actor attribution)

**Goal:** Build the greenfield control-lock as an App/Human dual (no live `ai_pilot` drive mode) and
tag every send-time keystroke `{app, human}` at the choke point — the reborn actor model, not the
legacy `{ai, trainer, human}` enum this canon's own findings log (WO-P0-006) records as a
divergence to avoid re-introducing.

**Scope:** `tw2002_aiclient/session/control_lock.py` (new — mode state machine: `human`, `app`/`auto_loop` collapse
to App, `spectate`; no `ai_pilot`), wire into `session.py` / `protocol.py` / `daemon.py` (send choke +
refuse-not-queue). Ledger persistence is **out of 025** if `ledger.py` still missing — prove via
`Session.last_sender` + typed controller_* errors until Trace Ledger WO lands.

**Out of bounds:** `MODE_AI_PILOT` / `"ai"` live sender · `credentials.py` · `session/login.py` during
CC P2-024 · inventing EV autopilot.

---

## PREP inventory (2026-07-24 — WO-P2-025-PREP · parallel fan-out)

### Already live (do not re-invent)

| Behavior | Where | Status |
|----------|-------|--------|
| `{app, human}` sender validation | `session/session.py:51` `VALID_SENDERS`; `send()` default `"app"` (~235); `send_raw()` default `"human"` (~256) | **live** choke-point tags |
| `last_sender` sticky | `session/session.py:92`, set at 253 / 318 | **live** (ledger consumer not ported) |
| Duck-typed fence wait on `send_raw` | `session/session.py:267–305` (`control_lock.is_driver_fenced`) | **partial** — awaits real `control_lock.py` |
| Per-daemon ensure drive lock | `daemon.py:222` `server.drive_lock`; `protocol.py:254–262` → `controller_busy` | **partial** — ensure-only, not full mode lock |
| Adapter maps `controller_*` → already_driving | `adapters.py:28`, `115–116` | **live** vocabulary consumer |

### Missing (025 must build)

| Gap | Note |
|-----|------|
| `session/control_lock.py` | Full mode SM `{human, app, spectate}`; take_human / release; fence; refuse-not-queue with `controller_locked_by_human` (and spectate/app busy names per canon) |
| Protocol/daemon wire of modes | Beyond ensure `drive_lock` — attach / do / concurrent claim |
| `ai_pilot` absence proof | Grep gate on greenfield tree (Accept) |
| Ledger rows with `actor` | **Deferred** until ledger module — Accept proves `last_sender` + unit tests instead |

### Accept (tightened draft for execute HANDOFF)

- Mode enum / API exposes exactly `{human, app, spectate}` — **zero** `ai_pilot` / `MODE_AI_PILOT`; any `auto_loop` collapses to `app` (not a third drive mode).
- Every `Session.send` / `send_raw` path still only accepts `VALID_SENDERS`; reject `"ai"` / `"trainer"`; protocol attach/do set sender correctly.
- Spectate cannot acquire send (typed refuse, e.g. `spectate_read_only`).
- Human claim always wins immediately (attach / escalation) — App cannot refuse or finish “one more” send.
- Concurrent second driver while lock held → typed refuse (`controller_locked_by_human` / `controller_busy`), never queue; adapters still map `controller_*` → `already_driving`.
- Unit tests: mode transitions · fence courtesy wait · refuse-not-queue · human preempt · no `"ai"`/`"trainer"` sender.
- Rehab rewrite-B (below) collect+green OR still ignored with explicit defer note if ledger/attach incomplete.

### Proof (tightened draft)

```bash
cd "$(git rev-parse --show-toplevel)"
rg -n "ai_pilot|MODE_AI_PILOT" tw2002_aiclient/   # expect no match
.venv/bin/python -m pytest tests/test_control_lock.py tests/test_session.py -q
# after un-ignore / rewrite:
# .venv/bin/python -m pytest tests/test_actor_attribution.py tests/test_tw04_toctou.py -q
```

### Rehab rewrite-B wave (all currently `--ignore`d in `pytest.ini`)

| File | Why under 025 | Hint |
|------|---------------|------|
| `tests/test_control_lock.py` | Core mode SM | Thin rewrite onto new module |
| `tests/test_actor_attribution.py` | Sender tags at choke | Thin; use `last_sender` if no ledger |
| `tests/test_tw04_toctou.py` | Lock TOCTOU / race | Fold with refuse-not-queue |
| `tests/test_attach_protocol.py` | Human attach + fence | Needs attach verb + lock |
| `tests/test_attach_redaction.py` | Secret + attach path | Cipher-adjacent; after attach |

**Not wave B:** `tests/test_clean_preempt.py` stays **DEFER** (rehab Play/TUI bucket) — reopen when protocol/ledger fence proofs land with/after 025.

---

## Lane 3 EXECUTE — rewrite-B status (2026-07-24T06:00Z follow-up)

**Gate flipped:** `control_lock.py` + greenfield `test_control_lock.py` landed (lane 1). Lane 3 completed remaining rewrites.

| File | Status | Proof |
|------|--------|-------|
| `tests/test_control_lock.py` | **GREEN** (lane 1; aligned) | 37 passed |
| `tests/test_actor_attribution.py` | **GREEN** rewritten | `last_sender` / `VALID_SENDERS` (no ledger) |
| `tests/test_tw04_toctou.py` | **GREEN** rewritten | Axis 1 races + fence/`send_raw`; Axis 2 attach e2e DEFER |
| `tests/test_attach_protocol.py` | **DEFER** | Docstring note; no attach verb — still `--ignore`d |
| `tests/test_attach_redaction.py` | **DEFER** | Docstring note; Cipher-adjacent — still `--ignore`d |
| `tests/test_clean_preempt.py` | **DEFER** | Out of wave B (unchanged) |

`pytest.ini`: un-ignored control_lock / actor_attribution / tw04_toctou after 53 passed under `--override-ini=addopts=`. Lane-3 `.draft` files lived only under gitignored `workorders/drafts/` (never on tip); directory removed locally (WO-CLEANUP-WO-P2-025-LANE3-SUPERSEDED-DRAFTS). Live tests are under `tests/`.

---

## Original Accept / Proof (pre-prep — superseded by drafts above when EXECUTE)

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
