import json,gzip
from pathlib import Path
from urllib.request import urlopen,Request
from dataclasses import asdict
from v2.nba_ws1.store import Receipt
from v2.nba_ws1.capture import now,BASE
from v2.nba_joint.forecast import freeze
root=Path('research/nba_phase8a/evidence/official_inventory');root.mkdir(exist_ok=False);items=[]
for kind,url in [('rules','https://official.nba.com/rule-no-3-players-substitutes-and-coaches/'),('lineups','https://www.nba.com/players/todays-lineups'),('transactions','https://www.nba.com/players/transactions'),('registered_game_summary',BASE+'/summary?event=401909994')]:
 try:
  with urlopen(Request(url,headers={'User-Agent':'pickem-phase8a-bounded-original-audit/1'}),timeout=20) as r:raw=r.read(4*1024*1024+1)
  receipt=Receipt.capture(raw,source=url,observed_at=now(),origin='original_capture');path=receipt.raw_sha256+'.gz'
  with (root/path).open('xb') as f:f.write(gzip.compress(raw,mtime=0))
  item=dict(kind=kind,receipt=asdict(receipt),path=path,bytes=len(raw))
  if kind=='registered_game_summary':
   d=json.loads(raw);item['header']=d.get('header');item['top_level_keys']=list(d);item['boxscore_keys']=list(d.get('boxscore',{}))
  else:
   from research.nba_phase7.evidence import page_data
   try:item['page_prop_keys']=list(page_data(raw))
   except ValueError:pass
 except Exception as exc:item=dict(kind=kind,url=url,retrieved_at=now(),error=str(exc))
 items.append(item)
freeze(root/'inventory.json',dict(items=items,complete_eligible_list_verified=False,game_day_evidence=False))
