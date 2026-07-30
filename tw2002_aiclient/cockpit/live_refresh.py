"""Idle-tick refresh of the always-on world/chain readouts
(WO-CHAINS-LIVE-REFRESH).

# What was broken

`world_stats` refreshed on the `L` keypress and on explore *completion*;
`chain_scalars` refreshed on the `L` keypress and nowhere else. So the GOALS
chain row and the HUD stayed empty for a whole explore run unless the
operator happened to press `L` -- an always-on surface that only updated
when a modal was opened (live, 2026-07-29).

# Why this is a BUDGET and not a throttle

The WO asked for a throttle. Measurement said a throttle is the wrong
instrument, because the hazard is per-call cost rather than frequency
(`chain_search.recompute`, this machine, worlds built with the real
`world_model.upsert_sector` producer):

    sectors  ports   recompute   known_sector_count
         40     10       65 ms              0.3 ms
        160     40      302 ms              0.8 ms
        640    160    1 332 ms              2.4 ms
       1280    320    9 432 ms              4.8 ms
       5000    800  220 073 ms             ~26 ms

The play loop is single-threaded on a 1 Hz `stdscr.timeout(1000)`. A
9-second synchronous recompute freezes the cockpit for nine seconds *during
explore*, which is exactly when the operator is watching it. No throttle
interval fixes that; it only makes the freeze rarer. The cost is
`build_trade_hops`' O(ports²) pair loop -- its `max_hops` cap truncates the
sorted candidate list *after* it is fully built, so it bounds the OUTPUT and
not the WORK. Bounding that loop is the real fix and is banked as its own
WO; it is deliberately not touched here.

So the chain half **measures itself** and retires when it gets expensive:
one automatic recompute over `CHAIN_BUDGET_S` disables automatic chain
refresh for the rest of the session, and chains fall back to `L`.

Measuring beats a sector-count threshold for two reasons. Sector count is a
poor proxy for the actual driver (port count), and any constant would have
been fitted to a fixture whose port density is a guess. An adaptive guard
also degrades in the useful direction: a freshly-explored world is small and
cheap, so live refresh works precisely when this WO wants it, and stands
down as the world grows past the point where it could be free. Worst case is
**one** over-budget hitch per session rather than one per throttle window.

# Honesty

A skipped refresh leaves the previous value in place; it never writes a
fabricated or cleared one. That is already `WorldStats.refresh`'s documented
posture for a failed read and `ChainScalars.update`'s for a not-seen result,
and this module adds no new way to display a number nobody observed.

# Hardening family

Matches `armconfirm.py` / `explore_flags.py` / `teachband.py`: never raises,
whatever it is handed. It runs on the idle tick of the play loop, so a raise
here costs the operator the whole cockpit.
"""

from __future__ import annotations

import time

# How often the idle tick may re-count sectors. `known_sector_count` is a
# directory count (~5 ms at 1 000 sectors, ~26 ms at 5 000, per its own
# docstring), so this is cheap -- but it is not free, and at 1 Hz an
# unthrottled count is a syscall burst every second for a number that changes
# slowly. Also the backstop for a dead-terminal spin, where `getch` returns
# -1 continuously and `_DeadTerminalGuard` is the only other brake.
WORLD_STATS_INTERVAL_S = 5.0

# How often the idle tick may re-discover chains, when it still may at all.
# Deliberately slower than the world count: even a cheap recompute is
# hundreds of times the cost of a directory count.
CHAIN_INTERVAL_S = 10.0

# The self-retirement budget. A quarter of the 1 Hz tick -- large enough that
# an early-explore world (measured 65-302 ms) keeps refreshing, small enough
# that the operator never waits on a frame. One breach retires automatic
# chain refresh for the session.
CHAIN_BUDGET_S = 0.25


class LiveRefresh:
    """Idle-tick refresh state for one play session.

    Instantiated per `_run_play`, so the retirement decision lasts exactly as
    long as the session that measured it -- a world that was too big last
    session is not held against the next one, which may be a different
    profile entirely.
    """

    __slots__ = (
        "_last_world",
        "_last_chain",
        "chain_auto_retired",
        "last_chain_cost_s",
        "_world_interval_s",
        "_chain_interval_s",
        "_chain_budget_s",
    )

    def __init__(
        self,
        *,
        world_interval_s: float = WORLD_STATS_INTERVAL_S,
        chain_interval_s: float = CHAIN_INTERVAL_S,
        chain_budget_s: float = CHAIN_BUDGET_S,
    ) -> None:
        self._last_world: float | None = None
        self._last_chain: float | None = None
        # Public: the STATUS surface and the pins both need to read whether
        # the session stood down, and a private name would push them into
        # asserting on behaviour they can only infer.
        self.chain_auto_retired: bool = False
        self.last_chain_cost_s: float | None = None
        self._world_interval_s = world_interval_s
        self._chain_interval_s = chain_interval_s
        self._chain_budget_s = chain_budget_s

    @staticmethod
    def _due(last: float | None, now: float, interval: float) -> bool:
        """`None` is due -- the operator should not wait one interval for the
        first reading of a surface that is empty on arrival. A clock that
        went backwards is also treated as due rather than as a lockout."""
        return last is None or now - last >= interval or now < last

    def tick(self, play: object, profile: object, *, now=None) -> None:
        """Refresh what is due. Never raises.

        Takes the PROFILE, not a resolved `world_id`, for two reasons that
        both bit during wiring. `world_identity.world_id` *raises*
        (`WorldIdentityError`) on a profile with an unusable host, and this
        runs on the play loop's idle tick -- resolving it at the call site
        would put a raise outside this module's containment and cost the
        operator the whole cockpit for a malformed profile. It is also work
        that is pointless when nothing is due, which on most ticks is the
        case.

        `now` is injectable for the pins: the budget behaviour is a statement
        about elapsed time, and a test that had to actually burn 250 ms to
        prove it would be both slow and flaky.
        """
        clock = now if callable(now) else time.monotonic
        try:
            t = clock()
        except Exception:  # noqa: BLE001 — a broken clock must not end the loop
            return
        if not (
            self._due(self._last_world, t, self._world_interval_s)
            or (
                not self.chain_auto_retired
                and self._due(self._last_chain, t, self._chain_interval_s)
            )
        ):
            return
        try:
            from tw2002_aiclient import world_identity as _world_identity

            world_id = _world_identity.world_id_from_profile(profile)
        except Exception:  # noqa: BLE001 — an unusable profile is not a crash
            return
        self._refresh_world(play, world_id, t)
        self._refresh_chains(play, world_id, t, clock)

    def _refresh_world(self, play: object, world_id: object, t: float) -> None:
        if not self._due(self._last_world, t, self._world_interval_s):
            return
        # Stamped UNCONDITIONALLY -- success and failure alike. That is what
        # keeps a broken world model from turning the 1 Hz loop into a retry
        # storm; a stamp that only landed on success would re-attempt an
        # unreadable store every single tick.
        #
        # The stamp is written before the call rather than after purely as
        # defence against a later refactor: under the blanket `except` below
        # the two orderings are equivalent today, and a mutation pass proved
        # exactly that by surviving the swap. An earlier version of this
        # comment credited the ORDERING with the anti-spin guarantee, which
        # was wrong -- the guarantee is the unconditional stamp.
        self._last_world = t
        try:
            status = None
            provider = getattr(play, "status_provider", None)
            if callable(provider):
                try:
                    status = provider()
                except Exception:  # noqa: BLE001 — sector lookup is best-effort
                    status = None
            play.world_stats.refresh(world_id, status=status)
        except Exception:  # noqa: BLE001
            pass

    def _refresh_chains(self, play: object, world_id: object, t: float, clock) -> None:
        if self.chain_auto_retired:
            return
        if not self._due(self._last_chain, t, self._chain_interval_s):
            return
        # Unlike `_refresh_world`'s, this stamp's POSITION is load-bearing:
        # the `except` below `return`s, so a stamp written after the try
        # would be skipped on every failure and a raising finder would be
        # re-entered on each due tick.
        self._last_chain = t
        try:
            # Lazy import for the same CPU-budget reason `app.py` and
            # `world_stats.py` give: this module is imported by the cockpit
            # wiring, while the discovery only runs on a due tick.
            from tw2002_aiclient import chain_search as _chain_search

            t0 = clock()
            discovered = _chain_search.recompute(world_id)
            cost = clock() - t0
        except Exception:  # noqa: BLE001
            # A raise is not a cost signal, so it does not retire the
            # refresh -- it is already stamped, so it will not spin.
            return
        self.last_chain_cost_s = cost
        try:
            play.chain_scalars.update(discovered)
        except Exception:  # noqa: BLE001
            pass
        # Retire AFTER applying: the result was paid for and is valid, and
        # discarding it would make the breach cost the operator twice.
        if cost > self._chain_budget_s:
            self.chain_auto_retired = True
