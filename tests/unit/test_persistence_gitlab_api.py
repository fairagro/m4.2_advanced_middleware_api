"""Unit tests for the GitLab API persistence layer."""

# pylint: disable=protected-access

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from gitlab.exceptions import GitlabGetError

# -------------------- Hilfsfunktionen --------------------


def test_compute_arc_hash(tmp_path, gitlab_api):
    """Tests the hash computation for ARC directories."""
    file = tmp_path / "f.txt"
    file.write_text("hello")
    h1 = gitlab_api._compute_arc_hash(tmp_path)
    file.write_text("world")
    h2 = gitlab_api._compute_arc_hash(tmp_path)
    assert h1 != h2  # nosec


def test_get_or_create_project_found(gitlab_api):
    """Tests finding an existing GitLab project."""
    project = MagicMock()
    project.path = "arc1"
    gitlab_api._gitlab.projects.list.return_value = [project]
    result = gitlab_api._get_or_create_project("arc1")
    assert result == project  # nosec


def test_get_or_create_project_create(gitlab_api):
    """Tests creating a new GitLab project if not found."""
    gitlab_api._gitlab.projects.list.return_value = []
    group = MagicMock()
    group.id = 1
    gitlab_api._gitlab.groups.get.return_value = group
    project = MagicMock()
    gitlab_api._gitlab.projects.create.return_value = project
    result = gitlab_api._get_or_create_project("arc1")
    assert result == project  # nosec


# -------------------- Create/Update --------------------


@pytest.mark.asyncio
async def test_create_or_update_no_changes(gitlab_api):
    """Tests that no commit is made if the ARC hash hasn't changed."""
    arc = MagicMock()
    arc.Write = lambda path: (Path(path) / "f.txt").write_text("abc")

    project = MagicMock()
    # .arc_hash mit "dummyhash" vorhanden
    project.files.get.return_value.content = base64.b64encode(b"dummyhash").decode()
    gitlab_api._get_or_create_project = lambda arc_id: project
    gitlab_api._compute_arc_hash = lambda path: "dummyhash"

    await gitlab_api.create_or_update("arc1", arc)
    project.commits.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_or_update_with_changes(gitlab_api):
    """Tests that a commit is made if the ARC hash has changed."""
    arc = MagicMock()
    arc.Write = lambda path: (Path(path) / "f.txt").write_text("abc")

    project = MagicMock()

    # kein .arc_hash vorhanden
    def raise_get(*args, **kwargs):
        raise GitlabGetError("not found", response_code=404)

    project.files.get.side_effect = raise_get
    gitlab_api._get_or_create_project = lambda arc_id: project
    gitlab_api._compute_arc_hash = lambda path: "newhash"

    await gitlab_api.create_or_update("arc1", arc)
    project.commits.create.assert_called_once()
    args, _kwargs = project.commits.create.call_args
    actions = args[0]["actions"]
    assert any(a["file_path"] == ".arc_hash" for a in actions)  # nosec


# -------------------- Get --------------------


def test_get_success(gitlab_api, monkeypatch):
    """Tests retrieving an ARC from GitLab."""
    project = MagicMock()
    project.path = "arc1"
    project.repository_tree.return_value = [
        {"type": "blob", "path": "f.txt"},
        {"type": "blob", "path": ".arc_hash"},
    ]

    fobj = MagicMock()
    fobj.content = base64.b64encode(b"hello").decode()
    fobj.encoding = None
    project.files.get.return_value = fobj

    gitlab_api._gitlab.projects.list.return_value = [project]

    dummy_arc = MagicMock()
    monkeypatch.setattr(
        "middleware_api.arc_store.gitlab_api.ARC.try_load_async", lambda path: dummy_arc
    )

    arc = gitlab_api.get("arc1")
    assert arc == dummy_arc  # nosec
    project.files.get.assert_any_call(file_path="f.txt", ref=gitlab_api._config.branch)


def test_get_not_found(gitlab_api):
    """Tests retrieving a non-existing ARC from GitLab."""
    gitlab_api._gitlab.projects.list.return_value = []
    arc = gitlab_api.get("arcX")
    assert arc is None  # nosec


# -------------------- Delete --------------------


def test_delete_found(gitlab_api):
    """Tests deleting an existing ARC from GitLab."""
    project = MagicMock()
    project.path = "arc1"
    gitlab_api._gitlab.projects.list.return_value = [project]
    gitlab_api.delete("arc1")
    project.delete.assert_called_once()


def test_delete_not_found(gitlab_api):
    """Tests deleting a non-existing ARC from GitLab."""
    gitlab_api._gitlab.projects.list.return_value = []
    # Sollte einfach durchlaufen, kein Fehler
    gitlab_api.delete("arcX")
