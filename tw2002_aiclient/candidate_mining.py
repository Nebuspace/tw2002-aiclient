"""Canon concept facade: candidate mining (``canon/engine/candidate-mining.md``).

Implementation lives in :mod:`tw2002_aiclient.miner` (PWO-095 / #350). This
module exists so tip audits searching ``candidate_mining`` / ``CandidateMining``
resolve to the real ledger miner, not a false "unbuilt" finding.

Drafts write under ``state/skills/_drafts/`` via ``loops.store.drafts_dir``;
promotion is the existing filesystem-location gate (blessed store), not a
second pipeline. Offline-only — never sends.
"""

from __future__ import annotations

from tw2002_aiclient.miner import (
    mine_ledger,
    mine_patterns,
    propose_drafts,
    write_mined_draft,
)

# Explicit names for audit / canon discoverability (not a second engine).
CandidateMining = mine_ledger

__all__ = [
    "CandidateMining",
    "mine_ledger",
    "mine_patterns",
    "propose_drafts",
    "write_mined_draft",
]
