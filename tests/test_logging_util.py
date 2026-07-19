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
