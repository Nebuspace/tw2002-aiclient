"""WO-MS-3 probe tests — classification, polite envelope, L0/L1 invariants."""

from pathlib import Path

import pytest

from twclient import probe


TWGS_BANNER = (
    "Telnet connection detected.\n"
    "Please enter your name (ENTER for none):\n"
)
BBS_BANNER = (
    "Synchronet BBS for Linux 3.18\n"
    'If you are a new user to the system, type "New" now.\n'
    "Otherwise, enter your user name or number now.\n"
)
PROTO_FAIL = "Failed to detect protocol. Expected Telnet...\n"


def test_classify_twgs_direct():
    assert probe.classify_banner(TWGS_BANNER) == "twgs-direct"


def test_classify_bbs():
    assert probe.classify_banner(BBS_BANNER) == "bbs"


def test_classify_mystic_bbs():
    """MS-3b: Mystic banner → bbs (was protocol-fail without this anchor)."""
    banner = "Welcome to Arcadia\nMystic BBS for Win32\nEnter your name:\n"
    assert probe.classify_banner(banner) == "bbs"


def test_classify_wildcat_bbs():
    """MS-3b: Wildcat banner → bbs."""
    banner = (
        "Wildcat! Interactive Net Server\n"
        "Wildcat's Castle BBS\n"
        "Please log in:\n"
    )
    assert probe.classify_banner(banner) == "bbs"


def test_classify_protocol_fail():
    assert probe.classify_banner(PROTO_FAIL) == "protocol-fail"


def test_l0_probe_sends_only_iac(monkeypatch):
    """Harness: L0 path may sendall only what TelnetHandler queues (IAC)."""
    sent = []

    class FakeSock:
        def __init__(self):
            self._chunks = [
                b"\xff\xfd\x18"  # IAC DO TTYPE — triggers a negotiation reply
                + TWGS_BANNER.encode(),
                b"",
            ]

        def settimeout(self, _t):
            return None

        def recv(self, _n):
            return self._chunks.pop(0) if self._chunks else b""

        def sendall(self, data):
            sent.append(bytes(data))

        def shutdown(self, _how):
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        probe.socket, "create_connection", lambda *a, **k: FakeSock()
    )
    result = probe.probe_endpoint("example.invalid", 2002, menu=False)
    assert result["classification"] == "twgs-direct"
    assert result["sent_cr"] is False
    # Every sent byte must be IAC negotiation (starts with 0xFF), never CR/LF/text.
    for chunk in sent:
        assert chunk.startswith(b"\xff"), chunk
        assert b"\r" not in chunk
        assert b"\n" not in chunk


def test_l1_sends_exactly_one_cr_at_twgs_prompt(monkeypatch):
    sent = []

    class FakeSock:
        def __init__(self):
            self.gave_banner = False
            self.cr_seen = False
            self.gave_menu = False

        def settimeout(self, _t):
            return None

        def recv(self, _n):
            if not self.gave_banner:
                self.gave_banner = True
                return TWGS_BANNER.encode()
            if self.cr_seen and not self.gave_menu:
                self.gave_menu = True
                return b"Select a game :\nA - Alpha\nB - Beta\n"
            return b""

        def sendall(self, data):
            sent.append(bytes(data))
            if data == b"\r":
                self.cr_seen = True

        def shutdown(self, _how):
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        probe.socket, "create_connection", lambda *a, **k: FakeSock()
    )
    result = probe.probe_endpoint("example.invalid", 2002, menu=True)
    assert result["classification"] == "twgs-direct"
    assert result["sent_cr"] is True
    crs = [c for c in sent if c == b"\r"]
    assert len(crs) == 1
    assert "Select a game" in result["menu_excerpt"]


def test_l1_refuses_cr_on_bbs_banner(monkeypatch):
    sent = []

    class FakeSock:
        def settimeout(self, _t):
            return None

        def recv(self, _n):
            if not hasattr(self, "_done"):
                self._done = True
                return BBS_BANNER.encode()
            return b""

        def sendall(self, data):
            sent.append(bytes(data))

        def shutdown(self, _how):
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        probe.socket, "create_connection", lambda *a, **k: FakeSock()
    )
    result = probe.probe_endpoint("example.invalid", 23, menu=True)
    assert result["classification"] == "bbs"
    assert result["sent_cr"] is False
    assert not any(c == b"\r" for c in sent)
    assert "menu_peek_refused" in (result.get("error") or "")


def test_non_telnet_transport_skipped():
    result = probe.probe_endpoint(
        "example.invalid", 22, transport="ssh", menu=False
    )
    assert result["classification"] == "protocol-fail"
    assert "transport_unsupported" in result["error"]


def test_unreachable(monkeypatch):
    def boom(*a, **k):
        raise ConnectionRefusedError("nope")

    monkeypatch.setattr(probe.socket, "create_connection", boom)
    result = probe.probe_endpoint("example.invalid", 2002)
    assert result["classification"] == "unreachable"
    assert result["status"] == "offline"


def test_l0_source_has_no_bare_cr_send():
    """Static guard: L0 helper `_send_iac_only` is the only TX on L0 reads;
    bare `sendall(b"\\r")` appears only under the menu/L1 branch."""
    src = Path(probe.__file__).read_text(encoding="utf-8")
    assert "def _send_iac_only" in src
    # The lone user-input send must be behind `if menu and`.
    cr_idx = src.find('sock.sendall(b"\\r")')
    assert cr_idx > 0
    window = src[max(0, cr_idx - 200) : cr_idx]
    assert "if menu" in window or "menu and" in window


def test_patch_catalog_status(tmp_path: Path):
    catalog = tmp_path / "servers.toml"
    catalog.write_text(
        "[servers.demo]\n"
        'hostname = "demo.example"\n'
        "port = 2002\n"
        'transport = "telnet"\n'
        'front_end = "auto"\n'
        'status = "listed"\n'
        "sources = []\n"
    )
    results = [
        {
            "key": "demo",
            "status": "online",
            "probed_at": "2026-07-20T00:00:00Z",
            "classification": "twgs-direct",
        }
    ]
    probe.patch_catalog_status(results, path=catalog)
    text = catalog.read_text()
    assert 'status = "online"' in text
    assert 'last_checked_at = "2026-07-20T00:00:00Z"' in text
    assert 'front_end = "auto"' in text  # untouched
