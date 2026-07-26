# WO-CLI-VERBS-CANON-RECONCILE

**Status:** OPEN · docs/canon · Claude Code (self-claimed post-M3) · same-day drift from M3
**Posted:** 2026-07-26 · after M3 closed at `13f34a8`

## Goal

Reconcile `canon/architecture/cli-verbs.md` with the shipped CLI surface at tip. M3 (X1–X6) changed
what ships; canon's own status block and catalog now describe a different product in two places, and
one of them is a same-day regression created by X6.

## Why now

This is drift authored **tonight**, not inherited. Caught same-day it is a small edit; left alone it
becomes the "canon says X, code does Y" puzzle someone re-derives from scratch in three weeks. The
whole point of a prescriptive doc is that it is trustworthy without reading the code.

## Known divergences (verified against tip `13f34a8`, re-verify — do not trust this list)

1. **`record` is listed as NOT SHIPPED but is shipped.** `cli-verbs.md:191` puts `record`/`replay`
   under *"NOT on tip (HOLD / later / retired — do not document as shipped)"*. X6 landed `tw record`
   in `13f34a8`. The status block is the section that explicitly answers "what can I run right now?",
   so it is the worst place in the document to be wrong.
2. **The shipped `record` has different semantics from the documented one.** Catalog line ~125
   describes `record {start,stop}` as a bracket capture — *"every `do` sent while open becomes a
   step; `stop` saves a replayable skill."* X6 shipped a **manifest** recorder: it reads a JSON
   capture manifest, and there is no start/stop bracketing. The lane disclosed this as
   manifest-not-live-attach and the hub Accepted it as honesty; canon has not caught up.
3. **`autoloop` ships as WIRE verbs only, with no CLI surface at all.** Catalog line ~135 documents
   `tw autoloop {start,stop,pause,resume}` with `--cycles --floor --param`. There is no `autoloop`
   CLI subparser. Shipped is three wire verbs (start/stop/status); `pause`/`resume` were argued down
   in X4 and `cycles`/`param` are refused as `unsupported_arg`. `floor` IS now real on the wire (X5)
   — so this line is wrong in both directions at once, and the status block's "G4 STAGED" note needs
   to reflect what actually landed.

## Scope

- `canon/architecture/cli-verbs.md` only, unless the sweep finds the same claims mirrored elsewhere
  in `canon/` — then those too, named in the report.
- **No product code.** No CLI changes. If canon describes a better design than what shipped, that is
  a finding to record, NOT a licence to change code.

## Constraints

- Derive the shipped verb set **structurally** (AST over the argparse subparsers), not by grep and
  not from this file's list.
- Do not "fix" the divergence by deleting the prescriptive target vocabulary — the catalog is
  deliberately the full target set, and the status block is what separates target from tip. Keep
  that distinction; correct which side each verb sits on.
- Where shipped semantics differ from documented ones, record the difference plainly rather than
  quietly rewriting canon to match code — DOCS WIN is the default, and a genuine "the shipped shape
  is different" needs to be visible, not smoothed away.

## Accept

The status block correctly partitions shipped vs not-shipped at tip; `record`'s documented shape
matches what ships or the difference is explicitly recorded; the `autoloop` row states the true wire
surface and its refusals. No product file modified. Suite count unmoved.

## Proof

STATUS + SHA · before/after quotes · the AST-derived shipped verb list · full sweep accounting of
every occurrence found, including ones deliberately left alone and why.

## Refs

M3 close `13f34a8` · X4 STATUS (verb refusals) · X5 STATUS (`floor` on the wire, no CLI surface) ·
X6 STATUS (manifest recorder disclosure)
