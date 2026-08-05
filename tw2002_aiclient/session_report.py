"""Post-session action report — ledger consumer #5 (accountability digest).

Canon: ``canon/engine/trace-ledger.md`` § session report · DECISIONS
post-session-action-report DOC-GAP. Pure retrospective read of the trace
ledger — never a live-decision input, never sends.

**Delivery choice:** CLI-invocable ``tw report`` (primary). Session-end can
call the same formatter; a pull verb means operators can review mid-session
or after exit without wiring a fragile process-exit hook first.
"""

from __future__ import annotations

__all__ = [
    "AppActionRow",
    "SessionReport",
    "build_session_report",
    "format_session_report",
    "write_session_report",
]

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from tw2002_aiclient.ledger import DEFAULT_LEDGER_PATH, read_entries
from tw2002_aiclient.session.session import VALID_SENDERS


@dataclass(frozen=True)
class AppActionRow:
    """One app-attributed dispatch for the digest."""

    ts: str
    screen: str
    rule_id: str | None
    target_player: str | None
    input_summary: str
    session_id: str


@dataclass(frozen=True)
class SessionReport:
    """Human-facing digest emphasizing autonomous ``app`` actions."""

    session_id: str | None
    app_actions: tuple[AppActionRow, ...]
    human_count: int
    skipped_interrupted: int
    ledger_path: str
    notes: tuple[str, ...] = field(default_factory=tuple)


def _str_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _input_summary(entry: Mapping[str, Any]) -> str:
    raw = entry.get("input")
    if raw is None:
        return "?"
    text = str(raw)
    if text == "<redacted>":
        return "<redacted>"
    if text == "":
        return "Enter (default)"
    if len(text) > 40:
        return text[:37] + "…"
    return text


def build_session_report(
    *,
    path: str | Path | None = None,
    session_id: str | None = None,
    world_id: str | None = None,
    include_interrupted: bool = False,
) -> SessionReport:
    """Build a digest from the ledger. Never raises on corrupt rows."""
    ledger_path = Path(path) if path is not None else DEFAULT_LEDGER_PATH
    entries = read_entries(ledger_path, world_id=world_id)
    want_session = _str_or_none(session_id)

    app_rows: list[AppActionRow] = []
    human_count = 0
    skipped_interrupted = 0
    notes: list[str] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        actor = entry.get("actor")
        if actor not in VALID_SENDERS:
            continue
        sid = _str_or_none(entry.get("session_id"))
        if want_session is not None and sid != want_session:
            continue
        if actor == "human":
            human_count += 1
            continue
        # actor == app
        if entry.get("interrupted_by_human") is True and not include_interrupted:
            skipped_interrupted += 1
            continue
        app_rows.append(
            AppActionRow(
                ts=str(entry.get("ts") or ""),
                screen=str(entry.get("settled_class") or "unknown"),
                rule_id=_str_or_none(entry.get("rule_id"))
                or _str_or_none(entry.get("intent")),
                target_player=_str_or_none(entry.get("target_player")),
                input_summary=_input_summary(entry),
                session_id=sid or "?",
            )
        )

    if want_session is None and app_rows:
        sessions = {r.session_id for r in app_rows}
        if len(sessions) > 1:
            notes.append(
                f"multiple sessions in window ({len(sessions)}); "
                "pass --session-id to narrow"
            )

    return SessionReport(
        session_id=want_session,
        app_actions=tuple(app_rows),
        human_count=human_count,
        skipped_interrupted=skipped_interrupted,
        ledger_path=str(ledger_path),
        notes=tuple(notes),
    )


def format_session_report(report: SessionReport) -> str:
    """Plain-text digest for TTY / file artifact."""
    lines: list[str] = []
    title = "Post-session action report"
    if report.session_id:
        title += f" — session {report.session_id}"
    lines.append(title)
    lines.append(f"ledger: {report.ledger_path}")
    lines.append(
        f"app dispatches: {len(report.app_actions)}  ·  "
        f"human keystrokes (same filter): {report.human_count}"
    )
    if report.skipped_interrupted:
        lines.append(
            f"skipped interrupted_by_human app rows: {report.skipped_interrupted}"
        )
    for note in report.notes:
        lines.append(f"note: {note}")
    lines.append("")
    if not report.app_actions:
        lines.append("(no app-attributed dispatches in this window)")
        return "\n".join(lines)

    lines.append("app actions (chronological):")
    for row in report.app_actions:
        rule = row.rule_id if row.rule_id else "?"
        player = f"  target={row.target_player}" if row.target_player else ""
        lines.append(
            f"  {row.ts}  screen={row.screen}  rule={rule}  "
            f"input={row.input_summary}{player}"
        )
    return "\n".join(lines)


def write_session_report(
    report: SessionReport,
    out_path: str | Path,
) -> Path:
    """Write the formatted digest to ``out_path`` (UTF-8)."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(format_session_report(report) + "\n", encoding="utf-8")
    return p
