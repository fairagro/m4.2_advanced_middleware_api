"""Tests for UrlStr redacting URL type."""

import pytest
from pydantic import BaseModel, ValidationError

from middleware.shared.security import UrlStr


def test_url_str_str_and_repr_redact_userinfo() -> None:
    """Ordinary string conversion hides oauth2 userinfo; host/path remain."""
    url = UrlStr("https://oauth2:secret-token@gitlab.example.com/group/repo.git")
    assert str(url) == "https://***@gitlab.example.com/group/repo.git"
    assert "secret-token" not in str(url)
    assert "secret-token" not in repr(url)
    assert "gitlab.example.com/group/repo.git" in str(url)


def test_url_str_unredacted_returns_raw() -> None:
    """Explicit accessor returns the full credential-bearing URL."""
    raw = "https://oauth2:secret-token@gitlab.example.com/group/repo.git"
    assert UrlStr(raw).unredacted() == raw


def test_url_str_equality_and_hash() -> None:
    """Equality and hashing use the raw URL between UrlStr values only."""
    raw = "https://oauth2:tok@host/r.git"
    a = UrlStr(raw)
    b = UrlStr(raw)
    assert a == b
    assert a != raw
    assert hash(a) == hash(b)
    assert a != UrlStr("https://other.example/r.git")


def test_url_str_pydantic_field_accepts_str_and_url_str() -> None:
    """Model fields typed as UrlStr accept str or UrlStr; dump is redacted."""

    class Model(BaseModel):
        repo: UrlStr

    # model_validate exercises str→UrlStr coercion (constructor is typed as UrlStr only).
    from_str = Model.model_validate({"repo": "https://oauth2:secret@host/r.git"})
    assert from_str.repo.unredacted() == "https://oauth2:secret@host/r.git"
    assert from_str.model_dump()["repo"] == "https://***@host/r.git"

    wrapped = UrlStr("https://oauth2:secret@host/r.git")
    from_url = Model(repo=wrapped)
    assert from_url.repo is wrapped or from_url.repo == wrapped

    with pytest.raises(ValidationError):
        Model.model_validate({"repo": 123})
