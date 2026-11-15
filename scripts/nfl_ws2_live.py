#!/usr/bin/env python3
"""Offline native WS1 executor. No quote collection, name joins or source writes."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2.contracts import utc, finite
from v2.stat_registry import canonical_stat
from v2.nfl_marginal_shadow import MODEL_IDS, PARAMETERS, fit_laws, fixed_logit, probability_only
from scripts.nfl_ws2_ws1_adapter import canonical, digest

SOURCE_SHA = '5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71'

def read_bound(root, ref):
    path=(root/ref['path']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('FEATURE_PATH_ESCAPE')
    raw=path.read_bytes()
    if digest(raw)!=ref['sha256']:
        raise ValueError('FEATURE_BYTES_HASH_MISMATCH')
    return json.loads(raw)

def stat_key(stat):
    return canonical_stat('NFL', {'rushing attempts':'carries', 'passing attempts':'pass attempts',
        'passing completions':'completions'}.get(stat,stat), 'full').key

def histories(candidate, packet, cutoff, target_events):
    """Native long player table; exact namespace IDs, source-bound roles, played only.

    The packet must retain original row availability/ingestion, rather than
    assigning retrospective publication times from a schedule or game date.
    """
    position,role=candidate.get('position'),None
    matches=[x for x in packet.get('contracts',[]) if x.get('candidate_id')==candidate['candidate_id']]
    if len(matches)!=1: raise ValueError('MISSING_OR_AMBIGUOUS_FEATURE_CONTRACT')
    binding=matches[0]
    if binding.get('original_candidate_sha256')!=digest(canonical(candidate)):
        raise ValueError('FEATURE_ORIGINAL_CONTRACT_MISMATCH')
    role=binding.get('role')
    if not role or not position: raise ValueError('MISSING_SOURCE_BOUND_ROLE_POSITION')
    own=[];peers=defaultdict(list);seen=set();excluded=Counter();lineage=[]
    for row in packet.get('players',[]):
        if stat_key(row['stat'])!=stat_key(candidate['stat']):continue
        if row.get('period') not in ('full','full_game'):continue
        if (row.get('position'),row.get('role'))!=(position,role):continue
        pid=row.get('player_id');gid=row.get('event_id',row.get('game_id'))
        if not all(isinstance(v,str) and v for v in (pid,gid,row.get('team'))):
            raise ValueError('MISSING_HISTORY_IDENTITY')
        if row.get('player_id_namespace')!=candidate.get('player_id_namespace'):
            raise ValueError('UNVERIFIED_PLAYER_ID_CROSSWALK')
        ident=(gid,pid,stat_key(row['stat']))
        if ident in seen:raise ValueError('DUPLICATE_HISTORY_PLAYER_EVENT_STAT')
        seen.add(ident)
        if gid in target_events:raise ValueError('TARGET_EVENT_IN_HISTORY')
        ended=utc(row.get('game_end_at'),'game_end_at')
        available=utc(row.get('available_at'),'available_at')
        received=utc(row.get('source_received_at'),'source_received_at')
        if not ended<=available<=cutoff or received>cutoff:
            raise ValueError('HISTORY_AFTER_CUTOFF_OR_UNVERIFIED_AVAILABILITY')
        if row.get('appearance')!='appeared':
            excluded[row.get('appearance') or 'unknown']+=1;continue
        value=finite(row.get('value'),'value')
        group=own if pid==candidate['player_id'] else peers[pid]
        group.append((ended,gid,value));lineage.append(ident)
    own.sort()
    return [x[2] for x in own], [[x[2] for x in sorted(xs)] for _,xs in sorted(peers.items())], {
        'eligible_observation_identities':lineage,'excluded_appearance_counts':dict(excluded),
        'role':role,'position':position,'historical_cutoff':cutoff.isoformat()}

def original_comparators(candidate, packet, freeze, now):
    """Only admit a WS1 bound original comparator, never regenerate production."""
    bindings=[b for b in packet.get('controls',[]) if b.get('candidate_id')==candidate['candidate_id']]
    if len(bindings)!=1:raise ValueError('ORIGINAL_FROZEN_60_40_NOT_AVAILABLE')
    b=bindings[0]
    if b.get('original_candidate_sha256')!=digest(canonical(candidate)):
        raise ValueError('CONTROL_EXACT_CONTRACT_MISMATCH')
    if b.get('model_version')!='production-historical-ensemble-60-40-20261108-v1':
        raise ValueError('WRONG_ORIGINAL_CONTROL_VERSION')
    if not utc(b['forecast_at'],'control_forecast_at')<=freeze<=now:
        raise ValueError('ORIGINAL_CONTROL_NOT_FROZEN')
    probs=[finite(b[k],k) for k in ('q_over','q_under','q_push')]
    if any(not 0<=x<=1 for x in probs) or abs(sum(probs)-1)>1e-10 or sum(probs[:2])<=0:
        raise ValueError('INVALID_ORIGINAL_CONTROL_PROBABILITIES')
    p=probs[0]/sum(probs[:2]);out={}
    for intensity,m in zip(PARAMETERS['shrinkage'],MODEL_IDS[6:]):
        out[m]={'status':'forecast',**probability_only((1-intensity)*p+intensity*.5,
            kind='neutral_shrinkage',push=probs[2])}
    try:
        prices=[finite(candidate[k],k) for k in ('over_odds','under_odds')]
        if any(abs(x)<100 for x in prices):raise ValueError('INVALID_ORIGINAL_AMERICAN_ODDS')
        implied=[100/(x+100) if x>0 else -x/(-x+100) for x in prices]
        market=implied[0]/sum(implied)
        out[MODEL_IDS[5]]={'status':'forecast',**probability_only(fixed_logit(p,market),kind='fixed_equal_logit')}
    except (ValueError,KeyError,TypeError) as exc:out[MODEL_IDS[5]]=missing(str(exc))
    return out


def missing(reason):
    return dict(status='unavailable',reason=reason,q_over=None,q_under=None,q_push=None,
        p_over_given_no_push=None,mean=None,variance=None)

def execute(source, *, packet, now, feature_freeze=None):
    target_events={c.get('event_id') for c in source['candidates']}
    rows=[];seen=set()
    for i,c in enumerate(source['candidates']):
        row={'input_index':i,'original_contract':c,'forecast_created_at':now.isoformat(),
             'models':{m:missing('ORIGINAL_FROZEN_60_40_NOT_AVAILABLE') for m in MODEL_IDS}}
        rows.append(row)
        try:
            if c.get('candidate_id') in seen:raise ValueError('DUPLICATE_CANDIDATE_ID')
            seen.add(c.get('candidate_id'))
            if not c.get('source_certified') or not c.get('research_shadow_eligible'):
                raise ValueError(c.get('source_validation_failure') or c.get('research_shadow_status') or 'SOURCE_NOT_SHADOW_ELIGIBLE')
            if now>=utc(c['event_start_at'],'event_start_at'):raise ValueError('FORECAST_NOT_PREGAME')
            if packet is None:raise ValueError('WS1_FORECAST_FEATURE_PIN_NOT_AVAILABLE')
            if not utc(source['input_freeze_at'],'quote_freeze')<=feature_freeze<=now:
                raise ValueError('INVALID_REAL_FEATURE_FREEZE')
            try:row['models'].update(original_comparators(c,packet,feature_freeze,now))
            except (ValueError,KeyError,TypeError) as exc:
                for m in MODEL_IDS[5:]:row['models'][m]=missing(str(exc))
            cutoff=utc(packet['model_training_cutoff_at'],'model_training_cutoff_at')
            if cutoff>feature_freeze:raise ValueError('TRAINING_AFTER_FEATURE_FREEZE')
            own,peers,lineage=histories(c,packet,cutoff,target_events)
            row['history_lineage']=lineage
            laws,reasons,diag=fit_laws(own,peers,stat=stat_key(c['stat']))
            row['sample_diagnostics']=diag
            for m in MODEL_IDS[:5]:
                row['models'][m]={'status':'forecast',**laws[m].record(c['line'])} if m in laws else missing(reasons.get(m,'NOT_APPLICABLE'))
        except (ValueError,KeyError,TypeError) as exc:
            for m in MODEL_IDS[:5]:row['models'][m]=missing(str(exc))
        # S6/S7 require an original production comparator. They never use a newly
        # generated surrogate. Native source currently has NOT_ORIGINALLY_FROZEN.
        row['research_only']=True
        row['conditioning']='player appearance; product-specific DNP/settlement rules unverified'
    return rows

def audit(rows):
    coverage=defaultdict(Counter);reasons=defaultdict(Counter);by_market=defaultdict(lambda:defaultdict(Counter))
    checks=0
    for r in rows:
        for m,p in r['models'].items():
            coverage[m][p['status']]+=1
            by_market[r['original_contract']['stat']][m][p['status']]+=1
            if p['status']!='forecast':reasons[m][p['reason']]+=1;continue
            probs=[p[k] for k in ('q_over','q_under','q_push')]
            if any(x is None for x in probs):
                assert all(x is None for x in probs) and 0<=p['p_over_given_no_push']<=1
                assert p['mean'] is None and p['variance'] is None
                checks+=1
                continue
            assert all(0<=x<=1 for x in probs) and abs(sum(probs)-1)<1e-10
            if not float(r['original_contract']['line']).is_integer():assert p['q_push']==0
            a,b=MODEL_IDS[2:4]
            if r['models'][a]['status']==r['models'][b]['status']=='forecast':
                assert r['models'][a]['mean']==r['models'][b]['mean']
            checks+=1
    return json.loads(json.dumps({'per_model':coverage,'per_market':by_market,'failure_reasons':reasons,'probability_rows_checked':checks}))

def freeze(root, source_raw, rows, provenance):
    """Index is the create-once commit marker; partial failed writes have no index."""
    out=root/provenance['created_at'].replace(':','').replace('+','_')
    out.mkdir(parents=True,exist_ok=False)
    raw=canonical(rows)+b'\n'
    with (out/'forecast_rows.json').open('xb') as f:f.write(raw)
    report={**provenance,'source_manifest_sha256':digest(source_raw),
        'forecast_rows_sha256':digest(raw),'input_contracts':len(rows),**audit(rows),
        'per_kickoff_window':{w:audit([r for r in rows if r['original_contract']['event_start_at']==w])['per_model'] for w in sorted({r['original_contract']['event_start_at'] for r in rows})},
        'original_quotes_preserved':True,'research_only':True,'production_modified':False}
    body=canonical(report)+b'\n'
    with (out/'INDEX.json').open('xb') as f:f.write(body)
    return {'index_path':str(out/'INDEX.json'),'index_sha256':digest(body),**report}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--out-root',type=Path,required=True)
    args=p.parse_args();root=args.source_root
    pin=json.loads((root/'source_control/HANDOFF_PIN.json').read_bytes())
    if pin['source_control_manifest_sha256']!=SOURCE_SHA:raise ValueError('NONCANONICAL_WS1_PIN')
    src=root/pin['source_control_manifest_relative_path'];raw=src.read_bytes()
    if digest(raw)!=SOURCE_SHA:raise ValueError('CANONICAL_SOURCE_BYTES_CHANGED')
    source=json.loads(raw)
    verified={}
    for c in source['candidates']:
        ref=c.get('source_archive_path');expected=c.get('source_sha256')
        if ref and expected and ref not in verified:
            bound=(root/ref).resolve()
            if not bound.is_relative_to(root.resolve()) or digest(bound.read_bytes())!=expected:
                raise ValueError('ORIGINAL_QUOTE_SOURCE_BYTES_CHANGED')
            verified[ref]=expected
    packet=None;feature_freeze=None;feature_provenance={'feature_freeze_at':None,'model_training_cutoff_at':None,'feature_pin_sha256':None}
    fp=root/'source_control/FORECAST_FEATURE_PIN.json'
    if fp.exists():
        fraw=fp.read_bytes();fpin=json.loads(fraw)
        if fpin.get('source_manifest_sha256')!=SOURCE_SHA:raise ValueError('FEATURE_PIN_WRONG_SOURCE')
        packet=read_bound(root,fpin['feature_packet'])
        if packet.get('owner')!='workstream1':raise ValueError('FEATURE_PACKET_NOT_WS1')
        feature_freeze=utc(packet['input_freeze_at'],'feature_freeze')
        feature_provenance={'feature_pin_sha256':digest(fraw),'feature_packet':fpin['feature_packet'],
            'feature_freeze_at':feature_freeze.isoformat(),'model_training_cutoff_at':packet['model_training_cutoff_at']}
    now=datetime.now(timezone.utc)
    rows=execute(json.loads(raw),packet=packet,now=now,feature_freeze=feature_freeze)
    # Stamp and revalidate at completion, never label time before computation.
    completed=datetime.now(timezone.utc)
    for r in rows:
        r['forecast_created_at']=completed.isoformat()
        if completed>=utc(r['original_contract']['event_start_at'],'event_start_at'):
            r['models']={m:missing('FORECAST_NOT_PREGAME') for m in MODEL_IDS}
    if src.read_bytes()!=raw:raise ValueError('ORIGINAL_SOURCE_CHANGED_DURING_EXECUTION')
    repo=Path(__file__).resolve().parents[1]
    provenance={'created_at':completed.isoformat(),'attempt_started_at':now.isoformat(),
        'quote_freeze_at':json.loads(raw)['input_freeze_at'],**feature_provenance,
        'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        'model_code_sha256':{x:digest((repo/x).read_bytes()) for x in
            ('scripts/nfl_ws2_live.py','scripts/nfl_ws2_ws1_adapter.py','scripts/nfl_ws2_shadow.py','v2/nfl_marginal_shadow.py','v2/contracts.py','v2/stat_registry.py')},
        'parameters':PARAMETERS,'verified_quote_archives':verified,'status':'UNCERTIFIED_SHADOW'}
    print(json.dumps(freeze(args.out_root,raw,rows,provenance),sort_keys=True))

if __name__=='__main__':main()
