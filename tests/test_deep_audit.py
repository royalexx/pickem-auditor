"""Reproductions from the fresh source-to-report audit; all offline."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pickem_math as pm
import probability_blend as pb
import context_validation as cv
import shared_context as sc
import usage_baseline as ub
import scouting_engine as se
import odds_providers as op
import research_packet as rp
import test_shared_context as fixtures
from test_shared_context import baseline,NOW,history
import test_research_packet as packet_fixtures
from test_research_packet import minimal_packet,make_fact,NOW as PACKET_NOW,STALE_ISO

class MathBoundaryTests(unittest.TestCase):
    def test_invalid_side_cannot_silently_become_under(self):
        for side in ('OVER','typo','',None):
            with self.assertRaises(pm.PickemError):pm.project('poisson',side,3,4,20)

    def test_tiny_shape_quantile_keeps_representable_lower_tail(self):
        # Independent scipy-generated reference constants, not our CDF.
        for shape,p,expected in [(.01,.5,4.465535018910562e-31),(.03,.1,2.6702219583104516e-34),(.001,.9,9.82165964406889e-47)]:
            self.assertAlmostEqual(pm._gamma_ppf(p,shape,1)/expected,1,places=9)
        self.assertEqual(pm._gamma_ppf(.01,.001,1),0)

    def test_context_uses_engine_a_effective_dispersion(self):
        c,a,b,blend,ctx=fixtures.JointAllocationTests().setup_case('NBA','threes')
        c.update(dist='negbin',var_ratio=20)
        a=pm.project('negbin','over',10.5,20,15,var_ratio=20,observation_ids={'baseline':[str(i) for i in range(15)]})
        ratios=[]
        real=sc.scaled_probabilities
        def inspect(*args):
            ratios.append(args[4]);return real(*args)
        with tempfile.TemporaryDirectory() as d,patch.object(sc,'history_path',return_value=Path(d)/'history.json'):
            (Path(d)/'history.json').write_text(json.dumps(history('NBA','threes')))
            with patch.object(sc,'scaled_probabilities',side_effect=inspect):result=sc.apply(c,a,b,blend,ctx,NOW)
        self.assertTrue(result['applied'],result)
        self.assertEqual(ratios[0],pm.VAR_RATIO_CAP)

    def test_malformed_context_never_becomes_no_context(self):
        c,a,b,blend,ctx=fixtures.JointAllocationTests().setup_case()
        for invalid in ([],False,'',{'events':{}},{'subject_status':False}):
            self.assertFalse(sc.apply(c,a,b,blend,invalid,NOW)['eligible'])

    def test_invalid_source_cache_abstains(self):
        c,_=baseline()
        with tempfile.TemporaryDirectory() as d,ub.using_directory(d):
            ub.directory().mkdir();(ub.directory()/(c['scouting']['historical_usage']+'.json')).write_text('[]')
            self.assertTrue(se.project_scout(c,now=NOW)['abstain'])

class CertificateTests(unittest.TestCase):
    def test_malformed_certificates_cannot_unlock_blend_or_context(self):
        a=pm.project('poisson','over',3,4,20,observation_ids={'baseline':[str(i) for i in range(20)]})
        b=dict(reliable=True,abstain=False,q_win_b=.7,q_push_b=0)
        ev=dict(score_rule=pb.SCORE_RULE,train_n=300,holdout_n=100,holdout_dates=25,train_end='2025-01-01',
                holdout_start='2025-02-01',holdout_end='2025-03-01',a_log_loss=.7,blend_log_loss=.6,improvement_ci_low=.01)
        cfg=dict(scope='x',engine_version=pb.VERSION,training_unit=pb.TRAINING_UNIT,weight_a=.5,underpowered=False,validation=ev)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'config.json'
            for invalid in ([],False,{'validation':[]}, {**cfg,'validation':{**ev,'train_n':float('inf')}},
                            {**cfg,'validation':{**ev,'train_end':'0000-bad'}}, {**cfg,'validation':{**ev,'blend_log_loss':-.1}}):
                path.write_text(json.dumps(invalid))
                self.assertFalse(pb.combine(a,b,path,scope='x')['validated'])
                self.assertFalse(cv.eligible(invalid,'x','A_ONLY',date(2026,1,1)))
            path.write_text(json.dumps(cfg));self.assertTrue(pb.combine(a,b,path,scope='x')['validated'])

class QuoteBoundaryTests(unittest.TestCase):
    def quote(self,**kw):
        return {**dict(player='Player',player_norm='player',team='BOS',opponent='NYK',sport='NBA',stat='points',
            line=20.5,book='Pinnacle',over_odds=-110,under_odds=-110,retrieved_at='2026-10-26T12:00:00Z'),**kw}

    def test_unknown_or_future_quote_cannot_borrow_freshness(self):
        for stamp in ('bad',None,'2099-01-01T00:00:00Z'):
            q=[self.quote(retrieved_at=stamp),self.quote(book='FanDuel')]
            group=op.consensus_input(q,now='2026-10-26T12:05:00Z')[0]
            self.assertIsNone(group['retrieved_minutes_ago'])
            self.assertFalse(pm.consensus(pm._consensus_tuples(group['books']),group['retrieved_minutes_ago'])['market_valid'])

    def test_quote_join_rejects_wrong_fixture_but_accepts_different_provider_ids(self):
        row=dict(player='Player',team='BOS',opponent='NYK',sport='NBA',stat='points',game_date='2026-10-26',event_id='espn1',event_id_namespace='espn')
        good=self.quote(event_id='odds1',event_id_namespace='the_odds_api',game_date='2026-10-26')
        self.assertEqual(op.quotes_for_row([good],row),[good])
        for change in ({'opponent':'LAL'},{'game_date':'2026-10-27'},{'event_id_namespace':'espn','event_id':'espn2'}):
            self.assertEqual(op.quotes_for_row([{**good,**change}],row),[])

    def test_consensus_never_combines_different_events(self):
        quotes=[self.quote(event_id='a'),self.quote(event_id='b',book='FanDuel')]
        self.assertEqual(len(op.consensus_input(quotes,now='2026-10-26T12:05:00Z')),2)

    def test_team_resolution_obeys_provider_fixture_teams(self):
        q=self.quote(team='',opponent='',event_teams=['LAL','NYK'])
        resolved,_=op.resolve_quote_teams([q],[dict(player='Player',team='BOS',opponent='NYK',stat='points',sport='NBA')])
        self.assertEqual(resolved[0]['team'],'')

class PacketBoundaryTests(unittest.TestCase):
    def test_empty_and_nonobject_prep_are_blocked(self):
        import io
        from contextlib import redirect_stdout,redirect_stderr
        with tempfile.TemporaryDirectory() as d:
            packet=Path(d)/'packet.json';prep=Path(d)/'prep.jsonl'
            packet.write_text(json.dumps(rp.empty_template('2026-10-26')))
            for content in ('','[]\n','null\n','42\n','not JSON'):
                prep.write_text(content)
                with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()) as err:
                    code=rp.main(['audit','--packet',str(packet),'--prep',str(prep)])
                self.assertEqual(code,1);self.assertTrue(err.getvalue())

    def test_fixture_metadata_passes_pipeline_without_affecting_math(self):
        c,data=baseline()
        c.update(id='NBA|P|points|over',soft_flags=0,mechanisms=2,hard_veto=False,data_veto=False,
                 research_checklist=True,q_market=.6,retrieved_minutes_ago=1)
        with patch.object(ub,'load',return_value=data):
            before=pm.evaluate_candidate(c,now=NOW)
            c.update(opponent='X',event_id_namespace='espn',event_start='2026-10-27T20:00:00Z')
            after=pm.evaluate_candidate(c,now=NOW)
        self.assertEqual(before['project'],after['project'])
        self.assertEqual(before['engine_b'],after['engine_b'])

    def test_packet_refresh_updates_collector_reference_without_erasing_research(self):
        import context_feeds as cf
        key='NBA|P|points|over'
        old={'date':'2026-10-26','scouting':{key:{'evidence':{'opportunity':'keep'},'scenarios':[]}}}
        fresh={'date':'2026-10-26','scouting':{key:{'historical_usage':'new-reference','scenarios':[]}}}
        result=cf.merge_packet_no_clobber(old,fresh)
        self.assertEqual(result['scouting'][key]['historical_usage'],'new-reference')
        self.assertEqual(result['scouting'][key]['evidence'],{'opportunity':'keep'})
        fresh['scouting'][key].pop('historical_usage')
        self.assertNotIn('historical_usage',cf.merge_packet_no_clobber(result,fresh)['scouting'][key])

    def test_source_baseline_does_not_request_researcher_scenarios(self):
        import context_feeds as cf
        key='NBA|P|points|over'
        packet={'date':'2026-10-26','scouting':{key:{'historical_usage':'reference'}}}
        with patch.object(se,'project_scout',return_value={'abstain':False,'reliable':True}):
            gaps=cf.gap_paths_for_shortlist(packet,[key],now=NOW)
        self.assertFalse(any(g['path'].endswith('.scenarios') for g in gaps))

    def test_remerging_same_research_does_not_stack_flags(self):
        packet=minimal_packet();packet['availability']['Test Player']['status']=make_fact('questionable')
        valid,issues=rp.validate_packet(packet,now=PACKET_NOW);self.assertEqual(issues,[])
        row=packet_fixtures.MergePipelineTests()._prep_row();row['soft_flags']=2
        first=rp.merge_into_pipeline(valid,[row])[0]
        second=rp.merge_into_pipeline(valid,[first])[0]
        self.assertEqual(first['soft_flags'],3);self.assertEqual(second['soft_flags'],3)

    def test_stable_identity_teammate_is_routed_once(self):
        packet=minimal_packet()
        player=dict(team='BOS',game='BOS@NSH',sport='NHL',player_id='Q')
        packet['index']['by_player_id']={'NHL|Q':player}
        packet['index']['by_player']['Teammate']=player
        absence=make_fact('out');absence.update(event_id='injury:Q',effective_at='2026-10-22T12:00:00Z')
        packet['availability']['NHL|Q']={'status':absence,'primary_source':make_fact('league')}
        valid,issues=rp.validate_packet(packet,now=PACKET_NOW);self.assertEqual(issues,[])
        row=rp.merge_into_pipeline(valid,[packet_fixtures.MergePipelineTests()._prep_row()])[0]
        events=row['event_context']['events']
        self.assertEqual(len(events),1);self.assertEqual(events[0]['player_id'],'Q')

    def test_implicit_away_team_does_not_inherit_home_rest(self):
        packet=minimal_packet();env=packet['environment']['BOS@NSH'];env['back_to_back']=make_fact(True)
        env['third_in_four']=make_fact(True)
        valid,issues=rp.validate_packet(packet,now=PACKET_NOW);self.assertEqual(issues,[])
        row=rp.merge_into_pipeline(valid,[packet_fixtures.MergePipelineTests()._prep_row()])[0]
        self.assertEqual(row['spread'],1.5)
        self.assertNotIn('back_to_back',row);self.assertNotIn('third_in_four',row)

    def test_stale_player_confirmation_is_rejected(self):
        packet=minimal_packet();packet['player_context']={'Test Player':{'goalie_confirmed':make_fact(True,retrieved_at=STALE_ISO)}}
        valid,issues=rp.validate_packet(packet,now=PACKET_NOW)
        self.assertIsNone(valid);self.assertTrue(any('goalie_confirmed' in i.path for i in issues))
