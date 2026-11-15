"""Read-only integrity audit, original-forecast reconciliation and diagnostic replay.

No model writes or release authority. Sequential automated audit is not an
independent human/statistical sign-off. It cannot certify book equivalence.
"""
import argparse,csv,gzip,io,hashlib,json,math,sys
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import nbinom
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
from nfl_tackle_repair import read,jsonl,table,stamp,sha,canonical,unchanged,now

def probabilities(p):
    assert all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in p)
    assert abs(sum(p)-1)<1e-10

def run(root,baseline,opportunity,out):
    out.mkdir(parents=True,exist_ok=False)
    b=json.loads((baseline/'EXECUTION_RECEIPT.json').read_bytes());p=json.loads((baseline/'HANDOFF_PIN.json').read_bytes())
    o=json.loads((opportunity/'EXECUTION_RECEIPT.json').read_bytes())
    for path,digest in p['parent_pins'].items():assert sha(Path(path).read_bytes())==digest
    hist=jsonl(read(root,p['tables']['history'])); snaps=jsonl(read(root,p['tables']['defensive_snaps']))
    for h in hist:
        vals=list(h['internal_components'].values())
        assert len(vals)==3 and all(v is not None and math.isfinite(v) and v>=0 and int(v)==v for v in vals)
        assert sum(vals)==h['combined_total']
        assert h['game_date']<'2026-11-15' and stamp(h['source_available_at'])<=stamp(p['input_freeze_at'])
    source_checks=Counter()
    for path in sorted({h['source_file'] for h in hist}):
        hs=[h for h in hist if h['source_file']==path]
        raw=read(root,{'path':path,'sha256':hs[0]['source_sha256']})
        source_rows=json.loads(gzip.decompress(raw))['rows'] if path.endswith('.gz') else list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        lookup={(r.get('game_id'),'gsis:'+str(r.get('player_id'))):r for r in source_rows}
        for h in hs:
            r=lookup[h['game_id'],h['player_id']]
            for k,v in h['internal_components'].items():assert r.get(k) is not None and float(r[k])==v
            source_checks['original_raw_component_row_reconciliations']+=1
        source_checks['original_raw_file_hashes']+=1
    assert len({(s['player_id'],s['game_id'],s['team']) for s in snaps})==len(snaps)
    rows=jsonl(read(root,b['outputs']['comparison_ledger']));oprows=jsonl(read(root,o['ledger']));ops={r['candidate_id']:r for r in oprows}
    assert len(ops)==len(oprows)==len(rows)==114
    original_pin=json.loads((root/'reports/nfl_20261115_prospective/source_control/HANDOFF_PIN.json').read_bytes())
    m=json.loads(read(root,{'path':str(root/'reports/nfl_20261115_prospective'/original_pin['source_control_manifest_relative_path']),'sha256':original_pin['source_control_manifest_sha256']}))
    authoritative={q['candidate_id']:q for q in m['candidates']}
    checks=Counter();counts=Counter();merged=[]
    identity_fields=('event_id','player_id','stat','period','book','quote_id','line','event_start_at','source_sha256','source_received_at')
    for row in rows:
        cid=row['candidate_id'];q=row['original_contract']['original_record'];other=ops[cid]
        assert q==other['original_contract']['original_record']==authoritative[cid]
        for field in identity_fields:assert q[field]==authoritative[cid][field]
        checks['exact_original_contract_identity']+=1
        if row['WS2']['status']=='GENERATED_SOURCE_COUNT_SHADOW':
            f=row['WS2'];law=f['law'];pr=[law[k] for k in ('q_over','q_under','q_push')];probabilities(pr)
            a=law['parameters']['alpha'];bb=law['parameters']['beta'];line=q['line'];pp=bb/(bb+1)
            expected=[nbinom.sf(line,a,pp),nbinom.cdf(math.ceil(line)-1,a,pp),nbinom.pmf(line,a,pp) if float(line).is_integer() else 0]
            assert max(abs(x-y) for x,y in zip(pr,expected))<1e-12
            assert stamp(f['model_training_cutoff_at'])<=stamp(row['input_freeze_at'])<=stamp(f['forecast_at'])<stamp(q['event_start_at'])
            counts['WS2']+=1;checks['analytic_law_independent_recalculation']+=1
        for k in ('O4','J1','J2','J3'):
            f=other[k]
            if f['status']!='FORECAST':continue
            probabilities(list(f['probabilities'].values()))
            assert stamp(other['source_cutoff_at'])<=stamp(other['input_freeze_at'])<=stamp(f['forecast_at'])<stamp(q['event_start_at'])
            if k=='O4':
                dist=f['distribution'];values=np.array(dist['values']);mass=np.array(dist['masses'])
                assert np.all(values>=0) and np.all(values.astype(int)==values) and abs(mass.sum()-1)<1e-12
                expected={'over':float(mass[values>q['line']].sum()),'under':float(mass[values<q['line']].sum()),'push':float(mass[values==q['line']].sum())}
            else:
                records=jsonl(read(root,f['shared_draws']));cov={x['player_id']:np.array(x['draws']) for x in records}
                pid=next(c['player_id'] for c in jsonl(read(root,p['tables']['defender_coverage'])) if c['player_stat_id']==row['original_contract']['player_stat_id'])
                values=cov[pid];assert len(values)==4096 and np.all(values>=0) and np.all(values.astype(int)==values)
                expected={label:float(np.mean(test)) for label,test in [('over',values>q['line']),('under',values<q['line']),('push',values==q['line'])]}
            assert all(abs(expected[k2]-f['probabilities'][k2])<1e-12 for k2 in expected)
            counts[k]+=1;checks['temporal_support_probability_'+k]+=1
        merged.append({**row,'WS3_O4':other['O4'],'WS4_J1':other['J1'],'WS4_J2':other['J2'],'WS4_J3':other['J3'],
            'automated_integrity':'PASS','independent_acceptance':'PENDING','certification':'UNCERTIFIED',
            'certification_blocker':'BOOK_PRODUCT_SETTLEMENT_AND_OFFICIAL_ACCOUNTING_NOT_CERTIFIED'})
    oldpath=Path(b['frozen_first_forecast_file']['path']);oldhash=sha(oldpath.read_bytes());old=[r for r in jsonl(oldpath.read_bytes()) if r['original_contract']['stat']=='tackles + assists']
    oldcounts=Counter();oldbad=Counter();source_versions=Counter();oldids=set()
    for r in old:
        q=r['original_contract'];cid=q['candidate_id'];assert q==authoritative[cid];oldids.add(cid)
        for model,f in r['models'].items():
            if f['status']!='forecast':continue
            oldcounts[model]+=1;probabilities([f[k] for k in ('q_over','q_under','q_push')])
            if stamp(r['forecast_created_at'])>=stamp(q['event_start_at']):oldbad['POST_KICKOFF']+=1
            if not q['source_certified'] or not q['research_shadow_eligible']:oldbad['SOURCE_INELIGIBLE']+=1
            if stamp(r['history_lineage']['historical_cutoff'])>stamp(r['forecast_created_at']):oldbad['FUTURE_HISTORY']+=1
        source_versions[q.get('code_commit_sha')]+=1
    # Source-hash ledger is immutable; add original comparisons without rewriting them.
    oldby={r['original_contract']['candidate_id']:r for r in old}
    for r in merged:r['frozen_WS2_original']=oldby.get(r['candidate_id'],{'status':'UNAVAILABLE'})
    ledger=table(out,'audited_comparison',merged)
    # Game-order retrospective diagnostic. Source receipts were collected later:
    # no historical pregame availability or frozen original-forecast claim.
    from v2.nfl_marginal_shadow import fit_laws,MODEL_IDS
    coverage=jsonl(read(root,p['tables']['defender_coverage']));pos={r['player_id']:r['position'] for r in coverage}
    prior=defaultdict(list);scored=[];skips=Counter()
    for date in sorted({h['game_date'] for h in hist}):
        day=[h for h in hist if h['game_date']==date]
        for h in day:
            own=[x['combined_total'] for x in prior[h['player_id']]]
            peers=[[x['combined_total'] for x in xs] for pid,xs in prior.items() if pid!=h['player_id'] and pos.get(pid)==pos.get(h['player_id'])]
            try:
                laws,_,_=fit_laws(own,peers,stat='tackles + assists')
                if MODEL_IDS[3] not in laws:raise ValueError('NO_PEERS')
                probs=[laws[k].probabilities(5.5).over for k in (MODEL_IDS[1],MODEL_IDS[3])];y=int(h['combined_total']>5.5)
                scored.append({'game_id':h['game_id'],'day':date,'y':y,'probabilities':probs})
            except ValueError as e:skips[str(e)]+=1
        for h in day:prior[h['player_id']].append(h)
    performance={};rng=np.random.default_rng(20261115)
    for i,name in enumerate(('unchanged_S2_empirical','unchanged_S4_gamma_poisson')):
        if not scored:continue
        ys=np.array([r['y'] for r in scored]);ps=np.array([r['probabilities'][i] for r in scored]);eps=1e-12
        performance[name]={'brier':float(np.mean((ps-ys)**2)),'log_loss_clip_1e_12':float(np.mean(-ys*np.log(np.clip(ps,eps,1-eps))-(1-ys)*np.log(np.clip(1-ps,eps,1-eps)))),
            'predicted_over_share':float(ps.mean()),'observed_over_share':float(ys.mean()),'over_selected_share':float(np.mean(ps>.5)),
            'calibration_bins':[{'lower':i/5,'n':int(np.sum(np.minimum(4,(ps*5).astype(int))==i)),'predicted':float(ps[np.minimum(4,(ps*5).astype(int))==i].mean()) if np.any(np.minimum(4,(ps*5).astype(int))==i) else None,'observed':float(ys[np.minimum(4,(ps*5).astype(int))==i].mean()) if np.any(np.minimum(4,(ps*5).astype(int))==i) else None} for i in range(5)]}
    grouped=defaultdict(list)
    for r in scored:grouped[r['game_id']].append((r['probabilities'][1]-r['y'])**2-(r['probabilities'][0]-r['y'])**2)
    if grouped:
        vals=list(grouped.values());ci=[]
        for _ in range(1000):
            sample=rng.integers(0,len(vals),len(vals));ci.append(sum(sum(vals[k]) for k in sample)/sum(len(vals[k]) for k in sample))
        interval=np.quantile(ci,[.025,.975]).tolist()
    else:interval=None
    report={'schema':'tackle_repair_automated_audit_v252','tested_at':now(),'original_quotes':len(rows),'checks':dict(checks),'original_source_checks':dict(source_checks),'numerically_temporally_accepted_source_count_forecasts':dict(counts),
        'independent_reviewer_acceptance':0,'release_approved':False,'book_equivalence_certified':False,
        'defender_coverage_reasons':dict(Counter(reason for r in jsonl(read(root,p['tables']['defender_coverage'])) for reason in r['source_count_abstention_reasons'])),
        'defenders_with_positive_snap_history':len({h['player_id'] for h in hist if h.get('defensive_snap_feature') and h['defensive_snap_feature']['defensive_snaps']>0}),
        'original_WS2_rows':len(old),'original_WS2_model_forecasts':dict(oldcounts),'original_WS2_temporal_source_failures':dict(oldbad),
        'original_source_code_versions':dict(source_versions),'original_WS2_sha256':oldhash,'original_WS2_unchanged':sha(oldpath.read_bytes())==oldhash,
        'ledger':ledger,'historical_diagnostic':{'population':len(hist),'scored':len(scored),'abstentions':dict(skips),'games':len(grouped),
            'line':5.5,'line_origin':'FIXED_DIAGNOSTIC_NOT_SPORTSBOOK','past_outcomes_only':True,'pregame_source_availability_verified':False,
            'model_development_exposure':'These historical years have prior development exposure; not a sealed holdout.',
            'performance':performance,'game_clustered_paired_Brier_S4_minus_S2_95pct':interval}}
    unchanged(out/'AUDIT_REPORT.json',canonical(report));print(json.dumps(report));return report
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--baseline',type=Path,required=True);a.add_argument('--opportunity',type=Path,required=True);a.add_argument('--out',type=Path,required=True);x=a.parse_args();run(x.root,x.baseline,x.opportunity,x.out)
