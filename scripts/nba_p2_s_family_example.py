#!/usr/bin/env python3
"""Four-stat synthetic S-family example. No official data, no forecast scoring."""
import hashlib
import json
from v2.nba_s_family import fit, predict_conditional

SRC = '1'*64
RAW = '2'*64
DAYS = ('2022-10-01','2022-10-03','2022-10-05')


def main():
    source = {SRC:{'raw_sha256':RAW,'available_at':'2022-10-07T00:00:00Z',
                   'status':'P1_VERIFIED'}}  # TEST FIXTURE STATUS, NOT REAL P1
    answers = {}
    for stat, own, peer in (('points',(12,15,18),(8,11,12)),
                            ('rebounds',(5,6,7),(4,3,5)),
                            ('assists',(3,7,6),(2,4,4)),
                            ('threes',(2,1,4),(1,2,1))):
        history=[]
        for pid, vals in [('espn:player:synthetic-a',own),('espn:player:synthetic-b',peer)]:
            for i,(day,y) in enumerate(zip(DAYS,vals)):
                hour = '2022-10-02T00:00:00Z' if i==0 else '2022-10-04T00:00:00Z' if i==1 else '2022-10-06T00:00:00Z'
                history.append({'game_id':'espn:game:synthetic-'+str(i),
                'player_id':pid,'team_id':'espn:team:synthetic','role':'wing',
                'stat':stat,'game_start_at':day+'T00:00:00Z',
                'outcome_available_at':hour,'source_receipt_sha256':SRC,
                'source_raw_sha256':RAW,'count':y,'minutes':30.0,
                'three_attempts':y+2 if stat=='threes' else None})
        artifact=fit(history,asof_cutoff_utc='2022-10-10T00:00:00Z',
                     source_manifest=source,stat=stat,family='S1',seed=12)
        out=predict_conditional(artifact,player_id='espn:player:synthetic-a',
                                role='wing',projected_exposure=31.,statistic=stat)
        assert out.abstain_reason is None, out.abstain_reason
        probs=out.parameters['support']
        answers[stat]={'model_artifact_sha256':artifact.artifact_sha256,
                       'probability_zero':probs[0]['mass'],
                       'mean':sum(x['value']*x['mass'] for x in probs),
                       'probability_sum':sum(x['mass'] for x in probs),
                       'tail_mass_upper_bound':out.parameters['tail_mass_upper_bound']}
    # S3: made threes must use integer scenario-projected 3PA, not realized 3PA.
    print(json.dumps({'status':'SYNTHETIC_SHADOW_NOT_PRE_GAME_CERTIFIED',
        'outputs':answers},sort_keys=True,indent=2))

if __name__=='__main__':main()