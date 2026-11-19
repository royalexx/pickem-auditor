"""Read-only native official roster/transaction/game evidence extraction.
No eligibility certification, new admission root or historical clock imputation.
"""
import hashlib,html,json,pathlib,re
P=pathlib.Path(__file__).resolve().parents[1];S=P/'independent/source_search';OLD=pathlib.Path('docs/nba_architecture/p1_overnight_20261119/raw/pregame-20261118T234000059565Z-aae5f441')
def native(raw):
 matches=re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',raw.decode(),re.S);assert len(matches)==1;return json.loads(matches[0])['props']['pageProps']
checks=[]
for receiptpath in S.glob('*/receipt.json'):
 receipt=json.loads(receiptpath.read_bytes());raw=(receiptpath.parent/'body.raw').read_bytes();assert hashlib.sha256(raw).hexdigest()==receipt['raw_sha256'];assert len(raw)==receipt['bytes'];checks.append({'source':receiptpath.parent.name,'status':receipt.get('status'),'raw_sha256':receipt['raw_sha256'],'actual_retrieval_completed_at':receipt['retrieval_completed_at']})
rosters={}
for team in ['cle','mem']:
 folder=OLD/('official-'+team+'-roster');x=native((folder/'body.raw').read_bytes());rows=x['rosterData']['roster'];assert len({r['id'] for r in rows})==len(rows);rosters[team]={'page_team_id':x['team']['id'],'count':len(rows),'rows':[dict(nba_id=r['id'],name=r['name'],row_team_id=r.get('teamId'),source_supplemental_status=r.get('supplementalStatus')) for r in rows]}
assert rosters['cle']['count']==17 and rosters['mem']['count']==18;assert all('Minix' not in r['name'] for r in rosters['cle']['rows'])
a=native((S/'official-austin-minix-release/body.raw').read_bytes())['pageObject'];text=' '.join(html.unescape(p.get('text','')) for p in a['contentExpanded']);assert 'the team has waived forward Riley Minix' in text;assert 'signed forward' in text and 'two-way contract' in text and 'Zack Austin' in text
article={'title':a['title'],'provider_declared_date':a['date'],'provider_declared_modified':a['modified'],'subhead':a['attributes']['subhead'],'transaction_statements':[html.unescape(p['text']) for p in a['contentExpanded'] if 'Minix' in p.get('text','') or 'signed forward' in p.get('text','')],'original_first_available_at':None,'actual_capture':'Nov19 receipt retained; not source-declaredNov18 date'}
g=native((S/'official-game-box-page/body.raw').read_bytes())['game'];assert g['gameId']=='0022600258' and g['gameStatus']==3
completed={}
for side,team in [('homeTeam','cle'),('awayTeam','mem')]:
 t=g[side];ids={r['personId'] for r in t['players']}|{r['personId'] for r in t['inactives']};assert ids=={r['nba_id'] for r in rosters[team]['rows']};completed[team]={'listed_players':len(t['players']),'listed_inactives':len(t['inactives']),'game_specific_legal_active_list_before_freeze':None}
f=native((S/'official-pregame-box-page/body.raw').read_bytes())['game'];assert f['gameId']=='0022600270' and f['gameStatus']==1
pregame={side:{'listed_players':len(f[side].get('players',[])),'listed_inactives':len(f[side].get('inactives',[])),'outer_roster_rows':len(f.get(side+'Players',[]))} for side in ['homeTeam','awayTeam']};assert all(v==0 for rows in pregame.values() for v in rows.values())
print(json.dumps({'source_capture_checks':checks,'captured_prefreeze_official_rosters':rosters,'official_transaction_content':article,'completed_game_native_population':completed,'one_current_pregame_native_probe':{'game':f['gameId'],'state':f['gameStatus'],'teams':pregame,'scope':'observational source capability probe; not a selected or scheduled closure target'},'legal_complete_prefreeze_source_established':False,'schedule_next_closure_capture':False,'B-P1-01':'BLOCKED','B-P1-02_original':'BLOCKED'},indent=2))
