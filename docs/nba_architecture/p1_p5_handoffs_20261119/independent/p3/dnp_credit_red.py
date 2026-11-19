"""Exact b415e8bf public native-history accounting red; synthetic source mutation."""
import json,pathlib,shutil,tempfile,subprocess,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[5];P=ROOT/'docs/nba_architecture/p1_p5_handoffs_20261119';C=json.loads((P/'PROSPECTIVE_COHORT.json').read_bytes());blob=subprocess.check_output(['git','show','b415e8bf294c4765021dd8a4067a275e48ef75ac:v2/nba_architecture/subset_p3_v1.py']);module=tempfile.NamedTemporaryFile(suffix='.py');module.write(blob);module.flush();ns={'__name__':'v2.nba_architecture.review_b415','__package__':'v2.nba_architecture','__file__':module.name};exec(compile(blob,'b415e8bf:subset_p3_v1.py','exec'),ns)
with tempfile.TemporaryDirectory() as tmp:
 h=pathlib.Path(tmp)/'history';shutil.copytree(P/'prospective_inputs',h);chosen=None
 for folder in h.glob('summary-*'):
  x=json.loads((folder/'body.raw').read_bytes());team=next((t for t in x['boxscore']['players'] if str(t['team']['id'])=='29'),None)
  if team:
   stat=team['statistics'][0];row=next((a for a in stat['athletes'] if a.get('didNotPlay') is True),None)
   if row:
    row['stats']=['0']*len(stat['names']);row['stats'][stat['names'].index('PTS')]='3';chosen=(folder,x,'espn:player:'+str(row['athlete']['id']));break
 assert chosen is not None;folder,x,pid=chosen;f=folder/'body.raw';f.write_text(json.dumps(x));r=folder/'receipt.json';v=json.loads(r.read_bytes());v['raw_sha256']=hashlib.sha256(f.read_bytes()).hexdigest();v['bytes']=len(f.read_bytes());r.write_text(json.dumps(v))
 games,_=ns['read_team_history'](h,'29',C);state=next(g['observations'][pid] for g in games if g['source_label']==folder.name);print(json.dumps({'mutated_game':folder.name,'player':pid,'source_MIN':'0','source_PTS':'3','accepted_state':state},indent=2));assert state['state']!='DNP','contradictory positive-credit zero-minute row was imputed DNP'
