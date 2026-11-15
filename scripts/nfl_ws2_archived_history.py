"""Read already captured WS1 raw CSVs. Never fetch or alter WS1 files."""
import csv,io,json,re,unicodedata
from pathlib import Path
from datetime import datetime,timezone
from scripts.nfl_ws2_ws1_adapter import digest
from v2.contracts import utc

def norm(s):
 return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',str(s or '')).encode('ascii','ignore').decode().casefold())
def number(v):
 try:return float(v) if v not in ('',None) else None
 except (ValueError,TypeError):return None

def derive(root,source):
 receipts={};datasets={}
 for label in ('players','stats2026','games2026'):
  rp=root/'source_control/feature_source_receipts'/f'{label}_CAPTURE.json'
  rb=rp.read_bytes();rec=json.loads(rb);p=Path(rec['raw_path'])
  if not p.is_absolute():p=root.parent.parent/p
  if not p.resolve().is_relative_to(root.resolve()):raise ValueError('ARCHIVED_WS1_PATH_ESCAPE')
  raw=p.read_bytes()
  if digest(raw)!=rec['sha256']:raise ValueError('ARCHIVED_WS1_SOURCE_HASH_MISMATCH')
  receipts[label]={**rec,'receipt_file_sha256':digest(rb)}
  datasets[label]=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
 freeze=datetime.now(timezone.utc)
 available=max(utc(r['observed_received_at'],'observed_received_at') for r in receipts.values())
 if available>freeze:raise ValueError('ARCHIVED_SOURCE_FROM_FUTURE')
 bridge={};names={}
 for r in datasets['players']:
  espn=str(r.get('espn_id') or r.get('player_espn_id') or '').removesuffix('.0')
  gsis=r.get('gsis_id') or r.get('player_gsis_id')
  if espn and gsis:
   bridge.setdefault(espn,set()).add(gsis);names[(espn,gsis)]=r.get('display_name') or r.get('player_name')
 games={}
 for g in datasets['games2026']:
  if g.get('season')!='2026' or g.get('game_type')!='REG':continue
  day=g.get('gameday','')[:10]
  if not day or day>='2026-11-15' or number(g.get('result')) is None:continue
  for side in ('home_team','away_team'):games[(g.get('week'),g.get(side))]=(g['game_id'],day)
 fields=('attempts','completions','passing_yards','carries','rushing_yards','receptions','receiving_yards',
  'targets','def_tackles_solo','def_tackles_with_assist','def_tackle_assists')
 players={}
 for r in datasets['stats2026']:
  if r.get('season')!='2026' or r.get('season_type')!='REG':continue
  match=games.get((r.get('week'),r.get('recent_team') or r.get('team')))
  if match is None:continue
  gsis=r.get('player_id') or r.get('gsis_id')
  if not gsis:continue
  gid,day=match
  h={'gsis_id':gsis,'game_id':gid,'game_date':day,'source_available_at':available.isoformat(),
   'source_sha256':receipts['stats2026']['sha256'],**{k:number(r.get(k)) for k in fields}}
  players.setdefault(gsis,[]).append(h)
 contracts=[];history=[]
 for c in source['candidates']:
  ids=bridge.get(str(c.get('player_id')),set());gsis=next(iter(ids)) if len(ids)==1 else None
  reasons=[]
  if not gsis:reasons.append('ESPN_GSIS_CROSSWALK_MISSING_OR_AMBIGUOUS')
  elif norm(c.get('player'))!=norm(names.get((str(c['player_id']),gsis))):reasons.append('INDEPENDENT_NAME_ID_MISMATCH')
  if c.get('stat') in ('pass attempts','completions','passing yards') and c.get('eligibility_status')!='EXPECTED_STARTER_SOURCE_BACKED':
   reasons.append('QB_STARTER_NOT_SOURCE_BACKED')
  contracts.append({**c,'gsis_player_id':gsis,'status':{'CONDITIONAL_ON_APPEARANCE_FORECASTABLE':not reasons},
   'abstention_reasons':reasons})
  if gsis and not reasons:
   for h in sorted(players.get(gsis,[]),key=lambda x:(x['game_date'],x['game_id']))[-10:]:
    history.append({'candidate_id':c['candidate_id'],**h})
 return {'native_ws1_feature_v1':True,'contracts':contracts,'history':history},freeze,{
  'feature_freeze_at':freeze.isoformat(),'model_training_cutoff_at':available.isoformat(),
  'feature_pin_sha256':None,'input_mode':'WS2_READ_ONLY_ADAPTER_OF_ALREADY_ARCHIVED_WS1_SOURCES',
  'ws1_feature_pin_absent':True,'archived_ws1_receipts':receipts}
