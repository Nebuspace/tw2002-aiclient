---
type: Reference
title: Test Cases — Cockpit Liveness Pty
description: WO-P3-038 wire -- control-strip liveness cluster, Layer-B.
resource: repo://tw2002-aiclient/tests/test_cockpit_liveness_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_liveness_pty.py`

_WO-P3-038 wire -- control-strip liveness cluster, Layer-B._

| Test | Blurb |
|------|-------|
| `test_full_tier_heartbeat_glyph_changes_between_controlled_clock_captures` | Full tier heartbeat glyph changes between controlled clock captures. |
| `test_full_tier_idle_tx_readout_and_cluster_visible` | Full tier idle tx readout and cluster visible. |
| `test_minimal_tier_cluster_present_despite_no_side_gutters` | CONTROL_STRIP's presence is decided by height alone, independent of. |
| `test_full_tier_ascii_mode_swaps_heartbeat_but_tx_arrow_survives` | Full tier ascii mode swaps heartbeat but tx arrow survives. |
| `test_poll_guard_fires_at_minimal_tier_because_of_control_strip` | LIVE, not latent (see ``screens. |
| `test_poll_guard_still_never_double_polls_when_control_strip_joins_other_consumers` | A tier where control_strip AND right_gutter/HUD are both present. |
| `test_play_shell_screen_handle_key_unchanged_esc_and_q_only` | Play shell screen handle key unchanged esc and q only. |
| `test_now_fn_seam_feeds_the_liveness_composer` | Now fn seam feeds the liveness composer. |
| `test_raising_now_fn_does_not_crash_draw_and_cluster_still_renders` | Mack finding, HIGH (directly reproduced): a raising ``now_fn`` --. |
