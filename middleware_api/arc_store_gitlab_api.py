import base64
import hashlib
from pathlib import Path
import tempfile
import gitlab
from gitlab.exceptions import GitlabGetError, GitlabAuthenticationError, GitlabConnectionError
import logging
from arctrl import ARC

from .arc_store import ARCStore


logger = logging.getLogger(__name__)

class ARCStoreGitlabAPI(ARCStore):

    def __init__(self, gitlab_url: str, private_token: str, group_id: int, branch: str = "main"):
        logger.info("Initializing ARCPersistenceGitlabAPI")
        self._gitlab = gitlab.Gitlab(gitlab_url, private_token=private_token)
        self._group_id = group_id
        self._branch = branch

    # -------------------------- Project Handling --------------------------
    def _get_or_create_project(self, arc_id: str):
        projects = self._gitlab.projects.list(search=arc_id)
        for project in projects:
            if project.path == arc_id:
                return project
        group = self._gitlab.groups.get(self._group_id)
        return self._gitlab.projects.create({
            "name": arc_id,
            "path": arc_id,
            "namespace_id": group.id,
            "initialize_with_readme": False,
        })

    def _find_project(self, arc_id: str):
        projects = self._gitlab.projects.list(search=arc_id)
        return next((p for p in projects if p.path == arc_id), None)

    # -------------------------- Hashing --------------------------
    def _compute_arc_hash(self, arc_dir: Path) -> str:
        sha = hashlib.sha256()
        for file_path in sorted(arc_dir.rglob("*")):
            if file_path.is_file():
                with open(file_path, "rb") as f:
                    while chunk := f.read(8192):
                        sha.update(chunk)
        return sha.hexdigest()

    def _load_old_hash(self, project) -> str | None:
        try:
            old_hash_file = project.files.get(file_path=".arc_hash", ref=self._branch)
            return base64.b64decode(old_hash_file.content).decode("utf-8").strip()
        except GitlabGetError:
            return None

    # -------------------------- File Actions --------------------------
    def _prepare_file_actions(self, project, arc_path: Path, old_hash: str | None) -> list:
        actions = []
        for file_path in arc_path.rglob("*"):
            if not file_path.is_file():
                continue
            relative_path = str(file_path.relative_to(arc_path))
            action_type = "update" if self._file_exists(project, relative_path) else "create"
            actions.append(self._build_file_action(file_path, relative_path, action_type))
        # ARC hash action separat hinzufügen
        actions.append(self._build_hash_action(old_hash, arc_path))
        return actions

    def _file_exists(self, project, file_path: str) -> bool:
        try:
            project.files.get(file_path=file_path, ref=self._branch)
            return True
        except GitlabGetError:
            return False

    def _build_file_action(self, file_path: Path, relative_path: str, action_type: str) -> dict:
        """Erstellt ein Action-Dict für eine Datei (Text oder Binär)."""
        content_bytes = file_path.read_bytes()
        if self._is_text_file(content_bytes):
            return {
                "action": action_type,
                "file_path": relative_path,
                "content": content_bytes.decode("utf-8"),
            }
        else:
            return {
                "action": action_type,
                "file_path": relative_path,
                "content": base64.b64encode(content_bytes).decode("utf-8"),
                "encoding": "base64",
            }

    def _is_text_file(self, content_bytes: bytes) -> bool:
        """Gibt True zurück, wenn Datei UTF-8-dekodierbar ist."""
        try:
            content_bytes.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    def _build_hash_action(self, old_hash: str | None, arc_path: Path) -> dict:
        """Erstellt die Commit-Action für die .arc_hash Datei."""
        return {
            "action": "create" if not old_hash else "update",
            "file_path": ".arc_hash",
            "content": self._compute_arc_hash(arc_path)
        }

    # -------------------------- Commit --------------------------
    def _commit_actions(self, project, actions, arc_id: str):
        commit_data = {
            "branch": self._branch,
            "commit_message": f"Add/update ARC {arc_id}",
            "actions": actions,
        }
        project.commits.create(commit_data)

    # -------------------------- Create/Update --------------------------
    def create_or_update(self, arc_id: str, arc) -> None:
        try:
            project = self._get_or_create_project(arc_id)
            with tempfile.TemporaryDirectory() as tmp_root:
                arc_path = Path(tmp_root) / arc_id
                arc_path.mkdir(parents=True, exist_ok=True)
                arc.Write(str(arc_path))

                new_hash = self._compute_arc_hash(arc_path)
                old_hash = self._load_old_hash(project)

                if new_hash == old_hash:
                    return

                actions = self._prepare_file_actions(project, arc_path, old_hash)
                self._commit_actions(project, actions, arc_id)
        except (GitlabAuthenticationError, GitlabConnectionError):
            raise
        except Exception:
            logger.exception(f"Unexpected error in create_or_update({arc_id})")
            raise

    # -------------------------- Get --------------------------
    def get(self, arc_id: str):
        try:
            project = self._find_project(arc_id)
            if not project:
                return None
            with tempfile.TemporaryDirectory() as tmp_root:
                arc_path = Path(tmp_root) / arc_id
                arc_path.mkdir(parents=True, exist_ok=True)
                self._download_project_files(project, arc_path)
                return ARC.try_load_async(str(arc_path))
        except (GitlabAuthenticationError, GitlabConnectionError):
            return None
        except Exception:
            logger.exception(f"Unexpected error in get({arc_id})")
            return None

    def _download_project_files(self, project, arc_path: Path):
        tree = project.repository_tree(ref=self._branch, all=True, recursive=True)
        for entry in tree:
            if entry["type"] != "blob" or entry["path"] == ".arc_hash":
                continue
            f = project.files.get(file_path=entry["path"], ref=self._branch)
            file_path = arc_path / entry["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_project_file(f, file_path)

    def _write_project_file(self, f, file_path: Path):
        content_bytes = base64.b64decode(f.content)
        if getattr(f, "encoding", None) == "base64":
            file_path.write_bytes(content_bytes)
        else:
            try:
                text_content = content_bytes.decode("utf-8")
                file_path.write_text(text_content, encoding="utf-8")
            except UnicodeDecodeError:
                file_path.write_bytes(content_bytes)

    # -------------------------- Delete --------------------------
    def delete(self, arc_id: str) -> None:
        try:
            project = self._find_project(arc_id)
            if project:
                project.delete()
            else:
                logger.warning(f"Project '{arc_id}' not found for deletion.")
        except (GitlabAuthenticationError, GitlabConnectionError):
            raise
        except Exception:
            logger.exception(f"Unexpected error in delete({arc_id})")
            raise
