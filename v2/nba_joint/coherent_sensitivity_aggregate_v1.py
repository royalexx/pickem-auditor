"""Independent global-index source/identity/mathematics audit for S4/J MC shards.

No source collection, fitting, outcome scoring, optimizer or release.
Only aggregate complete, immutable same-head create-only scenario shards.
"""
from __future__ import annotations

import gzip
import math
from pathlib import Path

from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_joint.coherent_sensitivity_pimh_v1 import (
    SEED,VARIANTS,STATS,PREFIX_SIZES,_analyze)

VERSION='NBA-S4-J-global-index-MC-shard-aggregate/1'


def aggregate_complete_shards(parent,model,cohort,*,expected_n=20000,
                             rare_sampler='sequential',write=True):
    root=Path(parent)
    require(root.is_dir() and type(expected_n) is int and expected_n>0
            and expected_n<=20000 and rare_sampler in ('sequential','pimh'),
            'S4_MC_AGGREGATE_ARGS')
    require(model['target']==cohort['game_id']=='401910026','S4_MC_MODEL_GAME')
    modelsha=digest(canonical(model))
    cohortsha=digest(canonical(cohort))
    named={p['player_id']:p['team_id'] for p in model['named_players']}
    require(len(named)==14,'S4_MC_SOURCE_NAMED_POPULATION')
    group={name:{pid:{stat:[None]*expected_n for stat in STATS}
                  for pid in named}
           for name,_ in VARIANTS}
    index_count=[0]*expected_n
    seen=set()
    shards=[];failures=[];statuses=[]
    dirs=sorted(x for x in root.iterdir() if x.is_dir() and
                (x/'RECEIPT.json').exists())
    require(bool(dirs),'S4_MC_NO_COMPLETED_SHARDS')
    experiment_code_shas=set()
    i_start=0
    totals=dict(accepted=0,path_proposals=0,ot_rejections=0,
                conditional_approximate_scenarios=0,
                finite_pimh_scenarios=0,zero_minute_records=0,
                score_assignment_rows=0,total_wall_seconds=0.)
    for sub in dirs:
        raw=(sub/'RECEIPT.json').read_bytes()
        rec=strict_json(raw)
        require(digest(raw)==digest(canonical(rec)+b'\n'),
                'S4_MC_NONCANONICAL_SHARD_RECEIPT')
        require(rec['schema']=='nba-s4-J-CRN-zero-sensitivity-conditional-PIMH/1'
                and rec['completed_variants'] and rec['scientific_status']!='FAILED_INCOMPLETE'
                and rec['model_semantic_sha256']==modelsha
                and rec['cohort_semantic_sha256']==cohortsha
                and rec['seed']==SEED
                and rec['rare_sampler']==rare_sampler
                and [x['name'] for x in rec['variants']]==[x[0] for x in VARIANTS]
                and rec['outcomes_scored']==0
                and rec['production_release'] is False
                and rec['historical_validation'] is False,
                'S4_MC_SHARD_PROVENANCE')
        start=rec['start_index'];end=rec['end_index_exclusive']
        require(type(start) is int and type(end) is int
                and start==i_start and 0<end-start==rec['requested_per_variant']
                and end<=expected_n,'S4_MC_SHARD_COVERAGE_OVERLAP_OR_GAP')
        i_start=end
        experiment_code_shas.add(rec['experiment_code_raw_sha256'])
        for name,_ in VARIANTS:
            require(rec['by_variant'][name]['completed']==end-start and
                    rec['by_variant'][name]['failed']==0 and
                    not rec['by_variant'][name]['errors'],
                    'S4_MC_SHARD_VARIANT_FAILURE')
        chunk_rows=0
        for chunk in rec['chunks']:
            packed=(sub/chunk['path']).read_bytes()
            require(digest(packed)==chunk['gzip_raw_sha256']
                    and len(packed)==chunk['gzip_bytes'],
                    'S4_MC_COMPRESSED_CHUNK_TAMPER')
            rawlines=gzip.decompress(packed)
            require(digest(rawlines)==chunk['raw_sha256']
                    and len(rawlines)==chunk['raw_bytes']
                    and rawlines.endswith(b'\n'),
                    'S4_MC_RAW_CHUNK_TAMPER')
            lines=rawlines.splitlines()
            require(len(lines)==chunk['rows'],'S4_MC_CHUNK_ROW_MISMATCH')
            for line in lines:
                row=strict_json(line)
                require(digest(canonical(row))==digest(line),
                        'S4_MC_NONCANONICAL_ROW')
                variant=row['variant'];i=row['index']
                require(variant in group and type(i) is int
                        and start<=i<end and row['seed']==SEED
                        and row['status']=='ACCEPTED_PATH' and
                        row['overtime_count']>=0,
                        'S4_MC_INVALID_ROW')
                key=(variant,i)
                require(key not in seen,'S4_MC_DUPLICATE_SCENARIO')
                seen.add(key)
                counts=row['counts']
                require(set(counts)==set(named)
                        and all(set(c)==set(STATS) for c in counts.values()),
                        'S4_MC_PLAYER_IDENTITY_OR_STAT_SET')
                for pid,stats in counts.items():
                    p,r,a=stats['points'],stats['rebounds'],stats['assists']
                    require(all(type(v) is int and v>=0 for v in stats.values())
                            and stats['pr']==p+r
                            and stats['pa']==p+a
                            and stats['ra']==r+a
                            and stats['pra']==p+r+a
                            and p>=3*stats['threes'],
                            'S4_MC_SAME_PATH_COMBO_OR_THREES')
                    for stat in STATS:group[variant][pid][stat][i]=stats[stat]
                    totals['score_assignment_rows']+=1
                totals['accepted']+=1
                totals['conditional_approximate_scenarios']+=bool(
                    row.get('numerical_conditional_scope')=='BOUNDED_APPROXIMATION_Q')
                totals['finite_pimh_scenarios']+=bool(
                    row.get('numerical_conditional_scope')=='FINITE_MCMC_RESEARCH')
                if variant==VARIANTS[0][0]:index_count[i]+=1
                chunk_rows+=1
        require(chunk_rows==rec['chunk_row_denominator']
                and chunk_rows==(end-start)*len(VARIANTS),
                'S4_MC_SHARD_DENOMINATOR')
        totals['path_proposals']+=sum(
            x['proposals'] for x in rec['by_variant'].values())
        totals['ot_rejections']+=sum(
            x['ot_rejections'] for x in rec['by_variant'].values())
        totals['total_wall_seconds']+=rec['wall_seconds']
        shards.append(dict(shard_dir=sub.name,start=start,end_exclusive=end,
                           scenario_rows=chunk_rows,
                           receipt_raw_sha256=digest(raw),
                           compressed_chunk_count=len(rec['chunks'])))
    require(i_start==expected_n and len(experiment_code_shas)==1
            and len(seen)==expected_n*len(VARIANTS)
            and all(x==1 for x in index_count),
            'S4_MC_MISSING_GLOBAL_SCENARIO_OR_MIXED_CODE')
    require(all(all(all(type(x) is int for x in values)
                    for values in bypid.values())
                for byvariant in group.values() for bypid in byvariant.values()),
            'S4_MC_INCOMPLETE_MATRIX')
    ots={(p['minutes']['ot_probability'],p['minutes']['ot_continuation'])
         for p in model['named_players']}
    require(len(ots)==1,'S4_MC_MIXED_OT_PRIORS')
    prob,cont=next(iter(ots));delta=prob*cont
    sections={}
    for prefix in [x for x in PREFIX_SIZES if x<=expected_n]:
        score=_analyze(group,prefix,VARIANTS)
        score['rare_OT_absolute_CDF_bias_envelope']=delta
        score['simultaneous_CDF_bound_DKW_plus_rare_OT_bias']=min(
            1.,delta+score['dkw_family_epsilon_ideal_iid'])
        score['iid_MC_reference_assumption_not_independently_proven']=True
        sections[str(prefix)]=score
    if str(expected_n) not in sections:
        score=_analyze(group,expected_n,VARIANTS)
        score['rare_OT_absolute_CDF_bias_envelope']=delta
        score['simultaneous_CDF_bound_DKW_plus_rare_OT_bias']=min(
            1.,delta+score['dkw_family_epsilon_ideal_iid'])
        sections[str(expected_n)]=score
    maximum={prefix:{variant:max(
            d['sup_empirical_cdf_difference'] for d in comp.values())
             for variant,comp in score['comparisons'].items()}
             for prefix,score in sections.items()}
    final=dict(schema=VERSION,status='RESEARCH_COMPLETE_SHARD_ACCOUNTING_ONLY',
        original_conditional_law_at_stationarity_but_not_automatically_certified=True,
        source_model_sha256=modelsha,cohort_sha256=cohortsha,
        sensitivity_code_sha256=next(iter(experiment_code_shas)),
        seed=SEED,n_per_variant=expected_n,
        variants=[x[0] for x in VARIANTS],rare_sampler=rare_sampler,
        rare_OT_prior_probability_bound=delta,
        nominal_95pct_familywise_iid_DKW_plus_rareOT_tv={
            k:v['simultaneous_CDF_bound_DKW_plus_rare_OT_bias']
            for k,v in sections.items()},
        maximum_empirical_CDF_delta_vs_original_beta=maximum,
        outcomes_scored=0,holdout_used=False,source_identity_count=len(named),
        total_expected_actor_stat_rows=expected_n*len(VARIANTS)*len(named),
        full_distribution_receipts=sections,shards=shards,totals=totals,
        G1_or_G2_accepted=False,independent_P6_accepted=False,
        production_release=False)
    if write:
        output=root/'AGGREGATE_RECEIPT.json'
        with output.open('xb') as fh:fh.write(canonical(final)+b'\n')
    return final
