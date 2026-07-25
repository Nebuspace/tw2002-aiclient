# Canon — Change Log

## 2026-07-25

- **Test Case Catalog (OKF).** Founded `canon/testing/` bundle: hub at `test-case-catalog.md` and 129 per-module OKF case files under `cases/`. Catalogues all 2271 pytest tests (1263 active · 1008 banked across 46 modules) with one-sentence blurbs derived from docstrings or test names. BANKED modules annotated per `pytest.ini --ignore`. Added Testing section to `canon/index.md`.

## 2026-07-24

- **WO-OKF-STATUS-TRUTH (Phases 0–3).** Status-honesty pass: ADR-001 Consequences + index mark
  one-tree **LIVE**; `trainer-cockpit` / `visual-language` / `spectate-and-attach` / `cli-verbs`
  Implementation-status tables — Phase 3 chrome/LOGS shipped (`6391bb7`); GAME viewport still
  placeholder; `tw spectate` F2 HOLD; secrets Code-Divergence #1 already names status-verb wire
  (`8f03289`). Phase 4 product subscribe **not** claimed DONE.

## 2026-07-23

- **Bundle founded — the reborn, human-centric vision.** Ground-up OKF bundle at `canon/`,
  superseding the AI-first `knowledge/` bundle (to be archived once this bundle stands complete).
  The operator ruled the three founding forks:
  1. **Greenfield** — build new canon rather than retrofit the old "fly itself" north star.
  2. **Human-first escalation** — on an unrecognized screen the app stops and hands the human the
     keyboard, and that moment is the primary teaching moment: respond directly · record a macro ·
     ask the AI to analyze after-the-fact and author its own macro.
  3. **Guarded, prioritized rules** — `when(screen_match + guards) → do(macro)`, with `priority`
     and `scope: one-shot | repeating`.
- North Star concept drafted first as the anchor everything else hangs off.
- **AI role ruled: teacher-only.** The operator ruled the AI never drives — it is a retrospective,
  human-invoked teach overlay, not a live pilot. Live control is an **App / Human dual**; "AI" is
  never a drive mode. AI-authored rules are human-approved before they can fire. Consequence: the
  existing `control_lock.py` `ai_pilot` live-drive mode diverges from canon and is slated for
  retirement/repurposing (surfaced as a finding, not silently reconciled).
