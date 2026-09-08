"""CLI entrypoint: `m42-ai <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from m42_ai import __version__
from m42_ai.auth import auth_status
from m42_ai.gh import GhError
from m42_ai.issue import (
    branch_ahead,
    create_issue,
    ensure_issue_branch,
    issue_start,
    view_issue,
)
from m42_ai.pr import pr_strip_footer
from m42_ai.review import fetch_review_open, review_reply, review_resolve


def _print_json(data: Any) -> None:
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _read_body(args: argparse.Namespace) -> str:
    if getattr(args, "body_file", None):
        return Path(args.body_file).read_text(encoding="utf-8")
    if getattr(args, "body", None) is not None:
        return str(args.body)
    raise SystemExit("provide --body or --body-file")


def cmd_auth_status(args: argparse.Namespace) -> int:
    data = auth_status(
        cwd=Path(args.cwd) if args.cwd else None,
        hostname=args.hostname,
    )
    _print_json(data)
    return 0 if data.get("ok") else 1


def cmd_review_open(args: argparse.Namespace) -> int:
    data = fetch_review_open(
        args.pr,
        owner=args.owner,
        repo=args.repo,
        review_id=args.review_id,
    )
    _print_json(data)
    return 0


def cmd_review_reply(args: argparse.Namespace) -> int:
    body = _read_body(args)
    data = review_reply(
        pr=args.pr,
        body=body,
        in_reply_to=args.in_reply_to,
        conversation=bool(args.conversation),
        owner=args.owner,
        repo=args.repo,
    )
    _print_json({"id": data.get("id"), "html_url": data.get("html_url"), "in_reply_to_id": data.get("in_reply_to_id")})
    return 0


def cmd_review_resolve(args: argparse.Namespace) -> int:
    data = review_resolve(args.thread_id)
    _print_json(data)
    return 0


def cmd_issue_create(args: argparse.Namespace) -> int:
    body = _read_body(args)
    labels = [args.severity, args.cost]
    if args.practicality:
        labels.insert(1, args.practicality)
    data = create_issue(
        title=args.title,
        body=body,
        issue_type=args.type,
        labels=labels,
        parent=args.parent,
    )
    _print_json(data)
    return 0


def cmd_issue_view(args: argparse.Namespace) -> int:
    data = view_issue(args.issue, cwd=Path(args.cwd) if args.cwd else None)
    _print_json(data)
    return 0


def cmd_issue_branch(args: argparse.Namespace) -> int:
    data = ensure_issue_branch(
        issue=args.issue,
        slug=args.slug,
        base=args.base,
        cwd=Path(args.cwd) if args.cwd else None,
    )
    _print_json(data)
    return 0


def cmd_branch_ahead(args: argparse.Namespace) -> int:
    data = branch_ahead(
        base=args.base,
        cwd=Path(args.cwd) if args.cwd else None,
    )
    _print_json(data)
    return 0 if data.get("ok") else 1


def cmd_issue_start(args: argparse.Namespace) -> int:
    data = issue_start(
        issue=args.issue,
        slug=args.slug,
        base=args.base,
        cwd=Path(args.cwd) if args.cwd else None,
        draft_title=args.title,
    )
    _print_json(data)
    return 0


def cmd_pr_strip_footer(args: argparse.Namespace) -> int:
    data = pr_strip_footer(
        args.pr,
        owner=args.owner,
        repo=args.repo,
        cwd=Path(args.cwd) if args.cwd else None,
    )
    _print_json(data)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="m42-ai", description="Deterministic GitHub/git plumbing for agent skills")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    au = sub.add_parser("auth-status", help="Probe gh auth as JSON (exit 1 when not ok)")
    au.add_argument("--hostname", default="github.com")
    au.add_argument("--cwd", help="Git repo root (default: cwd)")
    au.set_defaults(func=cmd_auth_status)

    ro = sub.add_parser("review-open", help="Fetch and shape open AI review work for a PR")
    ro.add_argument("--pr", type=int, required=True)
    ro.add_argument(
        "--review-id",
        type=int,
        dest="review_id",
        help="Optional pull-request review database id (from /pull/N#pullrequestreview-ID)",
    )
    ro.add_argument("--owner")
    ro.add_argument("--repo")
    ro.set_defaults(func=cmd_review_open)

    rr = sub.add_parser("review-reply", help="Reply on a review thread or PR conversation")
    rr.add_argument("--pr", type=int, required=True)
    rr.add_argument("--in-reply-to", type=int, dest="in_reply_to")
    rr.add_argument("--conversation", action="store_true")
    rr.add_argument("--body")
    rr.add_argument("--body-file")
    rr.add_argument("--owner")
    rr.add_argument("--repo")
    rr.set_defaults(func=cmd_review_reply)

    rv = sub.add_parser("review-resolve", help="Resolve a review thread by GraphQL node id")
    rv.add_argument("--thread-id", required=True, dest="thread_id")
    rv.set_defaults(func=cmd_review_resolve)

    ic = sub.add_parser("issue-create", help="Create an issue with org type + triage labels")
    ic.add_argument("--title", required=True)
    ic.add_argument(
        "--type", required=True, choices=["Bug", "Security", "Feature", "Task", "Discussion", "Refactoring"]
    )
    ic.add_argument(
        "--severity",
        required=True,
        choices=[
            "severity:blocker",
            "severity:high",
            "severity:medium",
            "severity:low",
        ],
    )
    ic.add_argument(
        "--practicality",
        required=False,
        default=None,
        choices=[
            "practicality:high",
            "practicality:medium",
            "practicality:low",
            "practicality:none",
            "practicality:seen-in-the-wild",
        ],
        help="Optional; omit for Feature/Task/etc. with no defect path",
    )
    ic.add_argument(
        "--cost",
        required=True,
        choices=["cost:cheap", "cost:medium", "cost:expensive"],
    )
    ic.add_argument("--parent", type=int, help="GitHub parent issue number (sub-of)")
    ic.add_argument("--body")
    ic.add_argument("--body-file")
    ic.set_defaults(func=cmd_issue_create)

    iv = sub.add_parser("issue-view", help="Fetch issue triage JSON (type, labels, body, url)")
    iv.add_argument("--issue", type=int, required=True)
    iv.add_argument("--cwd", help="Git repo root (default: cwd)")
    iv.set_defaults(func=cmd_issue_view)

    ib = sub.add_parser(
        "issue-branch",
        help="Ensure issue-<n>-<slug> exists and is checked out (no commit/PR)",
    )
    ib.add_argument("--issue", type=int, required=True)
    ib.add_argument("--slug")
    ib.add_argument("--base", default="main")
    ib.add_argument("--cwd", help="Git repo root (default: cwd)")
    ib.set_defaults(func=cmd_issue_branch)

    ba = sub.add_parser("branch-ahead", help="Report HEAD vs base; exit 1 when not ahead")
    ba.add_argument("--base", default="main")
    ba.add_argument("--cwd", help="Git repo root (default: cwd)")
    ba.set_defaults(func=cmd_branch_ahead)

    ist = sub.add_parser(
        "issue-start",
        help="Push issue branch + draft PR when tip is ahead of base (no empty commit)",
    )
    ist.add_argument("--issue", type=int, required=True)
    ist.add_argument("--slug")
    ist.add_argument("--base", default="main")
    ist.add_argument("--title", help="Override draft PR title (default: issue title)")
    ist.add_argument("--cwd", help="Git repo root (default: cwd)")
    ist.set_defaults(func=cmd_issue_start)

    ps = sub.add_parser("pr-strip-footer", help="Strip Made with Cursor (and similar) from a PR body")
    ps.add_argument("--pr", type=int, required=True)
    ps.add_argument("--owner")
    ps.add_argument("--repo")
    ps.add_argument("--cwd", help="Git repo root (default: cwd)")
    ps.set_defaults(func=cmd_pr_strip_footer)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func: Callable[[argparse.Namespace], int] = args.func
    try:
        return func(args)
    except (GhError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"m42-ai: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
