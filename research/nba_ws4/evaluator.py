"""Fail-closed prequential research evaluator. No fitting or production calls.

The caller must supply authenticated receipt manifests, never inferred public
availability. Hash verification proves byte identity, not truthful source clocks.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from .metrics import probability, threshold, summary, paired_bootstrap, binary, distribution, log_score, mean

SCHEMA='nba-ws4-evaluation-v1'
IDENTITY=('sport','event_id','player_id','team_id','opponent_id','stat','line','period','overtime','book','quote_id','quote_at','source_id','settlement_policy')
STATS={'points','rebounds','assists','threes','pr','pa','ra','pra','steals','blocks','turnovers'}


def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x): return hashlib.sha256(canonical(x)).hexdigest()
def require(ok, reason):
    if not ok: raise ValueError(reason)


def time(s):
    require(isinstance(s,str) and 'T' in s,'MISSING_TIME')
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    require(d.tzinfo is not None,'NAIVE_TIME'); return d.astimezone(timezone.utc)


def receipt(r, root):
    require(isinstance(r,dict),'RECEIPT_MISSING')
    path=r.get('path'); sha=r.get('sha256')
    require(isinstance(path,str) and bool(path) and isinstance(sha,str) and len(sha)==64,'INVALID_RECEIPT')
    p=(Path(root)/path).resolve()
    require(p.is_relative_to(Path(root).resolve()),'SOURCE_PATH_ESCAPE')
    require(hashlib.sha256(p.read_bytes()).hexdigest()==sha,'SOURCE_HASH_MISMATCH')
    require(r.get('clock_attestation')=='original_authenticated','AVAILABILITY_UNPROVEN')
    require(time(r['available_at'])<=time(r['retrieved_at']),'SOURCE_CLOCK_ORDER')


def contract_key(c):
    require(all(k in c and c[k] is not None and c[k]!='' for k in IDENTITY),'INCOMPLETE_CONTRACT')
    require(c['sport']=='NBA' and c['stat'] in STATS,'UNSUPPORTED_MARKET')
    require(c['period']=='full' and c['overtime'] is True,'UNSUPPORTED_PERIOD_POLICY')
    require(isinstance(c['line'],(int,float)) and not isinstance(c['line'],bool) and math.isfinite(c['line']) and c['line']>=0,'INVALID_LINE')
    require(c['team_id']!=c['opponent_id'],'TEAM_IDENTITY')
    return digest({k:c[k] for k in IDENTITY})


def validate_forecast(f,c,root,protocol):
    key=contract_key(c)
    require(f['contract_id']==key and f['contract']=={k:c[k] for k in IDENTITY},'FORECAST_CONTRACT_MISMATCH')
    require(f['snapshot_sha256']==digest({k:v for k,v in f.items() if k!='snapshot_sha256'}),'MUTATED_FORECAST')
    freeze,forecast,event=time(f['input_freeze_at']),time(f['forecast_at']),time(c['event_start'])
    require(freeze<=forecast<event,'POSTGAME_FORECAST')
    require(time(f['training_cutoff'])<=freeze and time(f['fit_completed_at'])<=freeze,'POSTFREEZE_TRAINING')
    require(time(f['original_archived_at'])<=forecast,'RETROSPECTIVE_REBRANDING')
    require(time(protocol['registered_at'])<=freeze,'POSTHOC_PROTOCOL')
    require(f['model_version']==protocol['models'][f['model_id']],'UNREGISTERED_MODEL_SELECTION')
    require(f['calibration_version']==protocol['calibration_version'],'UNREGISTERED_CALIBRATION')
    require(time(f['calibration_labels_available_through'])<freeze,'CALIBRATION_TARGET_LEAKAGE')
    require(time(f['selection_labels_available_through'])<freeze,'OUTCOME_DEPENDENT_SELECTION')
    require(f['evidence_kind'] in ('prospective','historical_research'),'INVALID_EVIDENCE_KIND')
    require(isinstance(f['development_exposed'],bool),'HOLDOUT_EXPOSURE_MISSING')
    require(f['stage'] in ('preliminary','finalized'),'FORECAST_STAGE_MISSING')
    require(isinstance(f['code_sha'],str) and len(f['code_sha'])==40,'CODE_VERSION_MISSING')
    receipt(f['model_artifact'],root)
    require(time(f['model_artifact']['retrieved_at'])<=forecast,'LATE_MODEL_ARTIFACT')
    require(f['features'],'FEATURE_MANIFEST_MISSING')
    for feature in f['features']:
        receipt(feature,root)
        require(time(feature['retrieved_at'])<=freeze,'POSTGAME_NEWS_OR_SOURCE')
        require(feature['team_id']==c['team_id'],'STALE_TEAM_AFTER_TRADE')
        require(feature['kind'] not in ('target_outcome','actual_minutes','postgame_lineup'),'TARGET_FEATURE_LEAKAGE')
        if feature['kind']=='historical_result':
            require(feature['event_id']!=c['event_id'] and time(feature['event_end'])<freeze,'CURRENT_OR_FUTURE_ROLLING_RESULT')
    receipt(c['quote_receipt'],root)
    require(time(c['quote_at'])<=freeze and time(c['quote_receipt']['retrieved_at'])<=freeze,'LATE_QUOTE')
    quote_doc=json.loads((Path(root)/c['quote_receipt']['path']).read_bytes())
    require(quote_doc['contract_id']==key,'SOURCE_QUOTE_CONTRACT_MISMATCH')
    require(c['quote_receipt']['contract_id']==key,'QUOTE_IDENTITY_MISMATCH')
    if f.get('abstention'):
        require(f.get('probabilities') is None and f.get('pmf') is None,'ABSTENTION_WITH_PREDICTION'); return None
    probs=f['probabilities']
    require(set(probs)=={'over','under','push'},'SIDE_LABELS')
    probs={s:probability(p) for s,p in probs.items()}
    require(abs(math.fsum(probs.values())-1)<1e-10,'PROBABILITY_COMPLEMENTARITY')
    if c['line']%1: require(probs['push']==0,'FRACTIONAL_PUSH')
    if f.get('pmf') is not None:
        expected=threshold(f['pmf'],c['line'])
        require(all(abs(expected[s]-probs[s])<1e-10 for s in probs),'REVERSED_OR_INCONSISTENT_THRESHOLD')
    require(probs['push']<1,'NO_NONPUSH_PROBABILITY')
    return probs['over']/(1-probs['push'])


def settlement(s,c,root):
    if s is None: return 'pending'
    require(s['contract_id']==contract_key(c),'SETTLEMENT_CONTRACT_MISMATCH')
    receipt(s['receipt'],root)
    require(time(s['receipt']['retrieved_at'])>time(c['event_start']),'EARLY_SETTLEMENT')
    source_settlement=json.loads((Path(root)/s['receipt']['path']).read_bytes())
    require(all(source_settlement.get(k)==v for k,v in s.items() if k!='receipt'),'SETTLEMENT_PAYLOAD_NOT_SOURCE_BOUND')
    require(s['team_id']==c['team_id'] and s['period']==c['period'] and s['overtime']==c['overtime'] and s['policy']==c['settlement_policy'],'SETTLEMENT_IDENTITY_POLICY_MISMATCH')
    require(s['status'] in ('final','void','pending'),'INVALID_SETTLEMENT_STATUS')
    if s['status']=='pending': return 'pending'
    if s['status']=='void':
        require(s.get('void_reason') and s.get('actual') is None,'VOID_NOT_ZERO'); return 'void'
    require(s['participation']=='played','DNP_NOT_ZERO')
    y=s['actual']; require(isinstance(y,int) and not isinstance(y,bool) and y>=0,'INVALID_COUNT')
    result='over' if y>c['line'] else 'under' if y<c['line'] else 'push'
    require(s['result']==result,'PUSH_OR_SIDE_MISCLASSIFICATION'); return result


def evaluate(candidates, *, root, protocol):
    """One registered snapshot stage per comparison. Every attempt stays in ledger.

    Origins are sorted by forecast-independent contract event time. Models are
    loaded from immutable predictions, so no after-target fitting is possible.
    A critical violation quarantines the candidate/model and fails the integrity
    gate; independent valid models remain available for descriptive analysis.
    """
    require(protocol['stage'] in ('preliminary','finalized'),'UNREGISTERED_STAGE')
    require(protocol['reference'] in protocol['models'],'UNREGISTERED_REFERENCE')
    require(len(set(protocol['attempt_ids']))==len(protocol['attempt_ids']),'DUPLICATE_REGISTERED_ATTEMPT')
    received=[a.get('attempt_id') for a in candidates]
    universe_errors=[]
    if (None in received or len(set(received))!=len(received) or set(received)!=set(protocol['attempt_ids'])):
        universe_errors.append('ELIGIBLE_UNIVERSE_MISMATCH')
    ledger=[]; seen=set(); model_rows=defaultdict(list); distribution_rows=defaultdict(list); threeway_rows=defaultdict(list); rejected=Counter(); abstentions=defaultdict(Counter)
    for i,attempt in enumerate(candidates):
        row={'attempt_id':attempt.get('attempt_id'),'attempt_index':i,'status':'rejected','model_status':{}}
        ledger.append(row)
        try:
            c=attempt['contract']; key=contract_key(c); row['contract_id']=key
            require(key not in seen,'DUPLICATE_CONTRACT'); seen.add(key)
            require(c['contract_id']==key,'CONTRACT_HASH_MISMATCH')
            row.update(contract=c)
            outcome=settlement(attempt.get('settlement'),c,root); row['outcome']=outcome
            forecasts=attempt['forecasts']; require(isinstance(forecasts,dict),'FORECASTS_MISSING')
            row['status']='eligible'
        except (ValueError,KeyError,OSError,TypeError) as exc:
            row['reason']=str(exc); rejected[str(exc)]+=1; continue
        for model in protocol['models']:
            try:
                require(model in forecasts,'MODEL_OUTPUT_MISSING')
                f=forecasts[model]; require(f['model_id']==model,'MODEL_ID_MISMATCH')
                require(f['stage']==protocol['stage'],'STAGE_MISMATCH')
                p=validate_forecast(f,c,root,protocol)
                if p is None:
                    row['model_status'][model]={'status':'abstained','reason':f['abstention']}
                    abstentions[model][f['abstention']]+=1; continue
                if outcome in ('over','under','push'):
                    probs=f['probabilities']
                    threeway_rows[model].append({'brier':sum((v-int(k==outcome))**2 for k,v in probs.items()),'log_loss':log_score(probs[outcome])})
                    if f.get('pmf') is not None:
                        distribution_rows[model].append(distribution(f['pmf'],attempt['settlement']['actual'],identity=key,tail=protocol.get('tail_thresholds',{}).get(c['stat'],10)))
                row['model_status'][model]={'status':'available','p':p,'snapshot_sha256':f['snapshot_sha256']}
                model_rows[model].append({'contract_id':key,'p':p,'outcome':outcome,'event_id':c['event_id'],
                    'player_id':c['player_id'],'date':c['slate_date'],'slate_id':c['slate_id'],'stat':c['stat']})
            except (ValueError,KeyError,OSError,TypeError) as exc:
                row['model_status'][model]={'status':'rejected','reason':str(exc)}
                abstentions[model]['INVALID:'+str(exc)]+=1
    n=sum(r['status']=='eligible' for r in ledger)
    metrics={m:summary(model_rows[m]) for m in protocol['models']}
    slices={m:{s:summary([r for r in model_rows[m] if r['stat']==s]) for s in sorted({r['stat'] for r in model_rows[m]})} for m in protocol['models']}
    paired={}
    reference=protocol['reference']
    ref={r['contract_id']:r for r in model_rows[reference] if r['outcome'] in ('over','under')}
    for m in protocol['models']:
        if m==reference:continue
        differences=[]
        for r in model_rows[m]:
            if r['contract_id'] not in ref or r['outcome'] not in ('over','under'): continue
            y=int(r['outcome']=='over'); b=ref[r['contract_id']]
            differences.append(dict(r,delta=binary(r['p'],y)['brier']-binary(b['p'],y)['brier']))
        paired[m]={c:paired_bootstrap(differences,cluster=c) for c in ('date','game')}
    critical=bool(universe_errors) or bool(rejected) or any(k.startswith('INVALID:') for v in abstentions.values() for k in v)
    return {'schema':SCHEMA,'protocol_sha256':digest(protocol),'universe_errors':universe_errors,'registered_attempts':len(protocol['attempt_ids']),'attempts':len(candidates),'eligible':n,'rejected':len(candidates)-n,
        'distribution_diagnostics':{m:{'n':len(rs),'per_contract':rs} for m,rs in distribution_rows.items()},
        'three_outcome_scores':{m:{'n':len(rs),'brier':mean([r['brier'] for r in rs]),'log_loss':mean([r['log_loss'] for r in rs])} for m,rs in threeway_rows.items()},
        'rejection_counts':dict(rejected),'ledger':ledger,'metrics':metrics,'market_slices':slices,'paired_brier':paired,
        'evaluation_origins':sorted({r['contract']['event_start'] for r in ledger if r['status']=='eligible'},key=time),
        'model_abstentions_and_rejections':{m:dict(abstentions[m]) for m in protocol['models']},
        'integrity_gate':'FAILED' if critical else 'PASSED','predictive_gate':'INCONCLUSIVE','release_allowed':False}


def append_artifact(folder, kind, payload):
    """Content addressed, exclusive creation; corrections link earlier hash."""
    require(kind in ('preliminary','finalized','settlement','evaluation'),'INVALID_ARTIFACT_KIND')
    root=Path(folder); root.mkdir(parents=True,exist_ok=True)
    raw=canonical(payload); sha=hashlib.sha256(raw).hexdigest(); path=root/(kind+'-'+sha+'.json')
    with path.open('xb') as f: f.write(raw)
    return {'path':str(path),'sha256':sha}


def json_safe(obj):
    """Infinite losses remain explicit; JSON never substitutes a finite cap."""
    if isinstance(obj,float) and math.isinf(obj): return "Infinity" if obj>0 else "-Infinity"
    if isinstance(obj,dict): return {k:json_safe(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)): return [json_safe(v) for v in obj]
    return obj
