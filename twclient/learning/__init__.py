"""Phase-3 try-then-verify learning loop — pure logic only.

No daemon imports, no key-sending. Live activation is gated on the
exec-flip; this package is offline-provable with fixtures today.
"""

from .candidates import propose_candidates
from .comparator import compare_transition
from .guards import blocked_actions_for_context
from .loop import dry_run_step

__all__ = [
    "blocked_actions_for_context",
    "compare_transition",
    "dry_run_step",
    "propose_candidates",
]
