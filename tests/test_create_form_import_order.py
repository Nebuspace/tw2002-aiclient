"""Regression: create_form_screen must import alone (circular-import catch).

WO-SCREENS-CREATE-FORM-SPLIT smoke imported ``screens`` first, which hid a cycle:
``create_form_screen`` → ``screens`` → ``create_form_screen`` while the latter
was still initializing.
"""

from __future__ import annotations


def test_create_form_screen_imports_alone() -> None:
    import tw2002_aiclient.create_form_screen as cfs

    assert cfs.CreateFormScreen is not None
    assert cfs.validate_create_form is not None


def test_screens_reexports_create_form_lazily() -> None:
    from tw2002_aiclient import screens
    from tw2002_aiclient.create_form_screen import CreateFormScreen

    assert screens.CreateFormScreen is CreateFormScreen
    assert screens.validate_create_form is not None
