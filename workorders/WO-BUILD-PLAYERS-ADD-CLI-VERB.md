# WO-BUILD-PLAYERS-ADD-CLI-VERB

**Status:** IN FLIGHT · impl-aiclient-h1  
**Priority:** LOW  

## Goal

Wire `tw players add` as a thin CLI wrapper over `credentials.create_profile()`.

## Accept

- Parser exposes `tw players add --server KEY --game-letter L --handle HANDLE [--profile NAME]`.
- Success prints the profile section name; `ValueError` → stderr + exit 1.
- No socket/login path; no new credential writes beyond `create_profile`.

## Proof

```bash
.venv/bin/python -m pytest tests/test_players_cli_add.py tests/test_cli_log.py -n0 -q -k players
```

live-prove: n/a (offline CLI metadata).
