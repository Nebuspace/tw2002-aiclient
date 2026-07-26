# WO-CODEQL-COCKPIT-STRIP-URL-SUBSTRING

**Status:** OPEN · READY · Cursor preferred (test pin) · banked from code-scanning sweep  
**Posted:** 2026-07-26 · GitHub code scanning alert #2  
**Alert:** https://github.com/Nebuspace/tw2002-aiclient/security/code-scanning/2  
**Rule:** `py/incomplete-url-substring-sanitization` (warning)  
**Path:** `tests/test_cockpit_strip.py` (~line 248)  
**Likely introduced:** `2a2d65c` (WO-P3-031-033 trainer-cockpit frame) — scan lagged onto `main`

## Goal

Clear the CodeQL warning that treats `assert result.startswith("resolved.example.net")` as an incomplete URL substring sanitization check.

## Context

This is a **unit test** asserting the profile strip displays the host string — not production URL sanitization. Still: fix the shape so the analyzer is satisfied (prefer honest assert rewrite over `nosec`/dismiss unless dismiss is clearly correct).

## Fix shape (pick one, prove green)

- Assert equality on the host token (`result.split(...)[0] == "resolved.example.net"`), or
- Build expected strip prefix via the same composer helpers, or
- Use `urllib.parse` if the test is genuinely about URL host identity

Do **not** weaken the pin (host must still win over `server=` catalog key).

## Scope

- `tests/test_cockpit_strip.py` (and only neighboring asserts if the same pattern repeats)

## Accept

1. Alert #2 clears on next scan / fixed in diff with no `startswith(host)` URL-shaped check CodeQL flags.
2. `pytest tests/test_cockpit_strip.py -q -n0` green.
3. Offline suite green on the PR.

## Proof

```text
pytest tests/test_cockpit_strip.py -q -n0
gh pr checks <PR>
```

## Refs

- Alert #2 · `scripts/hub-code-scanning-sweep.sh` · pre-merge sweep protocol
