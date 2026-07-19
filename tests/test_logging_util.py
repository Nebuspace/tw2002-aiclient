"""Transcript logger tests — no network involved."""

from twclient.logging_util import TranscriptLogger


def test_log_raw_writes_content(tmp_path):
    logger = TranscriptLogger(str(tmp_path))
    logger.log_raw("TX", b"hello\r\n")
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert "hello" in content
    assert "(7 bytes)" in content


def test_log_redacted_never_writes_content(tmp_path):
    logger = TranscriptLogger(str(tmp_path))
    logger.log_redacted("TX")
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert "secret input redacted" in content
    # No byte count either -- that would leak input length.
    assert "bytes)" not in content


def test_log_redacted_custom_note(tmp_path):
    logger = TranscriptLogger(str(tmp_path))
    logger.log_redacted("TX", note="password entry")
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert "password entry" in content


def test_log_note_writes_a_timestamped_diagnostic_line(tmp_path):
    """TW-06/TW-25 Finding 4: the world-model write-hook's swallow-guard
    routes here so a persistent failure leaves SOME operator-visible
    trace instead of vanishing silently forever."""
    logger = TranscriptLogger(str(tmp_path))
    logger.log_note("world_model write_from_state failed: WorldModelError('corrupt store')")
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert "NOTE" in content
    assert "world_model write_from_state failed" in content
