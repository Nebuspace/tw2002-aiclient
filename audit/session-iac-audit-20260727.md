# Honesty audit — `tw2002_aiclient/session/iac.py`

**Seat:** `impl-claudecode-aiclient` · **Tip audited:** `origin/main` `01b94e7` · **Mode:** READ-ONLY, no product change
**WO:** `WO-AUDIT-SESSION-IAC` · **Companion to:** `audit/session-env-audit-20260726.md`
**Method:** every finding below was produced by **executing** the state machine against a
constructed byte stream, not by reading it. Where a probe found nothing, that is stated too.

---

## Summary

`iac.py` is 153 lines and its two headline claims are **true** — the split-sequence
persistence and the `IAC IAC` data unescaping both do exactly what the docstrings say, and I
verified both by feeding them. The defects are not in what it says about itself; they are in
what it does **silently** when the byte stream is not well-formed.

The most serious one is not a crash. It is a stall that the app's own freeze detector cannot
see.

| # | Surface | Severity | Status |
|---|---|---|---|
| I-01 | An unterminated subnegotiation swallows the entire stream, unbounded — and the liveness signal still reads healthy | **MED** | **CLOSED** (`884f73e` / #64 · WO-IAC-SB-BUFFER-BOUND) — historical defect; tip has `_SB_BUF_MAX` |
| I-02 | An exception in `feed()` kills the reader thread while `connected` keeps claiming `True` | **MED** | defect (cross-module) |
| I-03 | Outbound `IAC` is never escaped in NAWS/TTYPE payloads | **LOW** (latent; unreachable at tip) | defect |
| I-04 | Negotiation is stateless — a mirroring peer never reaches a fixed point | **LOW** | defect |
| I-05 | "treat as continuing SB data" silently discards the `IAC` byte | **LOW** | comment vs code |
| I-06 | Module docstring implies NAWS subnegotiations are answered | **LOW** | wording |
| — | split-IAC persistence across `feed()` calls | — | **probed, clean** |
| — | `IAC IAC` → literal `0xFF` in the data stream | — | **probed, clean** |

---

## I-01 · MED · one stray `IAC SB` freezes the screen forever, and the freeze detector says everything is fine — **CLOSED**

> **Tip honesty (2026-07-27 · `WO-IAC-AUDIT-I01-DOC-HONESTY`):** the *unbounded*
> `_sb_buf` / permanent `_STATE_SB` wedge described below is **historical**. It was
> closed on main by PR #64 (`884f73e`) / `WO-IAC-SB-BUFFER-BOUND`: tip has
> `_SB_BUF_MAX = 1024` (`session/iac.py`); on overflow the handler abandons the
> subnegotiation, clears the buffer, returns to `_STATE_DATA`, and logs a WARNING.
> Pins: `tests/test_iac.py` (`test_sb_overflow_*`). The companion
> `rx_count`/`last_rx` vs terminal-feed question remains open as
> `WO-CONN-RX-COUNTERS-VS-TERMINAL-FEED` — not claimed closed here.

### Historical defect (pre-`884f73e`)

In `_STATE_SB`, every non-`IAC` byte was appended to `self._sb_buf`. There was no
length cap and no timeout. If the peer ever sent `IAC SB` without a matching
`IAC SE` — one corrupt byte pair on the wire was enough — the state machine never
returned to `_STATE_DATA`.

Measured (against the pre-fix tip):

```
feed(IAC SB TTYPE)            # open a subnegotiation, never close it
feed("A" * 5000) x 200        # 1,000,000 bytes of ordinary game text follow

_sb_buf                      -> 1,000,001 bytes and still growing
bytes returned to the terminal ->             0
```

**Every subsequent byte was swallowed.** `feed()` returned `b""` forever, pyte was
never fed, and the cockpit viewport froze on whatever it last drew. Recovery
required the peer to send `IAC SE` — which a corrupt or hostile stream never would.

**Why this was MED and not LOW: the honesty failure is that the app's freeze
detector is blind to precisely this freeze.** In `connection.py` the counters
advance *regardless* of whether `feed()` returned anything:

```python
clean = self.negotiator.feed(data)
with self.lock:
    if clean:
        self.terminal.feed(clean)     # ← skipped: clean is empty
    self.rx_count += len(data)        # ← advances anyway
    self.last_rx = time.monotonic()   # ← advances anyway
```

So `last_rx` kept ticking while the screen had stopped moving. That counter
honesty gap is **unchanged by the I-01 buffer cap** and is why
`WO-CONN-RX-COUNTERS-VS-TERMINAL-FEED` stays banked separately.

**Fix shipped:** `WO-IAC-SB-BUFFER-BOUND` — `_SB_BUF_MAX` (1 KiB), abandon +
`_STATE_DATA` + WARNING on overflow. Stamp: `884f73e` (#64); WO DONE stamp #105.

---

## I-02 · MED · an exception in `feed()` kills the reader thread while `connected` still says `True` — `connection.py:137-156`

`clean = self.negotiator.feed(data)` (`:147`) is not wrapped. It runs inside `_reader_loop`
(`:137`), a daemon thread. `self.connected = False` sits at `:156`, **after** the `while`
loop, so an exception propagates straight past it.

Proven by execution with a negotiator that raises the exact `ValueError` a >255-column
terminal produces today (see I-03):

```
reader thread alive after the raise : False
conn.connected still claims         : True
stderr                              : ValueError: bytes must be in range(0, 256)
```

The thread is gone, no byte will ever be read again, and the connection object reports
itself connected. In a curses TUI the stderr traceback is not visible to the operator
either. Note this is reachable from **any** future exception in the negotiation path, not
only the one below — it is the blast radius that makes I-03 worth fixing rather than
shrugging at.

**Suggested follow-on:** `WO-CONN-READER-THREAD-DEATH-HONESTY` — wrap the loop body so an
unexpected exception marks the connection down (and logs) instead of silently ending the
thread with `connected` left `True`. Filed against `connection.py`, not `iac.py`.

---

## I-03 · LOW (latent) · outbound `IAC` is never escaped in NAWS/TTYPE payloads — `iac.py:146-150`, `:138-144`

Telnet requires a `0xFF` inside subnegotiation data to be doubled. Neither `_send_naws` nor
the TTYPE reply does this. Measured:

```
width=255   -> ff fa 1f 00 ff 00 19 ff f0     bare 0xff inside the payload
height=255  -> ff fa 1f 00 50 00 ff ff f0     bare 0xff inside the payload
width=65535 -> ff fa 1f ff ff 00 19 ff f0     two of them
terminal_type=b"AN\xffSI" -> ff fa 18 00 41 4e ff 53 49 ff f0
```

A peer parsing `... 00 ff 00 ...` reads that `ff` as `IAC` and desynchronises.

Worse than the corruption, and more likely: **a dimension above 255 raises instead.**

```
width=-1     -> ValueError: bytes must be in range(0, 256)
width=70000  -> ValueError: bytes must be in range(0, 256)
height=-5    -> ValueError: bytes must be in range(0, 256)
terminal_type="ANSI" (str) -> TypeError: can't concat str to bytes
```

That raise happens inside `feed()`, on the reader thread — i.e. it lands squarely in I-02.

**Severity is LOW *today* and stated honestly as such:** both call sites
(`session.py:77`, `session.py:236`) construct `TelnetHandler()` with no arguments, so the
live values are `80 × 25` and `b"ANSI"` — no `0xFF`, nothing out of range. **The dangerous
inputs are currently unreachable.**

It is filed anyway, and marked *latent* rather than theoretical, because the whole purpose of
NAWS is to report the terminal's **actual** window size. The obvious next improvement to this
module is to pass the real dimensions the cockpit already knows — and a modern wide terminal
exceeding 255 columns is ordinary, not exotic. The bug is armed and waiting for the change
that makes the feature work.

**Suggested follow-on:** `WO-IAC-ESCAPE-OUTBOUND-SUBNEG` — escape `0xFF` → `0xFF 0xFF` in
both payload builders, and clamp/validate dimensions to `0..65535` before splitting them,
*before* anyone wires real terminal dimensions in.

---

## I-04 · LOW · negotiation is stateless, so a mirroring peer never converges — `iac.py:133-136`

`DONT x` → reply `WONT x`; `WONT x` → reply `DONT x`, unconditionally, with no memory of the
option's current state. Measured:

```
peer DONT 99 -> we reply ff fc 63   (WONT 99)
peer WONT 99 -> we reply ff fe 63   (DONT 99)
DO 99 three times -> ff fc 63, ff fc 63, ff fc 63   (identical every time)
```

RFC 854's loop-prevention rule is to respond **only when the option state actually changes**.
Against a well-behaved server this never bites — TWGS does not mirror — which is why this is
LOW and why nothing has gone wrong in practice. Against a peer applying the same naive
policy, `WONT → DONT → WONT → …` does not terminate.

**Suggested follow-on:** `WO-IAC-OPTION-STATE-TABLE` — track per-option state and suppress
no-op replies. Low priority; no observed failure.

---

## I-05 · LOW · "treat as continuing SB data" discards a byte of that data — `iac.py:98-101`

```python
else:
    # Malformed — treat as continuing SB data.
    self._sb_buf.append(b)
    self._state = _STATE_SB
```

The comment describes resuming SB data collection. It appends `b` — but the `IAC` that put
us in `_STATE_SB_IAC` is **never appended**, so it is silently dropped. Measured with
`IAC SB TTYPE 01 IAC 0x42 IAC SE`:

```
payload delivered to _handle_subnegotiation: 18 01 42     (3 bytes)
payload actually on the wire:                18 01 ff 42  (4 bytes)
```

No caller is affected today (only `TTYPE`+`TTYPE_SEND` is inspected, at fixed offsets 0 and
1), so this is a comment-vs-code gap rather than a live bug. Either append the `IAC` too, or
say that it is deliberately dropped.

---

## I-06 · LOW · the module docstring implies NAWS subnegotiations are answered — `iac.py:8-10`

> "Answer option negotiation (WILL/WONT/DO/DONT) and the TTYPE/NAWS subnegotiations a TWGS
> door expects"

`_handle_subnegotiation` inspects **only** TTYPE. A NAWS subnegotiation arriving from the
peer is received and silently ignored:

```
peer sends IAC SB NAWS 00 50 00 19 IAC SE -> our reply: b''
```

**That silence is correct** — NAWS is a client→server option; there is nothing to answer.
The code is right and the sentence is loose: NAWS is *sent* (in response to `DO NAWS`), not
*answered*. Worth one clause so a reader does not go looking for a missing handler.

---

## Probed and clean — stated so the absence of a finding is not mistaken for absence of a check

**Split IAC sequences across `feed()` calls.** The module docstring's headline claim
("an IAC sequence split across two recv() calls is handled correctly"). Fed
`[0x41, IAC]` then `[DO, NAWS, 0x42]`: returned `b'A'` then `b'B'`, with the correct
`WILL NAWS` + NAWS reply queued. **The claim holds.**

**`IAC IAC` unescaping in the data stream.** Fed `[0x41, IAC, IAC, 0x42]` → `b'A\xffB'`.
A literal `0xFF` in game output survives as exactly one byte. **Correct.**

**Reconnect state.** `session.py:236` constructs a **new** `TelnetHandler` on reconnect, so
none of the stuck states above survive a reconnect — including the historical I-01 wedged
`_STATE_SB` (pre-cap). That mitigation is why I-01 was rated MED rather than HIGH: the
operator could escape by reconnecting, if they realised they needed to. (Tip also caps
`_sb_buf` now — see §I-01 CLOSED.)

---

## Banked follow-on WOs (per Accept #3 — captured, not built here)

| WO | Target | From |
|---|---|---|
| `WO-IAC-SB-BUFFER-BOUND` | `iac.py` — cap `_sb_buf`, abandon + surface on overflow | I-01 · **DONE** (`884f73e` / #64; stamp #105) |
| `WO-CONN-RX-COUNTERS-VS-TERMINAL-FEED` | `connection.py` — should `last_rx` advance when nothing reached the terminal? | I-01 |
| `WO-CONN-READER-THREAD-DEATH-HONESTY` | `connection.py` — a dead reader thread must not leave `connected=True` | I-02 |
| `WO-IAC-ESCAPE-OUTBOUND-SUBNEG` | `iac.py` — escape `0xFF`, validate dimensions | I-03 |
| `WO-IAC-OPTION-STATE-TABLE` | `iac.py` — per-option state, suppress no-op replies | I-04 |

---

## Note on method

Findings I-01 through I-05 came from executing the state machine with adversarial byte
streams; I-02 was proven with a stand-in negotiator that raises the exact exception I-03
produces; the two "clean" surfaces came from the same treatment producing the documented
answer. **A surface reported clean here means a probe was run and returned the expected
result** — not that the code was read and looked reasonable.

No fuzzing infrastructure was added (WO constraint); every probe above is a handful of
literal byte sequences, reproducible from this document alone.
