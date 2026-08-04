# WO-AUDIT-BUILD-CLI-LIVE-ATTACH-RECORDER-X6

**Status:** BANKED / DEFERRED (tracking only — not building this PR)
**Priority:** LOW
**Seat:** `impl-aiclient-cursor` (claimed for visibility land)
**Depends-on:** none for this tracking artifact; product build depends on attach + recorder design pass
**Gated:** yes for *implementation* (live keystroke capture into teach path — human/Max GO before coding);
  **no** for this docs/tracking file

## Goal

Give the deferred **"live `tw attach` → recorder"** slice a durable workorder id so it cannot
silently fall off the backlog. Canon already names the gap; this WO is the queue handle.

## What this is / is not

| | |
|---|---|
| **Is** | Named follow-on to M3 **X6** (`WO-P2-G4-X6-TW-RECORD-WRITER`), which deliberately shipped a **manifest** writer only |
| **Is not** | A build of live keystroke capture in this PR |
| **Is not** | Closing or replacing tip `tw record <manifest>` |

## Canon pins (do not invent a new target)

- [cli-verbs](../canon/architecture/cli-verbs.md) § Implementation status — *Wiring a live `tw attach`
  session directly into the recorder … is real future work X6's own scope explicitly excluded*
- [macros](../canon/engine/macros.md) § Findings — mirrored deferred note
- Shipped X6: `tw2002_aiclient/loops/recorder.py` + `cmd_record` (`session/cli.py`)

## Future Accept (when Max GO's the build)

1. Live attach (or an explicit teach-capture mode) can append steps as keystrokes land, without
   inventing sends the human did not type.
2. Draft vs blessed store rules match existing recorder / `--draft` semantics.
3. Secrets doctrine: password / prompt redaction on any captured step.
4. Proof: offline suite + documented live-prove diversity (or honest `n/a` if still offline-only).

## This PR's Accept (tracking land)

1. This file exists under `workorders/` with the queue id in the filename.
2. live-prove: `n/a` (docs / backlog handle only).

## Refs

- queue-aiclient.md `AUDIT-BUILD-CLI-LIVE-ATTACH-RECORDER-X6`
- `workorders/WO-P2-G4-X6-TW-RECORD-WRITER.md` (shipped manifest slice)
- `workorders/WO-CLI-VERBS-CANON-RECONCILE.md` (X6 shape disclosure)
