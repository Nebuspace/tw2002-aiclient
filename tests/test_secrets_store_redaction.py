"""The secrets store's FAILURE surface — typed, bounded, payload-free.

WO-SECRETS-REPR-GET-PASSWORD-REHAB · `canon/DECISIONS.md` §C · doctrine
`canon/doctrine/secrets-and-credentials.md` invariant 1 ("secrets never touch
logs, argv, shell history, or the repo").

**The measured defect this file closes.** `credentials.get_password` used to let
the decoder's own exception escape. `repr()` of a `UnicodeDecodeError` renders
`args`, and `args[1]` is the ENTIRE buffer that failed to decode — for
`config/secrets.json` that is every profile's stored password, not just the one
being resolved. Measured on this tree: a 200 KB store produced a 200,153-character
`repr()`. Nothing on the login path reprs an exception, which is why the sibling
suite (`tests/test_login_redaction.py`) was green — but the now-retired
`menu/crawl_driver.py` wrote `repr(exc)` into a *persisted* status file and a
JSONL log for its own broad catch, so the pattern was one caller away from a
durable leak.

**Why the obvious probe is the one that does NOT fire.** The exposure depends on
the error's SHAPE, not on the file. The same store, malformed rather than
undecodable, raises `JSONDecodeError`, whose `repr()` is clean while `.doc` still
holds the whole document. A reader who checks the cheap case concludes "safe".
Both halves are driven below.

**Sinks swept.** Every rendering the product actually performs — `str()`,
`repr()`, both f-string forms, the type name, `traceback.format_exception`, the
`__cause__`/`__context__` chain, the daemon's wire frame, guardian's
`last_reconnect_error`, and the now-retired `crawl_driver`'s persisted `reason` —
plus, for the crawl scenarios, every byte left on disk. Assertions are against
SERIALISED output, never a dict key: a value nested in `args` / `detail` /
`object` passes a shallow check and still reaches disk.

**Never the operator's store.** Every file here is written under this module's own
`tempfile.mkdtemp()` root or pytest's `tmp_path`, and every `chmod` is guarded by
`_assert_disposable`, which refuses any path inside the repo. Modes are restored
in `finally` so the tree can always be torn down.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import tempfile
import traceback
from pathlib import Path

import pytest

from tw2002_aiclient.session import credentials

# Distinct from `tests/test_login_redaction.py`'s sentinel on purpose: if both
# files ever write into one sink, the value says which one did.
SENTINEL = "S3CR3T-STORE-PW-a17f3d"
# A sibling profile inside the SAME store. The key names it, the value is its
# stored credential. A decoder that quotes "what it was reading" quotes one of
# these long before it quotes the profile actually being resolved — which is
# what makes the store-failure sweeps non-vacuous, since those paths never send
# a password at all.
CANARY_KEY = "canary-store-profile-6c20e9"
CANARY_VALUE = "canary-store-pw-3e81b4"
NEEDLES = (SENTINEL, CANARY_KEY, CANARY_VALUE)

PROFILE = "storefail"
ENV_VAR = "TW2002_PASSWORD_STOREFAIL"

_REPO_ROOT = Path(credentials.PROJECT_ROOT).resolve()


# ---------------------------------------------------------------------------
# disposable roots — nothing here may touch the operator's config/
# ---------------------------------------------------------------------------


def _assert_disposable(path, root):
    """Refuse to chmod/write anything that is not under `root`, and never
    anything inside the repo. The operator may be flying live; `config/` and
    `run/` are theirs."""
    p = Path(path).resolve()
    root = Path(root).resolve()
    assert p == root or root in p.parents, f"refusing to touch {p}: outside {root}"
    assert p != _REPO_ROOT and _REPO_ROOT not in p.parents, f"refusing to touch {p}: inside the repo"


@pytest.fixture
def disposable():
    """A `tempfile.mkdtemp()` root, torn down unconditionally. Used instead of
    `tmp_path` wherever a test chmods something, so the destructive scenarios
    are provably confined to a directory this process created."""
    d = Path(tempfile.mkdtemp(prefix="tw-secrets-redact-"))
    try:
        yield d
    finally:
        # A denied scenario may have left the dir unenterable; restore before
        # the tree walk, or the teardown leaks the directory.
        with contextlib.suppress(OSError):
            os.chmod(d, 0o700)
        for sub in d.rglob("*"):
            with contextlib.suppress(OSError):
                os.chmod(sub, 0o700 if sub.is_dir() else 0o600)
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_env_override(monkeypatch):
    """Doctrine precedence is env-FIRST. An inherited `TW2002_PASSWORD_STOREFAIL`
    would short-circuit every store scenario here into a pass that proves
    nothing."""
    monkeypatch.delenv(ENV_VAR, raising=False)


def _point_at(monkeypatch, cfg: Path) -> Path:
    """Move `credentials`' module-level paths onto `cfg`.

    Those globals are resolved at import time, so `TW_CONFIG_DIR` alone would not
    move them in an already-imported process — the same reason
    `tests/test_login_redaction.py` and `tests/test_daemon_internal_error_typename.py`
    monkeypatch the resolved paths directly. `get_password` reads the global at
    call time, so this follows.
    """
    monkeypatch.setattr(credentials, "CONFIG_DIR", cfg)
    monkeypatch.setattr(credentials, "SECRETS_PATH", cfg / "secrets.json")
    monkeypatch.setattr(credentials, "PROFILES_PATH", cfg / "profiles.toml")
    monkeypatch.setattr(credentials, "SERVERS_PATH", cfg / "servers.toml")
    return cfg / "secrets.json"


# ---------------------------------------------------------------------------
# the store, in each of its broken shapes
# ---------------------------------------------------------------------------


def _good_store_text() -> str:
    return json.dumps(
        {PROFILE: {"password": SENTINEL}, CANARY_KEY: {"password": CANARY_VALUE}}, indent=2
    )


def _malformed_store_text() -> str:
    """Valid UTF-8, truncated mid-object — `json.load` raises `JSONDecodeError`,
    whose `.doc` holds the whole document."""
    return _good_store_text().rstrip()[:-2]


def _non_utf8_store_bytes() -> bytes:
    """A well-formed store with one lone `0xFF` appended. `get_password` opens
    with `encoding="utf-8"`, so this fails in the READ, as a
    `UnicodeDecodeError` — neither an `OSError` nor a `JSONDecodeError`, i.e. it
    escaped every typed handler in the package. Its `.object` is the whole
    buffer."""
    return _good_store_text().encode("utf-8") + b"\xff"


def _wrong_shape_store_text() -> str:
    """Valid UTF-8, valid JSON, wrong TYPE at the top level. `data.get(profile)`
    used to raise a bare `AttributeError` two lines later."""
    return json.dumps([{PROFILE: {"password": SENTINEL}}, CANARY_KEY, CANARY_VALUE])


def _write_store(cfg: Path, *, text: str | None = None, raw: bytes | None = None) -> Path:
    cfg.mkdir(parents=True, exist_ok=True)
    path = cfg / "secrets.json"
    _assert_disposable(path, cfg)
    path.write_bytes(raw if raw is not None else (text or "").encode("utf-8"))
    os.chmod(path, 0o600)  # doctrine: the store is 0600 on every write
    return path


# ---------------------------------------------------------------------------
# the sinks
# ---------------------------------------------------------------------------


def _renderings(exc: BaseException) -> dict[str, str]:
    """Every way this codebase renders an exception, applied to whatever escaped.

    `repr()` is IN this set, and that is the whole point of the work order:
    `tests/test_login_redaction.py::_exception_renderings` deliberately omits it
    because before this rehab it was the one rendering that leaked, and nothing
    on the login path performed it. The now-retired `menu/crawl_driver.py` did,
    into a persisted file, which is why it stayed swept here as a first-class
    product rendering.

    The `__cause__`/`__context__` chain is rendered with `str()`, which is what
    `traceback` itself uses. The cause's own `repr()` is the residual, pinned
    separately below rather than folded in here.
    """
    chain: list[BaseException] = []
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        chain.append(cur)
        cur = cur.__cause__ or cur.__context__
    return {
        "str(exc)": str(exc),
        "repr(exc)": repr(exc),
        'f"{exc}"': f"{exc}",
        'f"{exc!r}"': f"{exc!r}",
        "type(exc).__name__": type(exc).__name__,
        "traceback.format_exception": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
        "cause/context chain via str()": " | ".join(str(e) for e in chain),
        # daemon.py's widest catch — the whole frame, as JSON, not just a field.
        "daemon wire frame": json.dumps(
            {"ok": False, "error": f"internal_error:{type(exc).__name__}"}
        ),
        # guardian.py's broad catch.
        "guardian last_reconnect_error": f"guardian_tick_error:{type(exc).__name__}",
    }


def _tree_sinks(root: Path, sanctioned: Path | None = None) -> dict[str, str]:
    """Every byte left on disk under `root`, except the one sanctioned home for a
    credential. `latin-1` is total, so a non-UTF-8 store is read, not skipped."""
    sanctioned = sanctioned.resolve() if sanctioned is not None else None
    sinks: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        try:
            if not path.is_file() or (sanctioned is not None and path.resolve() == sanctioned):
                continue
            sinks[f"on-disk {path.relative_to(root)}"] = path.read_bytes().decode("latin-1")
        except OSError:
            # A file this run was not allowed to read is one it cannot have
            # written a secret into either (the denied scenarios plant exactly
            # one such file, and it is the sanctioned store).
            continue
    return sinks


def _assert_absent(sinks: dict[str, str], needles=NEEDLES):
    for name, text in sinks.items():
        for needle in needles:
            assert needle not in text, f"credential material leaked into {name}"


# ---------------------------------------------------------------------------
# 1. absence stays absence — the one negative the store is entitled to report
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shape", ["no-config-dir", "empty-config-dir", "no-entry-for-profile"])
def test_absent_store_still_answers_none(shape, tmp_path, monkeypatch):
    """A profile with no stored credential anywhere is the NORMAL state of a
    character that has never been registered (doctrine invariant 3: "absence is
    not an error"). Dropping the `SECRETS_PATH.exists()` pre-check must not turn
    any of the three ordinary absences into a raise -- `no-config-dir` is the
    fresh-install state and by far the most common.
    """
    cfg = tmp_path / "config"
    if shape != "no-config-dir":
        cfg.mkdir()
    if shape == "no-entry-for-profile":
        _write_store(cfg, text=json.dumps({CANARY_KEY: {"password": CANARY_VALUE}}))
    _point_at(monkeypatch, cfg)
    assert credentials.get_password(PROFILE) is None


def test_env_override_wins_without_ever_opening_a_broken_store(tmp_path, monkeypatch):
    """Doctrine invariant 3, resolution precedence: environment FIRST, store
    second. A corrupt store must not defeat the operator's out-of-band override
    — that override is precisely the escape hatch for a damaged store."""
    cfg = tmp_path / "config"
    _write_store(cfg, raw=_non_utf8_store_bytes())
    _point_at(monkeypatch, cfg)
    monkeypatch.setenv(ENV_VAR, "from-env")
    assert credentials.get_password(PROFILE) == "from-env"


# ---------------------------------------------------------------------------
# 2. every failure shape is a TYPED, BOUNDED error — never the decoder's own
# ---------------------------------------------------------------------------


def _drive(kind: str, root: Path, monkeypatch):
    """Plant a store broken in `kind`'s way and drive the real `get_password`.

    Returns `(exception, store_path)`. `pytest.raises(BaseException)` is
    deliberate: before this rehab three different unrelated exception types
    escaped this call (`UnicodeDecodeError`, `JSONDecodeError`, `PermissionError`
    — two of which are not even `OSError`), and the point of the sweep is that it
    is written against "whatever escaped" rather than against a type. Each caller
    pins the exact type immediately after, so an unrelated raise cannot slip
    through this net and be swept as clean.
    """
    cfg = root / "config"
    restore: list = []
    if kind == "non_utf8":
        store = _write_store(cfg, raw=_non_utf8_store_bytes())
    elif kind == "malformed":
        store = _write_store(cfg, text=_malformed_store_text())
    elif kind == "wrong_shape":
        store = _write_store(cfg, text=_wrong_shape_store_text())
    elif kind == "denied_file":
        store = _write_store(cfg, text=_good_store_text())
        _assert_disposable(store, root)
        os.chmod(store, 0o000)
        restore.append((store, 0o600))
    elif kind == "denied_dir":
        store = _write_store(cfg, text=_good_store_text())
        _assert_disposable(cfg, root)
        os.chmod(cfg, 0o000)
        restore.append((cfg, 0o700))
    elif kind == "is_a_directory":
        cfg.mkdir(parents=True, exist_ok=True)
        store = cfg / "secrets.json"
        _assert_disposable(store, root)
        store.mkdir()
    else:  # pragma: no cover - a typo in this file must not read as a pass
        raise AssertionError(f"unknown kind {kind!r}")

    _point_at(monkeypatch, cfg)
    try:
        with pytest.raises(BaseException) as excinfo:  # noqa: PT011 -- see the docstring
            credentials.get_password(PROFILE)
    finally:
        for path, mode in restore:
            os.chmod(path, mode)
    return excinfo.value, store


_ROOT_SKIP = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses mode 0000, so the read would succeed and prove nothing",
)

# (kind, expected `cause` vocabulary, marks)
_FAILURE_KINDS = [
    ("non_utf8", credentials.CAUSE_CORRUPT, ()),
    ("malformed", credentials.CAUSE_CORRUPT, ()),
    ("wrong_shape", credentials.CAUSE_MALFORMED, ()),
    ("denied_file", credentials.CAUSE_DENIED, (_ROOT_SKIP,)),
    ("denied_dir", credentials.CAUSE_DENIED, (_ROOT_SKIP,)),
    ("is_a_directory", credentials.CAUSE_UNUSABLE, ()),
]


@pytest.mark.parametrize(
    "kind, cause",
    [pytest.param(k, c, marks=list(m), id=k) for k, c, m in _FAILURE_KINDS],
)
def test_every_store_failure_is_typed_and_no_rendering_carries_the_document(
    kind, cause, disposable, monkeypatch
):
    """The Accept, in one shape, over every way the store can fail.

    Each failure raises ONE type carrying a bounded `(cause, reason, path)`
    payload, and not one of the renderings the product performs contains the
    sentinel or either canary — including `repr()`, which is the rendering that
    leaked before this rehab.
    """
    exc, store = _drive(kind, disposable, monkeypatch)

    assert isinstance(exc, credentials.SecretStoreUnreadable), (
        f"{kind} escaped as {type(exc).__name__}: the decoder's own exception, "
        f"or an unclassified raise, still reaches the caller"
    )
    assert exc.cause == cause
    assert Path(exc.path).name == "secrets.json"
    _assert_absent(_renderings(exc))

    # Non-vacuity: the store really does hold all three needles, so every
    # absence above is about a document that was genuinely there to leak.
    # Bytes, not text — one of these stores is deliberately not valid UTF-8.
    if store.is_file():
        planted = store.read_bytes()
        assert all(needle.encode() in planted for needle in NEEDLES)


def test_the_reason_is_bounded_to_a_type_name_and_integer_offsets(disposable, monkeypatch):
    """`reason` is the one free-text field on the typed error, so it is the one
    place a future edit could reintroduce the document. Pin its SHAPE, not just
    the absence of today's needles: a type name plus integer positions, which is
    what `_decoder_detail` exists to guarantee."""
    exc, _store = _drive("non_utf8", disposable, monkeypatch)

    assert exc.reason.startswith("not valid UTF-8 (")
    detail = exc.reason[len("not valid UTF-8 (") : -1]
    assert re.fullmatch(r"UnicodeDecodeError at byte \d+", detail), detail

    exc, _store = _drive("malformed", disposable, monkeypatch)
    assert exc.reason.startswith("not valid JSON (")
    detail = exc.reason[len("not valid JSON (") : -1]
    assert re.fullmatch(r"JSONDecodeError at line \d+, column \d+", detail), detail


def test_a_denied_directory_names_the_directory_not_the_file(disposable, monkeypatch):
    """An unreadable `config/` reported as a bare "Permission denied" sends the
    operator to chmod a file that is already readable. Same wording the two
    sibling loaders already use."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root bypasses mode 0000")
    exc, _store = _drive("denied_dir", disposable, monkeypatch)
    assert "containing directory" in exc.reason


def test_residual_the_cause_still_owns_the_document_but_nothing_renders_it(
    disposable, monkeypatch
):
    """HAZARD RECORD, not an approval.

    The typed error is raised `from exc`, exactly as `credentials._load_toml_store`
    and `env.load_dotenv` raise theirs — so the decoder's exception, and with it
    the whole buffer, is still reachable as `__cause__.object`. That is deliberate
    and it is safe under every rendering the product performs: `traceback` walks
    the chain with `str()`, and `str(UnicodeDecodeError)` renders positions plus
    at most one byte value (pinned below).

    `raise ... from None` was considered and rejected: it sets
    `__suppress_context__`, not `__context__`, so the buffer would remain exactly
    as reachable while the traceback lost the frame that explains the failure.

    Pinned so the guarantee is stated honestly — "nothing renders the cause",
    not "the payload is gone" — and so a future reader cannot mistake the clean
    sweep for an object that never held anything.
    """
    exc, _store = _drive("non_utf8", disposable, monkeypatch)

    cause = exc.__cause__
    assert isinstance(cause, UnicodeDecodeError)
    assert all(needle.encode() in cause.object for needle in NEEDLES)
    assert all(needle in repr(cause) for needle in NEEDLES), (
        "if the CAUSE's repr stopped carrying the document, CPython changed — "
        "re-measure before relaxing anything here"
    )
    # ...and not one product rendering reaches for it.
    _assert_absent(_renderings(exc))


# ---------------------------------------------------------------------------
# 3. the `str()` window — measured, not assumed
# ---------------------------------------------------------------------------


# The window backstop's bound is DERIVED, not chosen, because a backstop sized
# above the event it guards against cannot fire. Measured across all 16
# parametrizations below, the longest real `str(UnicodeDecodeError)` is 78 chars.
# The sentinel is 22, so any rendered window big enough to CARRY the secret puts
# the rendering at >= 78 + 22. Budgeting exactly that means the length check
# fires on precisely the case it exists for, and the slack it does keep is
# earmarked for CPython message drift rather than being arbitrary.
#
# The previous bound was 200 and could not fire at all: the largest buffer under
# test is 42 bytes, so even a FULL-buffer window renders near 120 -- comfortably
# under 200. Sized wrong, it was a backstop only in name (#193).
_WORST_REAL_RENDERING = 78


def _window_budget() -> int:
    return _WORST_REAL_RENDERING + len(SENTINEL)


def _assert_no_window(rendered: str) -> None:
    """The backstop, as ONE callable so its falsification exercises the real pin.

    A test that re-implements this check proves only that the copy works — the
    production assert could be deleted and the falsification would stay green.
    """
    budget = _window_budget()
    assert len(rendered) < budget, (
        f"str() grew a window: {len(rendered)} chars >= budget {budget} "
        f"(worst real rendering {_WORST_REAL_RENDERING} + sentinel {len(SENTINEL)}): {rendered!r}"
    )


_DAMAGE = {
    "lone-0xff": b"\xff",
    "truncated-2byte": b"\xc3",
    "truncated-3byte": b"\xe2\x82",
    "truncated-4byte": b"\xf0\x9f\x92",
    "overlong": b"\xc0\xaf",
    "surrogate": b"\xed\xa0\x80",
    "continuation-only": b"\x80",
    "invalid-start-f8": b"\xf8\x88\x80\x80\x80",
}


@pytest.mark.parametrize("arrangement", ["sentinel-before-damage", "sentinel-after-damage"])
@pytest.mark.parametrize("damage", sorted(_DAMAGE), ids=sorted(_DAMAGE))
def test_str_of_a_decode_error_never_quotes_a_window_of_the_buffer(damage, arrangement):
    """`str(UnicodeDecodeError)` is shorter than `repr()`, and the tempting
    assumption is that "shorter" means "safe". It quotes bytes *around the
    failure point*, so the question — can that window contain a credential? — has
    to be measured rather than argued.

    Measured here across 8 damage shapes x 2 sentinel positions: CPython renders
    either `byte 0x<hh> in position <n>` (exactly ONE byte value) or
    `bytes in position <n>-<m>` (no byte values at all). There is no window. The
    non-vacuity bookend is that `repr()` of the same object DOES carry the
    sentinel — the buffer is right there; `str()` simply does not render it.

    The third arrangement, damage *inside* the sentinel, is deliberately excluded:
    it splits the needle so a substring probe goes falsely clean and would prove
    nothing about the renderer.
    """
    dmg = _DAMAGE[damage]
    if arrangement == "sentinel-before-damage":
        buf = SENTINEL.encode() + b'","x":"' + dmg
    else:
        buf = b'{"x":"' + dmg + b'","p":"' + SENTINEL.encode() + b'"}'

    with pytest.raises(UnicodeDecodeError) as excinfo:
        buf.decode("utf-8")
    exc = excinfo.value

    rendered = str(exc)
    assert SENTINEL not in rendered
    _assert_no_window(rendered)
    byte_values = re.findall(r"0x[0-9a-fA-F]{2}", rendered)
    assert len(byte_values) <= 1, f"str() rendered more than one byte: {rendered!r}"
    # Non-vacuity: the buffer really is on the object.
    assert SENTINEL in repr(exc)


def test_the_window_backstop_can_actually_fire():
    """Falsify the backstop, because a bound that cannot fire is decoration.

    Before #193 this check read `< 200`. The largest buffer under test is 42
    bytes, so a CPython that quoted the WHOLE buffer would render ~120 chars and
    sail under 200 — the guard could not catch the very event it is named for.
    That was invisible from the source: the assert looks like a guard, passes
    every run, and its message claims growth detection.

    Both directions run against the SAME helper the production test calls. If
    `_assert_no_window` were gutted, this test goes green only by also going
    silent on the real rendering below — which the control catches.
    """
    buf = SENTINEL.encode() + b'","x":"' + _DAMAGE["lone-0xff"]
    with pytest.raises(UnicodeDecodeError) as excinfo:
        buf.decode("utf-8")
    real = str(excinfo.value)

    # CONTROL first: the real rendering must pass, or "everything fails" would
    # masquerade as a working guard.
    _assert_no_window(real)

    # A hypothetical CPython that appended the offending buffer as a window.
    # Nothing here is forged set-arithmetic: this is a string of the shape the
    # backstop exists to reject, handed to the production check.
    windowed = real + ": " + buf.decode("utf-8", "replace")
    assert len(windowed) >= _window_budget(), (
        "the simulated window is not actually over budget — this test would "
        f"pass vacuously ({len(windowed)} < {_window_budget()})"
    )
    with pytest.raises(AssertionError, match="grew a window"):
        _assert_no_window(windowed)

    # And the budget is anchored to a measured quantity, not a taste. If CPython's
    # message grows past the recorded worst case, re-measure deliberately rather
    # than discovering it as a mystery failure.
    assert len(real) <= _WORST_REAL_RENDERING, (
        f"real rendering is {len(real)} chars, above the recorded worst case "
        f"{_WORST_REAL_RENDERING} — re-measure all 16 parametrizations and "
        "update the constant with the new number"
    )


def test_the_production_pin_actually_routes_through_the_backstop(monkeypatch):
    """Wiring pin. A correct helper is worth nothing if the test stops calling it.

    Without this, deleting `_assert_no_window(rendered)` from the parametrized
    test above leaves the whole file green: the falsification exercises the
    helper directly, so it would go on proving that an uncalled function works.
    That is the failure mode where a composer is tested and never wired.
    """
    import sys as _sys

    module = _sys.modules[__name__]
    seen: list[str] = []
    original = _assert_no_window

    def _spy(rendered: str) -> None:
        seen.append(rendered)
        return original(rendered)

    monkeypatch.setattr(module, "_assert_no_window", _spy)
    test_str_of_a_decode_error_never_quotes_a_window_of_the_buffer(
        "lone-0xff", "sentinel-before-damage"
    )
    assert seen, (
        "the parametrized str() test no longer routes through _assert_no_window "
        "— the window backstop is unwired, and only its own unit falsification "
        "would still be green"
    )


def test_str_of_a_json_decode_error_never_quotes_the_document(disposable, monkeypatch):
    """The other half of the shape asymmetry. `JSONDecodeError`'s `repr()` is
    CLEAN while its `.doc` holds the whole document — the exact trap that makes
    "I checked repr, it's fine" a false conclusion when generalized from the JSON
    case to the decode case."""
    cfg = disposable / "config"
    store = _write_store(cfg, text=_malformed_store_text())
    _point_at(monkeypatch, cfg)
    with pytest.raises(json.JSONDecodeError) as excinfo:
        json.loads(store.read_text(encoding="utf-8"))
    exc = excinfo.value

    for needle in NEEDLES:
        assert needle not in str(exc)
        assert needle not in repr(exc), "repr is clean HERE -- do not generalize from it"
        assert needle in exc.doc, "...while the document is still on the exception"
