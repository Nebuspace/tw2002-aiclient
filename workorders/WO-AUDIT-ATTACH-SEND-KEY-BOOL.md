# WO-AUDIT-ATTACH-SEND-KEY-BOOL — Interactive tw attach honors send_key bool

> Status: **EXECUTED / DONE** 2026-07-25 · product tip **`7e13b7d`** (CC · rebased from `4754dd4`) · docs stamp Cursor  
> Refs: session-audit 🔴 F1 · scripted sibling `032bc12` · `app.py:382-394` · hub Accept `@ 12:51:12Z`

## Tip verdict
**DONE** on origin `7e13b7d` — interactive `tw attach` loop honors `send_key()` bool at **both** call sites via one shared `sent_ok` failure path (exit 1; restore→print→close ordering proven on real pty). AST tripwire bans bare `send_key(...)` Expr. Suite **1928/0/0** at Accept (isolated cert). Disclosed micros banked separately (settle-nudge `:249` · module docstring lifetime-stream lie).

## Goal
Same obligation as scripted `--keys` branch: False send must not leave operator in silent ATTACHED black hole.

## Proof
Hub Accept `@ 12:51:12Z` · origin tip `7e13b7d`. Push waits Accept (product already SHIPped).
