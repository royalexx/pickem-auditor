"""Offline current-season read, tackle and causal-identity contracts."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nfl_season_store as ns
import nfl_opportunity as no
import effect_ledger as el
import pickem_math as pm

NOW=datetime(2026,10,26,12,tzinfo=timezone.utc)
STAMP=NOW.isoformat()
def fact(value,event=None):
    f=dict(fact='verified scenario observation',value=value,source_url='https://www.nfl.com/news/test',
           retrieved_at=STAMP,confidence='confirmed')
    if event:f['event_id']=event
    return f


def dataset():
    games=[];plays=[];chart=[]
    # QB Q faces D and X; D makes the checkdown recipient the main target.
    for index,defense in enumerate(('D','X')):
        gid=f'2026_0{index+1}_A_{defense}'
        games.append(dict(game_id=gid,season=2026,game_type='REG',gameday=f'2026-10-{10+index:02}',result=7))
        codes=['CHK']*6+['0']*2 if defense=='D' else ['CHK']*2+['0']*6
        for i,code in enumerate(codes):
            plays.append(dict(game_id=gid,play_id=i,season=2026,season_type='REG',posteam='A',defteam=defense,
                pass_attempt=1,qb_dropback=1,passer_player_id='Q',receiver_player_id='RB' if code=='CHK' else 'WR',
                air_yards=2,solo_tackle_1_player_id='M' if i<2 else None,epa=-.2))
            chart.append(dict(nflverse_game_id=gid,nflverse_play_id=i,season=2026,read_thrown=code))
    # Opponent R runs inside at a higher rate than defender M's own history.
    gid='2026_03_R_D';games.append(dict(game_id=gid,season=2026,game_type='REG',gameday='2026-10-12',result=3))
    for i in range(8):
        plays.append(dict(game_id=gid,play_id=i,season=2026,season_type='REG',posteam='R',defteam='D',
                          rush_attempt=1,run_location='middle',solo_tackle_1_player_id='M'))
    return games,plays,chart


def profiles():
    games,plays,chart=dataset()
    with tempfile.TemporaryDirectory() as d:
        store=ns.SeasonStore(Path(d)/'season.sqlite3')
        store.refresh(2026,plays,chart,games,as_of=STAMP)
        return store.profiles(2026,as_of=STAMP)


class SeasonStoreTests(unittest.TestCase):
    def test_read_codes_disjoint_and_designs_separate(self):
        self.assertEqual(ns.bucket('0'),'first_read')
        self.assertEqual(ns.bucket('DES'),'designed')
        self.assertEqual(ns.bucket('SD'),'scramble_drill')
        self.assertEqual(ns.bucket(None),'unknown')
        self.assertEqual(ns.bucket('bogus'),'unknown')

    def test_refresh_is_idempotent_and_deduplicates(self):
        games,plays,chart=dataset()
        with tempfile.TemporaryDirectory() as d:
            store=ns.SeasonStore(Path(d)/'season.sqlite3')
            store.refresh(2026,plays+plays,chart+chart,games,as_of=STAMP)
            before=store.profiles(2026,as_of=STAMP)
            store.refresh(2026,plays,chart,games,as_of=STAMP)
            after=store.profiles(2026,as_of=STAMP)
            self.assertEqual(before['passers'],after['passers'])
            self.assertEqual(after['passers']['A|Q']['throws'],16)

    def test_future_same_day_and_prior_season_excluded(self):
        games,plays,chart=dataset()
        games.append(dict(game_id='future',season=2026,game_type='REG',gameday='2026-10-26',result=7))
        self.assertNotIn('future',ns.completed_catalog(games,2026,'2026-10-27T01:00:00+00:00'))
        plays.append({**plays[0],'game_id':'future'})
        plays.append({**plays[0],'play_id':99,'season':2025})
        with tempfile.TemporaryDirectory() as d:
            store=ns.SeasonStore(Path(d)/'season.sqlite3')
            store.refresh(2026,plays,chart,games,as_of=STAMP)
            p=store.profiles(2026,as_of=STAMP)
            self.assertEqual(p['passers']['A|Q']['throws'],16)
            with self.assertRaises(ValueError):store.profiles(2026,as_of='2026-10-01T00:00:00+00:00')

    def test_unknown_reads_are_not_coverage_wins(self):
        games,plays,chart=dataset();chart=[]
        with tempfile.TemporaryDirectory() as d:
            store=ns.SeasonStore(Path(d)/'season.sqlite3')
            store.refresh(2026,plays,None,games,as_of=STAMP)
            p=store.profiles(2026,as_of=STAMP)
            self.assertEqual(p['defenses']['D']['charting_coverage'],0)
            self.assertIsNone(p['defenses']['D']['checkdown_rate_on_known_reads'])

    def test_target_volume_is_conserved_and_conditional(self):
        p=profiles();packet={'confirmed_passer':fact('Q')}
        ctx=ns.candidate_context(p,'A','D','RB')
        rb=no.project(dict(mode='receiving',passer_id='Q',expected_pass_attempts=30),ctx,packet,now=NOW)
        wr=no.project(dict(mode='receiving',passer_id='Q',expected_pass_attempts=30),
                      ns.candidate_context(p,'A','D','WR'),packet,now=NOW)
        self.assertGreater(rb['opportunity_delta'],0)
        self.assertLess(wr['opportunity_delta'],0)
        self.assertAlmostEqual(rb['expected_targets']+wr['expected_targets'],30)
        self.assertTrue(rb['baseline_excludes_upcoming_defense'])
        self.assertAlmostEqual(rb['offense_only_targets'],7.5)

    def test_interior_run_funnel_and_credit_deduplication(self):
        p=profiles();ctx=ns.candidate_context(p,'D','R','M')
        result=no.project(dict(mode='tackles',expected_defensive_plays=60),ctx,{},now=NOW)
        self.assertAlmostEqual(result['expected_tackles_assists'],60)
        self.assertGreater(result['opportunity_delta'],0)
        # No expectation > 1 credited tackle per team play; combined credit is a count.
        games,plays,chart=dataset();plays[0]['assist_tackle_1_player_id']='M'
        with tempfile.TemporaryDirectory() as d:
            store=ns.SeasonStore(Path(d)/'s.db');store.refresh(2026,plays,chart,games,as_of=STAMP)
            dp=store.profiles(2026,as_of=STAMP)['defenders']['D|M']
            self.assertEqual(sum(dp['credits'].values()),10)

    def test_injury_and_weather_require_evidence_and_cannot_stack(self):
        ctx=ns.candidate_context(profiles(),'D','R','M')
        spec=dict(mode='tackles',expected_defensive_plays=60,role_factor=.9)
        with self.assertRaises(ValueError):no.project(spec,ctx,{},now=NOW)
        spec['role_evidence']=fact(.9,'injury:M:2026-10-26')
        spec['play_mix']={k:(1. if k=='interior_run' else 0.) for k in ns.CATEGORIES}
        spec['mix_evidence']=fact(spec['play_mix'],'injury:M:2026-10-26')
        projected=no.project(spec,ctx,{},now=NOW)
        with self.assertRaisesRegex(ValueError,'duplicate causal effect'):
            el.audit_scenario({}, {}, projected['effects'])


class DoubleCountingTests(unittest.TestCase):
    def test_same_event_multiple_citations_cannot_apply_twice(self):
        obs=fact('new starting role','injury:R:2026-10-26')
        row={'applied_effects':[dict(event_id=obs['event_id'],source_driver='injuries',inputs=['opportunities']),
                                dict(event_id=obs['event_id'],source_driver='minutes_usage',inputs=['conversion'])]}
        with self.assertRaises(ValueError):el.audit_scenario(row,{'injuries':obs,'minutes_usage':obs})

    def test_one_joint_effect_and_alternative_scenarios_are_allowed(self):
        obs=fact('role','injury:R:2026-10-26')
        row={'applied_effects':[dict(event_id=obs['event_id'],source_driver='injuries',inputs=['opportunities','conversion'])]}
        for _ in range(2):self.assertEqual(len(el.audit_scenario(row,{'injuries':obs})),1)
        row['embedded_event_ids']=[obs['event_id']]
        with self.assertRaisesRegex(ValueError,'embedded'):el.audit_scenario(row,{'injuries':obs})

    def test_duplicate_game_ids_rejected_even_when_counts_look_disjoint(self):
        args=dict(dist='poisson',side='over',line=2.5,baseline_mean=3,baseline_n=5,
                  recent_mean=4,recent_n=5,season_n=10)
        with self.assertRaisesRegex(pm.PickemError,'duplicate historical'):
            pm.project(**args,observation_ids={'baseline':['a','b','c','d','e'],'recent':['a','f','g','h','i']})
        a=pm.project(**args,observation_ids={'baseline':['a','b','c','d','e'],'recent':['f','g','h','i','j']})
        self.assertTrue(a['observation_ids_verified'])
        b=pm.project(**args,opponent_factor=1.2,pace_factor=1.2,workload_baseline=10,workload_expected=20)
        self.assertEqual(a['q_win_robust'],b['q_win_robust'])

class EndToEndSeasonTests(unittest.TestCase):
    def test_b_uses_total_opportunities_once_and_rejects_reapplication(self):
        import scouting_engine as se
        from scouting_checklist import required_checks
        ctx=ns.candidate_context(profiles(),'A','D','RB')
        packet=dict(season_context=ctx,confirmed_passer=fact('Q'),
            evidence={k:fact('sourced observation') for k in se.DIMENSIONS},
            supporting_stats={k:fact('sourced observation') for k in required_checks('NFL','receptions')},
            scenarios=[dict(weight=.5,conversion=.5,dist='poisson',scope='full_game',
                            rationale='checkdown funnel',drivers=['passer_progression'],
                            season_projection=dict(mode='receiving',passer_id='Q',expected_pass_attempts=n)) for n in (20,30)])
        candidate=dict(sport='NFL',stat='receptions',side='over',line=3.5,player_id='RB',team='A',scouting=packet)
        out=se.project_scout(candidate,now=NOW)
        self.assertFalse(out['abstain'])
        self.assertFalse(out['reliable'])
        self.assertIn('thin_independent_passer_receiver_history',out['quality']['reasons'])
        self.assertAlmostEqual(out['mean_b'],25*.75*.5)
        self.assertEqual(len(out['terms']['scenarios'][0]['effect_ledger']),1)
        packet['scenarios'][0]['opportunities']=100
        self.assertEqual(se.project_scout(candidate,now=NOW)['abstain_reason'],'manual_and_season_opportunities_conflict')
        del packet['scenarios'][0]['opportunities']
        packet['scenarios'][0]['embedded_event_ids']=['nfl:2026:D:read_tendency']
        blocked=se.project_scout(candidate,now=NOW)
        self.assertTrue(blocked['abstain'])
        self.assertIn('embedded',blocked['abstain_detail'])

    def test_packet_collector_routes_season_context(self):
        import context_feeds as cf
        row=dict(sport='NFL',player='Receiver',player_id='RB',team='A',opponent='D',stat='receptions',
                 season_context=ns.candidate_context(profiles(),'A','D','RB'))
        packet=cf.build_research_packet('2026-10-26',[row],[],{},{},{})
        self.assertEqual(packet['scouting']['NFL|Receiver|receptions|over']['season_context']['player_id'],'RB')

    def test_a_preparation_deduplicates_actual_history(self):
        import fetch_slate as fs
        games=[dict(value=3,workload=10,when=f'2026-10-{i:02}',tie=f'g{i}') for i in range(1,13)]
        summary=fs.summarize_log(games+games,'receptions')
        self.assertEqual(summary['season_n'],12)
        ids=summary['observation_ids']
        self.assertFalse(set(ids['baseline'])&set(ids['recent']))
        with self.assertRaises(ValueError):fs.summarize_log(games,'receptions',games)

    def test_correlated_read_effect_aliases_are_one_adjustment(self):
        effects=[dict(event_id='NFL:2026:D:forced_checkdown',inputs=['opportunities']),
                 dict(event_id='NFL:2026:D:first_read_suppression',inputs=['conversion'])]
        with self.assertRaisesRegex(ValueError,'duplicate causal effect'):el.audit_scenario({}, {}, effects)

    def test_source_revision_conflict_is_transactionally_rejected(self):
        games,plays,chart=dataset()
        with tempfile.TemporaryDirectory() as d:
            store=ns.SeasonStore(Path(d)/'s.db');store.refresh(2026,plays,chart,games,as_of=STAMP)
            bad=copy.deepcopy(chart);bad.append({**chart[0],'read_thrown':'DES'})
            with self.assertRaises(ValueError):store.refresh(2026,plays,bad,games,as_of=STAMP)
            self.assertEqual(store.profiles(2026,as_of=STAMP)['passers']['A|Q']['throws'],16)

    def test_sacks_not_counted_again_as_throws_or_targets(self):
        games,plays,chart=dataset()
        plays.append({**plays[0],'play_id':999,'pass_attempt':1,'sack':1,'receiver_player_id':None})
        with tempfile.TemporaryDirectory() as d:
            store=ns.SeasonStore(Path(d)/'s.db');store.refresh(2026,plays,chart,games,as_of=STAMP)
            p=store.profiles(2026,as_of=STAMP)
            self.assertEqual(p['passers']['A|Q']['throws'],16)
            self.assertEqual(p['defenses']['D']['dropbacks'],9)
