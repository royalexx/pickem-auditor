"""Regenerate synthetic fixtures using P2 owner fit, never real data or a new likelihood.
Run from repository root after prepare; this intentionally changes fixture pins.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, 'tests/nba_architecture')
from golden_v2 import pregame, model, game_state, j_scenarios
from v2.nba_architecture.v2_contracts import digest, seal
from v2.nba_joint.integration import load_upstream, FIXTURES, raw_sha
p2,p3=load_upstream('work/upstream/v2')
p=pregame('original_prospective')
g=game_state(p,j_scenarios(p));g.pop('content_hash')
g['scenarios']=[{'scenario_id':f'synthetic:integration:{i}','weight':.25,
    'overtime_periods':i,'pace_regulation':98.+i,
    'possessions_home':101.+12*i,'possessions_away':97.+11*i,
    'score_state':'home_leading'} for i in range(4)]
g=seal(g)
manifest={}
all_rows={}
for stat,value in [('points',18),('rebounds',7),('assists',4),('threes',2)]:
    rows=[]
    for player in p['players']:
        for day in (10,11,12):
            raw=p2.canonical({'synthetic':True,'day':day,'player':player['player_id'],'stat':stat,'count':value})
            receipt=raw_sha(b'fixture-receipt:'+raw)
            source={'raw_sha256':raw_sha(raw),'available_at':f'2026-11-{day:02d}T22:00:00Z','status':'P1_VERIFIED'}
            manifest[receipt]=source
            rows.append({'game_id':f'synthetic:prior:{day}','player_id':player['player_id'],
                'team_id':player['team_id'],'stat':stat,'role':'rotation',
                'game_start_at':f'2026-11-{day:02d}T18:00:00Z',
                'outcome_available_at':f'2026-11-{day:02d}T21:00:00Z',
                'source_receipt_sha256':receipt,'source_raw_sha256':source['raw_sha256'],
                'count':value,'minutes':30.,'three_attempts':6})
    all_rows[stat]=rows
pins={}
for name,stat,family in [('points','points','S1'),('rebounds','rebounds','S1'),('assists','assists','S2'),('threes','threes','S1'),('three_conversion','threes','S3')]:
    artifact=p2.fit(all_rows[stat],asof_cutoff_utc=p['training_cutoff_at'],
                    source_manifest=manifest,stat=stat,family=family,seed=17)
    (FIXTURES/(name+'.json')).write_bytes(artifact.payload)
    pins[name]=artifact.artifact_sha256
priors={}
for player in p['players']:
    priors[player['player_id']]={'source_snapshot_sha256':p['content_hash'],
        'source_receipt_sha256':p['sources'][0]['receipt_sha256'],
        'available_at':p['input_freeze_at'],'training_cutoff_at':p['training_cutoff_at'],
        'scenario_participation_prior':1.,'participation_basis':'historical_prior',
        'minutes_distribution':{'mean':40.,'variance':10.,'ot_probability':.12,'ot_continuation':.25,'family':'beta'},
        'played_zero_probability':0.,'early_exit_probability':0.,'early_exit_fraction':.25,
        'role_states':[{'probability':.5,'minutes_multiplier':.9},{'probability':.5,'minutes_multiplier':1.1}],
        'possession_intensity':1.,'usage_concentration':100.,'uncertainty_flags':['SYNTHETIC_CONTRACT_FIXTURE']}
roles={x['player_id']:'rotation' for x in p['players']}
data={'provenance':'PINNED_SYNTHETIC_OWNER_CONTRACT_FIXTURE_NO_P1_AUTHENTICATION',
      'pregame':p,'game_state':g,'priors':priors,'O_model':model('O',p),
      'source_manifest':manifest,'roles':roles}
(FIXTURES/'inputs.json').write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
(FIXTURES/'trust.json').write_text(json.dumps({'basis':'synthetic_contract_fixture_only',
    'artifacts':pins,'source_manifest_sha256':digest(manifest),'roles_sha256':digest(roles),
    'source_status_flag_is_not_authentication':True},sort_keys=True,indent=2)+'\n')
