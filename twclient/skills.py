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
"""

import json
import re
import time
from pathlib import Path

from .classify import classify_screen

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
    failing one."""

    def __init__(self, step_i, expected, actual, screen, results):
        self.step_i = step_i
        self.expected = expected
        self.actual = actual
        self.screen = screen
        self.results = results
        super().__init__(f"step {step_i}: expected {expected!r}, got {actual!r}")

    def as_dict(self):
        return {
            "step_i": self.step_i,
            "expected": self.expected,
            "actual": self.actual,
            "screen": self.screen,
            "results": self.results,
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


def save_skill(name, steps, source="recorded", mined_stats=None, draft=False, skills_dir=None, drafts_dir=None):
    path = skill_path(name, draft=draft, skills_dir=skills_dir, drafts_dir=drafts_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "name": name,
        "created_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,  # "recorded" (tw record) or "mined" (miner.py draft proposal)
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

    @property
    def recording(self):
        return self.active_name is not None

    def start(self, name=None):
        if self.recording:
            raise SkillError(f"already_recording:{self.active_name}")
        self.active_name = name or auto_capture_name()
        self._steps = []
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
        name, steps = self.active_name, self._steps
        self.active_name = None
        self._steps = []
        path = save_skill(name, steps, source="recorded", skills_dir=self.skills_dir)
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


def replay_skill(session, skill, params=None, step_timeout=8.0):
    """Re-issue `skill`'s steps via `session.send` + `wait_settle`,
    validating each step's actual post-classification against what was
    recorded/mined. Returns the list of per-step results on full success;
    raises ReplayDivergence (carrying every result up to and including
    the failing step) the instant reality disagrees -- never presses on
    past a surprise (DESIGN-v2 11b)."""
    results = []
    for i, step in enumerate(skill["steps"]):
        input_text = _apply_params(step["input"], params)
        session.send(input_text, enter=True, secret=False)
        reason, elapsed = session.wait_settle(wait_prompt=step.get("wait_prompt"), timeout=step_timeout)
        rows = session.render()
        text = session.render_text(rows)
        prompt = rows[-1].strip() if rows else ""
        actual = classify_screen(text, prompt)
        expected = step.get("expected_post_class")
        results.append(
            {"step": i, "input": input_text, "expected": expected, "actual": actual, "settled_reason": reason}
        )
        surprised = actual == "unknown" or (expected is not None and actual != expected)
        if surprised:
            raise ReplayDivergence(step_i=i, expected=expected, actual=actual, screen=rows, results=results)
    return results


def play_skill(session, skill, cycles, floor=None, params=None, step_timeout=8.0):
    """Loop `replay_skill()` for automated unattended playback (11d),
    bounded by two independent rails: `cycles` (hard cap, itself capped
    at `_MAX_PLAY_CYCLES`) and `floor` (stop-loss -- checked BEFORE every
    cycle so a losing run never digs itself deeper). `tw watch`/
    `tw spectate` already give a human a live view of whatever this is
    doing -- no separate streaming path needed here; this stays a single
    bounded dispatch, the same shape as `ensure`'s login automaton."""
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
            results = replay_skill(session, skill, params=params, step_timeout=step_timeout)
        except ReplayDivergence as e:
            return {"halted": "surprise", "cycles_completed": cycle, "divergence": e.as_dict(), "trace": trace}
        trace.append({"cycle": cycle, "steps": results})
    return {"halted": "cycles_complete", "cycles_completed": cycles, "trace": trace}
