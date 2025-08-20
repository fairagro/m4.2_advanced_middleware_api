import base64
import hashlib
from pathlib import Path
import tempfile
import gitlab
from gitlab.exceptions import GitlabGetError
from arctrl.arc import ARC

from .arc_persistence import ARCPersistence


class ARCPersistenceGitlabAPI(ARCPersistence):

    def __init__(self, gitlab_url: str, private_token: str, group_id: int, branch: str = "main"):
        self.gl = gitlab.Gitlab(gitlab_url, private_token=private_token)
        self.group_id = group_id
        self.branch = branch

    def _get_or_create_project(self, arc_id: str):
        # Projekt suchen
        projects = self.gl.projects.list(search=arc_id)
        for project in projects:
            if project.path == arc_id:
                return project

        # Projekt anlegen
        group = self.gl.groups.get(self.group_id)
        project = self.gl.projects.create({
            "name": arc_id, # Kann auch ein lesbarer Name sein
            "path": arc_id,
            "namespace_id": group.id,
            "initialize_with_readme": False,
        })
        return project
    
    def _compute_arc_hash(self, arc_dir: Path) -> str:
        sha = hashlib.sha256()
        for file_path in sorted(arc_dir.rglob("*")):
            if file_path.is_file():
                with open(file_path, "rb") as f:
                    while chunk := f.read(8192):
                        sha.update(chunk)
        return sha.hexdigest()

    def create_or_update(self, arc_id: str, arc) -> None:
        project = self._get_or_create_project(arc_id)

        with tempfile.TemporaryDirectory() as tmp_root:
            arc_path = Path(tmp_root) / arc_id
            arc_path.mkdir(parents=True, exist_ok=True)
            arc.Write(str(arc_path))
            new_hash = self._compute_arc_hash(arc_path)

            # Prüfen ob .arc_hash im Repo existiert
            try:
                old_hash_file = project.files.get(file_path=".arc_hash", ref=self.branch)
                old_hash = base64.b64decode(old_hash_file.content).decode("utf-8").strip()
            except GitlabGetError:
                old_hash = None

            if new_hash == old_hash:
                return

            actions = []
            for file_path in arc_path.rglob("*"):
                if file_path.is_file():
                    relative_path = str(file_path.relative_to(arc_path))

                    try:
                        # Prüfen, ob die Datei im Repo schon existiert
                        project.files.get(file_path=relative_path, ref=self.branch)
                        action = "update"
                    except GitlabGetError:
                        # Datei gibt es noch nicht
                        action = "create"

                    try:
                        # Try to read as text
                        content = file_path.read_text(encoding="utf-8")
                        actions.append({
                            "action": action,
                            "file_path": relative_path,
                            "content": content,
                        })
                    except UnicodeDecodeError:
                        # Fallback to base64 encoding for binary files
                        content = file_path.read_bytes()
                        actions.append({
                            "action": action,
                            "file_path": relative_path,
                            "content": base64.b64encode(content).decode("utf-8"),
                            "encoding": "base64",
                        })

            # arc_hash aktualisieren
            actions.append({
                "action": "create" if not old_hash else "update",
                "file_path": ".arc_hash",
                "content": new_hash
            })

            commit_data = {
                "branch": self.branch,
                "commit_message": f"Add/update ARC {arc_id}",
                "actions": actions,
            }
            project.commits.create(commit_data)

    def get(self, arc_id: str):
        projects = self.gl.projects.list(search=arc_id)
        project = next((p for p in projects if p.path == arc_id), None)
        if not project:
            return None

        # Files in GitLab holen
        with tempfile.TemporaryDirectory() as tmp_root:
            arc_path = Path(tmp_root) / arc_id
            arc_path.mkdir(parents=True, exist_ok=True)

            tree = project.repository_tree(ref=self.branch, all=True, recursive=True)
            for entry in tree:
                if entry["type"] == "blob":
                    f = project.files.get(file_path=entry["path"], ref=self.branch)
                    file_path = arc_path / entry["path"]
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_content = base64.b64decode(f.content)
                    if getattr(f, "encoding", None) == "base64":
                        # Datei war als Base64 gespeichert (Binary)
                        file_path.write_bytes(file_content)
                    else:
                        # Normaler Text (GitLab liefert das schon als Base64, aber UTF-8 decodierbar)
                        file_path.write_text(file_content.decode("utf-8"), encoding="utf-8")


            # ARC wieder laden
            arc = ARC.try_load_async(str(arc_path))
            return arc

    def delete(self, arc_id: str) -> None:
        projects = self.gl.projects.list(search=arc_id)
        project = next((p for p in projects if p.path == arc_id), None)
        if project:
            project.delete()
