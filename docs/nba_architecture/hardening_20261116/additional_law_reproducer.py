"""Known unresolved G0 challenges. Expected to FAIL: never an acceptance suite."""
import sys,copy,unittest
from pathlib import Path
sys.path.insert(0,str(Path.cwd()));sys.path.insert(0,str(Path('tests/nba_architecture').resolve()))
from golden_v2 import golden_cases
from v2.nba_architecture.v2_contracts import seal,ContractError
from v2.nba_architecture.families_v2 import validate_opportunity
class Unresolved(unittest.TestCase):
    def test_unregistered_negative_support_minutes_law(self):
        c=golden_cases()['joint_same_draw']; o=copy.deepcopy(c['opportunity'])
        o['players'][0]['minutes_law']['family']='unregistered_negative_support'
        o['players'][0]['minutes_law']['parameters']={'support':[-100,-1]}
        o.pop('content_hash');o=seal(o)
        with self.assertRaises(ContractError):validate_opportunity(o,c['pregame'],c['game_state'])
if __name__=='__main__':unittest.main(verbosity=2)
