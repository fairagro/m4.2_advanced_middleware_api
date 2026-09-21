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
from m42_ai.code_review import code_review_context, publish_report, write_report
from m42_ai.gh import GhError
from m42_ai.issue import (
    ISSUE_BRANCH_CHANNELS,
    branch_ahead,
    create_issue,
    ensure_issue_branch,
    issue_start,
    view_issue,
)
from m42_ai.pr import pr_strip_footer
from m42_ai.review import fetch_review_open, review_reply, review_resolve
from m42_ai.sync_followup import (
    collect_sync_followup_ids,
    ensure_sync_followup_issue,
    parse_sync_followup_ids,
    pr_for_commit,
)


def _print_json(data: Any) -> None:
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _read_body(args: argparse.Namespace) -> str:
    body_file = getattr(args, "body_file", None)
    if body_file:
        if body_file == "-":
            return sys.stdin.read()
        return Path(body_file).read_text(encoding="utf-8")
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
    try:
        data = fetch_review_open(
            args.pr,
            owner=args.owner,
            repo=args.repo,
            review_id=args.review_id,
            cwd=Path(args.cwd) if getattr(args, "cwd", None) else None,
        )
    except (GhError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 1
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
        channel=args.channel,
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
        channel=args.channel,
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


def cmd_code_review_context(args: argparse.Namespace) -> int:
    data = code_review_context(
        base=args.base,
        pr=args.pr,
        owner=args.owner,
        repo=args.repo,
        cwd=Path(args.cwd) if args.cwd else None,
    )
    _print_json(data)
    return 0 if data.get("ok") else 1


def cmd_code_review_report_write(args: argparse.Namespace) -> int:
    body = _read_body(args)
    data = write_report(
        body,
        slug=args.slug,
        tmp_dir=Path(args.tmp_dir) if args.tmp_dir else None,
    )
    _print_json(data)
    return 0 if data.get("ok") else 1


def cmd_code_review_publish(args: argparse.Namespace) -> int:
    data = publish_report(
        body_file=Path(args.body_file),
        pr=args.pr,
        owner=args.owner,
        repo=args.repo,
        cwd=Path(args.cwd) if args.cwd else None,
    )
    _print_json(data)
    return 0 if data.get("ok") else 1


def cmd_pr_for_commit(args: argparse.Namespace) -> int:
    data = pr_for_commit(
        args.sha,
        owner=args.owner,
        repo=args.repo,
        cwd=Path(args.cwd) if args.cwd else None,
    )
    _print_json({"ok": True, "pr": data})
    return 0


def cmd_sync_followup_ids(args: argparse.Namespace) -> int:
    if args.pr is not None:
        ids = collect_sync_followup_ids(
            pr=args.pr,
            owner=args.owner,
            repo=args.repo,
            cwd=Path(args.cwd) if args.cwd else None,
            body=args.body,
        )
        _print_json({"ok": True, "ids": ids, "pr": args.pr})
        return 0
    texts: list[str] = []
    if args.body_file:
        texts.append(Path(args.body_file).read_text(encoding="utf-8"))
    elif args.body is not None:
        texts.append(str(args.body))
    if args.comment:
        texts.extend(args.comment)
    if not texts:
        raise SystemExit("provide --pr, or --body/--body-file and/or --comment")
    ids = parse_sync_followup_ids(*texts)
    _print_json({"ok": True, "ids": ids})
    return 0


def cmd_sync_followup_ensure(args: argparse.Namespace) -> int:
    data = ensure_sync_followup_issue(
        repo=args.repo,
        stable_id=args.id,
        source_pr_url=args.source_pr_url,
        source_sha=args.source_sha,
        cost=args.cost,
        template_path=Path(args.template) if args.template else None,
        dry_run=bool(args.dry_run),
        cwd=Path(args.cwd) if args.cwd else None,
    )
    _print_json(data)
    return 0 if data.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="m42-ai", description="Deterministic GitHub/git plumbing for agent skills")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    au = sub.add_parser("auth-status", help="Probe gh auth as JSON (exit 1 when not ok)")
    au.add_argument("--hostname", default="github.com")
    au.add_argument("--cwd", help="Git repo root (default: cwd)")
    au.set_defaults(func=cmd_auth_status)

    ro = sub.add_parser(
        "review-open",
        help="Ensure PR head checkout, then fetch/shape open AI review work",
    )
    ro.add_argument("--pr", type=int, required=True)
    ro.add_argument(
        "--review-id",
        type=int,
        dest="review_id",
        help="Optional pull-request review database id (from /pull/N#pullrequestreview-ID)",
    )
    ro.add_argument("--owner")
    ro.add_argument("--repo")
    ro.add_argument("--cwd", help="Git repo root (default: cwd)")
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

    iv = sub.add_parser(
        "issue-view",
        help="Fetch issue triage JSON (type, labels, body, comments, url)",
    )
    iv.add_argument("--issue", type=int, required=True)
    iv.add_argument("--cwd", help="Git repo root (default: cwd)")
    iv.set_defaults(func=cmd_issue_view)

    ib = sub.add_parser(
        "issue-branch",
        help="Ensure {channel}/issue-<n>-<slug> exists and is checked out (no commit/PR)",
    )
    ib.add_argument("--issue", type=int, required=True)
    ib.add_argument("--slug")
    ib.add_argument(
        "--channel",
        choices=sorted(ISSUE_BRANCH_CHANNELS),
        default="build",
        help="Fleet CI channel prefix (default: build)",
    )
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
    ist.add_argument(
        "--channel",
        choices=sorted(ISSUE_BRANCH_CHANNELS),
        default="build",
        help="Fleet CI channel prefix (default: build)",
    )
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

    crc = sub.add_parser(
        "code-review-context",
        help="Shape local or PR diff metadata JSON for /code-review (paths/stats; no full patch)",
    )
    crc.add_argument("--base", default="main", help="Local base ref (default: main)")
    crc.add_argument("--pr", type=int, help="PR number (uses gh; ignores local merge-base)")
    crc.add_argument("--owner")
    crc.add_argument("--repo")
    crc.add_argument("--cwd", help="Git repo root (default: cwd)")
    crc.set_defaults(func=cmd_code_review_context)

    crw = sub.add_parser(
        "code-review-report-write",
        help="Write a code-review Markdown report under /tmp and print JSON path",
    )
    crw.add_argument("--body")
    crw.add_argument("--body-file", help="Markdown path, or '-' for stdin")
    crw.add_argument("--slug", help="Filename slug (default: local)")
    crw.add_argument("--tmp-dir", dest="tmp_dir", help="Override /tmp (tests)")
    crw.set_defaults(func=cmd_code_review_report_write)

    crp = sub.add_parser(
        "code-review-publish",
        help="Publish report as COMMENT PR review (or local no-op without --pr)",
    )
    crp.add_argument("--pr", type=int, help="PR number; omit for local-only (no GitHub)")
    crp.add_argument("--body-file", required=True, help="Report Markdown path")
    crp.add_argument("--owner")
    crp.add_argument("--repo")
    crp.add_argument("--cwd", help="Git repo root (default: cwd)")
    crp.set_defaults(func=cmd_code_review_publish)

    pfc = sub.add_parser("pr-for-commit", help="Resolve a pull request that contains a commit SHA")
    pfc.add_argument("--sha", required=True)
    pfc.add_argument("--owner")
    pfc.add_argument("--repo")
    pfc.add_argument("--cwd", help="Git repo root (default: cwd)")
    pfc.set_defaults(func=cmd_pr_for_commit)

    sfi = sub.add_parser(
        "sync-followup-ids",
        help="Parse SYNC-FOLLOWUP ids from a PR (body+comments) or raw text",
    )
    sfi.add_argument("--pr", type=int)
    sfi.add_argument("--owner")
    sfi.add_argument("--repo")
    sfi.add_argument("--cwd", help="Git repo root (default: cwd)")
    sfi.add_argument("--body", help="PR body text (offline / with --comment)")
    sfi.add_argument("--body-file")
    sfi.add_argument(
        "--comment",
        action="append",
        default=[],
        help="Extra comment body (repeatable); used with --body/--body-file",
    )
    sfi.set_defaults(func=cmd_sync_followup_ids)

    sfe = sub.add_parser(
        "sync-followup-ensure",
        help="Create or reuse a product sync-followup Task for a stable id",
    )
    sfe.add_argument("--repo", required=True, help="owner/name of the product repository")
    sfe.add_argument("--id", required=True, dest="id", help="SYNC-FOLLOWUP stable id")
    sfe.add_argument("--source-pr-url", dest="source_pr_url")
    sfe.add_argument("--source-sha", dest="source_sha")
    sfe.add_argument(
        "--cost",
        default="cost:medium",
        choices=["cost:cheap", "cost:medium", "cost:expensive"],
    )
    sfe.add_argument("--template", help="Override issue body template path")
    sfe.add_argument("--dry-run", action="store_true")
    sfe.add_argument("--cwd", help="Git repo root (default: cwd)")
    sfe.set_defaults(func=cmd_sync_followup_ensure)

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
