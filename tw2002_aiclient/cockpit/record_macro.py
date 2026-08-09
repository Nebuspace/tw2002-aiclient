"""R Record scaffold — WO-P5-067.

``R`` in the Play cockpit starts capturing a human-keystroke demonstration
into a macro document; a second ``R`` (or :meth:`RecordSession.stop`)
finalises and saves it.

# What this is

Canon (``canon/surfaces/mode-line-and-teach-controls.md`` §R ~63-65):

    R — Record.  Capture a macro: record the human's own keystroke
    demonstration as a replayable taught sequence.  The captured macro is
    the ``do`` a rule will later play.

This module owns the in-memory recording session that accumulates
(keystroke, screen) pairs and flushes them to a
:class:`~tw2002_aiclient.loops.recorder.LoopRecorder` document.  The
live-attach instrumentation (feeding raw human keystrokes into this session
as they happen) is wired in ``app.py``'s attach send path: each successful
``send_key`` call appends a step here while a session is active.

# What this is NOT

- NOT on the live autopilot fire path.  :class:`RecordSession` is inert
  — it cannot dispatch any keystroke to the game.
- NOT a replay source on its own.  The saved document is blessed-by-default
  per ``canon/engine/macros.md`` (``loops/recorder.py`` §"Blessed, not
  draft", Max ruling 2026-07-26).
- No ``explore_start`` / ``ensure_auto_arm`` calls of any kind — this module
  imports nothing from ``session/`` and nothing that touches a network
  connection or spawns a process.

# Redaction

Secret keystrokes — those sent while the current screen is a probable
password prompt — must be stored as :data:`REDACTED_SENTINEL`, never as
their plaintext bytes.  :func:`is_secret_prompt_line` encapsulates the
``session.classify`` query; callers pass ``is_secret=is_secret_prompt_line(prompt)``
to :meth:`RecordSession.add_step`.  Centralising the check here keeps
``app.py`` free of direct ``session.classify`` imports and away from the
``NEVER_AUTO_ACTION`` classify→send audit perimeter.

# Hardening

Never raises on any :class:`RecordSession` public method call, regardless of
argument type — mirrors the family standard ``arm.py`` /
``assign_trigger.py`` / ``teachband.py`` / ``stopbanner.py``.
"""

from __future__ import annotations

import time
from typing import NamedTuple, Optional

from tw2002_aiclient.session.classify import (
    is_probable_secret_prompt as _is_probable_secret_prompt,
)
from tw2002_aiclient.loops.recorder import (
    EmptyRecording,
    InvalidName,
    LoopRecorder,
    NoStartAnchor,
    RecorderError,
)

__all__ = [
    "REDACTED_SENTINEL",
    "RecordSession",
    "SaveResult",
    "auto_name",
    "is_secret_prompt_line",
]

# The placeholder stored for a secret keystroke — never the plaintext bytes.
# A short, unmistakeable token that survives a round-trip through the JSON
# store without being confused with a real keypress or an empty string.
REDACTED_SENTINEL = "<cockpit-redacted>"


class SaveResult(NamedTuple):
    """Outcome of a successful :meth:`RecordSession.stop` call."""

    path: object   # pathlib.Path of the written file
    name: str      # macro name written to the document
    steps: int     # number of steps saved
    blessed: bool = True


def auto_name(classification: object = None) -> str:
    """A unique, filesystem-safe macro name derived from the current UTC
    timestamp and the optional screen classification.

    Used when the human presses ``R`` to start recording and no explicit
    name is supplied; a timestamp guarantees uniqueness across sessions.
    Never raises.
    """
    safe_class = classification if isinstance(classification, str) and classification else "macro"
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return f"{safe_class}-{ts}"


def is_secret_prompt_line(prompt: str) -> bool:
    """Return ``True`` if *prompt* looks like a password / secret prompt.

    Delegates to :func:`~tw2002_aiclient.session.classify.is_probable_secret_prompt`.
    Centralised here so ``app.py``'s attach-record path can query without
    importing ``session.classify`` directly — keeping ``app.py`` outside
    the ``NEVER_AUTO_ACTION`` classify→send audit perimeter.

    Never raises.
    """
    try:
        return bool(_is_probable_secret_prompt(prompt))
    except Exception:
        return False


class RecordSession:
    """In-memory recording state for one human demonstration.

    Analogous to ``assign_trigger.StubStore`` (WO-068) but with a
    list-of-steps lifecycle instead of a single latest-slot::

        session = RecordSession()
        session.start("ore-run", opening_rows)
        session.add_step("P", port_rows)
        session.add_step("Y", command_rows)
        result = session.stop()          # SaveResult or None

    Thread safety: not guaranteed — the cockpit runs on a single thread
    (the curses draw/input loop); no locking is added.

    Never raises on any public method call.
    """

    def __init__(self) -> None:
        self._active: bool = False
        self._name: str = ""
        self._opening_rows: list[str] = []
        # Each entry: (keystrokes: str, result_rows: list[str])
        self._steps: list[tuple[str, list[str]]] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def active(self) -> bool:
        """``True`` while a recording is in progress."""
        return self._active

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, name: object, opening_rows: object) -> None:
        """Begin recording — name the macro and capture the opening screen.

        Silently coerces bad inputs: a non-str or blank name is replaced
        by an auto-generated timestamp name at :meth:`stop` time (the blank
        is kept internally so :meth:`stop` can detect "no explicit name was
        given").  A non-list/tuple ``opening_rows`` degrades to ``[]``
        (honest absence of information beats a wrong value).

        Calling :meth:`start` while already active resets the capture with
        the new name and screen — press ``R`` twice to restart from the
        current position.

        Never raises.
        """
        safe_name = name if isinstance(name, str) and name.strip() else ""
        safe_rows = list(opening_rows) if isinstance(opening_rows, (list, tuple)) else []
        self._name = safe_name
        self._opening_rows = safe_rows
        self._steps = []
        self._active = True

    def add_step(
        self,
        keystrokes: object,
        result_rows: object,
        *,
        is_secret: bool = False,
    ) -> None:
        """Append one keystroke + resulting-screen pair to the capture.

        ``keystrokes`` is the key(s) the human pressed; ``result_rows`` is
        the ``screen`` rows list the game showed after that press (the same
        shape a ``tw do`` / ``tw screen --json`` response's ``"screen"``
        field carries).

        If ``is_secret`` is ``True`` the keystroke is stored as
        :data:`REDACTED_SENTINEL` instead of its plaintext bytes — the
        screen rows are kept verbatim (the RX channel is not redacted; see
        ``canon/doctrine/secrets-and-credentials.md`` §"Redaction: the send
        path").

        Silently drops the step if:

        * the session is not active,
        * ``keystrokes`` is not a ``str``, or
        * ``result_rows`` is not a list / tuple.

        Never raises.
        """
        if not self._active:
            return
        if not isinstance(keystrokes, str):
            return
        if not isinstance(result_rows, (list, tuple)):
            return
        stored_key = REDACTED_SENTINEL if is_secret else keystrokes
        self._steps.append((stored_key, list(result_rows)))

    def save(
        self,
        *,
        state_dir=None,
        skills_dir: object = None,
        world_id=None,
    ) -> Optional[SaveResult]:
        """Finalise the recording and save to the macro store.

        Returns a :class:`SaveResult` on success; returns ``None`` if:

        * the session was not active,
        * the session had no steps (nothing was captured), or
        * the recorder refused the opening screen (no readable
          ``start_anchor`` — the human must be at a known sector before
          starting a recording).

        On any refusal the session is cancelled so a subsequent
        :meth:`start` begins fresh.

        ``state_dir`` and ``skills_dir`` are the same injection seams
        :class:`~tw2002_aiclient.loops.recorder.LoopRecorder` exposes
        (tests point them at ``tmp_path``); ``None`` uses the package
        default (``state/skills/`` flat, or ``state/world/<id>/skills/`` when ``world_id`` is set).

        Never raises.
        """
        if not self._active:
            return None
        # Mark inactive immediately — no re-entry if an exception unwinds.
        self._active = False
        try:
            name = self._name or auto_name()
            recorder = LoopRecorder(name, self._opening_rows)
            for keystrokes, result_rows in self._steps:
                recorder.step(keystrokes, result_rows)
            path = recorder.save(
                blessed=True,
                state_dir=state_dir,
                skills_dir=skills_dir if skills_dir is None else skills_dir,
                world_id=world_id,
            )
            return SaveResult(path=path, name=recorder.name, steps=len(recorder.steps))
        except (RecorderError, InvalidName, EmptyRecording, NoStartAnchor, Exception):
            # RecorderError covers EmptyRecording / InvalidName / NoStartAnchor;
            # the bare Exception catch is the hardening floor — canon's
            # "never raises" family contract applies.
            pass
        self.cancel()
        return None

    def cancel(self) -> None:
        """Discard the current capture without saving.

        Resets all internal state so the next :meth:`start` begins fresh.
        Never raises.
        """
        self._active = False
        self._name = ""
        self._opening_rows = []
        self._steps = []
