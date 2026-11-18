"""Independent finite public-path challenge. Synthetic evidence only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json, math
from v2.nba_c.native_adapters import NativeOutcomeArchive, NativeForecastArchive, P1_VERSION
from v2.nba_c.warehouse import WarehouseError
from v2.nba_c.scores import crps, nll
from v2.nba_architecture.v2_contracts import threshold_triplet

checks=[]
def check(name, condition):
    assert condition, name
    checks.append(name)

for y, expected in [(0,.5625),(1,.0625)]:
    check('bernoulli_crps_'+str(y), abs(crps({0:.25,1:.75},y)-expected)<1e-12)
check('nlpd_reference',abs(nll({0:.25,1:.75},1)+math.log(.75))<1e-12)
for line, expected in [(0,{'over':.75,'under':0,'push':.25}),(.5,{'over':.75,'under':.25,'push':0}),(1,{'over':0,'under':.25,'push':.75})]:
    check('threshold_'+str(line), threshold_triplet([{'value':0,'mass':.25},{'value':1,'mass':.75}],line)==expected)
with TemporaryDirectory() as root:
    for mode in ('real','admitted','verified',''):
        for name, call in [('outcome',lambda:NativeOutcomeArchive(root).put_p1({},evidence_mode=mode)),('forecast',lambda:NativeForecastArchive(root).put_s(None,None,frozen_pregame=None,target_player_id='x',role='wing',source_manifest={},evidence_mode=mode))]:
            try: call()
            except WarehouseError as exc: check(name+'_'+repr(mode),str(exc)=='NATIVE_REAL_ADMISSION_REGISTRY_UNAVAILABLE')
            else: raise AssertionError('real mode admitted')
    check('real_reject_before_storage',not list(Path(root).rglob('*')))
    e={'schema':P1_VERSION,'kind':'outcome_export','game_id':'nba:test','player_id':'nba:p1','team_id':None,'source_profile':'unadmitted_isolated_outcome_vault','admission_status':'BLOCKED','status':'UNRESOLVED','participation':'UNRESOLVED','stats':{},'official_count':None,'displayed_minutes':None,'exact_minutes':None,'event_start_at':None,'event_end_at':None,'outcome_released_at':None,'vault_schema':None,'revisions':[],'correction_version':None,'scoring_authorized':False,'missing_requirements':['INDEPENDENT_SOURCE_ADMISSION','SOURCE_BOUND_EVENT_END','SOURCE_BOUND_OUTCOME_RELEASE_CLOCK','OFFICIAL_OUTCOME_MISSING']}
    vault=NativeOutcomeArchive(root); key=vault.put_p1(e,evidence_mode='synthetic_engineering')
    check('duplicate_idempotent',key==vault.put_p1(e,evidence_mode='synthetic_engineering'))
    check('missing_unscored',vault.scoring_disposition(key)['scored'] is False)
    check('missing_not_DNP',vault.get(key)['participation']=='UNRESOLVED')
    e['event_end_at']='2000-01-01T00:00:00Z'
    try:vault.put_p1(e,evidence_mode='synthetic_engineering')
    except WarehouseError:check('unsupported_end_reject',True)
    else:raise AssertionError('unsupported end accepted')
    check('original_preserved',vault.get(key)['event_end_at'] is None)
print(json.dumps({'scope':'synthetic engineering only; zero real games','checks':checks,'count':len(checks),'result':'PASS'},indent=2))
