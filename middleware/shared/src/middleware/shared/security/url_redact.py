"""Redact credentials embedded in URL userinfo (e.g. oauth2 tokens in Git remotes)."""

from __future__ import annotations

import re

# http(s)://user:pass@host or http(s)://token@host — used by Git HTTPS remotes.
_URL_USERINFO = re.compile(r"(https?://)([^/\s\"'<>]+)@", re.IGNORECASE)


def redact_url_userinfo(text: str) -> str:
    """Replace URL userinfo with ``***@`` so tokens never appear in logs/events."""
    return _URL_USERINFO.sub(r"\1***@", text)
