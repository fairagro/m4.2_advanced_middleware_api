"""Implements an ArcStore using Gitlab API as backend."""

import asyncio
import base64
import concurrent.futures
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Annotated, Any, Literal

import gitlab
from arctrl import ARC  # type: ignore[import-untyped]
from gitlab.exceptions import GitlabGetError
from gitlab.v4.objects import Project, ProjectFile
from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator

from . import ArcStore

logger = logging.getLogger(__name__)


class GitlabApiConfig(BaseModel):
    """Configuration for Gitlab API ArcStore."""

    type: Annotated[Literal["gitlab"], Field(description="Type of backend")] = "gitlab"  # Discriminator
    url: Annotated[HttpUrl, Field(description="URL of the gitlab server to store ARCs in")]
    group: Annotated[
        str,
        Field(
            description="The gitlab group the ARC repos belong to",
            min_length=1,  # may not be empty
        ),
    ]
    branch: Annotated[str, Field(description="The git branch to use for ARC repos")] = "main"
    token: Annotated[
        SecretStr,
        Field(description="A gitlab token with CRUD permissions to the gitlab group"),
    ]
    max_workers: Annotated[
        int,
        Field(
            description="Maximum number of parallel threads for GitLab API calls",
            ge=1,
        ),
    ] = 5
    commit_chunk_size: Annotated[
        int,
        Field(
            description="Maximum number of file actions per commit (avoids 'Too many total parameters' error)",
            ge=1,
        ),
    ] = 100

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
        super().__init__()
        logger.info("Initializing ARCPersistenceGitlabAPI")
        self._config = config
        self._gitlab = gitlab.Gitlab(str(self._config.url), private_token=self._config.token.get_secret_value())
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=self._config.max_workers)

    def arc_id(self, identifier: str, rdi: str) -> str:
        """Generate a unique ARC ID by hashing the ideArcStorentifier and RDI.

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
        with self._tracer.start_as_current_span(
            "gitlab.get_or_create_project",
            attributes={"arc_id": arc_id},
        ):
            logger.debug("Looking up GitLab project for ARC: %s", arc_id)
            projects = self._gitlab.projects.list(search=arc_id)
            for project in projects:
                if project.path == arc_id:
                    logger.debug("Found existing project: %s (id=%s)", arc_id, project.id)
                    return project
            logger.info("Creating new GitLab project for ARC: %s", arc_id)
            group = self._gitlab.groups.get(self._config.group)
            new_project = self._gitlab.projects.create(
                {
                    "name": arc_id,
                    "path": arc_id,
                    "namespace_id": group.id,
                    "initialize_with_readme": False,
                }
            )
            logger.info("Created project: %s (id=%s)", arc_id, new_project.id)
            return new_project

    def _find_project(self, arc_id: str) -> Project | None:
        with self._tracer.start_as_current_span(
            "gitlab.find_project",
            attributes={"arc_id": arc_id},
        ):
            logger.debug("Searching for GitLab project: %s", arc_id)
            projects = self._gitlab.projects.list(search=arc_id)
            result = next((p for p in projects if p.path == arc_id), None)
            if result:
                logger.debug("Found project: %s (id=%s)", arc_id, result.id)
            else:
                logger.debug("Project not found: %s", arc_id)
            return result

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
        with self._tracer.start_as_current_span("gitlab.load_old_hash"):
            try:
                old_hash_file = project.files.get(file_path=".arc_hash", ref=self._config.branch)
                old_hash = base64.b64decode(old_hash_file.content).decode("utf-8").strip()
                logger.debug("Loaded existing ARC hash from GitLab: %s", old_hash[:16])
                return old_hash
            except GitlabGetError:
                logger.debug("No existing .arc_hash file found in project")
                return None

    # -------------------------- File Actions --------------------------
    def _get_existing_files(self, project: Project) -> set[str]:
        """Get all existing file paths in the project with a single API call."""
        with self._tracer.start_as_current_span(
            "gitlab.get_existing_files",
            attributes={"project_id": project.id},
        ):
            try:
                logger.debug("Fetching repository tree for project %s", project.id)
                tree = project.repository_tree(ref=self._config.branch, all=True, recursive=True, per_page=100)
                file_paths = {item["path"] for item in tree if item["type"] == "blob"}
                logger.debug("Found %d existing files in repository", len(file_paths))
                return file_paths
            except GitlabGetError:
                # Branch doesn't exist yet (new project)
                logger.debug("Branch %s doesn't exist yet (new project)", self._config.branch)
                return set()

    def _prepare_file_actions(
        self, project: Project, arc_path: Path, old_hash: str | None, new_hash: str
    ) -> list[dict[str, Any]]:
        """Prepare file actions with optimized batch file existence check."""
        with self._tracer.start_as_current_span(
            "gitlab.prepare_file_actions",
            attributes={"arc_path": str(arc_path)},
        ) as span:
            logger.debug("Preparing file actions for ARC at: %s", arc_path)
            # Single API call to get all existing files
            existing_files = self._get_existing_files(project)
            span.set_attribute("existing_files_count", len(existing_files))

            actions = []
            for file_path in arc_path.rglob("*"):
                if not file_path.is_file():
                    continue
                relative_path = str(file_path.relative_to(arc_path))
                action_type = "update" if relative_path in existing_files else "create"
                actions.append(self._build_file_action(file_path, relative_path, action_type))

            span.set_attribute("actions_count", len(actions))
            logger.debug("Prepared %d file actions (%d existing files)", len(actions), len(existing_files))

            # ARC hash action separat hinzufügen
            actions.append(self._build_hash_action(old_hash, new_hash))
            return actions

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

    def _build_hash_action(self, old_hash: str | None, new_hash: str) -> dict[str, Any]:
        """Erstellt die Commit-Action für die .arc_hash Datei."""
        return {
            "action": "create" if not old_hash else "update",
            "file_path": ".arc_hash",
            "content": new_hash,
        }

    # -------------------------- Commit --------------------------
    def _commit_actions(self, project: Project, actions: list[dict[str, Any]], arc_id: str) -> None:
        with self._tracer.start_as_current_span(
            "gitlab.commit_actions",
            attributes={"arc_id": arc_id, "num_actions": len(actions)},
        ):
            logger.debug("Committing %d actions to GitLab for ARC: %s", len(actions), arc_id)

            # Split actions into chunks to avoid "Too many total parameters" error
            chunk_size = self._config.commit_chunk_size
            action_chunks = [actions[i : i + chunk_size] for i in range(0, len(actions), chunk_size)]
            total_chunks = len(action_chunks)

            if total_chunks > 1:
                logger.info(
                    "Commit for ARC %s is large, splitting into %d chunks (chunk_size=%d)",
                    arc_id,
                    total_chunks,
                    chunk_size,
                )

            for i, chunk in enumerate(action_chunks):
                commit_message = (
                    f"Add/update ARC {arc_id}"
                    if total_chunks == 1
                    else f"Add/update ARC {arc_id} (part {i + 1}/{total_chunks})"
                )
                commit_data = {
                    "branch": self._config.branch,
                    "commit_message": commit_message,
                    "actions": chunk,
                }

                with self._tracer.start_as_current_span(
                    "gitlab.commit_chunk",
                    attributes={"arc_id": arc_id, "chunk_num": i + 1, "chunk_size": len(chunk)},
                ):
                    commit = project.commits.create(commit_data)
                    logger.info(
                        "Successfully committed chunk %d/%d for ARC %s to GitLab (commit: %s)",
                        i + 1,
                        total_chunks,
                        arc_id,
                        commit.id[:8],
                    )

    # -------------------------- Create/Update --------------------------
    async def _create_or_update(self, arc_id: str, arc: ARC) -> None:
        logger.debug("Creating/updating ARC %s in GitLab", arc_id)
        loop = asyncio.get_running_loop()

        project = await loop.run_in_executor(self._executor, self._get_or_create_project, arc_id)

        with tempfile.TemporaryDirectory() as tmp_root:
            arc_path = Path(tmp_root) / arc_id
            arc_path.mkdir(parents=True, exist_ok=True)

            # arc.Write is not async, run in executor
            logger.debug("Writing ARC to temporary directory: %s", arc_path)
            await loop.run_in_executor(self._executor, arc.Write, str(arc_path))

            # Compute hash once with tracing
            with self._tracer.start_as_current_span("gitlab.compute_arc_hash"):
                new_hash = await loop.run_in_executor(self._executor, self._compute_arc_hash, arc_path)
            logger.debug("Computed ARC hash: %s", new_hash[:16])

            old_hash = await loop.run_in_executor(self._executor, self._load_old_hash, project)

            if new_hash == old_hash:
                logger.info("ARC %s unchanged (hash: %s...), skipping commit", arc_id, new_hash[:16])
                return

            logger.debug("ARC %s has changed, preparing commit", arc_id)
            actions = await loop.run_in_executor(
                self._executor, self._prepare_file_actions, project, arc_path, old_hash, new_hash
            )
            await loop.run_in_executor(self._executor, self._commit_actions, project, actions, arc_id)

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
