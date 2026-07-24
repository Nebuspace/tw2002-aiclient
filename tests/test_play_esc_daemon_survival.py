"""WO-P3-030 lane 2 — Esc→launcher must NOT tear down the session/daemon.

ADR-001 / PREP Accept: Esc returns to the launcher; daemon survives.
Out of scope: the Mode-line N5 "Stop the daemon too?" exit-confirm popup.

Isolation: no live ``run/twd.sock``. Ensure is stubbed; stop-path spies
assert no teardown verb is issued on the Esc→``back`` path.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from tw2002_aiclient import adapters, app
from tw2002_aiclient.adapters import EnsureResult
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow
from tw2002_aiclient.session import cli as session_cli


def _profile() -> ProfileRow:
    return ProfileRow(
        name="alpha",
        handle="Alpha",
        server="demo-a",
        host="demo-a.example",
        game_letter="B",
    )


def test_play_shell_esc_returns_back_not_quit():
    """Esc ends the TUI binding (``back``); it is not process quit."""
    screen = PlayShellScreen.__new__(PlayShellScreen)
    screen.profile = _profile()
    assert screen.handle_key(27) == "back"
    assert screen.handle_key(ord("q")) == "quit"
    assert screen.handle_key(ord("x")) is None


def test_run_play_source_never_calls_stop():
    """Static guard: ``_run_play`` body has no stop/teardown call sites."""
    src = Path(inspect.getsourcefile(app._run_play)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_run_play"
    )
    attrs = {
        n.attr
        for n in ast.walk(fn)
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load)
    }
    names = {
        n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }
    banned = {"stop", "request_stop", "stop_autopilot", "shutdown", "kill"}
    hit = (attrs | names) & banned
    assert not hit, f"_run_play must not call teardown helpers; found {sorted(hit)}"


def test_run_play_esc_issues_no_daemon_stop_verb(monkeypatch):
    """Drive Esc through ``_run_play``; assert no ``stop`` wire verb / sock traffic.

    Play chrome is still a placeholder, but entry *does* call
    ``ensure_session``. Survival proof for this lane: Esc returns ``back``
    without issuing daemon teardown (never touches live ``run/twd.sock``).
    """
    wire: list[tuple] = []

    monkeypatch.setattr(
        adapters,
        "ensure_session",
        lambda *a, **k: EnsureResult(ok=True, classification="main_command"),
    )

    def _spy_send(verb, args_payload=None, **kwargs):
        wire.append((verb, args_payload, kwargs.get("run_dir")))
        raise AssertionError(f"Esc path must not hit the daemon wire; got verb={verb!r}")

    monkeypatch.setattr(session_cli, "send_request", _spy_send)

    class _FakeStdscr:
        def __init__(self) -> None:
            self._keys = [27]  # Esc once

        def getch(self) -> int:
            return self._keys.pop(0) if self._keys else -1

        def timeout(self, _ms: int) -> None:
            return None

        def erase(self) -> None:
            return None

        def getmaxyx(self) -> tuple[int, int]:
            return (24, 80)

        def attron(self, *_a, **_k) -> None:
            return None

        def attroff(self, *_a, **_k) -> None:
            return None

        def box(self) -> None:
            return None

        def addstr(self, *_a, **_k) -> None:
            return None

        def addnstr(self, *_a, **_k) -> None:
            return None

        def refresh(self) -> None:
            return None

    # Avoid real curses color init inside PlayShellScreen.__init__.
    monkeypatch.setattr(PlayShellScreen, "_init_colors", lambda self: None)
    monkeypatch.setattr(PlayShellScreen, "draw", lambda self: None)

    result = app._run_play(_FakeStdscr(), _profile())
    assert result == "back"
    assert wire == [], f"daemon wire traffic on Esc path: {wire!r}"
