"""Warnings for obsolete top-level ArcStore configuration keys."""

from __future__ import annotations

import warnings

from pydantic import BaseModel

OBSOLETE_TOP_LEVEL_GIT_REPO = "Top-level git_repo is obsolete; use arc_store.type with nested settings instead."
OBSOLETE_TOP_LEVEL_GITLAB_API = "Top-level gitlab_api is obsolete; use arc_store.type with nested settings instead."
OBSOLETE_TOP_LEVEL_CONSOLIDATED_GIT = (
    "Top-level consolidated_git is obsolete; use arc_store.type with nested settings instead."
)

OBSOLETE_TOP_LEVEL_FIELD_MESSAGES: dict[str, str] = {
    "git_repo": OBSOLETE_TOP_LEVEL_GIT_REPO,
    "gitlab_api": OBSOLETE_TOP_LEVEL_GITLAB_API,
    "consolidated_git": OBSOLETE_TOP_LEVEL_CONSOLIDATED_GIT,
}


def warn_obsolete_top_level_arc_store_fields(model: BaseModel) -> None:
    """Emit ``DeprecationWarning`` for each obsolete top-level key present in parsed config."""
    fields_set = model.model_fields_set
    for field_name, message in OBSOLETE_TOP_LEVEL_FIELD_MESSAGES.items():
        if field_name in fields_set:
            warnings.warn(message, DeprecationWarning, stacklevel=3)


def count_obsolete_top_level_arc_store_fields(config: BaseModel) -> int:
    """Count obsolete top-level ArcStore backends that are actually configured.

    Explicit ``null`` values are ignored: only non-``None`` backends count toward
    mutual exclusivity. Accessing the fields may emit Pydantic ``Field(deprecated=...)``
    warnings; that is intentional for production use of obsolete keys.
    """
    return sum(1 for name in OBSOLETE_TOP_LEVEL_FIELD_MESSAGES if getattr(config, name, None) is not None)
