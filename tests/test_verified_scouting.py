import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from datetime import datetime,timezone
import unittest
from research_packet import empty_template,validate_packet
from scouting_checklist import seed
from verified_scouting import apply

NOW=datetime(2026,10,26,21,50,tzinfo=timezone.utc)
FACT={'fact':'deployment workload','value':18.0,'source_url':'https://www.nhl.com/gamecenter/1',
      'retrieved_at':NOW.isoformat(),'quote':'played 18 minutes last game',
      'confidence':'confirmed','source_read':True}

class VerifiedScoutingTests(unittest.TestCase):
 def packet(self):
  p=empty_template('2026-10-26')
  p['index']['by_player']['Player']={'player_id':12,'sport':'NHL','team':'EDM','game':'DET@EDM'}
  p['scouting']['NHL|Player|shots on goal|under']=seed('NHL','shots on goal')
  return p
 def report(self,entry):
  return {'date':'2026-10-26','reviewer':'analyst','entries':[
     {**dict(candidate_id='NHL|Player|shots on goal|under',team='EDM',game='DET@EDM',player_id=12),**entry}]}
 def test_import_supports_validated_packet_and_does_not_change_numeric_model(self):
  p=self.packet();entry={**FACT,'kind':'evidence','field':'opportunity'}
  out=apply(p,self.report(entry),now=NOW)
  self.assertIsNotNone(out['scouting']['NHL|Player|shots on goal|under']['evidence']['opportunity'])
  self.assertIsNone(p['scouting']['NHL|Player|shots on goal|under']['evidence']['opportunity'])
 def test_refuses_inferred_quote_and_bad_identity(self):
  for bad in ({**FACT,'source_read':False},{**FACT,'quote':''}):
   with self.assertRaises(ValueError):apply(self.packet(),self.report({**bad,'kind':'evidence','field':'opportunity'}),now=NOW)
  with self.assertRaises(ValueError):apply(self.packet(),self.report({**FACT,'kind':'evidence','field':'opportunity','team':'DET'}),now=NOW)
 def test_mechanisms_are_unique_causal_events(self):
  m={'kind':'mechanism','event_id':'opposing-top-line-change','type':'role',
     'supports_side':'under','description':'Source-confirmed reduction in deployment',
     'sources':[FACT]}
  out=apply(self.packet(),self.report(m),now=NOW)
  self.assertEqual(len(out['mechanisms']['NHL|Player|shots on goal|under']),1)
  with self.assertRaises(ValueError):apply(out,self.report(m),now=NOW)

if __name__=='__main__':unittest.main()
