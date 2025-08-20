import base64
import hashlib
from pathlib import Path
import tempfile
import gitlab
from gitlab.exceptions import GitlabGetError, GitlabAuthenticationError, GitlabConnectionError, GitlabCreateError
import logging
from arctrl.arc import ARC

from .arc_persistence import ARCPersistence

logger = logging.getLogger(__name__)

class ARCPersistenceGitlabAPI(ARCPersistence):

    def __init__(self, gitlab_url: str, private_token: str, group_id: int, branch: str = "main"):
        logger.info("Initializing ARCPersistenceGitlabAPI")
        self.gl = gitlab.Gitlab(gitlab_url, private_token=private_token)
        self.group_id = group_id
        self.branch = branch

    def _get_or_create_project(self, arc_id: str):
        logger.info(f"Searching for GitLab project with path '{arc_id}'")
        projects = self.gl.projects.list(search=arc_id)
        for project in projects:
            logger.debug(f"Found project candidate: {project.path}")
            if project.path == arc_id:
                logger.info(f"Project '{arc_id}' found.")
                return project

        logger.info(f"Project '{arc_id}' not found. Creating new project.")
        group = self.gl.groups.get(self.group_id)
        project = self.gl.projects.create({
            "name": arc_id,
            "path": arc_id,
            "namespace_id": group.id,
            "initialize_with_readme": False,
        })
        logger.info(f"Project '{arc_id}' created with id {project.id}.")
        return project
    
    def _compute_arc_hash(self, arc_dir: Path) -> str:
        logger.info(f"Computing hash for ARC directory: {arc_dir}")
        sha = hashlib.sha256()
        for file_path in sorted(arc_dir.rglob("*")):
            if file_path.is_file():
                logger.debug(f"Hashing file: {file_path}")
                with open(file_path, "rb") as f:
                    while chunk := f.read(8192):
                        sha.update(chunk)
        hash_value = sha.hexdigest()
        logger.info(f"Computed ARC hash: {hash_value}")
        return hash_value

    def create_or_update(self, arc_id: str, arc) -> None:
        logger.info(f"Starting create_or_update for ARC '{arc_id}'")
        try:
            project = self._get_or_create_project(arc_id)
            with tempfile.TemporaryDirectory() as tmp_root:
                arc_path = Path(tmp_root) / arc_id
                arc_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Writing ARC to temp path: {arc_path}")
                arc.Write(str(arc_path))
                new_hash = self._compute_arc_hash(arc_path)

                try:
                    old_hash_file = project.files.get(file_path=".arc_hash", ref=self.branch)
                    old_hash = base64.b64decode(old_hash_file.content).decode("utf-8").strip()
                    logger.info(f"Loaded old ARC hash: {old_hash}")
                except GitlabGetError:
                    old_hash = None
                    logger.info("No previous ARC hash found.")

                if new_hash == old_hash:
                    logger.info(f"No changes detected for ARC '{arc_id}'. Skipping update.")
                    return

                actions = []
                for file_path in arc_path.rglob("*"):
                    if file_path.is_file():
                        relative_path = str(file_path.relative_to(arc_path))
                        logger.debug(f"Preparing file for commit: {relative_path}")
                        try:
                            project.files.get(file_path=relative_path, ref=self.branch)
                            action = "update"
                            logger.debug(f"File '{relative_path}' exists. Action: update")
                        except GitlabGetError:
                            action = "create"
                            logger.debug(f"File '{relative_path}' does not exist. Action: create")

                        try:
                            content = file_path.read_text(encoding="utf-8")
                            actions.append({
                                "action": action,
                                "file_path": relative_path,
                                "content": content,
                            })
                            logger.debug(f"Added text file '{relative_path}' to actions.")
                        except UnicodeDecodeError:
                            content = file_path.read_bytes()
                            actions.append({
                                "action": action,
                                "file_path": relative_path,
                                "content": base64.b64encode(content).decode("utf-8"),
                                "encoding": "base64",
                            })
                            logger.debug(f"Added binary file '{relative_path}' to actions.")

                actions.append({
                    "action": "create" if not old_hash else "update",
                    "file_path": ".arc_hash",
                    "content": new_hash
                })
                logger.info(f"Prepared {len(actions)} actions for commit.")

                commit_data = {
                    "branch": self.branch,
                    "commit_message": f"Add/update ARC {arc_id}",
                    "actions": actions,
                }
                logger.info(f"Committing changes to project '{arc_id}'")
                try:
                    project.commits.create(commit_data)
                    logger.info(f"Commit successful for ARC '{arc_id}'")
                except GitlabCreateError as e:
                    logger.error(f"Failed to commit changes to ARC '{arc_id}': {e}")
                    raise
        except (GitlabAuthenticationError, GitlabConnectionError) as e:
            logger.error(f"GitLab connection/authentication error: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in create_or_update({arc_id}): {e}")
            raise

    def get(self, arc_id: str):
        logger.info(f"Starting get for ARC '{arc_id}'")
        try:
            projects = self.gl.projects.list(search=arc_id)
            project = next((p for p in projects if p.path == arc_id), None)
            if not project:
                logger.warning(f"ARC project '{arc_id}' not found in GitLab.")
                return None

            with tempfile.TemporaryDirectory() as tmp_root:
                arc_path = Path(tmp_root) / arc_id
                arc_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Downloading files from project '{arc_id}' to '{arc_path}'")

                tree = project.repository_tree(ref=self.branch, all=True, recursive=True)
                for entry in tree:
                    if entry["type"] == "blob":
                        try:
                            f = project.files.get(file_path=entry["path"], ref=self.branch)
                        except GitlabGetError as e:
                            logger.error(f"File '{entry['path']}' not found in project '{arc_id}': {e}")
                            continue
                        file_path = arc_path / entry["path"]
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_content = base64.b64decode(f.content)
                        if getattr(f, "encoding", None) == "base64":
                            file_path.write_bytes(file_content)
                            logger.debug(f"Wrote binary file '{entry['path']}'")
                        else:
                            try:
                                file_path.write_text(file_content.decode("utf-8"), encoding="utf-8")
                                logger.debug(f"Wrote text file '{entry['path']}'")
                            except Exception as e:
                                logger.error(f"Error decoding file '{entry['path']}' as UTF-8: {e}")
                                continue

                try:
                    logger.info(f"Loading ARC from '{arc_path}'")
                    arc = ARC.try_load_async(str(arc_path))
                except Exception as e:
                    logger.error(f"Failed to load ARC from '{arc_path}': {e}")
                    return None
                logger.info(f"Successfully loaded ARC '{arc_id}'")
                return arc
        except (GitlabAuthenticationError, GitlabConnectionError) as e:
            logger.error(f"GitLab connection/authentication error: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error in get({arc_id}): {e}")
            return None

    def delete(self, arc_id: str) -> None:
        logger.info(f"Starting delete for ARC '{arc_id}'")
        try:
            projects = self.gl.projects.list(search=arc_id)
            project = next((p for p in projects if p.path == arc_id), None)
            if project:
                try:
                    logger.info(f"Deleting project '{arc_id}'")
                    project.delete()
                    logger.info(f"Project '{arc_id}' deleted successfully.")
                except Exception as e:
                    logger.error(f"Failed to delete project '{arc_id}': {e}")
                    raise
            else:
                logger.warning(f"Project '{arc_id}' not found for deletion.")
        except (GitlabAuthenticationError, GitlabConnectionError) as e:
            logger.error(f"GitLab connection/authentication error: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in delete({arc_id}): {e}")
            raise
