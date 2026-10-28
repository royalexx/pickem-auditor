#!/usr/bin/env bash
# Independent historical Bayesian warehouse branch, never production data.
set -euo pipefail
mode="$1"
branch="data/bayesian-history"
src="data/bayesian_warehouse"
mkdir -p "$src"
if [[ "$mode" == load ]]; then
  git fetch --quiet origin "refs/heads/$branch:refs/remotes/origin/$branch"
  if git cat-file -e "refs/remotes/origin/$branch:$src" 2>/dev/null; then
    temp="$(mktemp -d)"
    trap 'rm -rf "$temp"' EXIT
    git archive "refs/remotes/origin/$branch" "$src" | tar -x -C "$temp"
    cp -a "$temp/$src/." "$src/"
    echo "Loaded independently persisted historical Bayesian warehouse."
  else
    echo "Warehouse branch has no data yet; starting first idempotent shard."
  fi
elif [[ "$mode" == save ]]; then
  [[ -f "$src/backfill_state.json" ]] || { echo 'NO_VERIFIED_HISTORY_CHECKPOINT' >&2; exit 2; }
  tmp="$(mktemp -d)"
  trap 'git worktree remove -f "$tmp/tree" >/dev/null 2>&1 || :; rm -rf "$tmp"' EXIT
  git fetch --quiet origin "refs/heads/$branch:refs/remotes/origin/$branch"
  git worktree add --quiet --detach "$tmp/tree" "refs/remotes/origin/$branch"
  mkdir -p "$tmp/tree/$src"
  # Old game/player observations must never disappear or change silently.
  python - "$tmp/tree/$src" "$src" <<'PY'
import gzip,json,sys
from pathlib import Path
old,new=map(Path,sys.argv[1:])
for prior in sorted(old.glob('nhl_shots/*.jsonl.gz')):
    now=new/'nhl_shots'/prior.name
    if not now.is_file():
        raise SystemExit('WAREHOUSE_SHARD_MISSING: '+str(prior))
    def records(path):
        with gzip.open(path,'rt') as handle:
            return {(v['game_id'],v['player_id']):v for v in
                    (json.loads(line) for line in handle if line.strip())}
    previous,current=records(prior),records(now)
    for key,value in previous.items():
        if current.get(key)!=value:
            raise SystemExit('IMMUTABLE_HISTORICAL_PLAYER_GAME_CONFLICT: '+str(key))
prior=old/'backfill_state.json'
if prior.exists():
    o=json.loads(prior.read_text());n=json.loads((new/'backfill_state.json').read_text())
    if n['next_date']<o['next_date']:
        raise SystemExit('HISTORICAL_CURSOR_REGRESSION')
    for name in ('dates_complete','games_ingested','skater_games_ingested'):
        if n[name]<o[name]:
            raise SystemExit('HISTORICAL_COUNTER_REGRESSION: '+name)
PY
  cp -a "$src/." "$tmp/tree/$src/"
  git -C "$tmp/tree" config user.name "pickem-bayesian-history"
  git -C "$tmp/tree" config user.email "bayesian-history@users.noreply.github.com"
  git -C "$tmp/tree" add -f "$src"
  if ! git -C "$tmp/tree" diff --cached --quiet; then
    git -C "$tmp/tree" commit -qm "data: checkpoint completed NHL game histories"
    git -C "$tmp/tree" push origin "HEAD:refs/heads/$branch"
  else
    echo "Warehouse is already up to date."
  fi
else
  echo "usage: history_warehouse_store.sh load|save" >&2
  exit 2
fi
