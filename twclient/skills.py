"""Skill record/replay (DESIGN-v2.md §3 v2.1 item 11b, C3) + automated
playback (item 11d).

A "skill" is a named, saved sequence of steps -- `{input, wait_prompt,
expected_post_class}` -- captured live between `tw record start [name]`
and `tw record stop` (this module's `SkillRecorder`), or proposed by
`twclient/miner.py` as a DRAFT from a recurring profitable ledger
subsequence. `tw replay <name>` re-issues a skill's steps and HALTS the
moment reality diverges from what was recorded/mined, rather than
pressing on blind; `tw play <name> --cycles N` loops `replay_skill()`
with stop-loss/cycle-cap rails for unattended automated playback (11d).

Skills live at `state/skills/<name>.json` (recorded/blessed) and
`state/skills/_drafts/<name>.json` (miner proposals awaiting a human/AI
to bless them by re-saving into the top-level directory).

**TW-03 start-anchor (P0, near-miss-autopilot class):** a live incident
replayed a skill verbatim from the wrong sector and warped the ship off
into a stale sector -- a skill's recorded steps only make sense from the
sector they were recorded in, and nothing was checking that before this.
Every skill now carries a `start_anchor` (the sector `tw record start`
was standing in, persisted by `SkillRecorder`/`save_skill`); replay/play
validates the CURRENT sector against it before the first send of every
cycle -- see `_check_start_anchor()`. A skill saved before this field
existed has `start_anchor: null` and refuses to replay by default (never
silently unanchored) unless the caller passes `force=True`.

**TW-04 replay-ledgering (P0):** a second live incident -- a replayed
buy that moved -9,047cr left NO Trace-Ledger row, because `replay_skill`
sends via `session.send()` directly rather than through protocol.py's
`do`/`send` dispatch (the only place that currently calls
`ledger.record_do()`). `replay_skill`/`play_skill` now take an optional
`ledger` (a `ledger.LedgerWriter`-shaped object) and `session_id`, and
record one ledger row per step with `actor="trainer"` -- see
`knowledge/architecture/autonomy-loop.md` for the `actor`/`session_id`
schema this is wired against. Deliberately NOT tagged with `capture=`:
that field means "the currently-open `tw record` window" elsewhere in
this codebase, and reusing it here would silently inflate
`protocol.py`'s demo-profit sum (which assumes `capture`-tagged entries
belong to the ONE original recording) every time a recorded skill gets
replayed. `ledger`/`session_id` default to `None` (no-op) so callers
that don't wire them up yet keep working unchanged.
"""

import json
import re
import time
from pathlib import Path

from .classify import classify_screen
from .settle import send_and_confirm
from .state_parser import parse_state

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "state" / "skills"
DRAFTS_DIR = SKILLS_DIR / "_drafts"

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_\-]")

# Rails (DESIGN-v2 11d): this repo's hard-cap ethos applied to an
# unattended playback loop -- `tw play --cycles` cannot request more than
# this regardless of caller intent.
_MAX_PLAY_CYCLES = 50


class SkillError(Exception):
    """Missing/unreadable/invalid skill file, or an invalid record
    request (e.g. starting a capture while one is already open)."""


class ReplayDivergence(Exception):
    """A replayed step's actual outcome didn't match what was recorded
    (or landed on a screen classify.py can't even name) -- raised rather
    than pressed through, per DESIGN-v2 11b/11d's halt-on-surprise
    requirement. Carries every step result up to and including the
    failing one.

    `reason` distinguishes the ordinary "post_class" divergence (a
    step's actual post-classification didn't match what was recorded)
    from `"start_anchor_mismatch"` (TW-03: the CURRENT sector doesn't
    match -- or can't even be read off -- the skill's `start_anchor`,
    checked before step 0 of every cycle, `step_i=-1`) and
    `"confirm_failed"` (TW-02: `settle.send_and_confirm` never
    positively confirmed the step's send -- see `replay_skill`'s
    docstring). All three are a live "reality disagreed with the
    recording" surprise, so all three reuse this one halt-on-surprise
    exception rather than a separate type per case -- a `play_skill()`
    run already treats any `ReplayDivergence` as `"halted": "surprise"`
    with the trace-so-far intact, which is exactly the right outcome
    for a loop that quietly wandered off its anchor sector mid-run, not
    just one that got a bad first launch."""

    def __init__(self, step_i, expected, actual, screen, results, reason="post_class"):
        self.step_i = step_i
        self.expected = expected
        self.actual = actual
        self.screen = screen
        self.results = results
        self.reason = reason
        super().__init__(f"step {step_i}: expected {expected!r}, got {actual!r}")

    def as_dict(self):
        return {
            "step_i": self.step_i,
            "expected": self.expected,
            "actual": self.actual,
            "screen": self.screen,
            "results": self.results,
            "reason": self.reason,
        }


def _safe_name(name: str) -> str:
    safe = _SAFE_NAME_RE.sub("_", name).strip("_")
    if not safe:
        raise SkillError(f"invalid_skill_name:{name!r}")
    return safe


def auto_capture_name() -> str:
    return "capture-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def skill_path(name, draft=False, skills_dir=None, drafts_dir=None):
    base = (drafts_dir if draft else skills_dir) or (DRAFTS_DIR if draft else SKILLS_DIR)
    return Path(base) / f"{_safe_name(name)}.json"


def save_skill(name, steps, source="recorded", mined_stats=None, start_anchor=None, draft=False, skills_dir=None, drafts_dir=None):
    path = skill_path(name, draft=draft, skills_dir=skills_dir, drafts_dir=drafts_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "name": name,
        "created_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,  # "recorded" (tw record) or "mined" (miner.py draft proposal)
        # TW-03: the sector this skill was recorded/mined FROM, or None
        # for a skill saved before this field existed -- always present
        # in the schema (never an absent key) so `.get("start_anchor")`
        # means the same thing whether the file predates this field or
        # was saved with no anchor available. See _check_start_anchor().
        "start_anchor": start_anchor,
        "steps": steps,
    }
    if mined_stats is not None:
        doc["mined_stats"] = mined_stats
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    return path


def load_skill(name, draft=False, skills_dir=None, drafts_dir=None):
    path = skill_path(name, draft=draft, skills_dir=skills_dir, drafts_dir=drafts_dir)
    if not path.exists():
        raise SkillError(f"skill_not_found:{name}")
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise SkillError(f"skill_corrupt:{name}:{e}") from e


class SkillRecorder:
    """Session/daemon-scoped: brackets a `tw record start`/`tw record
    stop` window (11b). Distinct from `ledger.LedgerWriter` -- the ledger
    always records every do/send; this only accumulates steps while a
    capture is open, and produces exactly one artifact (the saved skill)
    at `stop()`."""

    def __init__(self, skills_dir=None):
        self.skills_dir = skills_dir
        self.active_name = None
        self._steps = []
        self._start_anchor = None

    @property
    def recording(self):
        return self.active_name is not None

    def start(self, name=None, start_anchor=None):
        """`start_anchor` (TW-03): the sector the caller was standing in
        when this capture began, if known (e.g. `parse_state(current
        text).get("sector")` -- this class stays session-agnostic, so
        computing that value is the caller's job, same division of
        labor as `record_step()` already has for wait_prompt/
        expected_post_class). Persisted verbatim into the saved skill by
        `stop()` below; `None` if the caller doesn't have/pass one."""
        if self.recording:
            raise SkillError(f"already_recording:{self.active_name}")
        self.active_name = name or auto_capture_name()
        self._steps = []
        self._start_anchor = start_anchor
        return self.active_name

    def record_step(self, input_text, wait_prompt, expected_post_class, secret=False):
        if not self.recording:
            return
        if secret:
            # A password (or any --secret send) mid-capture is dropped,
            # never persisted into a replayable skill file -- the same
            # redaction contract the ledger and transcript log honor.
            return
        self._steps.append(
            {"input": input_text, "wait_prompt": wait_prompt, "expected_post_class": expected_post_class}
        )

    def stop(self):
        if not self.recording:
            return None
        name, steps, start_anchor = self.active_name, self._steps, self._start_anchor
        self.active_name = None
        self._steps = []
        self._start_anchor = None
        path = save_skill(name, steps, source="recorded", start_anchor=start_anchor, skills_dir=self.skills_dir)
        return {"name": name, "steps": len(steps), "path": str(path)}


def _apply_params(input_text, params):
    if not params:
        return input_text
    try:
        return input_text.format(**params)
    except (KeyError, IndexError, ValueError):
        # No matching placeholder for the given params, or a literal
        # '{'/'}' in a captured keystroke -- send it verbatim rather than
        # raising on a false-positive template match.
        return input_text


def _check_start_anchor(session, skill, force):
    """TW-03 safety guard, called before the first send of every
    `replay_skill()` invocation (so `play_skill()`'s per-cycle loop gets
    it re-checked every cycle for free -- see ReplayDivergence's
    docstring for why that's the right behavior for a loop, not just a
    one-off replay).

    Two distinct failure shapes, on purpose:
    - `start_anchor` missing entirely (a skill saved before this field
      existed) -- there is nothing to check reality against, so this is
      a skill-level config problem, not an in-flight surprise: it raises
      plain `SkillError` (an "invalid artifact for safe replay" error,
      same family as a corrupt/missing skill file) and fires identically
      on every cycle, so it's always caught at cycle 0 -- never mid-loop
      only. The ONLY way past it is the caller explicitly passing
      `force=True`; this NEVER silently replays unanchored.
    - `start_anchor` present but the CURRENT sector doesn't match it (or
      can't even be read off the current screen at all) -- a live
      "reality disagrees with the recording" surprise, so it raises
      `ReplayDivergence` (reason="start_anchor_mismatch") exactly like a
      diverged post-classification. `force` does NOT bypass this case --
      forcing past a *detected* mismatch is the exact near-miss this
      guard exists to prevent; `force` only ever waives the
      "nothing-to-check-against" legacy case above.
    """
    start_anchor = skill.get("start_anchor")
    if start_anchor is None:
        if force:
            return
        name = skill.get("name", "?")
        raise SkillError(
            f"missing_start_anchor:{name}: recorded before start-anchor tracking existed, "
            "so the current sector can't be safety-checked against it -- re-record this "
            "skill, or replay with force=True to proceed unanchored at your own risk"
        )
    rows = session.render()
    text = session.render_text(rows)
    current_sector = parse_state(text).get("sector")
    if current_sector != start_anchor:
        raise ReplayDivergence(
            step_i=-1,
            expected=f"sector:{start_anchor}",
            actual=f"sector:{current_sector}" if current_sector is not None else "sector:unknown",
            screen=rows,
            results=[],
            reason="start_anchor_mismatch",
        )


def replay_skill(session, skill, params=None, step_timeout=8.0, force=False, ledger=None, session_id=None):
    """Re-issue `skill`'s steps via `settle.send_and_confirm`, validating
    each step's actual post-classification against what was
    recorded/mined. Returns the list of per-step results on full success;
    raises ReplayDivergence (carrying every result up to and including
    the failing step) the instant reality disagrees -- never presses on
    past a surprise (DESIGN-v2 11b).

    **TW-02 (send/settle race, -75-alignment/false-halt class):** a bare
    `session.send()` + idle-only settle can hand back a screen that only
    LOOKS settled mid-transition (settle.py's own module docstring), and
    an autonomous replay/play/AUTO-LOOP run must never fire the NEXT
    step's send against a screen it hasn't positively confirmed is the
    one it thinks it's looking at. Every step's send now goes through
    `settle.send_and_confirm(confirm_prompt=step.get("wait_prompt"))` --
    the step's own recorded `wait_prompt` when the caller supplied one at
    record time, else `None` (send_and_confirm's own idle+stability-
    recheck fallback, since most recorded steps have no explicit
    wait_prompt at all). `confirmed=False` is itself a surprise: raised
    as `ReplayDivergence(reason="confirm_failed")` BEFORE ever attempting
    to classify the (still possibly unsettled) screen against
    `expected_post_class` -- classifying an unconfirmed screen would
    just relocate the same false-halt/false-pass risk one line down.

    Before the first send, validates the CURRENT sector against the
    skill's `start_anchor` (TW-03) -- see `_check_start_anchor()`;
    `force=True` waives ONLY a missing/legacy anchor, never a detected
    mismatch. `ledger`/`session_id` (TW-04) are optional: when `ledger`
    is given (a `ledger.LedgerWriter`-shaped object), every step's send
    also produces one Trace-Ledger row via `ledger.record_do(...,
    actor="trainer", session_id=session_id)` -- recorded even for a step
    that turns out to be the surprising one (including an unconfirmed
    send), since that's the send most worth having a ledger row for.
    Both default to `None`/no-op so an unwired caller keeps behaving
    exactly as before."""
    _check_start_anchor(session, skill, force)
    results = []
    for i, step in enumerate(skill["steps"]):
        input_text = _apply_params(step["input"], params)
        expected = step.get("expected_post_class")
        pre_text = session.render_text(session.render())
        settled_reason, _elapsed, confirmed = send_and_confirm(
            session, input_text, confirm_prompt=step.get("wait_prompt"), enter=True, secret=False, timeout_s=step_timeout
        )
        rows = session.render()
        text = session.render_text(rows)
        prompt = rows[-1].strip() if rows else ""

        if not confirmed:
            actual = f"unconfirmed_settle:{settled_reason}"
            results.append(
                {"step": i, "input": input_text, "expected": expected, "actual": actual, "settled_reason": settled_reason}
            )
            if ledger is not None:
                ledger.record_do(pre_text, input_text, False, text, actual, actor="trainer", session_id=session_id)
            raise ReplayDivergence(
                step_i=i, expected=expected, actual=actual, screen=rows, results=results, reason="confirm_failed"
            )

        actual = classify_screen(text, prompt)
        results.append(
            {"step": i, "input": input_text, "expected": expected, "actual": actual, "settled_reason": settled_reason}
        )
        if ledger is not None:
            ledger.record_do(pre_text, input_text, False, text, actual, actor="trainer", session_id=session_id)
        surprised = actual == "unknown" or (expected is not None and actual != expected)
        if surprised:
            raise ReplayDivergence(step_i=i, expected=expected, actual=actual, screen=rows, results=results)
    return results


def play_skill(session, skill, cycles, floor=None, params=None, step_timeout=8.0, force=False, ledger=None, session_id=None):
    """Loop `replay_skill()` for automated unattended playback (11d),
    bounded by two independent rails: `cycles` (hard cap, itself capped
    at `_MAX_PLAY_CYCLES`) and `floor` (stop-loss -- checked BEFORE every
    cycle so a losing run never digs itself deeper). `tw watch`/
    `tw spectate` already give a human a live view of whatever this is
    doing -- no separate streaming path needed here; this stays a single
    bounded dispatch, the same shape as `ensure`'s login automaton.

    `force`/`ledger`/`session_id` are forwarded unchanged into every
    cycle's `replay_skill()` call (see its docstring for TW-03/TW-04) --
    a start-anchor mismatch on cycle 2+ (the loop wandered off where it
    started) surfaces exactly like any other mid-run surprise, via the
    existing `except ReplayDivergence` below."""
    if cycles > _MAX_PLAY_CYCLES:
        raise SkillError(f"cycles_exceeds_cap:{cycles}>{_MAX_PLAY_CYCLES}")
    trace = []
    for cycle in range(cycles):
        if floor is not None:
            rows = session.render()
            text = session.render_text(rows)
            from .ledger import snapshot_state

            credits = snapshot_state(text).get("credits")
            if credits is not None and credits <= floor:
                return {"halted": "floor_reached", "cycles_completed": cycle, "credits": credits, "trace": trace}
        try:
            results = replay_skill(
                session,
                skill,
                params=params,
                step_timeout=step_timeout,
                force=force,
                ledger=ledger,
                session_id=session_id,
            )
        except ReplayDivergence as e:
            return {"halted": "surprise", "cycles_completed": cycle, "divergence": e.as_dict(), "trace": trace}
        trace.append({"cycle": cycle, "steps": results})
    return {"halted": "cycles_complete", "cycles_completed": cycles, "trace": trace}
