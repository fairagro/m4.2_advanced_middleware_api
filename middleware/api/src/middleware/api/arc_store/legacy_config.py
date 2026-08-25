"""Message constants and helpers for obsolete top-level ArcStore configuration keys."""

from __future__ import annotations

from pydantic import BaseModel

OBSOLETE_TOP_LEVEL_GIT_REPO = "Top-level git_repo is obsolete; use arc_store.type with nested settings instead."
OBSOLETE_TOP_LEVEL_GITLAB_API = "Top-level gitlab_api is obsolete; use arc_store.type with nested settings instead."
OBSOLETE_TOP_LEVEL_CONSOLIDATED_GIT = (
    "Top-level consolidated_git is obsolete; use arc_store.type with nested settings instead."
)

OBSOLETE_TOP_LEVEL_FIELDS: tuple[str, ...] = (
    "git_repo",
    "gitlab_api",
    "consolidated_git",
)


def count_obsolete_top_level_arc_store_fields(config: BaseModel) -> int:
    """Count obsolete top-level ArcStore backends that are actually configured.

    Explicit ``null`` values are ignored: only non-``None`` backends count toward
    mutual exclusivity. Accessing the fields may emit Pydantic ``Field(deprecated=...)``
    warnings; that is intentional for production use of obsolete keys.
    """
    return sum(1 for name in OBSOLETE_TOP_LEVEL_FIELDS if getattr(config, name, None) is not None)
