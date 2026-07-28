"""The Trade-Loop-Chains library popup — canon's ``L)chains``
(WO-PLAY-AUTOLOOP-START).

Pure: no filesystem, no session, no curses. Formats whatever
``loops.store.read_loop_store`` found (plus, display-only, whatever
discovered-chains payload the caller passed in — see "What this is NOT")
and answers which TAUGHT row is selected; ``app.py::_run_play`` owns the
state transitions and the one call that spends, and ``screens.py`` owns
drawing. Same split ``teachband`` / ``autoloop_controls`` / ``panic``
already use.

# Why ``L`` and not another free letter

``canon/surfaces/mode-line-and-teach-controls.md`` §"The operate-the-APP
control cluster (N5)" names the cluster's hint band, and three canon files
render it identically: ``^A)ode  A)nalyze  R)ecord  T)rigger  L)chains  P
panic``. ``L`` is *already* canon's letter for this affordance —
``autoloop_controls.py`` declined it for the relaunch offer on exactly that
reservation and took ``G``. Any other letter here would have squatted a
non-canon key that this popup would later have to take back.

# What this is NOT

Canon's cluster entry calls the popup "a modal listing the taught trade-loop
chains the human can launch". **Taught** is the load-bearing word for
ARMING: ``rows`` lists only macros a human already demonstrated, read from
the shipped loop store, and those rows are the only thing ``selected()`` can
return — the only shape the arm path can ever receive. Since
WO-CHAINS-TUI-FULL the popup ALSO DISPLAYS a separate read-only "Discovered
profit chains" section (``ChainsSession.discovered``, a
``chain_search.recompute``-shaped payload the CALLER passes in): display
only, visually distinct (``detected`` provenance tag, no selection marker),
and structurally non-armable — a discovered chain never enters ``rows``,
the cursor never traverses it, and ``selected()`` cannot express it. The
invariant is **never armable**, not never displayed. This module still runs
no discovery of its own — no EV, no priority engine, no chain-finder import
(``chain_search_view`` is a pure formatter, not a finder); ``app.py``
computes the payload and passes it in (WO-PLAY-AUTOLOOP-START Scope 4
posture, re-scoped by WO-CHAINS-TUI-FULL).

# The money-path posture

Canon §"Confirm-gate — never one keystroke to live money": "selecting a chain
or launching a run **arms** a pending action and raises an explicit confirm
prompt ... only a deliberate second confirm fires it. A bare Enter must never
fire a launch." So ``Enter`` on a row produces an *intent to arm*, never a
start: the gate mechanics stay ``cockpit.armconfirm``'s job (``y``/``Y``
only, default-deny), reused verbatim. Nothing in this module can start a run
— it has no adapter import and no send path, by construction.

``compose_arm_action`` says **"one pass"** rather than a cycle count because
one pass is what the daemon does: ``autoloop_start`` refuses ``cycles``
outright (``session/protocol.py::_dispatch_autoloop_start``). Canon asks the
gate to show "how many cycles"; the honest answer on tip is "one", and a
prompt offering a number the runtime would refuse is the kind of agreement
this surface exists to prevent.

Hardening family (matches ``panic.py`` / ``armconfirm.py`` /
``autoloop_controls.py``): every public function is never-raises regardless
of input shape.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

# Pure FORMATTER, not a finder: `chain_search_view` imports nothing of this
# package and runs no discovery — it only renders a `chain_search`-shaped
# payload. Importing it is what "reuse the wording discipline, do not
# re-derive it" means concretely: the PARTIAL banner and the
# truncated-empty-is-not-absence wording live in exactly one module.
from tw2002_aiclient import chain_search_view as _search_view

# `L` — canon's own letter for this popup; see the module docstring. Both
# cases bind, matching the A/R/T teach band's posture.
_CHAINS_OFFER_KEYS = frozenset({ord("l"), ord("L")})

# Canon's glyph vocabulary (`canon/surfaces/trainer-cockpit.md` §"Glyph /
# status-marker vocabulary"): `▸` the selected/armed row marker, `○ ○` the
# empty-chain placeholder. The `sel` ASCII twin is `>`, taken from
# `screens.py`'s `_GLYPHS_ASCII` rather than re-invented here -- the glyph
# table dedupe WO exists because two tables drift.
SELECTED_UNICODE = "▸"
SELECTED_ASCII = ">"
EMPTY_UNICODE = "○ ○"
EMPTY_ASCII = "o o"
EMPTY_TEXT = "no trade loop yet"
# What an unreadable / partial store says instead of the empty placeholder.
# "could not read" is a different fact from "none taught", and only one of
# them is safe to show an operator who is deciding whether their macros
# survived.
UNREADABLE_TEXT = "loop store unreadable — cannot list"

# The honest-unknown mark, same rule `list_view` and `covermeter` follow.
UNKNOWN = "?"

TITLE = "Taught loops"

# WO-CHAINS-TUI-FULL: what the discovered section says when NO usable
# payload was passed in (finder raised, profile could not form a world_id,
# or a caller predating the section). The same fail-closed split the taught
# side makes with `UNREADABLE_TEXT`: "could not compute" is a different
# fact from "computed, none exist", and rendering the second when only the
# first is true would claim an absence nobody established. The
# computed-but-empty wordings (reason text, and the truncated-empty hedge)
# belong to `chain_search_view` and are NOT re-derived here.
DISCOVERY_UNAVAILABLE_TEXT = "chain discovery unavailable — cannot list"


def _usable_discovered(payload: object) -> object | None:
    """*payload* when it is a renderable discovered-chains result (anything
    carrying a ``chains`` attribute, the one field the formatter branches
    on), else ``None``. The single predicate both `ChainsSession.open` and
    `compose_chain_lines` use, so the two sites cannot drift: junk shapes
    map to the honest "unavailable" rendering rather than falling through
    `chain_search_view`'s default empty text — which reads as an
    ESTABLISHED absence and must not be reachable from garbage."""
    return payload if hasattr(payload, "chains") else None


def resolve_chains_offer_key(key: object) -> bool:
    """``True`` when ``key`` opens/closes the chains popup. ``bool`` is
    rejected even though ``isinstance(True, int)`` holds — the same
    ``panic.resolve_panic_key`` guard against ``True == 1`` matching a
    keycode by accident. Never raises."""
    if isinstance(key, bool) or not isinstance(key, int):
        return False
    return key in _CHAINS_OFFER_KEYS


def playable_loops(store_result: object) -> list[dict]:
    """The rows a human could actually arm, from a ``read_loop_store``
    result. Never raises; an unreadable or malformed store yields ``[]``.

    Two exclusions, both deliberate:

    * **Drafts.** A draft is pre-approval (``cockpit/draft_approve.py``:
      "promotion to a playback-eligible stub"), so offering one to arm would
      route around the approval it is still waiting for.
    * **Zero-step macros.** A macro with no steps cannot replay anything;
      listing it as armable invites a confirm prompt for a run that does
      nothing, which is worse than its absence because it looks like a
      working affordance.

    A row missing a usable ``name`` is dropped rather than rendered blank —
    the name is what ``autoloop_start`` sends, so a nameless row could only
    ever produce ``missing_name``.
    """
    if not isinstance(store_result, Mapping):
        return []
    # The documented top-level field -- "``loops`` (real rows only, blessed
    # before drafts)". Deliberately NOT a walk of ``roots``: those are
    # per-directory outcomes whose rows are the same objects, so summing them
    # would list a macro twice the moment a second root is consulted.
    loops = store_result.get("loops")
    if not isinstance(loops, Sequence) or isinstance(loops, (str, bytes)):
        return []
    out: list[dict] = []
    for loop in loops:
        if not isinstance(loop, Mapping):
            continue
        if loop.get("draft"):
            continue
        name = loop.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        steps = loop.get("steps")
        if not isinstance(steps, int) or isinstance(steps, bool) or steps < 1:
            continue
        out.append(dict(loop))
    return out


def store_status(store_result: object) -> str:
    """The store's own ``status`` (``"ok"`` / ``"partial"`` / ``"unreadable"``),
    or ``"unreadable"`` when the result is not a readable shape.

    Exists because ``read_loop_store``'s contract names ``status`` as "the
    field a caller must branch on before saying anything about how many loops
    exist". An empty list means "none taught" ONLY under ``ok``; under any
    other status it means "could not establish", and the popup must say so.
    Defaulting the unknown case to ``"unreadable"`` rather than ``"ok"`` is
    the fail-closed direction: the cost of wrongly saying "unknown" is a
    confused operator, and the cost of wrongly saying "none taught" is an
    operator who believes their macros are gone.
    """
    if not isinstance(store_result, Mapping):
        return "unreadable"
    status = store_result.get("status")
    if status in ("ok", "partial", "unreadable"):
        return status
    return "unreadable"


class ChainsSession:
    """Open/closed state and the row cursor for the popup.

    Shaped after ``analyze.AnalyzeSession`` so the cockpit has one overlay
    idiom rather than two. Never auto-opens: only an explicit ``L`` (or the
    matching close action) moves this state, the same sovereignty posture
    the explore and relaunch offers take — a gate the human did not ask for
    is a gate that can be dismissed by reflex.
    """

    def __init__(self) -> None:
        self.is_open: bool = False
        self.rows: list[dict] = []
        self.index: int = 0
        # Carried so the EMPTY rendering can tell "none taught" from "could
        # not read the store" -- see `store_status`.
        self.status: str = "unreadable"
        # WO-CHAINS-TUI-FULL: the DISPLAY-ONLY discovered-chains payload
        # (`chain_search.recompute`-shaped, passed in by the caller). Kept
        # deliberately OUTSIDE `rows` and never row-shaped: `move` walks
        # `rows` and `selected` indexes `rows`, so there is no path — not a
        # guard, an absent path — by which a discovered chain can sit under
        # the cursor or reach the arm gate.
        self.discovered: object | None = None

    def open(
        self,
        rows: object = None,
        status: object = "unreadable",
        discovered: object = None,
    ) -> None:
        """Open over *rows*. A non-list, or anything else unusable, opens an
        EMPTY popup rather than staying closed: "the store had nothing" is a
        thing the operator needs to see, and a key that silently does
        nothing reads as a broken build.

        ``status`` defaults to ``"unreadable"``, not ``"ok"``: a caller that
        forgets to pass it gets the honest-unknown rendering rather than a
        fabricated "no trade loop yet".

        ``discovered`` (display-only, never armable) defaults to ``None``
        for the same fail-closed reason: no payload renders as "discovery
        unavailable", never as a fabricated "no discovered profit chains".
        A junk shape is folded to ``None`` rather than handed to the
        formatter, whose default empty text claims an established absence."""
        self.rows = [r for r in rows if isinstance(r, Mapping)] if isinstance(rows, list) else []
        self.is_open = True
        self.index = 0
        self.status = status if status in ("ok", "partial", "unreadable") else "unreadable"
        self.discovered = _usable_discovered(discovered)

    def close(self) -> None:
        self.is_open = False
        self.index = 0

    def move(self, delta: object) -> None:
        """Move the cursor, clamped to the list. Clamped rather than
        wrapping: wrapping past the end of a list of live-money actions puts
        a different row under a confirm the operator may already be
        reaching for. Never raises."""
        if not self.rows:
            self.index = 0
            return
        if isinstance(delta, bool) or not isinstance(delta, int):
            return
        self.index = max(0, min(len(self.rows) - 1, self.index + delta))

    def selected(self) -> dict | None:
        """The row under the cursor, or ``None`` when there is nothing to
        arm. ``None`` is what stops the arm intent from ever reaching the
        adapter with a guessed name."""
        if not self.rows:
            return None
        if not 0 <= self.index < len(self.rows):
            return None
        return self.rows[self.index]


def compose_arm_action(loop: object) -> str:
    """The confirm line's meaning clause — handed to
    ``armconfirm.compose_arm_confirm_line`` as its ``action`` text, which
    appends canon's `` LIVE?  y/N`` suffix.

    Renders ``"Arm {name} — one pass, {n} steps"``. ``{n}`` is ``"?"`` for
    any non-``int``/negative/``bool`` step count — unknown is not zero, the
    same honest-``?`` rule ``compose_relaunch_confirm_action`` follows. A
    loop with no usable name renders the fallback rather than an empty
    quote, so the prompt can never read as "Arm  — one pass".
    """
    name = None
    steps: object = None
    if isinstance(loop, Mapping):
        name = loop.get("name")
        steps = loop.get("steps")
    if not isinstance(name, str) or not name.strip():
        name = UNKNOWN
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        n = UNKNOWN
    else:
        n = str(steps)
    return f"Arm {name.strip()} — one pass, {n} steps"


def compose_chain_lines(
    session: object,
    *,
    unicode_ok: bool = True,
    width: int = 40,
) -> list[str]:
    """The popup's body lines. Never raises; a session of the wrong shape
    renders the empty placeholder rather than blowing up the draw pass.

    TWO independent sections, each rendered regardless of the other's
    emptiness (WO-CHAINS-TUI-FULL — the old taught-empty early-return would
    have swallowed a present discovered section):

    * **Taught** — the selected row carries canon's ``▸`` (ASCII ``>``);
      unselected rows are indented by the same width so the list does not
      shift horizontally as the cursor moves. An empty store renders canon's
      ``○ ○  no trade loop yet`` placeholder — a stated negative, never a
      blank box — and only under ``status == "ok"``; anything else renders
      the could-not-establish line instead.
    * **Discovered** — display-only, never armable: ``session.discovered``
      is formatted by ``chain_search_view.format_profit_chain_lines``
      (PARTIAL banner, truncated-empty hedge and all — the wording lives
      there, not here), so every row carries its ``detected`` tag and none
      can carry the selection marker. No payload renders the honest
      "unavailable" line, never a fabricated absence.
    """
    sel = SELECTED_UNICODE if unicode_ok else SELECTED_ASCII
    empty = EMPTY_UNICODE if unicode_ok else EMPTY_ASCII
    try:
        w = int(width)
    except Exception:  # noqa: BLE001
        w = 40
    w = max(12, w)
    rows = getattr(session, "rows", None)
    index = getattr(session, "index", 0)
    lines = [TITLE]
    if not isinstance(rows, list) or not rows:
        # The honest empty, reached ONLY when the store established the
        # negative. `read_loop_store`'s contract: `status` is "the field a
        # caller must branch on before saying anything about how many loops
        # exist". A store that could not be read renders as unknown -- the
        # same rule `loops/list_view.py` enforces for the CLI listing, and
        # the reason an absent status defaults to "unreadable" here.
        if getattr(session, "status", "unreadable") == "ok":
            lines.append(f"{empty}  {EMPTY_TEXT}")
        else:
            lines.append(f"{UNKNOWN}  {UNREADABLE_TEXT}")
    else:
        if isinstance(index, bool) or not isinstance(index, int):
            index = 0
        for i, row in enumerate(rows):
            name = row.get("name") if isinstance(row, Mapping) else None
            if not isinstance(name, str) or not name.strip():
                name = UNKNOWN
            steps = row.get("steps") if isinstance(row, Mapping) else None
            if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
                steps_text = f"{UNKNOWN} steps"
            else:
                steps_text = f"{steps} steps"
            marker = f"{sel} " if i == index else "  "
            name_w = max(4, w - len(marker) - len(steps_text) - 2)
            lines.append(f"{marker}{name.strip()[:name_w]:<{name_w}}  {steps_text}")
    # The discovered section — appended AFTER the taught rows (tests pin the
    # taught rows at fixed indices) and unconditionally, so zero taught
    # loops can never swallow it.
    lines.append("")
    discovered = _usable_discovered(getattr(session, "discovered", None))
    if discovered is None:
        lines.append(_search_view.TITLE)
        lines.append(f"{UNKNOWN}  {DISCOVERY_UNAVAILABLE_TEXT}")
    else:
        lines.extend(
            _search_view.format_profit_chain_lines(
                discovered, unicode_ok=unicode_ok, width=w
            )
        )
    return lines
