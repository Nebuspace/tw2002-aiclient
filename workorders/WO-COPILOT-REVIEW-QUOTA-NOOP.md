# WO-COPILOT-REVIEW-QUOTA-NOOP

**Status:** 🧑‍⚖️ Max-gated (account quota · ruleset intent)  
**Goal:** Resolve silent Copilot code-review no-op on `tw2002-aiclient` `main`.

**Evidence (CC 2026-07-28T19:47:13Z):** PRs #181/#184/#185/#186 — every Copilot review record is *"quota limit reached"*; zero inline comments. `copilot_code_review` is in the ruleset but **non-blocking**, so merges proceeded with suite-only review. A present/non-blocking/silent-no-op gate is counted as coverage it does not provide.

**Open questions for Max:**
1. Does the requesting account's Copilot review quota reset on its own? Which account?
2. Make the gate **blocking** (would have stopped those merges) vs **remove** as decoration vs leave + monitor?
3. Same account / same shape on `Sectorwars2102`? (CC: #156–#159 open ~1d with **zero** reviews of any author — unknown whether review was requested; hub to verify separately.)

**Hub interim:** do not treat Copilot as a load-bearing reviewer until this is resolved. Suite + hub Accept remain the real gates.

**Accept (after Max ruling):** ruleset/account action landed · STATUS · optional canary PR proving a real Copilot verdict appears.
