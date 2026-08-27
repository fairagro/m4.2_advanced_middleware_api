"""Integration tests for ConsolidatedGitArcStore finalize against a real Git remote."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from git import Repo

from middleware.api.arc_store.consolidated_git import ConsolidatedGitArcStore, ConsolidatedGitConfig
from middleware.api.arc_store.consolidated_git.catalog_jsonld import normalize_catalog_datasets
from middleware.api.arc_store.consolidated_git.catalog_serialize import extract_catalog_dataset, serialize_catalog_file
from middleware.shared.json_types import JsonValue, RoCrateContent, RoCrateGraphNode


def _minimal_rocrate_dict(identifier: str, **root_fields: JsonValue) -> RoCrateContent:
    """Build a minimal RO-Crate wire document for catalog finalize tests."""
    root: RoCrateGraphNode = {
        "@id": "./",
        "@type": "Dataset",
        "additionalType": "Investigation",
        "identifier": identifier,
        **root_fields,
    }
    return {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            root,
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
                "about": {"@id": "./"},
            },
        ],
    }


@pytest.fixture
def bare_catalog_remote(tmp_path: Path) -> Path:
    """Bare Git remote directory for the shared catalog repository."""
    remote = tmp_path / "catalog.git"
    remote.parent.mkdir(parents=True, exist_ok=True)
    return remote


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Ephemeral clone cache directory for finalize operations."""
    path = tmp_path / "cache"
    path.mkdir()
    return path


@pytest.fixture
def consolidated_config(bare_catalog_remote: Path, cache_dir: Path) -> ConsolidatedGitConfig:
    """Consolidated Git config pointing at a local file:// bare remote."""
    return ConsolidatedGitConfig(
        repo_url=f"file://{bare_catalog_remote.resolve()}",
        branch="main",
        cache_dir=cache_dir,
    )


@pytest.fixture
def doc_store() -> MagicMock:
    """Document store returning two ARC bodies for catalog rebuild."""
    arcs = [
        ("arc-b", _minimal_rocrate_dict("DS-B", name="Dataset B")),
        ("arc-a", _minimal_rocrate_dict("DS-A", name="Dataset A")),
    ]
    store = MagicMock()

    async def _iter_arcs(_rdi: str):
        for item in arcs:
            yield item

    store.iter_arc_contents_by_rdi = MagicMock(side_effect=_iter_arcs)
    store._catalog_arcs = arcs  # test helper for expected bytes
    return store


@pytest.fixture
def catalog_store(
    consolidated_config: ConsolidatedGitConfig,
    doc_store: MagicMock,
) -> Generator[ConsolidatedGitArcStore, None, None]:
    """ConsolidatedGitArcStore wired to mock CouchDB and real Git."""
    store = ConsolidatedGitArcStore(consolidated_config, doc_store)
    yield store


async def _expected_catalog_bytes(doc_store: MagicMock) -> bytes:
    """Rebuild expected catalog bytes the same way finalize does."""
    datasets = [extract_catalog_dataset(content) for _, content in doc_store._catalog_arcs]
    normalized = await normalize_catalog_datasets(datasets)
    return serialize_catalog_file(normalized)


def _read_catalog_from_remote(bare_remote: Path, rdi: str, *, branch: str = "main") -> bytes:
    """Clone the bare remote and read ``{rdi}.json`` from the checked-out tree."""
    with tempfile.TemporaryDirectory(prefix="catalog_verify_") as clone_dir:
        Repo.clone_from(str(bare_remote), clone_dir, branch=branch)
        return (Path(clone_dir) / f"{rdi}.json").read_bytes()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_finalize_pushes_catalog_to_bare_remote(
    catalog_store: ConsolidatedGitArcStore,
    bare_catalog_remote: Path,
    doc_store: MagicMock,
) -> None:
    """First finalize performs a real commit/push and writes ``{rdi}.json`` to the remote."""
    expected_bytes = await _expected_catalog_bytes(doc_store)

    pushed = await catalog_store.finalize(rdi="edal")

    assert pushed is True
    assert bare_catalog_remote.exists()
    assert _read_catalog_from_remote(bare_catalog_remote, "edal") == expected_bytes


@pytest.mark.asyncio
@pytest.mark.integration
async def test_finalize_skips_push_when_catalog_unchanged(
    catalog_store: ConsolidatedGitArcStore,
    bare_catalog_remote: Path,
    doc_store: MagicMock,
) -> None:
    """Second finalize with identical ARC bodies does not push again."""
    expected_bytes = await _expected_catalog_bytes(doc_store)

    first_pushed = await catalog_store.finalize(rdi="edal")
    remote_after_first = _read_catalog_from_remote(bare_catalog_remote, "edal")

    second_pushed = await catalog_store.finalize(rdi="edal")
    remote_after_second = _read_catalog_from_remote(bare_catalog_remote, "edal")

    assert first_pushed is True
    assert second_pushed is False
    assert remote_after_first == expected_bytes
    assert remote_after_second == remote_after_first


@pytest.mark.asyncio
@pytest.mark.integration
async def test_finalize_removes_ephemeral_clone_directories(
    catalog_store: ConsolidatedGitArcStore,
    cache_dir: Path,
) -> None:
    """Temp working directories under ``cache_dir`` are removed after finalize."""
    await catalog_store.finalize(rdi="edal")

    leftover = list(cache_dir.glob("catalog_finalize_*"))
    assert not leftover
