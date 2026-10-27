#!/usr/bin/env bash
# Persist append-only calibration history on a dedicated branch, WITHOUT force push.
set -euo pipefail
mode="${1:?use load or save}"
branch="data/shadow-calibration"
root="$(git rev-parse --show-toplevel)"
cd "$root"
if [[ "$mode" == load ]]; then
  if git fetch origin "refs/heads/${branch}:refs/remotes/origin/${branch}"; then
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT
    git archive "refs/remotes/origin/${branch}" | tar -x -C "$tmpdir"
    if [[ -f "$tmpdir/data/prop_snapshots.jsonl" ]]; then
      mkdir -p data
      cp -p "$tmpdir/data/prop_snapshots.jsonl" data/
    fi
  else
    echo "No remote calibration branch yet; starting an empty calibration history."
  fi
elif [[ "$mode" == save ]]; then
  tmpdir="$(mktemp -d)"
  trap 'git worktree remove -f "$tmpdir/tree" >/dev/null 2>&1 || true; rm -rf "$tmpdir"' EXIT
  if git show-ref --verify --quiet "refs/remotes/origin/${branch}"; then
    git worktree add --quiet --detach "$tmpdir/tree" "refs/remotes/origin/${branch}"
  else
    git worktree add --quiet --detach "$tmpdir/tree" HEAD
  fi
  mkdir -p "$tmpdir/tree/data" "$tmpdir/tree/logs"
  [[ ! -f data/prop_snapshots.jsonl ]] || cp -p data/prop_snapshots.jsonl "$tmpdir/tree/data/"
  for f in data/blend_fit_*.json; do
    [[ ! -f "$f" ]] || cp -p "$f" "$tmpdir/tree/data/"
  done
  for f in logs/*.log; do
    [[ ! -f "$f" ]] || cp -p "$f" "$tmpdir/tree/logs/"
  done
  git -C "$tmpdir/tree" config user.name 'pickem-auditor-shadow'
  git -C "$tmpdir/tree" config user.email 'shadow@users.noreply.github.com'
  # Only allow-listed calibration outputs; never persist live research packet or odds keys.
  for f in "$tmpdir/tree"/data/prop_snapshots.jsonl "$tmpdir/tree"/data/blend_fit_*.json "$tmpdir/tree"/logs/*.log; do
    [[ ! -f "$f" ]] || git -C "$tmpdir/tree" add -f -- "${f#"$tmpdir/tree/"}"
  done
  if ! git -C "$tmpdir/tree" diff --cached --quiet; then
    git -C "$tmpdir/tree" commit -qm "shadow calibration ${GITHUB_RUN_ID:-local} ${GITHUB_RUN_ATTEMPT:-1}"
    git -C "$tmpdir/tree" push origin "HEAD:refs/heads/${branch}"
  else
    echo 'Calibration store unchanged.'
  fi
else
  echo 'Usage: shadow_store.sh load|save' >&2
  exit 2
fi
