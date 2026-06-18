"""Abstraction for managing remote git repositories on different platforms."""

import http
import logging
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import gitlab
from arctrl import ARC  # type: ignore[import-untyped]
from git import Repo
from gitlab.exceptions import GitlabError, GitlabGetError
from gitlab.v4.objects import Project
from opentelemetry import trace

from . import ArcStoreError

logger = logging.getLogger(__name__)

_GITLAB_TOPIC_RE = re.compile(r"[^a-z0-9-]+")
_GITLAB_NAME_MAX_LEN = 255
_GITLAB_NAME_UNSAFE_RE = re.compile(r"[\r\n\t]+")


@dataclass(frozen=True)
class GitProjectMetadata:
    """Human-readable GitLab project fields alongside the hashed repository path."""

    rdi: str
    arc_id: str
    identifier: str
    display_name: str
    description: str | None = None


def sanitize_gitlab_project_name(name: str) -> str:
    """Normalize a RO-Crate identifier for GitLab project titles."""
    collapsed = _GITLAB_NAME_UNSAFE_RE.sub(" ", name.strip())
    collapsed = " ".join(collapsed.split())
    collapsed = collapsed.replace("/", "-").replace("\\", "-")
    if not collapsed:
        msg = "GitLab project name cannot be empty after sanitization"
        raise ValueError(msg)
    if len(collapsed) > _GITLAB_NAME_MAX_LEN:
        return collapsed[:_GITLAB_NAME_MAX_LEN].rstrip()
    return collapsed


def git_project_metadata_from_arc(
    arc: ARC,
    rdi: str,
    *,
    arc_id: str,
) -> GitProjectMetadata:
    """Build GitLab project metadata from an arctrl ARC and the originating RDI."""
    canonical = (arc.Identifier or "").strip()
    if not canonical:
        msg = "ARC identifier is required for GitLab project metadata"
        raise ValueError(msg)
    return GitProjectMetadata(
        rdi=rdi,
        arc_id=arc_id,
        identifier=sanitize_gitlab_project_name(canonical),
        display_name=arc.Title or "",
        description=arc.Description,
    )


def normalize_gitlab_topic(rdi: str) -> str | None:
    """Normalize an RDI name for GitLab project topics (lowercase alphanumeric + hyphens)."""
    normalized = _GITLAB_TOPIC_RE.sub("-", rdi.strip().lower()).strip("-")
    if normalized:
        return normalized
    alnum = re.sub(r"[^a-z0-9]", "", rdi.lower())
    return alnum or None


def merge_rdi_gitlab_topic(existing_topics: list[str] | None, rdi: str) -> list[str] | None:
    """Return updated topics with the RDI tag present, or None when unchanged."""
    rdi_topic = normalize_gitlab_topic(rdi)
    if rdi_topic is None:
        return None
    topics = list(existing_topics or [])
    if rdi_topic in topics:
        return None
    return [*topics, rdi_topic]


def build_gitlab_project_description(metadata: GitProjectMetadata) -> str:
    """Build the GitLab project description shown in list preview and on the project home page."""
    lines: list[str] = []
    if metadata.display_name:
        lines.append(metadata.display_name)
    if metadata.description:
        lines.append(metadata.description)
    return "\n".join(lines)


def apply_gitlab_project_metadata(
    project: Project,
    arc_id: str,
    metadata: GitProjectMetadata,
) -> None:
    """Update GitLab project title, description, and RDI topic."""
    changed = False
    if project.name != metadata.identifier:
        project.name = metadata.identifier
        changed = True

    description = build_gitlab_project_description(metadata)
    if project.description != description:
        project.description = description
        changed = True

    topics = merge_rdi_gitlab_topic(project.topics, metadata.rdi)
    if topics is not None:
        project.topics = topics
        changed = True

    if changed:
        logger.info("Updating GitLab project metadata for %s", arc_id)
        project.save()


class RemoteGitProvider(ABC):
    """Base class for managing remote git repositories."""

    @abstractmethod
    def ensure_repo_exists(self, arc_id: str, metadata: GitProjectMetadata) -> None:
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
    def from_url(
        url: str,
        group: str,
        token: str | None = None,
    ) -> "RemoteGitProvider":
        """Create a provider based on the URL protocol.

        Args:
            url (str): Base URL of the git server.
            group (str): Group/Namespace name.
            token (str | None): Optional auth token.

        Returns:
            RemoteGitProvider: An instance of a concrete provider.

        Raises:
            ValueError: If no suitable provider can be determined.

        """
        url_lower = url.lower()

        if url_lower.startswith("file://"):
            return FileSystemGitProvider(url, group)

        # TODO: any URL that is not file:// is assumed to be GitLab for now,
        # but of course, this is a bold assumption. We should improve this later.
        # Maybe there is a way to detect GitLab and bailout if not?
        if url_lower.startswith(("http://", "https://")):
            return GitlabGitProvider(url=url, group_name=group, token=token)

        msg = f"Could not determine git provider for URL '{url}'. Supported protocols: file://, http://, https://"
        raise ValueError(msg)


class FileSystemGitProvider(RemoteGitProvider):
    """Provider for local file-system based 'remotes' (mainly for tests)."""

    def __init__(self, base_url: str, group: str) -> None:
        """Initialize with base URL and group."""
        self.base_url = base_url.rstrip("/")
        self.group = group.strip("/")

    def ensure_repo_exists(self, arc_id: str, _metadata: GitProjectMetadata) -> None:
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

    def get_repo_url(self, arc_id: str, _authenticated: bool = True) -> str:
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

    def ensure_repo_exists(self, arc_id: str, metadata: GitProjectMetadata) -> None:
        """Ensure the project exists in the GitLab group and apply human-readable metadata."""
        if not self._gl:
            logger.debug("Skipping project creation check (no GitLab token provided)")
            return

        with self._tracer.start_as_current_span(
            "api.GitlabGitProvider.ensure_repo_exists",
            attributes={"arc_id": arc_id, "group": self.group_name},
        ):
            try:
                group = self._gl.groups.get(self.group_name)
                project_path = f"{group.full_path}/{arc_id}"
                try:
                    project = self._gl.projects.get(project_path)
                    logger.debug("GitLab project %s already exists", project_path)
                    apply_gitlab_project_metadata(project, arc_id, metadata)
                except GitlabGetError:
                    logger.info("Creating new GitLab project: %s in group %s", arc_id, self.group_name)
                    create_attrs: dict[str, object] = {
                        "name": metadata.identifier,
                        "path": arc_id,
                        "namespace_id": group.id,
                        "visibility": "private",
                    }
                    project_description = build_gitlab_project_description(metadata)
                    if project_description:
                        create_attrs["description"] = project_description
                    rdi_topic = normalize_gitlab_topic(metadata.rdi)
                    if rdi_topic is not None:
                        create_attrs["topics"] = [rdi_topic]
                    self._gl.projects.create(create_attrs)
            except GitlabError as e:
                msg = f"GitLab API error: {e}"
                if hasattr(e, "response_code") and e.response_code == http.HTTPStatus.UNAUTHORIZED:
                    msg = (
                        "GitLab API 401 Unauthorized: Please check your token and its permissions (API scope required)."
                    )

                logger.error("Failed to ensure GitLab project exists: %s", msg)
                raise ArcStoreError(msg) from e

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

        # Fallback for when no token is provided but we still want to check reachability.
        # URL is admin-configured; reject non-http(s) schemes before opening.
        if not self.url.lower().startswith(("http://", "https://")):
            return False

        try:
            with urllib.request.urlopen(self.url, timeout=5) as response:  # nosec B310
                return bool(response.status < http.HTTPStatus.BAD_REQUEST)
        except (urllib.error.URLError, TimeoutError):
            return False
        except Exception as e:  # noqa: BLE001
            logger.warning("Unexpected error during health check for %s: %s", self.url, e)
            return False
