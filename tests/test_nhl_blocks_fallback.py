import sys
import unittest
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from nhl_blocks_fallback import fetch_nhl_blocked_shots

class FallbackTests(unittest.TestCase):
    def now(self):
        return datetime(2026,10,29,16,tzinfo=timezone.utc)
    def test_no_credits_without_explicit_key_and_consent(self):
        def fail(*args,**kwargs):raise AssertionError('should not fetch')
        for enabled,key in ((False,'secret'),(True,'')):
            qs,d=fetch_nhl_blocked_shots('2026-10-29',[],fetch=fail,enabled=enabled,api_key=key,now=self.now())
            self.assertEqual(qs,[])
            self.assertEqual(d['event_requests'],0)
        qs,d=fetch_nhl_blocked_shots('2026-10-29',
            [{'sport':'NHL','stat':'blocked shots'}],fetch=fail,
            enabled=True,api_key='secret',now=self.now())
        self.assertEqual(d['status'],'primary_market_present')
    def test_single_event_source_id_and_secret_are_preserved_safely(self):
        event={'id':'game-1','sport_key':'icehockey_nhl','home_team':'Colorado Avalanche',
               'away_team':'New Jersey Devils','commence_time':'2026-10-30T00:00:00Z'}
        payload={**event,'bookmakers':[
          {'key':'fanduel','markets':[{'key':'player_blocked_shots',
            'outcomes':[{'name':'Over','description':'Nathan MacKinnon','point':1.5,'price':-115},
                        {'name':'Under','description':'Nathan MacKinnon','point':1.5,'price':-105}]}]}]}
        urls=[]
        def fake(url,timeout=20):
            urls.append(url)
            return [event] if '/events?' in url else payload
        qs,d=fetch_nhl_blocked_shots('2026-10-29',[],fetch=fake,enabled=True,api_key='secret',now=self.now())
        self.assertEqual(d['event_requests'],1)
        self.assertEqual(d['returned_quotes'],1)
        self.assertEqual(qs[0]['stat'],'blocked shots')
        self.assertEqual(qs[0]['event_id_namespace'],'the_odds_api')
        self.assertEqual(qs[0]['event_teams'],['COL','NJD'])
        self.assertNotIn('secret',str(qs)+str(d))
        self.assertEqual(len(urls),2)
    def test_limit_prevents_unbounded_billable_queries(self):
        e=lambda i:dict(id=str(i),home_team='Colorado Avalanche',
               away_team='New Jersey Devils',commence_time='2026-10-30T00:00:00Z')
        calls=[]
        def mock(url,timeout=20):
            calls.append(url)
            return [e(i) for i in range(12)] if '/events?' in url else {**e(url.split('/events/')[1].split('/')[0]),'bookmakers':[]}
        _,diag=fetch_nhl_blocked_shots('2026-10-29',[],fetch=mock,
             enabled=True,api_key='safe',now=self.now())
        self.assertEqual(diag['event_requests'],8)
        self.assertEqual(diag['skipped_event_budget'],4)
        self.assertEqual(len(calls),9)
if __name__=='__main__':
    unittest.main()
