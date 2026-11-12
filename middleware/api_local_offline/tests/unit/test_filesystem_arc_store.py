"""Tests for FilesystemArcStore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from arctrl import ARC, ArcInvestigation, Comment

from middleware.api_local_offline.config import LocalOfflineConfig
from middleware.api_local_offline.filesystem_store import FilesystemArcStore


def _minimal_arc(identifier: str = "demo-arc") -> ARC:
    payload = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "additionalType": "Investigation",
                "identifier": identifier,
                "name": "Demo",
            }
        ],
    }
    return ARC.from_rocrate_json_string(json.dumps(payload))


@pytest.mark.asyncio
async def test_create_or_update_writes_arc_tree(tmp_path: Path) -> None:
    store = FilesystemArcStore(LocalOfflineConfig(output_root=tmp_path))
    arc = _minimal_arc("safe-id")
    pushed = await store.create_or_update("arcid123", arc, rdi="publisso")
    assert pushed is True
    target = tmp_path / "arcid123"
    assert target.is_dir()
    assert any(target.iterdir())


@pytest.mark.asyncio
async def test_create_or_update_collapses_duplicate_comment_names(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicate Comment names on one holder must not block offline WriteAsync."""
    store = FilesystemArcStore(LocalOfflineConfig(output_root=tmp_path))
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="dup-note", title="T"))
    arc.Comments.append(Comment.create("note", "first"))
    arc.Comments.append(Comment.create("note", "second"))
    with caplog.at_level("WARNING"):
        pushed = await store.create_or_update("arc_dup_comments", arc, rdi="publisso")
    assert pushed is True
    target = tmp_path / "arc_dup_comments"
    assert target.is_dir()
    assert any(target.iterdir())
    assert {c.Name: c.Value for c in arc.Comments} == {"note": "second"}
    assert any("note" in r.message and "Investigation" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_same_identifier_basename_different_arc_ids_do_not_collide(tmp_path: Path) -> None:
    store = FilesystemArcStore(LocalOfflineConfig(output_root=tmp_path))
    arc = _minimal_arc("10.1234/shared-suffix")
    await store.create_or_update("arc_from_rdi_a", arc, rdi="rdi-a")
    await store.create_or_update("arc_from_rdi_b", arc, rdi="rdi-b")
    assert (tmp_path / "arc_from_rdi_a").is_dir()
    assert (tmp_path / "arc_from_rdi_b").is_dir()


@pytest.mark.asyncio
async def test_unsafe_arc_id_stays_under_output_root(tmp_path: Path) -> None:
    store = FilesystemArcStore(LocalOfflineConfig(output_root=tmp_path))
    arc = _minimal_arc("demo-arc")
    await store.create_or_update("../../etc/passwd", arc, rdi="publisso")
    written = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert written
    for path in written:
        assert "etc" not in path.parts


def test_check_health_without_git(tmp_path: Path) -> None:
    store = FilesystemArcStore(LocalOfflineConfig(output_root=tmp_path))
    assert store.check_health() is True


@pytest.mark.asyncio
async def test_finalize_is_noop(tmp_path: Path) -> None:
    store = FilesystemArcStore(LocalOfflineConfig(output_root=tmp_path))
    assert await store.finalize(rdi="publisso") is False
