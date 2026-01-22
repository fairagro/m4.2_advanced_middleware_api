"""Abstraction for managing remote git repositories on different platforms."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import unquote, urlparse

import gitlab
from git import Repo
from gitlab.exceptions import GitlabError, GitlabGetError
from opentelemetry import trace

logger = logging.getLogger(__name__)


class RemoteRepoManager(ABC):
    """Base class for managing remote git repositories."""

    @abstractmethod
    def ensure_repo_exists(self, arc_id: str) -> None:
        """Ensure the remote repository exists."""
        pass


class FileSystemRemoteManager(RemoteRepoManager):
    """Manager for local file-system based 'remotes' (mainly for tests)."""

    def __init__(self, base_url: str, group: str) -> None:
        """Initialize with base URL and group."""
        self.base_url = base_url.rstrip("/")
        self.group = group.strip("/")

    def ensure_repo_exists(self, arc_id: str) -> None:
        """Create a bare repository on the local filesystem if it doesn't exist."""
        parsed_url = urlparse(self.base_url)
        if parsed_url.scheme.lower() != "file":
            return

        # The path from a file URL might be URL-encoded (e.g. spaces as %20).
        # We assume the path is local and can ignore the netloc part.
        base_path = Path(unquote(parsed_url.path))
        remote_path = base_path / self.group / f"{arc_id}.git"

        if not remote_path.exists():
            logger.info("Creating local 'remote' bare repository at %s", remote_path)
            remote_path.parent.mkdir(parents=True, exist_ok=True)
            Repo.init(remote_path, bare=True)


class GitlabRemoteManager(RemoteRepoManager):
    """Manager for GitLab hosted repositories."""

    def __init__(self, url: str, group_name: str, token: str) -> None:
        """Initialize with GitLab connection details."""
        self.url = url
        self.group_name = group_name
        self._gl = gitlab.Gitlab(url=url, private_token=token)
        self._tracer = trace.get_tracer(__name__)

    def ensure_repo_exists(self, arc_id: str) -> None:
        """Ensure the project exists in the GitLab group."""
        with self._tracer.start_as_current_span(
            "remote_manager.gitlab.ensure_exists",
            attributes={"arc_id": arc_id, "group": self.group_name},
        ):
            try:
                # 1. Get the group
                group = self._gl.groups.get(self.group_name)

                # 2. Check if project exists
                project_path = f"{group.full_path}/{arc_id}"
                try:
                    self._gl.projects.get(project_path)
                    logger.debug("GitLab project %s already exists", project_path)
                except GitlabGetError:
                    # 3. Create project if it doesn't exist
                    logger.info("Creating new GitLab project: %s in group %s", arc_id, self.group_name)
                    self._gl.projects.create(
                        {
                            "name": arc_id,
                            "path": arc_id,
                            "namespace_id": group.id,
                            "visibility": "private",
                        }
                    )
            except GitlabError as e:
                logger.error("Failed to ensure GitLab project exists: %s", e)
                raise
