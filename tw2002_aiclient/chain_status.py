"""Chain scalars on ``status`` — the producer `cockpit/goals.py` has been
waiting for, and the input `coach_engine.infer_coach_triggers` needs.

**The gap this closes.** `goals.py` renders its GOALS Chain row from
``status["chain_hops"]`` / ``status["chain_unit"]``. Until now **no product code
wrote either field** — only tests did — so the row could render nothing but
"unknown" on a live run while the suite stayed green on supplied values. The
pre-rebirth producer lived in `spectate_app.py`, which the rebirth deleted.

**Why the cache, and why only two scalars.** Discovered chains are computed
client-side and **on demand**: `app.py` imports `chain_search` lazily inside the
chains-popup branch precisely because that import pulls the finder +
trade_adapter + world_model, *~40ms of CPU nothing else in the cockpit needs*,
against a whole-process budget (`tests/test_dead_terminal_spin.py`, 0.5s) that
the code comments there describe as already within ~50ms of its ceiling. The
DECISIONS and GOALS panels redraw continuously, so recomputing per draw is not
available to us. Instead the derived scalars are cached when a discovery
*already happened* for its own reasons, and the draw path only ever reads two
cheap values. Nothing here imports `chain_search`, and nothing here runs a
search.

**Honest absence, and the one case that is not absence.** Before a discovery
has *established* something, this contributes **nothing** to ``status`` — the
GOALS row then reports "unknown", which is true: we have not looked, or we
looked and the search itself came back inconclusive. It never fabricates a zero
on the strength of not having run. The single case that does report zero is a
completed, untruncated search over a world we actually have a map of: there,
"none yet" is a fact, and withholding it would be its own dishonesty. `update`
enumerates the split.
"""

from __future__ import annotations

__all__ = ["ChainScalars", "as_chain_like", "pair_as_chain_like"]

from tw2002_aiclient.chain_units import chain_hop_count_and_unit

HOPS_KEY = "chain_hops"
UNIT_KEY = "chain_unit"

# Literal copy of ``chain_search.REASON_NO_WORLD_MODEL`` /
# ``chain_detect.REASON_NO_WORLD_MODEL``. Copied, not imported: importing
# `chain_search` / `chain_detect` pulls the finder + trade_adapter +
# world_model (~40ms) into every module that touches `cockpit/decisions.py`,
# which is the whole reason this module deals in cached scalars. A test pins
# the two against each other so the copy cannot drift silently -- the same
# trick `chain_search.recompute` uses for its `min_hops` default.
_REASON_NO_WORLD_MODEL = "no_world_model"


def pair_as_chain_like(pair: object) -> dict | None:
    """Adapt a ``CandidatePair`` into the ``{sectors: (a, b, a)}`` shape
    ``compose_chain_bubbles`` already reads. Never invents margin.

    ``None`` when the pair lacks usable sector ids — draw then falls through
    to the quiet empty placeholder.
    """
    try:
        a = int(getattr(pair, "sector_a"))  # type: ignore[arg-type]
        b = int(getattr(pair, "sector_b"))  # type: ignore[arg-type]
    except (AttributeError, TypeError, ValueError):
        return None
    return {"sectors": (a, b, a)}


def _valid_class_triple(cls: object) -> bool:
    """Same B/S triple gate as ``trade_adapter._valid_class_triple`` — copied
    so this module never imports the adapter (and its world_model pull) at
    load time."""
    return isinstance(cls, str) and len(cls) == 3 and set(cls) <= {"B", "S"}


def _port_snapshot_from_world(
    world_id: object, *, state_dir: object = None
) -> tuple[dict[int, str], set[int]]:
    """One lazy world-model scan → ``(port_classes, known_ports)``.

    Called only from ``ChainScalars.update`` after a successful discovery —
    never from the draw path. Hostile / missing worlds yield empty maps
    (never raise).
    """
    if not isinstance(world_id, str) or not world_id:
        return {}, set()
    try:
        from tw2002_aiclient import world_model  # lazy — keep draw-path cold
    except Exception:  # noqa: BLE001
        return {}, set()
    classes: dict[int, str] = {}
    known: set[int] = set()
    try:
        recs = world_model.query(
            world_id, lambda s: bool(s.get("port")), state_dir=state_dir
        )
    except Exception:  # noqa: BLE001
        return {}, set()
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        port = rec.get("port")
        if port is None:
            continue
        try:
            sid = int(rec["sector_id"])
        except (KeyError, TypeError, ValueError):
            continue
        known.add(sid)
        if isinstance(port, dict):
            cls = port.get("class")
            if _valid_class_triple(cls):
                classes[sid] = cls  # type: ignore[assignment]
    return classes, known


class ChainScalars:
    """Memoises ``(hops, unit)`` and the ranked-first chain for bubble viz.

    Both methods are total: they never raise, whatever shape they are handed.
    That is a hard requirement rather than defensiveness for its own sake --
    ``screens.py`` calls the status provider once per draw and
    ``compose_decisions_lines`` documents that it never raises regardless of
    ``status``. A producer that could throw would convert both guarantees into
    "usually".

    WO-PLAY-CHAIN-BUBBLE-VIZ: ``best_chain`` retains ``chains[0]`` (global
    longest) for GOALS hop scalars. Failed / truncated / no-world-model
    updates never wipe the last good sequence; a completed empty search
    clears it to quiet empty. The chain object is **never** merged onto
    daemon ``status`` JSON.

    WO-CHAIN-BUBBLE-PREFER-CURRENT: the always-on bubble strip reads via
    ``bubble_subject(current_sector=…)``, which prefers the first ranked
    priced cycle that includes the player's sector when one exists, else
    ``chains[0]``. Full ranked tuple is retained so sector moves re-pick
    without waiting for the next discovery tick. GOALS may still show
    global hop count from ``best_chain`` / ``chains[0]``.

    WO-CHAIN-BUBBLE-PORT-CLASSES: successful non-empty updates also refresh
    ``port_classes`` / ``known_ports`` from the world-model port records for
    ``discovered.world_id``. Failed updates retain the last good maps (same
    retention as ``best_chain``); completed empty clears them. Never on status.

    WO-CHAIN-BUBBLE-PAIR-FALLBACK: ``best_pair`` retains the ranked-first
    class-derived ``CandidatePair`` from ``chain_detect.recompute`` for the
    always-on bubble strip when no positive-margin ``best_chain`` exists.
    Retention mirrors ``best_chain``: failed / missing / no-world-model
    pair updates never wipe the last good pair; a completed empty pair
    result clears it. Never on status JSON; never carries a margin field.

    WO-CHAIN-BUBBLE-TRUNCATION-CAPTION: remember when the latest priced
    ``update`` was truncated-empty (absence not established). Pair-fallback
    caption then becomes ``"class pair · search incomplete"`` instead of
    bare ``"class pair"``. Cleared on any completed priced update. Never on
    status JSON.
    """

    def __init__(self) -> None:
        self._hops: int | None = None
        self._unit: str | None = None
        self._seen: bool = False
        self._best_chain: object | None = None
        self._ranked_chains: tuple = ()
        self._best_pair: object | None = None
        self._priced_search_incomplete: bool = False
        self._port_classes: dict[int, str] = {}
        self._known_ports: set[int] = set()

    def update(self, discovered: object, *, state_dir: object = None) -> None:
        """Record the scalars for a `chain_search.recompute` result.

        ``discovered`` is a ``ProfitChainResult`` -- **not** a chain. Its
        ``chains`` field is a tuple already ranked hop-count-descending, so
        ``chains[0]`` is the longest known cycle: the one the GOALS row means
        by "Chain N hops" and the one worth teaching from. Reading ``.hops``
        off the *result* instead would find no such attribute and silently
        report ``None`` forever -- the exact starved-consumer shape this
        module exists to close, one layer up.

        **Only some outcomes are "seen".** The distinction being protected is
        *"we looked and there is nothing"* versus *"we have not established
        anything"*, and only the first may reach the operator as "none yet":

        * no ``chains`` attribute (finder raised, no ``world_id``, ``None``)
          -> not seen. Same predicate `cockpit/chains.py::_usable_discovered`
          branches on, expressed as the attribute read it actually needs.
        * empty and ``truncated`` -> not seen. `chain_search`'s own words: "a
          truncated search that found nothing has not established that
          nothing is there." Sets ``_priced_search_incomplete`` so pair-
          fallback captions stay honest.
        * empty because the world was never explored
          (``REASON_NO_WORLD_MODEL``) -> not seen. There was no map to search.
        * empty for any other reason -> **seen, zero.** Sectors were known and
          searched; "none yet" is the true statement. Clears ``best_chain``
          and clears ``_priced_search_incomplete``.
        * non-empty -> seen, ``len(chains[0].hops)``, retain ``chains[0]``,
          refresh port class / known-port caches from the world model,
          clears ``_priced_search_incomplete``.

        ``state_dir`` is an injectable world-model root for tests; production
        callers omit it (default store).
        """
        try:
            chains = getattr(discovered, "chains", None)
            if chains is None:
                return
            if not chains:
                if getattr(discovered, "truncated", False):
                    self._priced_search_incomplete = True
                    return
                if getattr(discovered, "reason", None) == _REASON_NO_WORLD_MODEL:
                    return
                self._hops = 0
                self._unit = "hops"
                self._seen = True
                self._best_chain = None
                self._ranked_chains = ()
                self._priced_search_incomplete = False
                self._port_classes = {}
                self._known_ports = set()
                return
            hops, unit = chain_hop_count_and_unit(chains[0])
        except Exception:  # noqa: BLE001 -- a hostile shape is an unknown, not a crash
            return
        if not isinstance(hops, int) or isinstance(hops, bool):
            return
        self._hops = hops
        self._unit = unit if isinstance(unit, str) and unit else "hops"
        self._seen = True
        self._best_chain = chains[0]
        try:
            self._ranked_chains = tuple(chains)
        except TypeError:
            self._ranked_chains = (chains[0],)
        self._priced_search_incomplete = False
        try:
            classes, known = _port_snapshot_from_world(
                getattr(discovered, "world_id", None), state_dir=state_dir
            )
            self._port_classes = classes
            self._known_ports = known
        except Exception:  # noqa: BLE001 -- enrichment must not undo scalars
            pass

    def update_pairs(self, pair_result: object, *, state_dir: object = None) -> None:
        """Record the ranked-first class pair for bubble viz fallback.

        ``pair_result`` is a ``PairLoopResult`` -- **not** a pair. Its
        ``pairs`` field is already ranked turns-ascending, so ``pairs[0]``
        is the cheapest known class loop.

        Retention mirrors ``update`` / ``best_chain``:

        * no ``pairs`` attribute / ``None`` result -> not seen; retain last.
        * empty and ``reason == no_world_model`` -> not seen; retain last
          (there was no map to search — same honesty gate as chains).
        * empty for any other reason -> clear ``best_pair``.
        * non-empty -> retain ``pairs[0]``; refresh port class / known-port
          caches from the world model so pair bubbles keep real class
          labels even when the priced-chain half cleared them on
          ``no_closed_cycle``.

        Never invents a margin onto the pair. Never merges the pair onto
        daemon ``status`` JSON.
        """
        try:
            if pair_result is None:
                return
            pairs = getattr(pair_result, "pairs", None)
            if pairs is None:
                return
            if not pairs:
                if getattr(pair_result, "reason", None) == _REASON_NO_WORLD_MODEL:
                    return
                self._best_pair = None
                return
            self._best_pair = pairs[0]
        except Exception:  # noqa: BLE001 -- hostile shape is unknown, not a crash
            return
        try:
            classes, known = _port_snapshot_from_world(
                getattr(pair_result, "world_id", None), state_dir=state_dir
            )
            # Only overwrite when the snapshot actually found something —
            # a hostile/empty world_id must not wipe maps the chain half
            # already enriched on the same tick.
            if classes or known:
                self._port_classes = classes
                self._known_ports = known
        except Exception:  # noqa: BLE001 -- enrichment must not undo the pair
            pass

    @property
    def seen(self) -> bool:
        return self._seen

    @property
    def best_chain(self) -> object | None:
        """Global longest ranked chain (GOALS hops); never on status JSON."""
        return self._best_chain

    @property
    def best_pair(self) -> object | None:
        """Ranked-first class pair for bubble fallback; never on status JSON."""
        return self._best_pair

    def _chain_includes_sector(self, chain: object, sector: int) -> bool:
        try:
            sectors = getattr(chain, "sectors", None)
            if sectors is None and isinstance(chain, dict):
                sectors = chain.get("sectors")
            if sectors is None:
                return False
            return sector in sectors
        except Exception:  # noqa: BLE001
            return False

    def _bubble_priced_chain(self, current_sector: object = None) -> object | None:
        """Priced subject for the strip: local cycle if any, else global first."""
        ranked = self._ranked_chains
        if not ranked:
            return self._best_chain
        cur: int | None
        try:
            cur = int(current_sector) if current_sector is not None else None  # type: ignore[arg-type]
        except (TypeError, ValueError):
            cur = None
        if cur is not None:
            for chain in ranked:
                if self._chain_includes_sector(chain, cur):
                    return chain
        return ranked[0]

    def bubble_subject(
        self, current_sector: object = None
    ) -> tuple[object | None, str | None]:
        """Prefer a priced cycle through ``current_sector`` when one exists.

        Else the global ranked-first ``chains[0]``. Else adapt ``best_pair``
        as a 2-hop cycle.

        Returns ``(chain_like, caption)``. Caption is ``"class pair"`` for a
        completed priced miss, or ``"class pair · search incomplete"`` when
        the priced half truncated empty (WO-CHAIN-BUBBLE-TRUNCATION-CAPTION).
        Never claim credits/turn for class pairs.

        GOALS hop scalars still come from ``best_chain`` / ``chains[0]``
        (global longest) — only this strip selection is local-preferring.
        """
        priced = self._bubble_priced_chain(current_sector)
        if priced is not None:
            return priced, None
        if self._best_pair is not None:
            adapted = pair_as_chain_like(self._best_pair)
            if adapted is not None:
                if self._priced_search_incomplete:
                    return adapted, "class pair · search incomplete"
                return adapted, "class pair"
        return None, None

    @property
    def port_classes(self) -> dict[int, str]:
        """Sector → class cache for bubble labels (may be empty)."""
        return dict(self._port_classes)

    @property
    def known_ports(self) -> set[int]:
        """Sectors with a non-``None`` port record; never on status JSON."""
        return set(self._known_ports)

    def merge(self, status: object) -> dict | None:
        """``status`` with the cached scalars added; never mutates the input.

        Returns the argument unchanged when it is not a dict (the provider's
        own "no status" signal must survive untouched), and adds nothing before
        a discovery has been seen.

        **Does not clobber.** A key the caller already supplied with a
        non-``None`` value wins. Today the daemon emits neither field -- checked,
        not assumed -- so this changes nothing now; it means that if a future
        producer starts supplying them, this cache cannot silently overwrite a
        fresher value with a stale one.
        """
        if not isinstance(status, dict):
            return status
        if not self._seen:
            return status
        merged = dict(status)
        if merged.get(HOPS_KEY) is None:
            merged[HOPS_KEY] = self._hops
        if merged.get(UNIT_KEY) is None:
            merged[UNIT_KEY] = self._unit
        return merged


    def wrap(self, provider):
        """``provider`` with these scalars merged into whatever it returns.

        The overlay belongs here rather than inside `app._daemon_status_
        provider` because it is not part of polling the daemon: the daemon
        does not carry these fields and is not being asked to. Wrapping keeps
        that poller's signature (and the several tests that substitute a
        scripted one-argument factory for it) untouched, and means any status
        source at all picks up the scalars.

        A ``None`` provider wraps to ``None`` -- an absent status source stays
        absent rather than becoming a callable returning a chain-only dict.
        """
        if provider is None:
            return None

        def _merged():
            return self.merge(provider())

        return _merged


def as_chain_like(hops: object, unit: object) -> dict | None:
    """Re-pack ``(hops, unit)`` into the shape ``chain_hop_count_and_unit``
    reads, for handing to ``infer_coach_triggers(chain=…)``.

    The exact inverse of `chain_units.chain_hop_count_and_unit` over the
    library-row form, kept **here in one named place** rather than inlined at
    the call site: the trigger map takes a chain-like value, the status dict
    carries scalars, and something has to bridge them. Doing it once, named and
    tested, is what stops a second ad-hoc re-derivation appearing the next time
    a panel wants the same thing.

    ``None`` when there is no usable hop count -- the caller then passes no
    chain at all, and the fail-closed trigger map simply omits
    ``chain_opportunity``.
    """
    if isinstance(hops, bool) or not isinstance(hops, int):
        return None
    if hops <= 0:
        return None
    source = "discovered" if unit == "hops" else "recorded"
    return {"source": source, "steps": hops}
