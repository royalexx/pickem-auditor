#!/usr/bin/env bash
# Authoritative source/history store for scheduled GitHub Actions runs.
# The immutable legacy history-archive branch is read only. New pregame
# forecasts, settled outcomes and source caches live on data/shadow-calibration.
# No automatic coefficient, weight or calibration updates are performed here.
set -euo pipefail
mode="${1:?use load or save}"
branch="data/shadow-calibration"
archive_branch="data/history-archive"
root="$(git rev-parse --show-toplevel)"
cd "$root"

load_cached_sources() {
  local cache="$1"
  if [[ ! -s "$cache" ]]; then return 0; fi
  local unpack="$(mktemp -d)"
  trap 'rm -rf "$unpack"' RETURN
  tar -I zstd -xf "$cache" -C "$unpack" -- data/usage data/season
  for dir in usage season; do
    if [[ -d "$unpack/data/$dir" ]]; then
      mkdir -p "data/$dir"
      cp -an "$unpack/data/$dir/." "data/$dir/"
    fi
  done
}

if [[ "$mode" == load ]]; then
  if git fetch origin "refs/heads/${branch}:refs/remotes/origin/${branch}"; then
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT
    git archive "refs/remotes/origin/${branch}" | tar -x -C "$tmpdir"
    if [[ -s "$tmpdir/data/prop_snapshots.jsonl" ]]; then
      mkdir -p data
      cp -p "$tmpdir/data/prop_snapshots.jsonl" data/
      echo 'Restored persistent forecast and outcome history.'
    else
      echo 'CALIBRATION_ARCHIVE_MISSING_FORECASTS' >&2
      exit 2
    fi
    load_cached_sources "$tmpdir/data/source_cache.tar.zst"
    if [[ -d "$tmpdir/data/morning_runs" ]]; then
      mkdir -p data/morning_runs
      cp -an "$tmpdir/data/morning_runs/." data/morning_runs/
    fi
    # Restore immutable Bayesian Engine A shadow forecasts, never production grades.
    if [[ -d "$tmpdir/data/bayesian_shadow" ]]; then
      mkdir -p data/bayesian_shadow
      cp -an "$tmpdir/data/bayesian_shadow/." data/bayesian_shadow/
    fi
    # Separate immutable Bayesian Engine B shadow forecasts.
    if [[ -d "$tmpdir/data/bayesian_b_shadow" ]]; then
      mkdir -p data/bayesian_b_shadow
      cp -an "$tmpdir/data/bayesian_b_shadow/." data/bayesian_b_shadow/
    fi
    # Verification sidecars are independent of original forecasts and may be
    # updated before game start. Old decision receipts must remain intact.
    if [[ -d "$tmpdir/data/verification" ]]; then
      mkdir -p data/verification
      cp -a "$tmpdir/data/verification/." data/verification/
    fi
  else
    echo 'No calibration branch yet; verifying legacy history archive.'
    if ! git fetch origin "refs/heads/${archive_branch}:refs/remotes/origin/${archive_branch}"; then
      echo 'HISTORY_ARCHIVE_UNAVAILABLE: refusing to create a fresh empty forecast history.' >&2
      exit 2
    fi
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT
    git archive "refs/remotes/origin/${archive_branch}" archive/2026-10-26 | tar -x -C "$tmpdir"
    python scripts/history_bootstrap.py --archive-dir "$tmpdir/archive/2026-10-26" --destination "$root"
  fi
elif [[ "$mode" == save ]]; then
  if [[ ! -s data/prop_snapshots.jsonl ]]; then
    echo 'NO_VERIFIED_FORECAST_HISTORY: refusing to replace persistent branch.' >&2
    exit 2
  fi
  tmpdir="$(mktemp -d)"
  trap 'git worktree remove -f "$tmpdir/tree" >/dev/null 2>&1 || true; rm -rf "$tmpdir"' EXIT
  git fetch origin "refs/heads/${branch}:refs/remotes/origin/${branch}" >/dev/null 2>&1 || true
  if git show-ref --verify --quiet "refs/remotes/origin/${branch}"; then
    git worktree add --quiet --detach "$tmpdir/tree" "refs/remotes/origin/${branch}"
  else
    git worktree add --quiet --detach "$tmpdir/tree" HEAD
  fi
  mkdir -p "$tmpdir/tree/data" "$tmpdir/tree/logs"
  cp -p data/prop_snapshots.jsonl "$tmpdir/tree/data/"
  # Store historical source observations alongside predictions for subsequent
  # collection windows. These data are NOT calibration weights or forecasts.
  sources=()
  [[ ! -d data/usage ]] || sources+=(data/usage)
  [[ ! -d data/season ]] || sources+=(data/season)
  if (( ${#sources[@]} )); then
    tar -I 'zstd -6' -cf "$tmpdir/tree/data/source_cache.tar.zst" "${sources[@]}"
  fi
  for file in data/blend_fit_*.json; do
    [[ ! -f "$file" ]] || cp -p "$file" "$tmpdir/tree/data/"
  done
  # Worktree keeps every prior decision. A decision identity may not be rewritten.
  if [[ -d data/verification ]]; then
    while IFS= read -r -d '' evidence; do
      relative="${evidence#data/verification/}"
      target="$tmpdir/tree/data/verification/$relative"
      if [[ -e "$target" ]] && ! cmp -s "$evidence" "$target"; then
        echo "IMMUTABLE_VERIFICATION_DECISION_CONFLICT: $relative" >&2
        exit 2
      fi
    done < <(find data/verification -path '*/decisions/*.json' -type f -print0)
    mkdir -p "$tmpdir/tree/data/verification"
    cp -a data/verification/. "$tmpdir/tree/data/verification/"
  fi
  # Morning completion receipts live next to the authoritative forecast
  # history, never on main. Once written, a same-date receipt is immutable.
  if [[ -d data/morning_runs ]]; then
    mkdir -p "$tmpdir/tree/data/morning_runs"
    while IFS= read -r -d '' marker; do
      relative="${marker#data/morning_runs/}"
      target="$tmpdir/tree/data/morning_runs/$relative"
      if [[ -e "$target" ]] && ! cmp -s "$marker" "$target"; then
        echo "IMMUTABLE_MORNING_SETTLEMENT_MARKER_CONFLICT: $relative" >&2
        exit 2
      fi
    done < <(find data/morning_runs -type f -name '*.json' -print0)
    cp -a data/morning_runs/. "$tmpdir/tree/data/morning_runs/"
  fi
  # Persist the separate append-only posterior-predictive history.
  if [[ -d data/bayesian_shadow ]]; then
    while IFS= read -r -d '' forecast; do
      relative="${forecast#data/bayesian_shadow/}"
      target="$tmpdir/tree/data/bayesian_shadow/$relative"
      if [[ -e "$target" ]]; then
        python - "$target" "$forecast" <<'PY'
import sys
from pathlib import Path
old=Path(sys.argv[1]).read_bytes()
new=Path(sys.argv[2]).read_bytes()
if not new.startswith(old):
    raise SystemExit('IMMUTABLE_BAYESIAN_SHADOW_CONFLICT: '+sys.argv[2])
PY
      fi
    done < <(find data/bayesian_shadow -type f -name '*.jsonl' -print0)
    mkdir -p "$tmpdir/tree/data/bayesian_shadow"
    cp -a data/bayesian_shadow/. "$tmpdir/tree/data/bayesian_shadow/"
  fi
  if [[ -d data/bayesian_b_shadow ]]; then
    while IFS= read -r -d '' forecast; do
      relative="${forecast#data/bayesian_b_shadow/}"
      target="$tmpdir/tree/data/bayesian_b_shadow/$relative"
      if [[ -e "$target" ]]; then
        python - "$target" "$forecast" <<'PY'
import sys
from pathlib import Path
old=Path(sys.argv[1]).read_bytes()
new=Path(sys.argv[2]).read_bytes()
if not new.startswith(old):
    raise SystemExit('IMMUTABLE_BAYESIAN_B_SHADOW_CONFLICT: '+sys.argv[2])
PY
      fi
    done < <(find data/bayesian_b_shadow -type f -name '*.jsonl' -print0)
    mkdir -p "$tmpdir/tree/data/bayesian_b_shadow"
    cp -a data/bayesian_b_shadow/. "$tmpdir/tree/data/bayesian_b_shadow/"
  fi
  for file in logs/*.log; do
    [[ ! -f "$file" ]] || cp -p "$file" "$tmpdir/tree/logs/"
  done
  git -C "$tmpdir/tree" config user.name pickem-auditor-shadow
  git -C "$tmpdir/tree" config user.email shadow@users.noreply.github.com
  for file in "$tmpdir/tree/data/prop_snapshots.jsonl" "$tmpdir/tree/data/source_cache.tar.zst" \
              "$tmpdir/tree"/data/blend_fit_*.json "$tmpdir/tree"/logs/*.log; do
    [[ ! -f "$file" ]] || git -C "$tmpdir/tree" add -f -- "${file#"$tmpdir/tree/"}"
  done
  if [[ -d "$tmpdir/tree/data/bayesian_shadow" ]]; then
    git -C "$tmpdir/tree" add -f data/bayesian_shadow/
  fi
  if [[ -d "$tmpdir/tree/data/bayesian_b_shadow" ]]; then
    git -C "$tmpdir/tree" add -f data/bayesian_b_shadow/
  fi
  if [[ -d "$tmpdir/tree/data/verification" ]]; then
    git -C "$tmpdir/tree" add -f data/verification/
  fi
  if [[ -d "$tmpdir/tree/data/morning_runs" ]]; then
    git -C "$tmpdir/tree" add -f data/morning_runs/
  fi
  if ! git -C "$tmpdir/tree" diff --cached --quiet; then
    git -C "$tmpdir/tree" commit -qm "persist verified source history ${GITHUB_RUN_ID:-local} ${GITHUB_RUN_ATTEMPT:-1}"
    git -C "$tmpdir/tree" push origin "HEAD:refs/heads/${branch}"
  else
    echo 'Persistent history is already current.'
  fi
else
  echo 'Usage: shadow_store.sh load|save' >&2
  exit 2
fi