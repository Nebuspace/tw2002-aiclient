"""Persistence and product reach for the guarded rule-macro reflex layer.

The decision kernel is :mod:`tw2002_aiclient.rule_engine` -- pure, offline,
and deliberately unaware of where rules come from. This package is the half
that gives it a body: :mod:`.store` reads persisted rule documents, and
:mod:`.reflex` turns a live screen classification into the kernel's answer.

**Nothing here fires anything.** A :class:`~tw2002_aiclient.rule_engine.Decision`
naming a macro is a *proposal*; the taught run path
(``arm-confirm -> adapters.autoloop_start -> session/autoloop.py ->
loops.player.replay_loop``) is unchanged and still requires the human's
confirmed arm before a byte moves. See :mod:`.reflex` for the two landings
this slice deliberately leaves inert.
"""
