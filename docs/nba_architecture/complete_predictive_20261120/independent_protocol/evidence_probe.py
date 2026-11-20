"""Read-only new PBP capability inspection; no classification/model admission."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[4];P=ROOT/'docs/nba_architecture/complete_predictive_20261120'
OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
utc=lambda s:datetime.fromisoformat(s.replace('Z','+00:00'))
def page(raw):
    scripts=re.findall(rb'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',raw,re.S)
    assert len(scripts)==1
    return json.loads(scripts[0])['props']['pageProps']
population=json.loads((P/'PBP_POPULATION.json').read_bytes());card=json.loads((P/'FULL_PLAYED_MODEL_CARD.json').read_bytes())
assert len(population['sources'])==20
oldspec=json.loads((OLD/'PREFIT_POPULATION.json').read_bytes());original=json.loads((OLD/'corrected_archive/forecast.json').read_bytes())
assert set(population['sources'])=={'pbp-'+j['nba_id'] for j in oldspec['game_joins']}
reports=[];counts=Counter();unknown=[];counterexamples=[]
for label,expected in population['sources'].items():
    body=(P/'raw'/label/'body.raw').read_bytes();rraw=(P/'raw'/label/'receipt.json').read_bytes();receipt=json.loads(rraw)
    assert sha(body)==expected['body_sha256']==receipt['raw_sha256'];assert sha(rraw)==expected['receipt_sha256']
    assert receipt['status']==expected['status']==200 and receipt['url']==expected['url'] and len(body)==receipt['bytes']
    assert utc(receipt['retrieval_started_at'])<=utc(receipt['retrieval_completed_at'])<=utc(receipt['ingested_at'])<=utc(population['frozen_at'])
    assert utc(receipt['retrieval_completed_at'])>utc(original['cohort']['freeze_at'])
    value=page(body);game=value['game'];pbp=value['playByPlay'];actions=pbp['actions'];gid=label.removeprefix('pbp-')
    assert game['gameId']==pbp['gameId']==gid and game['gameStatus']==3
    assert game['period']>=4 and game['gameClock']=='PT00M00.00S'
    number_counts=Counter(a['actionNumber'] for a in actions)
    assert len({a['actionId'] for a in actions})==len(actions)
    assert {a['period'] for a in actions}==set(range(1,game['period']+1))
    assert actions[-1]['period']==game['period'] and actions[-1]['clock']=='PT00M00.00S'
    assert int(actions[-1]['scoreHome'])==game['homeTeam']['score'] and int(actions[-1]['scoreAway'])==game['awayTeam']['score']
    oldgame=page((OLD/'raw'/('nba-box-'+gid)/'body.raw').read_bytes())['game']
    for side in ('homeTeam','awayTeam'):
        assert game[side]['teamId']==oldgame[side]['teamId']
        oldpeople={r['personId']:r for r in oldgame[side]['players']}
        for person in game[side]['players']:
            prior=oldpeople[person['personId']]
            assert person['statistics']==prior['statistics']
            display=prior['statistics']['minutes'];comment=prior.get('comment','')
            if display=='' and not comment.startswith('DNP'):
                unknown.append(dict(game_id=gid,person_id=person['personId'],name=person['firstName']+' '+person['familyName'],
                    original_comment=comment,original_display=display,
                    PBP_primary_actor_occurrences=sum(a.get('personId')==person['personId'] for a in actions),
                    disposition='ORIGINAL_UNKNOWN_RETAINED_NEW_CLASSIFICATION_REQUIRES_SEPARATE_REVIEW'))
    types=Counter(a.get('actionType','') for a in actions);counts.update(types)
    reports.append(dict(game_id=gid,actions=len(actions),periods=game['period'],action_types=dict(types),
        shared_primary_secondary_action_numbers={str(n):v for n,v in number_counts.items() if v>1},
        first_action=actions[0],last_action=actions[-1],original_box_statistics_unchanged=True))
    if gid=='0022600165':
        episode=[a for a in actions if 'Mashack' in a.get('description','')]
        assert any(a['clock']=='PT00M11.00S' and a['period']==2 and a['description']=='SUB: Mashack FOR Jerome' for a in episode)
        assert any(a['clock']=='PT00M02.00S' and a['period']==2 and a['personId']==1642942 and 'STEAL' in a['description'] for a in episode)
        counterexamples=episode
result=dict(profile_raw_sha256=sha((P/'PBP_POPULATION.json').read_bytes()),model_card_raw_sha256=sha((P/'FULL_PLAYED_MODEL_CARD.json').read_bytes()),
    HTTP200_sources=20,total_actions=sum(r['actions'] for r in reports),source_frozen_at=population['frozen_at'],
    aggregate_action_types=dict(counts),games=reports,original_unknown_rows=unknown,
    genuine_sub30_episode=counterexamples,
    parser_warning='SUB: Mashack FOR Jerome carries outgoing Jerome personId1629660, not incoming Mashack. Steal row has Mashack personId1642942; incoming identity needs a reviewed game/team/name join.',
    no_true_zero_absence_estimate=True,source_admission_granted=False,model_admission_granted=False,fit_performed=False,holdout_scoring=False)
print(json.dumps(result,indent=2,sort_keys=True))
