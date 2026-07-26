#!/usr/bin/env python3
"""Scout for WO-GAME-SELECT-CLASSIFY-SCOUT — throwaway analysis, not product code.

Replays archived session transcripts through the REAL `TelnetHandler ->
TerminalScreen` pipeline -- the same pipeline `Session.classify()` drives in
production (`tw2002_aiclient/session/session.py`) -- and classifies every
SETTLED frame that carries the TWGS "Selection (? for menu):" prompt (the
generic prompt shared by the boxed/banner `game_select` variants and by an
ordinary TWGS lobby menu; see `classify.py`'s own docstring).

A frame is SETTLED at the render captured immediately before each real `TX`
event -- the screen the operator was actually looking at when they typed
their answer. This mirrors the corpus methodology already established
elsewhere in this codebase (`tw2002_aiclient/menu/crawler.py`'s
`_UNSAFE_SCREEN_PATTERNS` comment: "91 archived session transcripts ...
11,240 settled prompt frames the operator actually answered"). `TX-IAC`
(our own automatic telnet negotiation replies) does not count as an
answered prompt and is not captured.

The "active prompt" for a frame is `render_cropped()`'s own LAST row,
`.strip()`ped -- byte-for-byte the same definition `Session.
current_prompt_line()` uses in production. This is deliberate and load-
bearing: a scout that substitutes some OTHER line containing the Selection
text (one found elsewhere in the buffer, possibly stale) as the "prompt"
argument to `classify_screen()` is evaluating a shape the live gate-anchor
path never actually evaluates (gate anchors — including the game_select
boxed/banner checks — always run against the true last line only; see
`classify.py`'s own module docstring and `Session.classify()`). Reusing the
exact same accessor as production is what makes this scout's numbers mean
anything about the live path, rather than about a hand-rolled variant of it.

Log format (`archive/pre-rebirth-2026-07-23/code/twclient/logging_util.py`):
each record is `[timestamp] DIRECTION (N bytes)\\n<payload>` where payload is
exactly N *characters*, the result of `raw_bytes.decode("latin-1")`, written
into a UTF-8 text file. Opened here with `encoding="utf-8", newline=""` per
the WO -- `newline=""` is load-bearing: the payload can itself contain raw
`\\r`/`\\n` bytes (real telnet CRLF line endings), and Python's universal-
newline translation would silently rewrite/collapse them under the default
text mode, corrupting the exact byte count `parse_log` relies on to slice
the payload out.

Prints ONLY aggregate counts (plus, with --show-example, ONE full rendered
door-select screen -- server banner + menu text, no player-typed content) to
stdout -- never raw corpus lines otherwise -- since the corpus
(`archive/.../runtime/logs/*.log`, gitignored, NOT tracked in git) may
contain real player handles.
"""

import argparse
import os
import re
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _REPO_ROOT)

from tw2002_aiclient.session import classify  # noqa: E402
from tw2002_aiclient.session.iac import TelnetHandler  # noqa: E402
from tw2002_aiclient.session.terminal import TerminalScreen  # noqa: E402

DEFAULT_CORPUS_DIR = os.path.join(_REPO_ROOT, "archive", "pre-rebirth-2026-07-23", "runtime", "logs")

# NOTE: no `^` anchor. `Pattern.match(text, pos)` already anchors the
# attempt at exactly `pos` -- adding `^` (without re.MULTILINE) would
# additionally require `pos == 0` (the TRUE start of the string), which
# silently kills every match after the first record. This bit once; keep
# it documented so nobody "cleans up" the missing anchor back in.
_HEADER_BYTES_RE = re.compile(r"\[[^\]]*\] (RX|TX|TX-IAC) \((\d+) bytes\)\n")
_HEADER_OTHER_RE = re.compile(r"\[[^\]]*\] [^\n]*\n")


def parse_log(path):
    """Yield (direction, raw_bytes) tuples in file order. Reconstructs the
    ORIGINAL bytes the daemon RX'd/TX'd (see module docstring for the
    latin-1-decode-into-utf-8 round trip logging_util.py performs)."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    pos = 0
    n = len(text)
    while pos < n:
        m = _HEADER_BYTES_RE.match(text, pos)
        if m:
            direction = m.group(1)
            nbytes = int(m.group(2))
            start = m.end()
            payload_text = text[start : start + nbytes]
            pos = start + nbytes
            if not payload_text.endswith("\n") and pos < n and text[pos] == "\n":
                pos += 1
            yield direction, payload_text.encode("latin-1")
            continue
        m2 = _HEADER_OTHER_RE.match(text, pos)
        if m2:
            # NOTE lines / redacted-secret markers: no byte payload to
            # replay, and not a real answered prompt either way.
            pos = m2.end()
            continue
        # Unrecognized content at this position -- stop defensively rather
        # than risk mis-slicing the rest of the file as data.
        break


def replay_log(path):
    """Real TelnetHandler -> TerminalScreen pipeline, exactly
    `Session.classify()`'s own pair (session.py). Returns one
    (full_text, prompt_line, tx_payload) tuple per SETTLED frame -- the
    render captured immediately before each real TX (see module
    docstring), plus what was actually sent in answer to it."""
    handler = TelnetHandler()
    term = TerminalScreen()
    frames = []
    for direction, payload in parse_log(path):
        if direction == "RX":
            clean = handler.feed(payload)
            term.feed(clean)
        elif direction == "TX":
            rows = term.render_cropped()
            full_text = "\n".join(rows)
            prompt_line = rows[-1].strip() if rows else ""
            frames.append((full_text, prompt_line, payload))
        # TX-IAC: our own negotiation reply, not an answered prompt -- skip.
    return frames


def has_boxed_game_header(full_text):
    """Mirrors classify.py's own `_is_twgs_boxed_game_select_menu` header
    scan (presence only, not "last wins" -- this scout just needs to know
    whether the signal exists anywhere on the settled grid)."""
    for line in full_text.splitlines():
        for cell in classify._BOX_VERTICAL_SEPARATOR_RE.split(line):
            if classify._GAME_HEADER_LINE_RE.match(cell.strip()):
                return True
    return False


def banner_signals(full_text):
    """(title, version, registered, all_three) presence on the CURRENT
    settled grid -- the literal "is the TWGS startup banner still on the
    rendered 80x25 grid" measurement the WO asks for. `render_cropped()`
    never drops non-blank content (it only trims trailing blank rows/
    cols), so presence here is equivalent to presence in the raw 25-row
    buffer."""
    title = bool(classify._TWGS_BANNER_TITLE_RE.search(full_text))
    version = bool(classify._TWGS_BANNER_VERSION_RE.search(full_text))
    registered = bool(classify._TWGS_BANNER_REGISTERED_RE.search(full_text))
    return title, version, registered, (title and version and registered)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-dir", default=DEFAULT_CORPUS_DIR)
    ap.add_argument(
        "--show-example",
        action="store_true",
        help="print ONE full settled game_select frame + the TX bytes that answered it "
        "(server banner + menu text only -- no player-typed content survives past the "
        "first such frame found)",
    )
    args = ap.parse_args()

    corpus_dir = args.corpus_dir
    if not os.path.isdir(corpus_dir):
        print(f"no corpus at {corpus_dir!r} -- nothing to replay", file=sys.stderr)
        return 1

    log_paths = []
    for root, _dirs, files in os.walk(corpus_dir):
        for fn in files:
            if fn.endswith(".log"):
                log_paths.append(os.path.join(root, fn))
    log_paths.sort()

    total_settled_frames = 0
    selection_frames = 0
    class_counts = {}
    # Diagnosis buckets, only meaningful for non-game_select outcomes:
    conjunction_broken = 0  # banner (or boxed header) WAS on-grid, still not game_select
    banner_scrolled_off = 0  # neither banner nor boxed header on-grid
    diagnosis_examples = {"conjunction_broken": [], "banner_scrolled_off": []}
    shown_example = False

    for path in log_paths:
        frames = replay_log(path)
        total_settled_frames += len(frames)
        for full_text, prompt_line, tx_payload in frames:
            if not classify._TWGS_SELECTION_PROMPT_RE.search(prompt_line):
                continue
            selection_frames += 1
            cls = classify.classify_screen(full_text, prompt_line)
            class_counts[cls] = class_counts.get(cls, 0) + 1
            if cls != "game_select":
                title, version, registered, banner_full = banner_signals(full_text)
                boxed_header = has_boxed_game_header(full_text)
                on_grid = banner_full or boxed_header
                sample = {
                    "file": os.path.basename(path),
                    "class": cls,
                    "banner_title": title,
                    "banner_version": version,
                    "banner_registered": registered,
                    "boxed_game_header": boxed_header,
                }
                if on_grid:
                    conjunction_broken += 1
                    if len(diagnosis_examples["conjunction_broken"]) < 5:
                        diagnosis_examples["conjunction_broken"].append(sample)
                else:
                    banner_scrolled_off += 1
                    if len(diagnosis_examples["banner_scrolled_off"]) < 5:
                        diagnosis_examples["banner_scrolled_off"].append(sample)
            elif args.show_example and not shown_example:
                shown_example = True
                print("=== example settled game_select frame (server banner + menu text only) ===")
                print(full_text)
                print(f"--- prompt_line: {prompt_line!r}")
                print(f"--- TX that answered it: {tx_payload!r}")
                print(f"--- classify_screen result: {cls}")
                print()

    print(f"logs replayed: {len(log_paths)}")
    print(f"settled frames (pre-TX renders): {total_settled_frames}")
    print(f"settled frames carrying the Selection(?for menu) prompt: {selection_frames}")
    print()
    print("class distribution at Selection-prompt settled frames:")
    for cls, count in sorted(class_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {cls}: {count}")
    print()
    print("of the non-game_select Selection-prompt frames:")
    print(f"  conjunction broken (banner/boxed header STILL on-grid, still not game_select): {conjunction_broken}")
    print(f"  banner scrolled off (neither banner nor boxed header present on-grid): {banner_scrolled_off}")
    print()
    print("up to 5 examples of each (filename + flags only -- no corpus content):")
    for bucket, examples in diagnosis_examples.items():
        print(f"  {bucket}:")
        for ex in examples:
            print(f"    {ex}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
