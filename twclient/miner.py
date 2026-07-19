"""Profit-miner (DESIGN-v2.md §3 v2.1 item 11c, C10).

Mines `twclient/ledger.py`'s JSONL trace for recurring
`(pre_class, input-subsequence) -> post_class` patterns, ranked by profit
rate -- credits-per-turn, falling back to credits-per-action when a
subsequence never consumed a turn -- and proposes the top-ranked
PROFITABLE ones as DRAFT skills at `state/skills/_drafts/` for an AI/
human to review and bless (`twclient.skills.save_skill(..., draft=False)`
promotes one to the real skills directory).

A ledger entry doesn't store its own pre-classification (state_parser's
"omit what's unknown" convention -- see ledger.py); it's derived here as
the PREVIOUS entry's `settled_class`, since entries are sequential
do/send dispatches against one continuously-driven session.

Deliberately a bounded sliding-window count, not a general sequence-
mining algorithm (suffix trees, PrefixSpan, ...) -- this repo's
prove-the-need-first discipline (DESIGN-v2.md §4): the ledger this mines
is small enough that an O(N * window) scan is instant, and a fancier
algorithm has nothing to earn its keep against yet.
"""

import re
from collections import defaultdict

from .ledger import read_entries
from .skills import save_skill

_MIN_WINDOW = 2
_MAX_WINDOW = 10
_DEFAULT_MIN_SUPPORT = 2
_DEFAULT_TOP_K = 3

# Live-caught (this build's own money-loop proof, 2026-07-19): a real
# port ALWAYS haggles, so the quantity/offer steps of an otherwise
# identical buy-then-sell loop are numerically different every single
# occurrence (146 credits one round, 158 the next -- never the literal
# same string). Matching signatures on raw input text therefore never
# recurs at the step that actually carries the profit -- either the
# window includes the ever-changing numeral (support stuck at 1, filtered
# out) or excludes it (support recurs, but credits look like 0). Numeric
# inputs are wildcarded to "<NUM>" for GROUPING only; the real observed
# values are preserved in `sample_steps` (and reward math already comes
# from the entry's `reward` field, never from the input text, so summing
# is unaffected either way).
_NUMERIC_RE = re.compile(r"^\d[\d,]*$")


def _normalize_input(text):
    if isinstance(text, str) and _NUMERIC_RE.match(text):
        return "<NUM>"
    return text


def _turns_spent(entry):
    """Turn COST of one entry (>= 0), or None if turns_left wasn't
    parseable on either side of it."""
    d = entry.get("reward", {}).get("d_turns")
    if d is None:
        return None
    return max(-d, 0)


def _credits_delta(entry):
    return entry.get("reward", {}).get("d_credits") or 0


def mine_patterns(entries=None, min_support=_DEFAULT_MIN_SUPPORT, min_window=_MIN_WINDOW, max_window=_MAX_WINDOW,
                   ledger_path=None):
    """Slide every window length in `[min_window, max_window]` over the
    ledger, group occurrences by `(pre_class, input-tuple, post_class)`,
    and rank the ones recurring at least `min_support` times by average
    credits-per-turn (falling back to credits-per-action when no
    occurrence of that window ever consumed a turn). Returns a list of
    pattern dicts, richest-first."""
    if entries is None:
        entries = read_entries(ledger_path)
    groups = defaultdict(list)  # (pre_class, inputs, post_class) -> [occurrence, ...]

    for window in range(min_window, max_window + 1):
        for start in range(0, len(entries) - window + 1):
            chunk = entries[start : start + window]
            raw_inputs = tuple(e.get("input") for e in chunk)
            if any(i == "<redacted>" for i in raw_inputs):
                continue  # never mine/replay a pattern built on a redacted secret
            inputs = tuple(_normalize_input(i) for i in raw_inputs)
            pre_class = entries[start - 1].get("settled_class") if start > 0 else None
            post_class = chunk[-1].get("settled_class")
            d_credits_total = sum(_credits_delta(e) for e in chunk)
            turns_list = [t for t in (_turns_spent(e) for e in chunk) if t is not None]
            turns_total = sum(turns_list) if turns_list else None
            groups[(pre_class, inputs, post_class)].append(
                {
                    "d_credits": d_credits_total,
                    "turns_spent": turns_total,
                    # TW-03 parity for mined drafts (P0): the sector the
                    # chunk's FIRST row was standing in before its own
                    # input was sent -- the same start_anchor semantic
                    # SkillRecorder.start() already persists for a
                    # human-recorded capture. A ledger row lacking
                    # `pre_state`/`sector` (an older row, or a test
                    # fixture that predates it) yields None here, same
                    # as a legacy skill -- never invented, only read.
                    "start_anchor": (chunk[0].get("pre_state") or {}).get("sector"),
                    "steps": [
                        {"input": e.get("input"), "wait_prompt": None, "expected_post_class": e.get("settled_class")}
                        for e in chunk
                    ],
                }
            )

    patterns = []
    for (pre_class, inputs, post_class), occurrences in groups.items():
        support = len(occurrences)
        if support < min_support:
            continue
        avg_credits = sum(o["d_credits"] for o in occurrences) / support
        turn_occurrences = [o for o in occurrences if o["turns_spent"]]
        cr_per_turn = (
            sum(o["d_credits"] / o["turns_spent"] for o in turn_occurrences) / len(turn_occurrences)
            if turn_occurrences
            else None
        )
        cr_per_action = avg_credits / len(inputs)
        patterns.append(
            {
                "pre_class": pre_class,
                "inputs": list(inputs),
                "post_class": post_class,
                "support": support,
                "cr_per_turn": cr_per_turn,
                "cr_per_action": cr_per_action,
                "sample_steps": occurrences[0]["steps"],
                # Same "occurrences[0]" convention sample_steps already
                # uses -- one anchor per pattern, from its first-seen
                # occurrence.
                "start_anchor": occurrences[0]["start_anchor"],
            }
        )

    patterns.sort(
        key=lambda p: (p["cr_per_turn"] if p["cr_per_turn"] is not None else float("-inf"), p["cr_per_action"]),
        reverse=True,
    )
    return patterns


def propose_drafts(patterns, top_k=_DEFAULT_TOP_K, drafts_dir=None):
    """Write the top `top_k` PROFITABLE (cr_per_turn or cr_per_action > 0)
    patterns as draft skills for an AI/human to review and bless --
    never floods `state/skills/_drafts/` with every recurring-but-
    unprofitable pattern the miner also found."""
    proposed = []
    profitable = [p for p in patterns if (p["cr_per_turn"] or 0) > 0 or (p["cr_per_action"] or 0) > 0]
    for i, pattern in enumerate(profitable[:top_k]):
        slug = "_".join(pattern["inputs"]) or "empty"
        safe_slug = "".join(c if c.isalnum() else "_" for c in slug)[:40]
        name = f"mined-{i}-{safe_slug}"
        path = save_skill(
            name,
            pattern["sample_steps"],
            source="mined",
            mined_stats={
                "pre_class": pattern["pre_class"],
                "support": pattern["support"],
                "cr_per_turn": pattern["cr_per_turn"],
                "cr_per_action": pattern["cr_per_action"],
            },
            # TW-03 parity (P0): a mined draft is just as replayable-from-
            # the-wrong-sector as a recorded one -- thread the mined
            # origin sector through so `_check_start_anchor()`'s guard
            # covers it too, instead of every mined draft silently
            # defaulting to the unanchored legacy path.
            start_anchor=pattern.get("start_anchor"),
            draft=True,
            drafts_dir=drafts_dir,
        )
        proposed.append({"name": name, "path": str(path), **pattern})
    return proposed


def mine_ledger(min_support=_DEFAULT_MIN_SUPPORT, top_k=_DEFAULT_TOP_K, entries=None, propose=True,
                 ledger_path=None, drafts_dir=None):
    """The `tw patterns`/`tw mine` entry point: mine + (by default)
    propose draft skills in one call."""
    patterns = mine_patterns(entries=entries, min_support=min_support, ledger_path=ledger_path)
    drafts = propose_drafts(patterns, top_k=top_k, drafts_dir=drafts_dir) if propose else []
    return {"patterns": patterns, "drafts": drafts}
