"""Tests for URL userinfo redaction."""

import logging

from middleware.shared.config.logging import RedactingFormatter, install_url_userinfo_redaction
from middleware.shared.security.url_redact import redact_url_userinfo


def test_redact_url_userinfo_oauth2_token() -> None:
    """oauth2 tokens in https URLs are replaced with ***."""
    raw = "push failed: https://oauth2:secret-token@gitlab.example.com/group/repo.git"
    assert redact_url_userinfo(raw) == "push failed: https://***@gitlab.example.com/group/repo.git"
    assert "secret-token" not in redact_url_userinfo(raw)


def test_redacting_formatter_preserves_wrapped_fmt() -> None:
    """Outer formatter exposes the same _fmt as the wrapped layout."""
    inner = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    outer = RedactingFormatter(inner)
    assert outer._fmt == inner._fmt  # noqa: SLF001


def test_redacting_formatter_preserves_wrapped_brace_and_dollar_style() -> None:
    """Brace and dollar styles must survive wrapping so format() stays valid."""
    leak = "https://oauth2:secret-token@host/r.git"
    record = logging.LogRecord("n", logging.ERROR, __file__, 1, leak, (), None)

    brace = logging.Formatter("{message}", style="{")
    brace_outer = RedactingFormatter(brace)
    assert type(brace_outer._style) is type(brace._style)  # noqa: SLF001
    assert "secret-token" not in brace_outer.format(record)

    dollar = logging.Formatter("$message", style="$")
    dollar_outer = RedactingFormatter(dollar)
    assert type(dollar_outer._style) is type(dollar._style)  # noqa: SLF001
    assert "secret-token" not in dollar_outer.format(record)


def test_redacting_formatter_covers_message_and_exception_text() -> None:
    """Formatted log lines (including traceback text) are redacted."""
    logger = logging.getLogger("test_url_redact_formatter")
    logger.handlers.clear()
    logger.propagate = False
    stream = logging.StreamHandler()
    stream.setFormatter(RedactingFormatter(logging.Formatter("%(message)s")))
    logger.addHandler(stream)

    record = logger.makeRecord(
        logger.name,
        logging.ERROR,
        __file__,
        1,
        "failed https://oauth2:secret-token@host/repo.git",
        (),
        None,
    )
    assert "secret-token" not in stream.format(record)


def test_install_url_userinfo_redaction_is_idempotent() -> None:
    """Wrapping handlers twice must not nest forever."""
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    try:
        install_url_userinfo_redaction()
        install_url_userinfo_redaction()
        assert isinstance(handler.formatter, RedactingFormatter)
        assert not isinstance(handler.formatter._wrapped, RedactingFormatter)  # noqa: SLF001
    finally:
        root.removeHandler(handler)


def test_install_url_userinfo_redaction_rewraps_replaced_formatter() -> None:
    """If a handler formatter is replaced after install, the next install re-wraps."""
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    try:
        install_url_userinfo_redaction()
        assert isinstance(handler.formatter, RedactingFormatter)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        install_url_userinfo_redaction()
        assert isinstance(handler.formatter, RedactingFormatter)
        assert handler.formatter._fmt == "%(levelname)s %(message)s"  # noqa: SLF001
        assert "secret-token" not in handler.format(
            logging.LogRecord(
                "test",
                logging.ERROR,
                __file__,
                1,
                "leak https://oauth2:secret-token@host/r.git",
                (),
                None,
            )
        )
    finally:
        root.removeHandler(handler)
