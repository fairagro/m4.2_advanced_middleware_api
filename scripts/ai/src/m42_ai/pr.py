"""PR body hygiene helpers."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from m42_ai.gh import run_gh

# Tool marketing footers commonly injected into PR bodies.
_FOOTER_BLOCK_RE = re.compile(
    r"(?:\r?\n)+"
    r"(?:---+[ \t]*(?:\r?\n)+)?"
    r"(?:Made with[ \t]+(?:\[Cursor\]\([^)]*\)|Cursor)[^\r\n]*)"
    r"(?:[ \t]*(?:\r?\n)+)?$",
    re.IGNORECASE,
)
_FOOTER_HTML_RE = re.compile(
    r"(?:\r?\n)*<!--\s*Made with Cursor.*?-->\s*$",
    re.IGNORECASE | re.DOTALL,
)


def strip_marketing_footers(body: str) -> tuple[str, bool]:
    """Remove trailing Cursor/tool marketing footers. Returns (new_body, changed)."""
    cleaned = body
    changed = False
    for pattern in (_FOOTER_HTML_RE, _FOOTER_BLOCK_RE):
        new = pattern.sub("", cleaned)
        if new != cleaned:
            changed = True
            cleaned = new
    cleaned = cleaned.rstrip() + ("\n" if cleaned.strip() else "")
    if cleaned != body:
        changed = True
    return cleaned, changed


def pr_strip_footer(
    pr: int,
    *,
    owner: str | None = None,
    repo: str | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Fetch PR body, strip marketing footers, edit when changed."""
    view_args = ["pr", "view", str(pr), "--json", "number,url,body,title"]
    if owner and repo:
        view_args.extend(["--repo", f"{owner}/{repo}"])
    proc = run_gh(view_args, cwd=cwd)
    meta = json.loads(proc.stdout)
    body = str(meta.get("body") or "")
    cleaned, changed = strip_marketing_footers(body)
    result: dict[str, Any] = {
        "pr": int(meta["number"]),
        "url": meta["url"],
        "title": meta.get("title"),
        "changed": changed,
        "body": cleaned,
    }
    if not changed:
        return result

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(cleaned)
        body_path = tmp.name
    try:
        edit_args = ["pr", "edit", str(pr), "--body-file", body_path]
        if owner and repo:
            edit_args.extend(["--repo", f"{owner}/{repo}"])
        run_gh(edit_args, cwd=cwd)
    finally:
        Path(body_path).unlink(missing_ok=True)
    return result
