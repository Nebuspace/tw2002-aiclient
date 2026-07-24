# WO-P1-011 — Launcher empty / broken states

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 1 · **Type:** build · **Depends:** WO-P1-010
**Canon:** `canon/surfaces/entry-and-profile-selection.md` (Panel states)

**Goal:** Render the launcher's two honest non-happy-path states — a cold empty picker pointing the
operator at profile creation, and a broken-profile row that stays visible with its error rather than
vanishing.

**Scope:** `tw2002_aiclient/screens.py` (launcher row rendering + empty-state branch).

**Accept:**
- With zero profiles configured, the launcher shows only the **Create New Player** action — no bare
  empty box, no fabricated row.
- A profile that fails to parse (malformed `config/profiles.toml` entry, simulated via a fixture)
  still renders as a row carrying its `error` string, never silently dropped from the list.
- The broken row is visually distinguishable from a healthy row (per canon: `[ASPIRATIONAL]` warn
  tint is the target; at minimum the error text itself must be visible inline if color isn't wired
  yet — do not silently pass this WO on a plain, indistinguishable row).

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
mv config/profiles.toml /tmp/profiles.toml.bak 2>/dev/null; .venv/bin/python -m tw2002_aiclient   # empty state, CTA only
# restore a profiles.toml with one row containing a malformed entry (missing game_letter)
.venv/bin/python -m tw2002_aiclient   # broken row visible with its error, not dropped
```
