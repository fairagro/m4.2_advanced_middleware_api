from pathlib import Path
import tempfile
import gitlab
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

    def create_or_update(self, arc_id: str, arc) -> None:
        project = self._get_or_create_project(arc_id)

        with tempfile.TemporaryDirectory() as tmp_root:
            tmp_path = Path(tmp_root) / arc_id
            tmp_path.mkdir(parents=True, exist_ok=True)
            arc.Write(str(tmp_path))

            actions = []
            for file_path in tmp_path.rglob("*"):
                if file_path.is_file():
                    relative_path = str(file_path.relative_to(tmp_path))
                    content = file_path.read_text(encoding="utf-8")

                    actions.append({
                        "action": "create",  # könnte auch "update" sein, wenn file existiert
                        "file_path": relative_path,
                        "content": content,
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
            tmp_path = Path(tmp_root) / arc_id
            tmp_path.mkdir(parents=True, exist_ok=True)

            tree = project.repository_tree(ref=self.branch, all=True, recursive=True)
            for entry in tree:
                if entry["type"] == "blob":
                    f = project.files.get(file_path=entry["path"], ref=self.branch)
                    file_path = tmp_path / entry["path"]
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(f.decode(), encoding="utf-8")

            # ARC wieder laden
            arc = ARC.try_load_async(str(tmp_path))
            return arc

    def delete(self, arc_id: str) -> None:
        projects = self.gl.projects.list(search=arc_id)
        project = next((p for p in projects if p.path == arc_id), None)
        if project:
            project.delete()
