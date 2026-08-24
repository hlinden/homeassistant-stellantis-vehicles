#!/usr/bin/env bash
# Merge upstream into this fork and check that the fork's additions still work.
# Conflict resolutions are remembered by git rerere, so a conflict in the same
# place resolves itself on the next sync.
set -uo pipefail
cd "$(dirname "$0")/.."

if [ -n "$(git status --porcelain)" ]; then
    echo "working tree is dirty, commit or stash first"
    exit 1
fi

branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" != "develop" ]; then
    echo "on branch '$branch', expected develop"
    exit 1
fi

git fetch upstream || exit 1

incoming=$(git log --oneline develop..upstream/develop)
if [ -z "$incoming" ]; then
    echo "nothing new upstream"
    exit 0
fi

echo "incoming from upstream:"
echo "$incoming" | sed 's/^/  /'

echo
echo "of those, touching files this fork also changed:"
ours=$(git diff --name-only "$(git merge-base develop upstream/develop)" develop)
theirs=$(git diff --name-only develop...upstream/develop)
overlap=$(comm -12 <(echo "$ours" | sort) <(echo "$theirs" | sort))
if [ -z "$overlap" ]; then
    echo "  none, this should merge cleanly"
else
    echo "$overlap" | sed 's/^/  /'
fi

if [ "${1:-}" = "--dry-run" ]; then
    exit 0
fi

echo
if ! git merge upstream/develop; then
    echo
    echo "resolve the conflicts, then: git add -A && git commit && ./tests/run_all.sh"
    echo "FORK.md lists what each hunk of this fork is for."
    exit 1
fi

echo
./tests/run_all.sh || exit 1

echo
echo "merged and checked. Next: git push, then Redownload in HACS and restart."
