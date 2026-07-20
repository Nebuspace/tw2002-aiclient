"""WO-MS-3 — read-only catalog probe (`tw probe`).

L0 (default): TCP connect + TelnetHandler IAC replies ONLY — never a byte of
user input. Classify front-end from the opening banner.

L1 (`--menu`): optional, default OFF. At most one bare CR, and only when the
cleaned banner already contains the exact TWGS outer ``(ENTER for none)``
prompt. Then disconnect. Structurally incapable of answering any other prompt.

Polite envelope: 7s connect/read budget, sequential, no retries, one
connection per endpoint per run. No credentials. No catalog ``front_end`` rewrite.
"""

from __future__ import annotations

import json
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

from .iac import TelnetHandler
from . import servers as servers_mod

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROBE_TIMEOUT_S = 7.0
CLASSIFICATIONS = frozenset(
    {"twgs-direct", "bbs", "protocol-fail", "unreachable"}
)

# Exact TWGS outer-name anchor — the ONLY place L1 may emit a CR.
_TWGS_OUTER_PROMPT_RE = re.compile(
    r"Please enter your name\s*\(ENTER for none\)\s*:",
    re.IGNORECASE,
)
_BBS_MARKERS = (
    'type "New"',
    "type 'New'",
    "enter your user name or number",
    "Synchronet BBS",
    "user name or number now",
    # MS-3b: directory BBS packages that previously fell through to protocol-fail
    "Mystic BBS",
    "Wildcat! Interactive Net Server",
)
_PROTOCOL_FAIL_MARKERS = (
    "Failed to detect protocol",
    "Expected Telnet",
)
_ESC = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][A-Za-z0-9]|\x1b[=>]")


class ProbeError(Exception):
    """Probe configuration / invariant failure (not a network result)."""


def clean_ansi(s: str) -> str:
    s = _ESC.sub("", s)
    return "".join(ch for ch in s if ch == "\n" or ch == "\t" or ord(ch) >= 32)


def classify_banner(text: str) -> str:
    """Map cleaned banner text → classification (pure, no I/O)."""
    if not text or not text.strip():
        return "protocol-fail"
    lower = text.lower()
    if any(m.lower() in lower for m in _PROTOCOL_FAIL_MARKERS):
        return "protocol-fail"
    if _TWGS_OUTER_PROMPT_RE.search(text) or (
        "telnet connection detected" in lower and "enter your name" in lower
    ):
        return "twgs-direct"
    if any(m.lower() in lower for m in _BBS_MARKERS):
        return "bbs"
    # Ambiguous banner — reachable but unclassified shape.
    return "protocol-fail"


def status_for_classification(classification: str) -> str:
    if classification in ("twgs-direct", "bbs"):
        return "online"
    if classification == "unreachable":
        return "offline"
    return "unverified"


def _send_iac_only(sock: socket.socket, handler: TelnetHandler) -> None:
    """The ONLY allowed TX on the L0 path: queued IAC negotiation replies."""
    pending = handler.pop_pending_output()
    if pending:
        sock.sendall(pending)


def _read_banner(sock: socket.socket, handler: TelnetHandler, deadline: float) -> bytes:
    out = bytearray()
    idle_rounds = 0
    while time.time() < deadline:
        try:
            data = sock.recv(4096)
        except socket.timeout:
            _send_iac_only(sock, handler)
            idle_rounds += 1
            # Enough idle after a classifiable banner → stop waiting.
            clean = clean_ansi(bytes(out).decode("utf-8", "replace"))
            if idle_rounds >= 2 and classify_banner(clean) in (
                "twgs-direct",
                "bbs",
                "protocol-fail",
            ):
                break
            continue
        except OSError:
            break
        if not data:
            idle_rounds += 1
            if idle_rounds >= 2:
                break
            continue
        idle_rounds = 0
        out.extend(handler.feed(data))
        _send_iac_only(sock, handler)
        if len(out) > 8000:
            break
    return bytes(out)


def _menu_peek_allowed(clean_text: str) -> bool:
    return bool(_TWGS_OUTER_PROMPT_RE.search(clean_text))


def probe_endpoint(
    host: str,
    port: int,
    *,
    menu: bool = False,
    timeout_s: float = PROBE_TIMEOUT_S,
    transport: str = "telnet",
) -> dict:
    """Probe one endpoint. Never retries. One connection attempt.

    Returns a result dict with keys: host, port, classification, status,
    banner_excerpt, error, menu_excerpt, sent_cr (bool).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = {
        "host": host,
        "port": port,
        "transport": transport,
        "probed_at": now,
        "menu": bool(menu),
        "sent_cr": False,
        "banner_excerpt": "",
        "menu_excerpt": "",
        "error": None,
    }
    if transport != "telnet":
        base["classification"] = "protocol-fail"
        base["status"] = status_for_classification("protocol-fail")
        base["error"] = f"transport_unsupported:{transport}"
        return base

    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout_s)
    except OSError as e:
        base["classification"] = "unreachable"
        base["status"] = status_for_classification("unreachable")
        base["error"] = f"CONNECT-FAIL:{e!r}"
        return base

    sock.settimeout(1.0)
    handler = TelnetHandler()
    deadline = time.time() + timeout_s
    raw = b""
    try:
        raw = _read_banner(sock, handler, deadline)
        clean = clean_ansi(raw.decode("utf-8", "replace"))
        base["banner_excerpt"] = "\n".join(
            ln.rstrip() for ln in clean.splitlines() if ln.strip()
        )[:2000]
        classification = classify_banner(clean)

        # L1: exactly one CR, only at TWGS outer prompt, then brief re-read.
        if menu and classification == "twgs-direct" and _menu_peek_allowed(clean):
            sock.sendall(b"\r")
            base["sent_cr"] = True
            more = _read_banner(sock, handler, time.time() + min(3.0, timeout_s))
            menu_clean = clean_ansi(more.decode("utf-8", "replace"))
            base["menu_excerpt"] = "\n".join(
                ln.rstrip() for ln in menu_clean.splitlines() if ln.strip()
            )[:2000]
        elif menu and not _menu_peek_allowed(clean):
            # Refuse to emit CR on non-TWGS prompts (BBS / unknown).
            base["error"] = "menu_peek_refused:not_twgs_outer_prompt"

        base["classification"] = classification
        base["status"] = status_for_classification(classification)
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()
    return base


def probe_server_key(
    key: str,
    *,
    menu: bool = False,
    path=None,
    timeout_s: float = PROBE_TIMEOUT_S,
) -> dict:
    rec = servers_mod.get_server(key, path=path)
    result = probe_endpoint(
        rec["hostname"],
        rec["port"],
        menu=menu,
        timeout_s=timeout_s,
        transport=rec.get("transport") or "telnet",
    )
    result["key"] = key
    result["front_end"] = rec.get("front_end")
    return result


def probe_all(
    *,
    menu: bool = False,
    path=None,
    timeout_s: float = PROBE_TIMEOUT_S,
) -> list[dict]:
    """Sequential, one connection per catalog row, no retries."""
    rows = servers_mod.list_servers(path=path)
    out = []
    for rec in rows:
        result = probe_endpoint(
            rec["hostname"],
            rec["port"],
            menu=menu,
            timeout_s=timeout_s,
            transport=rec.get("transport") or "telnet",
        )
        result["key"] = rec["key"]
        result["front_end"] = rec.get("front_end")
        out.append(result)
    return out


def patch_catalog_status(
    results: list[dict],
    *,
    path=None,
) -> Path:
    """Surgical patch of status= / last_checked_at= lines for probed keys.

    Does not rewrite front_end. Leaves unrelated lines untouched.
    """
    catalog_path = Path(path) if path is not None else servers_mod.SERVERS_PATH
    text = catalog_path.read_text(encoding="utf-8")
    by_key = {r["key"]: r for r in results if r.get("key")}

    # Split on [servers.<key>] headers and patch each section independently.
    parts = re.split(r"(?=^\[servers\.[^\]]+\])", text, flags=re.MULTILINE)
    rebuilt = []
    for part in parts:
        m = re.match(r"^\[servers\.([^\]]+)\]", part)
        if not m:
            rebuilt.append(part)
            continue
        key = m.group(1)
        if key not in by_key:
            rebuilt.append(part)
            continue
        rec = by_key[key]
        status = rec["status"]
        checked = rec["probed_at"]
        section = part
        if re.search(r"(?m)^status\s*=", section):
            section = re.sub(
                r"(?m)^status\s*=\s*\".*?\"",
                f'status = "{status}"',
                section,
                count=1,
            )
        else:
            section = section.rstrip() + f'\nstatus = "{status}"\n'
        if re.search(r"(?m)^last_checked_at\s*=", section):
            section = re.sub(
                r"(?m)^last_checked_at\s*=\s*\".*?\"",
                f'last_checked_at = "{checked}"',
                section,
                count=1,
            )
        else:
            section = section.rstrip() + f'\nlast_checked_at = "{checked}"\n'
        rebuilt.append(section if section.endswith("\n") else section + "\n")

    new_text = "".join(rebuilt)
    catalog_path.write_text(new_text, encoding="utf-8")
    return catalog_path


def write_results_file(results: list[dict], out_dir: Path | None = None) -> Path:
    out_dir = out_dir or (PROJECT_ROOT / "state")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"probe-results-{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "count": len(results),
                "results": results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
