import base64
from pathlib import Path
from unittest.mock import MagicMock

from gitlab.exceptions import GitlabGetError


# -------------------- Hilfsfunktionen --------------------

def test_compute_arc_hash(tmp_path, api):
    file = tmp_path / "f.txt"
    file.write_text("hello")
    h1 = api._compute_arc_hash(tmp_path)
    file.write_text("world")
    h2 = api._compute_arc_hash(tmp_path)
    assert h1 != h2 # nosec


def test_get_or_create_project_found(api):
    project = MagicMock()
    project.path = "arc1"
    api._gitlab.projects.list.return_value = [project]
    result = api._get_or_create_project("arc1")
    assert result == project # nosec


def test_get_or_create_project_create(api):
    api._gitlab.projects.list.return_value = []
    group = MagicMock()
    group.id = 1
    api._gitlab.groups.get.return_value = group
    project = MagicMock()
    api._gitlab.projects.create.return_value = project
    result = api._get_or_create_project("arc1")
    assert result == project # nosec


# -------------------- Create/Update --------------------

def test_create_or_update_no_changes(api):
    """Wenn Hash gleich ist, darf kein Commit passieren."""
    arc = MagicMock()
    arc.Write = lambda path: (Path(path) / "f.txt").write_text("abc")

    project = MagicMock()
    # .arc_hash mit "dummyhash" vorhanden
    project.files.get.return_value.content = base64.b64encode(b"dummyhash").decode()
    api._get_or_create_project = lambda arc_id: project
    api._compute_arc_hash = lambda path: "dummyhash"

    api.create_or_update("arc1", arc)
    project.commits.create.assert_not_called()


def test_create_or_update_with_changes(api):
    """Wenn Hash unterschiedlich ist, muss ein Commit erstellt werden."""
    arc = MagicMock()
    arc.Write = lambda path: (Path(path) / "f.txt").write_text("abc")

    project = MagicMock()
    # kein .arc_hash vorhanden
    def raise_get(*args, **kwargs):
        raise GitlabGetError("not found", response_code=404)

    project.files.get.side_effect = raise_get
    api._get_or_create_project = lambda arc_id: project
    api._compute_arc_hash = lambda path: "newhash"

    api.create_or_update("arc1", arc)
    project.commits.create.assert_called_once()
    args, kwargs = project.commits.create.call_args
    actions = args[0]["actions"]
    assert any(a["file_path"] == ".arc_hash" for a in actions) # nosec


# -------------------- Get --------------------

def test_get_success(api, monkeypatch):
    project = MagicMock()
    project.path = "arc1"
    project.repository_tree.return_value = [
        {"type": "blob", "path": "f.txt"},
        {"type": "blob", "path": ".arc_hash"},
    ]

    fobj = MagicMock()
    fobj.content = base64.b64encode("hello".encode()).decode()
    fobj.encoding = None
    project.files.get.return_value = fobj

    api._gitlab.projects.list.return_value = [project]

    dummy_arc = MagicMock()
    monkeypatch.setattr("app.arc_store_gitlab_api.ARC.try_load_async", lambda path: dummy_arc)

    arc = api.get("arc1")
    assert arc == dummy_arc # nosec
    project.files.get.assert_any_call(file_path="f.txt", ref=api._branch)


def test_get_not_found(api):
    api._gitlab.projects.list.return_value = []
    arc = api.get("arcX")
    assert arc is None # nosec


# -------------------- Delete --------------------

def test_delete_found(api):
    project = MagicMock()
    project.path = "arc1"
    api._gitlab.projects.list.return_value = [project]
    api.delete("arc1")
    project.delete.assert_called_once()


def test_delete_not_found(api):
    api._gitlab.projects.list.return_value = []
    # Sollte einfach durchlaufen, kein Fehler
    api.delete("arcX")
