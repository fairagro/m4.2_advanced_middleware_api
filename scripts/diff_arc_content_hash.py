#!/usr/bin/env python3
r"""Compare two RO-Crate payloads the same way middleware change detection does.

Use this when GitLab shows daily ``Update ARC …`` commits and you need to see
*why* ``has_changes`` became true: which JSON paths still differ after volatile
timestamp stripping and ``@graph`` canonicalization.

Examples:
    # Two harvest payloads / exports
    uv run python scripts/diff_arc_content_hash.py --a old.json --b new.json

    # Stored CouchDB document vs a new harvest file
    uv run python scripts/diff_arc_content_hash.py \
        --arc-id 83e3f3a60b3defb46413f9fe873ac0c323581f95654389b6ecd711607d6070bf \
        --b harvest.json \
        --couchdb-url http://localhost:5984 \
        --couchdb-user admin \
        --couchdb-password secret

Environment (optional CouchDB defaults):
    COUCHDB_URL, COUCHDB_USER, COUCHDB_PASSWORD, COUCHDB_DB_NAME
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from middleware.api.document_store.config import CouchDBConfig
from middleware.api.document_store.content_hash import (
    RoCrateContent,
    calculate_arc_content_hash,
    canonicalize_rocrate_for_hash,
    strip_volatile_rocrate_fields,
)
from middleware.api.document_store.couchdb_client import CouchDBClient


def _iter_json_diffs(left: Any, right: Any, path: str = "$") -> Iterator[tuple[str, Any, Any]]:
    """Yield ``(json_path, left_value, right_value)`` for leaves that differ."""
    if type(left) is not type(right):
        yield path, left, right
        return

    if isinstance(left, dict) and isinstance(right, dict):
        keys = set(left) | set(right)
        for key in sorted(keys):
            child = f"{path}.{key}"
            if key not in left:
                yield child, None, right[key]
            elif key not in right:
                yield child, left[key], None
            else:
                yield from _iter_json_diffs(left[key], right[key], child)
        return

    if isinstance(left, list) and isinstance(right, list):
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=False)):
            yield from _iter_json_diffs(left_item, right_item, f"{path}[{index}]")
        if len(left) != len(right):
            yield f"{path}.length", len(left), len(right)
        return

    if left != right:
        yield path, left, right


def _load_json(path: Path) -> RoCrateContent:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"{path} must contain a JSON object"
        raise TypeError(msg)
    return data


async def _load_couchdb_arc(
    arc_id: str,
    *,
    url: str,
    user: str | None,
    password: str | None,
    db_name: str,
) -> RoCrateContent:

    client = CouchDBClient(
        CouchDBConfig(
            url=url,
            db_name=db_name,
            user=user,
            password=SecretStr(password) if password else None,
        )
    )
    await client.connect()
    try:
        doc = await client.get_document(f"arc_{arc_id}")
    finally:
        await client.close()

    if doc is None:
        msg = f"CouchDB document 'arc_{arc_id}' not found in database '{db_name}'"
        raise SystemExit(msg)
    content = doc.get("arc_content")
    if not isinstance(content, dict):
        msg = f"Document 'arc_{arc_id}' has no object field 'arc_content'"
        raise SystemExit(msg)
    return content


def _summarize(label: str, content: RoCrateContent) -> None:
    raw_hash = calculate_arc_content_hash(content)
    print(f"{label}:")
    print(f"  content_hash = {raw_hash}")
    volatile_only = strip_volatile_rocrate_fields(content)
    print(f"  keys_after_strip (top-level) = {sorted(volatile_only)}")


def _print_diffs(left: RoCrateContent, right: RoCrateContent, *, limit: int) -> int:
    left_c = canonicalize_rocrate_for_hash(left)
    right_c = canonicalize_rocrate_for_hash(right)
    diffs = list(_iter_json_diffs(left_c, right_c))
    print(f"canonicalized diffs: {len(diffs)}")
    for path, old, new in diffs[:limit]:
        print(f"  {path}")
        print(f"    a = {old!r}")
        print(f"    b = {new!r}")
    if len(diffs) > limit:
        print(f"  … {len(diffs) - limit} more")
    return len(diffs)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: compare two RO-Crates and print hash / path diffs."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--a", type=Path, help="Left RO-Crate JSON file (or omit when using --arc-id)")
    parser.add_argument("--b", type=Path, required=True, help="Right RO-Crate JSON file")
    parser.add_argument("--arc-id", help="Load left side from CouchDB document arc_{arc_id}")
    parser.add_argument("--couchdb-url", default=os.getenv("COUCHDB_URL", "http://localhost:5984"))
    parser.add_argument("--couchdb-user", default=os.getenv("COUCHDB_USER"))
    parser.add_argument("--couchdb-password", default=os.getenv("COUCHDB_PASSWORD"))
    parser.add_argument("--couchdb-db", default=os.getenv("COUCHDB_DB_NAME", "middleware"))
    parser.add_argument("--limit", type=int, default=50, help="Max diff paths to print")
    args = parser.parse_args(argv)

    if bool(args.a) == bool(args.arc_id):
        parser.error("Provide exactly one of --a or --arc-id")

    right = _load_json(args.b)
    if args.a is not None:
        left = _load_json(args.a)
    else:
        assert args.arc_id is not None
        left = asyncio.run(
            _load_couchdb_arc(
                args.arc_id,
                url=args.couchdb_url,
                user=args.couchdb_user,
                password=args.couchdb_password,
                db_name=args.couchdb_db,
            )
        )

    _summarize("a", left)
    _summarize("b", right)
    equal = calculate_arc_content_hash(left) == calculate_arc_content_hash(right)
    print(f"hashes_equal = {equal}")
    if equal:
        return 0
    count = _print_diffs(left, right, limit=args.limit)
    return 1 if count else 0


if __name__ == "__main__":
    sys.exit(main())
