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
    # Phase 3 posterior MC predictions; independent append-only sidecars.
    if [[ -d "$tmpdir/data/posterior_mc" ]]; then
      mkdir -p data/posterior_mc
      cp -an "$tmpdir/data/posterior_mc/." data/posterior_mc/
    fi
    if [[ -d "$tmpdir/data/nfl_context" ]]; then
      mkdir -p data/nfl_context
      cp -an "$tmpdir/data/nfl_context/." data/nfl_context/
    fi
    for extra in nhl_joint_saves_shadow population_nuts_shadow model_comparisons; do
      if [[ -d "$tmpdir/data/$extra" ]]; then
        mkdir -p "data/$extra"
        cp -an "$tmpdir/data/$extra/." "data/$extra/"
      fi
    done
    # Verification sidecars are independent of original forecasts and may be
    # updated before game start. Old decision receipts must remain intact.
    # Restore independent immutable odds observations.
    if [[ -d "$tmpdir/data/market_odds_history" ]]; then
      mkdir -p data/market_odds_history
      cp -an "$tmpdir/data/market_odds_history/." data/market_odds_history/
    fi
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
  # Preserve every frozen forecast, including nightly rows added after the
  # original archive. Only additive settlement/closing enrichment is allowed.
  python scripts/forecast_store_guard.py \
    --previous "$tmpdir/tree/data/prop_snapshots.jsonl" \
    --current data/prop_snapshots.jsonl
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
  # Every price capture is immutable. Never mutate an earlier source observation.
  if [[ -d data/market_odds_history ]]; then
    while IFS= read -r -d '' observation; do
      relative="${observation#data/market_odds_history/}"
      target="$tmpdir/tree/data/market_odds_history/$relative"
      if [[ -e "$target" ]] && ! cmp -s "$observation" "$target"; then
        echo "IMMUTABLE_MARKET_ODDS_SNAPSHOT_CONFLICT: $relative" >&2
        exit 2
      fi
    done < <(find data/market_odds_history -type f -name '*.json' -print0)
    mkdir -p "$tmpdir/tree/data/market_odds_history"
    cp -an data/market_odds_history/. "$tmpdir/tree/data/market_odds_history/"
  fi
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
  if [[ -d data/posterior_mc ]]; then
    while IFS= read -r -d '' forecast; do
      relative="${forecast#data/posterior_mc/}"
      target="$tmpdir/tree/data/posterior_mc/$relative"
      if [[ -e "$target" ]]; then
        python - "$target" "$forecast" <<'PY'
import sys
from pathlib import Path
old=Path(sys.argv[1]).read_bytes()
new=Path(sys.argv[2]).read_bytes()
if not new.startswith(old):
    raise SystemExit('IMMUTABLE_POSTERIOR_MC_CONFLICT: '+sys.argv[2])
PY
      fi
    done < <(find data/posterior_mc -type f -name '*.jsonl' -print0)
    mkdir -p "$tmpdir/tree/data/posterior_mc"
    cp -a data/posterior_mc/. "$tmpdir/tree/data/posterior_mc/"
  fi
  if [[ -d data/nfl_context ]]; then
    while IFS= read -r -d '' forecast; do
      relative="${forecast#data/nfl_context/}"
      target="$tmpdir/tree/data/nfl_context/$relative"
      if [[ -e "$target" ]]; then
        python - "$target" "$forecast" <<'PY_CHECK'
import sys
from pathlib import Path
if not Path(sys.argv[2]).read_bytes().startswith(Path(sys.argv[1]).read_bytes()):
    raise SystemExit('IMMUTABLE_NFL_CONTEXT_FORECAST_CONFLICT')
PY_CHECK
      fi
    done < <(find data/nfl_context -type f -name '*.jsonl' -print0)
    mkdir -p "$tmpdir/tree/data/nfl_context"
    cp -a data/nfl_context/. "$tmpdir/tree/data/nfl_context/"
    git -C "$tmpdir/tree" add -f data/nfl_context/
  fi
  for extra in nhl_joint_saves_shadow population_nuts_shadow model_comparisons; do
    [[ -d "data/$extra" ]] || continue
    while IFS= read -r -d '' forecast; do
      relative="${forecast#data/$extra/}"
      target="$tmpdir/tree/data/$extra/$relative"
      if [[ -e "$target" ]]; then
        python - "$target" "$forecast" <<'PY_EXTRA'
import json,sys
from pathlib import Path
from collections import Counter
def unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('duplicate_json_field')
        d[k]=v
    return d
def reject(value):raise ValueError('nonfinite_json_value')
def records(path):
    return Counter(json.dumps(json.loads(s,object_pairs_hook=unique,parse_constant=reject),
                    sort_keys=True,separators=(',',':'),allow_nan=False)
                   for s in Path(path).read_text().splitlines() if s.strip())
old,new=records(sys.argv[1]),records(sys.argv[2])
if old-new:
    raise SystemExit('IMMUTABLE_VALIDATION_SIDECAR_CONFLICT')
PY_EXTRA
      fi
    done < <(find "data/$extra" -type f -name '*.jsonl' -print0)
    mkdir -p "$tmpdir/tree/data/$extra"
    cp -a "data/$extra/." "$tmpdir/tree/data/$extra/"
    git -C "$tmpdir/tree" add -f "data/$extra/"
  done
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
  if [[ -d "$tmpdir/tree/data/posterior_mc" ]]; then
    git -C "$tmpdir/tree" add -f data/posterior_mc/
  fi
  if [[ -d "$tmpdir/tree/data/verification" ]]; then
    git -C "$tmpdir/tree" add -f data/verification/
  fi
  if [[ -d "$tmpdir/tree/data/market_odds_history" ]]; then
    git -C "$tmpdir/tree" add -f data/market_odds_history/
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
