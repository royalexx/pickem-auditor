import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from v2.nba_architecture.p1_subset_handoff_v1 import canonical
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset,parse_completed_game,next_data

PACK=Path(__file__).resolve().parents[2]/'docs/nba_architecture/genuine_s_prospective_20261120'
RAW=PACK/'raw';SPEC=PACK/'PREFIT_POPULATION.json';POLICY=PACK/'policy/nba_rule5.raw'


def inputs():
    j=json.loads((RAW/'game_joins.json').read_bytes())[0]
    return [(RAW/('nba-box-'+j['nba_id'])/'body.raw').read_bytes(),
        (RAW/('summary-'+j['espn_id'])/'body.raw').read_bytes(),(RAW/j['index']/'body.raw').read_bytes(),j]


def html(game):return b'<script id="__NEXT_DATA__">'+canonical({'props':{'pageProps':{'game':game}}})+b'</script>'


class ProspectiveSourceTests(unittest.TestCase):
    def test_actual_frozen_population_exact_rows_and_every_stat_attempt(self):
        x=build_dataset(RAW,SPEC,POLICY)
        self.assertEqual((x['source_capture_count'],x['game_count'],x['source_observation_denominator'],x['training_attempt_denominator'],x['included_training_attempts'],x['excluded_training_attempts']),(60,20,698,2792,1824,968))
        self.assertFalse(x['fit_performed']);self.assertEqual({k:len(v) for k,v in x['histories'].items()},{s:456 for s in ('points','rebounds','assists','threes')})
        self.assertTrue(all(r['exact_seconds']>=30 for r in x['records'] if r['fit_included']))
        for name in ('Malachi Smith','Hansen Yang'):
            self.assertTrue(any(r['name']==name and not r['fit_included'] and r['reason'] in ('CROSS_SOURCE_FULL_COUNT_VECTOR_CONFLICT','UNMATCHED_OR_AMBIGUOUS_NAME') for r in x['records']))

    def test_structural_source_parser_is_not_admission_and_zero_dnp_sub30_stay_distinct(self):
        args=inputs();g=next_data(args[0])['game'];result=parse_completed_game(*args)
        self.assertEqual(result['verification_scope'],'STRUCTURAL_ONLY_NOT_SOURCE_ADMISSION')
        row=g['awayTeam']['players'][0]
        for display,state in [('00:00','ZERO_DISPLAY'),('00:29','PLAYED_SUB30'),('00:30','PLAYED_ORDINARY')]:
            v=copy.deepcopy(g);v['awayTeam']['players'][0]['statistics']['minutes']=display
            out=parse_completed_game(html(v),*args[1:]);r=next(r for r in out['rows'] if r['nba_person_id']==str(row['personId']))
            self.assertEqual(r['state'],state)
            if state!='PLAYED_ORDINARY':self.assertFalse(r['fit_included'])

    def test_identity_period_clock_count_and_duplicate_mutations_reject(self):
        args=inputs();g=next_data(args[0])['game']
        for attack in ('id','period','clock','team','count','duplicate'):
            v=copy.deepcopy(g)
            if attack=='id':v['gameId']='wrong'
            if attack=='period':v['period']=3
            if attack=='clock':v['gameClock']='PT01M00.00S'
            if attack=='team':v['awayTeam']['teamName']='wrong'
            if attack=='count':v['awayTeam']['players'][0]['statistics']['points']+=1
            if attack=='duplicate':v['awayTeam']['players'].append(copy.deepcopy(v['awayTeam']['players'][0]))
            with self.subTest(attack=attack),self.assertRaises(ValueError):parse_completed_game(html(v),*args[1:])

    def test_resealed_spec_policy_and_capture_bytes_cannot_admit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);spec=json.loads(SPEC.read_bytes());spec['approved']=True;(p/'spec.json').write_bytes(canonical(spec))
            with self.assertRaises(ValueError):build_dataset(RAW,p/'spec.json',POLICY)
            (p/'rule.raw').write_bytes(POLICY.read_bytes()+b' ')
            with self.assertRaises(ValueError):build_dataset(RAW,SPEC,p/'rule.raw')
            raw=p/'raw';shutil.copytree(RAW,raw);file=next(raw.glob('nba-box-*/body.raw'));file.write_bytes(file.read_bytes()+b' ')
            with self.assertRaises(ValueError):build_dataset(raw,SPEC,POLICY)

    def test_full_vector_conflict_and_ambiguous_name_do_not_create_fit_rows(self):
        x=build_dataset(RAW,SPEC,POLICY)
        for record in x['records']:
            if record['source_list']=='players' and record['reason'] in ('CROSS_SOURCE_FULL_COUNT_VECTOR_CONFLICT','UNMATCHED_OR_AMBIGUOUS_NAME'):
                self.assertFalse(record['fit_included'])
        self.assertEqual(len([r for r in x['records'] if r['state']=='DNP']),68)
        self.assertEqual(len([r for r in x['records'] if r['state']=='PLAYED_SUB30']),1)
