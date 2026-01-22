"""Abstraction for managing remote git repositories on different platforms."""

import http
import logging
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import gitlab
from git import Repo
from gitlab.exceptions import GitlabError, GitlabGetError
from opentelemetry import trace

logger = logging.getLogger(__name__)


class RemoteGitProvider(ABC):
    """Base class for managing remote git repositories."""

    @abstractmethod
    def ensure_repo_exists(self, arc_id: str) -> None:
        """Ensure the remote repository exists."""
        pass

    @abstractmethod
    def get_repo_url(self, arc_id: str, authenticated: bool = True) -> str:
        """Construct the URL for the remote repository."""
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """Check if the remote storage is reachable."""
        pass

    @staticmethod
    def from_url(url: str, group: str, token: str | None = None) -> "RemoteGitProvider":
        """Create a provider based on the URL.

        Args:
            url (str): Base URL of the git server.
            group (str): Group/Namespace name.
            token (str | None): Optional auth token.

        Returns:
            RemoteGitProvider: An instance of a concrete provider.

        """
        url_lower = url.lower()
        if url_lower.startswith("file://"):
            return FileSystemGitProvider(url, group)
        if "gitlab" in url_lower:
            return GitlabGitProvider(url=url, group_name=group, token=token)

        return StaticGitProvider(url, group)


class FileSystemGitProvider(RemoteGitProvider):
    """Provider for local file-system based 'remotes' (mainly for tests)."""

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

    def get_repo_url(self, arc_id: str, authenticated: bool = True) -> str:  # noqa: ARG002
        """Return the file:// URL for the repository."""
        return f"{self.base_url}/{self.group}/{arc_id}.git"

    def check_health(self) -> bool:
        """FileSystem 'remote' is always considered healthy if base URL starts with file://."""
        return self.base_url.lower().startswith("file://")


class GitlabGitProvider(RemoteGitProvider):
    """Provider for GitLab hosted repositories."""

    def __init__(self, url: str, group_name: str, token: str | None = None) -> None:
        """Initialize with GitLab connection details."""
        self.url = url.rstrip("/")
        self.group_name = group_name.strip("/")
        self.token = token
        self._gl = None
        if token:
            self._gl = gitlab.Gitlab(url=url, private_token=token)
        self._tracer = trace.get_tracer(__name__)

    def ensure_repo_exists(self, arc_id: str) -> None:
        """Ensure the project exists in the GitLab group."""
        if not self._gl:
            logger.debug("Skipping project creation check (no GitLab token provided)")
            return

        with self._tracer.start_as_current_span(
            "remote_provider.gitlab.ensure_exists",
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

    def get_repo_url(self, arc_id: str, authenticated: bool = True) -> str:
        """Construct the GitLab repository URL, optionally with auth token."""
        repo_url = f"{self.url}/{self.group_name}/{arc_id}.git"
        if not authenticated or not self.token:
            return repo_url

        safe_token = quote(self.token)
        if repo_url.startswith("https://"):
            return f"https://oauth2:{safe_token}@{repo_url[8:]}"
        if repo_url.startswith("http://"):
            return f"http://oauth2:{safe_token}@{repo_url[7:]}"
        return repo_url

    def check_health(self) -> bool:
        """Check if the GitLab server is reachable."""
        if self._gl:
            try:
                self._gl.auth()
                return True
            except GitlabError:
                return False

        # Fallback for when no token is provided but we still want to check reachability
        try:
            with urllib.request.urlopen(self.url, timeout=5) as response:  # nosec B310
                return bool(response.status < http.HTTPStatus.BAD_REQUEST)
        except (urllib.error.URLError, TimeoutError):
            return False


class StaticGitProvider(RemoteGitProvider):
    """Provider for any other git remotes without automated project management."""

    def __init__(self, base_url: str, group: str) -> None:
        """Initialize with base URL and group."""
        self.base_url = base_url.rstrip("/")
        self.group = group.strip("/")

    def ensure_repo_exists(self, arc_id: str) -> None:
        """Do nothing for static remotes."""
        pass

    def get_repo_url(self, arc_id: str, _authenticated: bool = True) -> str:
        """Construct the repository URL."""
        return f"{self.base_url}/{self.group}/{arc_id}.git"

    def check_health(self) -> bool:
        """Check if the generic git server is reachable."""
        try:
            with urllib.request.urlopen(self.base_url, timeout=5) as response:  # nosec B310
                return bool(response.status < http.HTTPStatus.BAD_REQUEST)
        except (urllib.error.URLError, TimeoutError):
            return False
