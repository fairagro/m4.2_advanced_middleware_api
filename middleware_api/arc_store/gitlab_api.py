"""Implements an ArcStore using Gitlab API as backend."""

import asyncio
import base64
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Annotated, Any

import gitlab
from arctrl import ARC  # type: ignore[import-untyped]
from gitlab.exceptions import GitlabGetError
from gitlab.v4.objects import Project, ProjectFile
from pydantic import BaseModel, Field, HttpUrl, field_validator

from . import ArcStore

logger = logging.getLogger(__name__)


class GitlabApiConfig(BaseModel):
    """Configuration for Gitlab API ArcStore."""

    url: Annotated[HttpUrl, Field(description="URL of the gitlab server to store ARCs in")]
    group: Annotated[
        str,
        Field(
            description="The gitlab group the ARC repos belong to",
            min_length=1,  # may not be empty
        ),
    ]
    branch: Annotated[str, Field(description="The git branch to use for ARC repos", default="main")]
    token: Annotated[
        str,
        Field(description="A gitlab token with CRUD permissions to the gitlab group"),
    ]

    @field_validator("group", mode="before")
    @classmethod
    def to_lowercase(cls, v: str) -> str:
        """Ensure group is lowercase and trimmed.

        Args:
            v (str): Input value.

        Returns:
            str: Normalized value.

        """
        if isinstance(v, str):
            return v.lower().strip()
        return v


class GitlabApi(ArcStore):
    """Implements an ArcStore using Gitlab API as backend."""

    def __init__(self, config: GitlabApiConfig) -> None:
        """Konstruktor.

        Args:
            config (GitlabApiConfig): Configuration for the Gitlab API ArcStore.

        """
        logger.info("Initializing ARCPersistenceGitlabAPI")
        self._config = config
        self._gitlab = gitlab.Gitlab(str(self._config.url), private_token=self._config.token)

    def arc_id(self, identifier: str, rdi: str) -> str:
        """Generate a unique ARC ID by hashing the identifier and RDI.

        Args:
            identifier (str): The ARC identifier.
            rdi (str): The RDI string.

        Returns:
            str: A SHA-256 hash representing the ARC ID.
        """
        input_str = f"{identifier}:{rdi}"
        return hashlib.sha256(input_str.encode("utf-8")).hexdigest()

    # -------------------------- Project Handling --------------------------
    def _get_or_create_project(self, arc_id: str) -> Project:
        projects = self._gitlab.projects.list(search=arc_id)
        for project in projects:
            if project.path == arc_id:
                return project
        group = self._gitlab.groups.get(self._config.group)
        return self._gitlab.projects.create(
            {
                "name": arc_id,
                "path": arc_id,
                "namespace_id": group.id,
                "initialize_with_readme": False,
            }
        )

    def _find_project(self, arc_id: str) -> Project | None:
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

    def _load_old_hash(self, project: Project) -> str | None:
        try:
            old_hash_file = project.files.get(file_path=".arc_hash", ref=self._config.branch)
            return base64.b64decode(old_hash_file.content).decode("utf-8").strip()
        except GitlabGetError:
            return None

    # -------------------------- File Actions --------------------------
    def _prepare_file_actions(self, project: Project, arc_path: Path, old_hash: str | None) -> list[dict[str, Any]]:
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

    def _file_exists(self, project: Project, file_path: str) -> bool:
        try:
            project.files.get(file_path=file_path, ref=self._config.branch)
            return True
        except GitlabGetError:
            return False

    def _build_file_action(self, file_path: Path, relative_path: str, action_type: str) -> dict[str, Any]:
        """Erstellt ein Action-Dict für eine Datei (Text oder Binär)."""
        content_bytes = file_path.read_bytes()
        if self._is_text_file(content_bytes):
            return {
                "action": action_type,
                "file_path": relative_path,
                "content": content_bytes.decode("utf-8"),
            }
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

    def _build_hash_action(self, old_hash: str | None, arc_path: Path) -> dict[str, Any]:
        """Erstellt die Commit-Action für die .arc_hash Datei."""
        return {
            "action": "create" if not old_hash else "update",
            "file_path": ".arc_hash",
            "content": self._compute_arc_hash(arc_path),
        }

    # -------------------------- Commit --------------------------
    def _commit_actions(self, project: Project, actions: list[dict[str, Any]], arc_id: str) -> None:
        commit_data = {
            "branch": self._config.branch,
            "commit_message": f"Add/update ARC {arc_id}",
            "actions": actions,
        }
        project.commits.create(commit_data)

    # -------------------------- Create/Update --------------------------
    async def _create_or_update(self, arc_id: str, arc: ARC) -> None:
        project = self._get_or_create_project(arc_id)
        with tempfile.TemporaryDirectory() as tmp_root:
            arc_path = Path(tmp_root) / arc_id
            arc_path.mkdir(parents=True, exist_ok=True)

            # arc.Write is using asyncio internally, but is not async itself.
            # We need to run it our event loop to avoid blocking.
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, arc.Write, str(arc_path))

            new_hash = self._compute_arc_hash(arc_path)
            old_hash = self._load_old_hash(project)

            if new_hash == old_hash:
                return

            actions = self._prepare_file_actions(project, arc_path, old_hash)
            self._commit_actions(project, actions, arc_id)

    # -------------------------- Get --------------------------
    def _get(self, arc_id: str) -> ARC | None:
        project = self._find_project(arc_id)
        if not project:
            return None
        with tempfile.TemporaryDirectory() as tmp_root:
            arc_path = Path(tmp_root) / arc_id
            arc_path.mkdir(parents=True, exist_ok=True)
            self._download_project_files(project, arc_path)
            try:
                return ARC.load(str(arc_path))
            except FileNotFoundError as e:
                logger.warning("ARC files for %s not found: %s", arc_id, e)
                return None
            except Exception as e:
                logger.error("Unexpected error loading ARC for %s: %s", arc_id, e, exc_info=True)
                raise

    def _download_project_files(self, project: Project, arc_path: Path) -> None:
        tree = project.repository_tree(ref=self._config.branch, all=True, recursive=True)
        for entry in tree:
            if entry["type"] != "blob" or entry["path"] == ".arc_hash":
                continue
            f = project.files.get(file_path=entry["path"], ref=self._config.branch)
            file_path = arc_path / entry["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_project_file(f, file_path)

    def _write_project_file(self, f: ProjectFile, file_path: Path) -> None:
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
    def _delete(self, arc_id: str) -> None:
        project = self._find_project(arc_id)
        if project:
            project.delete()
        else:
            logger.warning("Project %s not found for deletion.", arc_id)

    # -------------------------- Exists --------------------------
    def _exists(self, arc_id: str) -> bool:
        project = self._find_project(arc_id)
        return bool(project)
