#!/usr/bin/env bash
#
# Prune local and origin branches that are safe to delete after PRs land on main.
#
# Dry-run by default. Pass --apply to delete.
#
# Deletion rule (A ∪ B):
#   A — tip is ancestor of origin/<base>, OR head of a MERGED PR into <base> (incl. squash)
#   B — head of a CLOSED-unmerged PR that reaches a MERGED PR via recursive
#       "Superseded by #<n>" edges (sync closes older PRs this way)
#
# Never deletes: <base>, current checkout, heads of OPEN PRs.
#
# Usage:
#   ./scripts/prune-merged-branches.sh
#   ./scripts/prune-merged-branches.sh --apply
#   ./scripts/prune-merged-branches.sh --base main --remote origin --apply
#
# Requires: git, gh on PATH (Dev Container: scripts/bin/gh).
#
set -euo pipefail

BASE=main
REMOTE=origin
APPLY=0

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply | --yes) APPLY=1 ;;
    --base)
      BASE="${2:?}"
      shift
      ;;
    --remote)
      REMOTE="${2:?}"
      shift
      ;;
    -h | --help) usage 0 ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage 1
      ;;
  esac
  shift
done

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh not on PATH (Dev Container: ensure scripts/bin is first)" >&2
  exit 1
fi
if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git not on PATH" >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "Fetching ${REMOTE}/${BASE}..."
git fetch "$REMOTE" "$BASE" --prune

BASE_REF="${REMOTE}/${BASE}"
if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
  echo "ERROR: missing ${BASE_REF}" >&2
  exit 1
fi

CURRENT="$(git branch --show-current || true)"
OWNER_REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# All PRs targeting BASE (open/closed/merged) — head ref + state + merge info.
# Paginate; sync fleets can accumulate hundreds of sync PRs.
gh pr list --repo "$OWNER_REPO" --base "$BASE" --state all --limit 500 \
  --json number,state,mergedAt,headRefName,url >"$TMP/prs.json"

# Collect issue/PR comments that may contain "Superseded by #N" (issue comments on the PR).
# Batch per PR would be slow; fetch timeline comments via graphql for closed PRs only when needed.

python3 - "$TMP/prs.json" "$TMP" "$BASE" <<'PY'
import json, os, re, subprocess, sys

prs_path, tmp, base = sys.argv[1], sys.argv[2], sys.argv[3]
prs = json.load(open(prs_path))
by_num = {p["number"]: p for p in prs}
by_head: dict[str, list] = {}
for p in prs:
    h = p.get("headRefName") or ""
    if not h:
        continue
    by_head.setdefault(h, []).append(p)

open_heads = {
    p["headRefName"]
    for p in prs
    if p.get("state") == "OPEN" and p.get("headRefName")
}

SUPERSEDE_RE = re.compile(r"(?i)superseded\s+by\s+#(\d+)")


def gh_json(args: list[str]):
    out = subprocess.check_output(["gh", *args], text=True)
    return json.loads(out) if out.strip() else None


def supersede_target(num: int) -> int | None:
    """Return next PR number from body/comments, or None."""
    # Prefer cached body from list; comments need a fetch.
    p = by_num.get(num)
    texts = []
    if p:
        # list JSON has no body by default — fetch once
        pass
    try:
        detail = gh_json(
            [
                "pr",
                "view",
                str(num),
                "--json",
                "body,comments",
            ]
        )
    except subprocess.CalledProcessError:
        return None
    if not detail:
        return None
    texts.append(detail.get("body") or "")
    for c in detail.get("comments") or []:
        texts.append(c.get("body") or "")
    for t in texts:
        m = SUPERSEDE_RE.search(t)
        if m:
            return int(m.group(1))
    return None


_chain_cache: dict[int, int | None] = {}


def chain_merged_into(num: int, stack: set[int] | None = None) -> int | None:
    """If this PR or a supersede successor MERGED into base, return that PR number."""
    if num in _chain_cache:
        return _chain_cache[num]
    if stack is None:
        stack = set()
    if num in stack:
        _chain_cache[num] = None
        return None
    stack.add(num)
    p = by_num.get(num)
    if p is None:
        # May be outside the 500 window — fetch
        try:
            p = gh_json(["pr", "view", str(num), "--json", "number,state,mergedAt,headRefName"])
            if p:
                by_num[num] = p
        except subprocess.CalledProcessError:
            _chain_cache[num] = None
            return None
    if not p:
        _chain_cache[num] = None
        return None
    state = p.get("state")
    if state == "MERGED" or p.get("mergedAt"):
        _chain_cache[num] = num
        return num
    if state == "OPEN":
        _chain_cache[num] = None
        return None
    # CLOSED (unmerged)
    nxt = supersede_target(num)
    if nxt is None:
        _chain_cache[num] = None
        return None
    result = chain_merged_into(nxt, stack)
    _chain_cache[num] = result
    return result


# Write helpers for bash
with open(os.path.join(tmp, "open_heads.txt"), "w") as f:
    for h in sorted(open_heads):
        f.write(h + "\n")

# Precompute per-head reasons candidates (gh-side only); bash adds ancestor check.
reasons: dict[str, str] = {}
for head, plist in by_head.items():
    # Prefer MERGED
    merged = [p for p in plist if p.get("state") == "MERGED" or p.get("mergedAt")]
    if merged:
        reasons[head] = f"merged-pr→#{merged[0]['number']}"
        continue
    closed = [p for p in plist if p.get("state") == "CLOSED" and not p.get("mergedAt")]
    for p in closed:
        m = chain_merged_into(p["number"])
        if m is not None:
            reasons[head] = f"superseded-chain→#{m}"
            break

with open(os.path.join(tmp, "gh_reasons.json"), "w") as f:
    json.dump(reasons, f)
with open(os.path.join(tmp, "open_heads.txt"), "w") as f:
    for h in sorted(open_heads):
        f.write(h + "\n")
PY

# Bash side: enumerate branches and decide
mapfile -t OPEN_HEADS < <(sort -u "$TMP/open_heads.txt" 2>/dev/null || true)

is_open_head() {
  local b=$1 h
  for h in "${OPEN_HEADS[@]:-}"; do
    [[ "$h" == "$b" ]] && return 0
  done
  return 1
}

gh_reason_for() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' \
    "$TMP/gh_reasons.json" "$1"
}

KEPT=()
WOULD=()
DELETED=()

consider() {
  local kind=$1 # local|remote
  local name=$2 # branch short name
  local ref=$3  # full ref for rev-parse

  if [[ "$name" == "$BASE" ]]; then
    KEPT+=("$kind $name (protected:base)")
    return
  fi
  if [[ "$kind" == "local" && -n "$CURRENT" && "$name" == "$CURRENT" ]]; then
    KEPT+=("$kind $name (protected:current)")
    return
  fi
  if is_open_head "$name"; then
    KEPT+=("$kind $name (protected:open-pr)")
    return
  fi

  local reason=""
  if git merge-base --is-ancestor "$ref" "$BASE_REF" 2>/dev/null; then
    # Tip reachable from base → fully merged (ff/merge commit)
    reason="merged-ancestor"
  else
    reason="$(gh_reason_for "$name")"
  fi

  if [[ -z "$reason" ]]; then
    KEPT+=("$kind $name (keep:not-proven)")
    return
  fi

  if [[ "$APPLY" -eq 0 ]]; then
    WOULD+=("$kind $name ($reason)")
    return
  fi

  if [[ "$kind" == "local" ]]; then
    # -D: squash-merged tips are often not ancestors
    if git branch -D "$name"; then
      DELETED+=("local $name ($reason)")
    else
      KEPT+=("local $name (delete-failed)")
    fi
  else
    if git push "$REMOTE" --delete "$name"; then
      DELETED+=("remote $name ($reason)")
    else
      KEPT+=("remote $name (delete-failed)")
    fi
  fi
}

echo "Scanning local branches..."
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  consider local "$name" "$name"
done < <(git for-each-ref --format='%(refname:short)' refs/heads/)

echo "Scanning ${REMOTE} branches..."
while IFS= read -r name; do
  [[ -z "$name" || "$name" == "HEAD" || "$name" == "$REMOTE" ]] && continue
  # Only real remote-tracking branches under refs/remotes/<remote>/<name>
  git rev-parse --verify "${REMOTE}/${name}" >/dev/null 2>&1 || continue
  consider remote "$name" "${REMOTE}/${name}"
done < <(
  git for-each-ref --format='%(refname:short)' "refs/remotes/${REMOTE}/" \
    | sed "s#^${REMOTE}/##" \
    | grep -vxF '' \
    | grep -vxF 'HEAD' \
    | grep -vxF "$REMOTE"
)

echo
if [[ "$APPLY" -eq 1 ]]; then
  echo "=== Summary (apply) ==="
  echo "Mode: apply"
else
  echo "=== Summary (dry-run) ==="
  echo "Mode: dry-run (pass --apply to delete)"
fi
echo
echo "Would delete / deleted (${#WOULD[@]} dry-run candidates, ${#DELETED[@]} deleted):"
if ((${#WOULD[@]})); then
  printf '  %s\n' "${WOULD[@]}"
fi
if ((${#DELETED[@]})); then
  printf '  %s\n' "${DELETED[@]}"
fi
if ((${#WOULD[@]} == 0 && ${#DELETED[@]} == 0)); then
  echo "  (none)"
fi
echo
echo "Kept (${#KEPT[@]}):"
if ((${#KEPT[@]})); then
  printf '  %s\n' "${KEPT[@]}"
else
  echo "  (none)"
fi
