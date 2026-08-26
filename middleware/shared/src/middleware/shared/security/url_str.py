"""URL value type that redacts HTTP(S) userinfo on ordinary stringification."""

from __future__ import annotations

from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import PydanticCustomError, core_schema

from middleware.shared.security.url_redact import redact_url_userinfo


class UrlStr:
    """Credential-bearing URL: ``str()`` redacts userinfo; ``unredacted()`` for Git.

    Use this instead of plain ``str`` (or fully opaque ``SecretStr``) for remotes
    that may embed oauth2 tokens in the URL. Host and path remain visible after
    redaction for ops diagnostics.
    """

    __slots__ = ("_url",)

    def __init__(self, url: str) -> None:
        """Wrap *url*; may contain userinfo credentials."""
        self._url = url

    def unredacted(self) -> str:
        """Return the full URL including credentials (Git CLI / GitPython only)."""
        return self._url

    def __str__(self) -> str:
        """Redacted form safe for logs, traces, and diagnostics."""
        return redact_url_userinfo(self._url)

    def __repr__(self) -> str:
        """Repr uses the redacted form so tokens never appear in debug output."""
        return f"UrlStr({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        """Compare on the raw URL; also accepts an equal plain ``str``."""
        if isinstance(other, UrlStr):
            return self._url == other._url
        if isinstance(other, str):
            return self._url == other
        return NotImplemented

    def __hash__(self) -> int:
        """Hash the raw URL so equal ``UrlStr`` values collide correctly."""
        return hash(self._url)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source: type[Any],
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        """Accept ``str`` or ``UrlStr``; serialize as the redacted string."""

        def _validate(value: object) -> UrlStr:
            if isinstance(value, UrlStr):
                return value
            if isinstance(value, str):
                return UrlStr(value)
            raise PydanticCustomError(
                "url_str_type",
                "UrlStr input should be a str or UrlStr",
            )

        python_schema = core_schema.no_info_plain_validator_function(_validate)
        return core_schema.json_or_python_schema(
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(cls),
                python_schema,
            ]),
            json_schema=core_schema.no_info_after_validator_function(
                _validate,
                core_schema.str_schema(),
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                str,
                when_used="always",
            ),
        )
