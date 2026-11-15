"""Micro-TOI sensitivity: do not change frozen replay, raw rate numerator, or release gates."""
import datetime as dt, hashlib, importlib.util, math, pathlib, tempfile, unittest
from scripts import v25_phase5_microtoi_sensitivity as S
from scripts import v25_phase5_nhl_sog_historical_replay as F

BASE = pathlib.Path(__file__).parents[1]/"scripts/v25_phase5_nhl_sog_historical_replay.py"

class MicroTOISensitivityTests(unittest.TestCase):
    def candidate(self, folder):
        source=S.candidate_source(BASE)
        path=pathlib.Path(folder)/"research_v2.py"
        path.write_text(source,encoding="utf-8")
        spec=importlib.util.spec_from_file_location("research_v2",str(path))
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        return mod
    def history(self):
        h={}
        for i in range(26):
            rows=[]
            for j in range(10):
                when=dt.datetime(2025,10,1+j,19,tzinfo=dt.timezone.utc)
                rows.append({"game_id":str(2025020000+j),"game_date":when.date().isoformat(),
                             "season":"20252026","player_id":str(8400000+i),
                             "team":"AAA","position_group":"F","sog":1+(i%3),
                             "toi_minutes":(.05 if i==1 and j==8 else 11.5+i%8),
                             "_start":when,"_release":when+dt.timedelta(hours=8)})
            h[str(8400000+i)]=rows
        return h
    def test_original_frozen_source_never_modified(self):
        before=hashlib.sha256(BASE.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            self.candidate(d)
        self.assertEqual(hashlib.sha256(BASE.read_bytes()).hexdigest(),before)
        self.assertNotIn("microtoi_sensitivity",BASE.read_text())
    def test_only_3_exposure_bin_callsites_versioned(self):
        src=S.candidate_source(BASE)
        start=src.index("def build_params(pid,history):")
        end=src.index("def pmfs(model):",start)
        body=src[start:end]
        self.assertEqual(body.count("v2_microtoi_bin("),3)
        self.assertNotIn("frozen.bin_toi_minutes(",body)
        self.assertIn('EXPERIMENT_ID = "'+S.EXPERIMENT+'"',src)
        self.assertIn("min-positive TOI exposure bin sensitivity",src)
    def test_fails_closed_on_wrong_original_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"bad.py"
            p.write_text('EXPERIMENT_ID = "changed"',encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"VERSION_MISMATCH"):
                S.candidate_source(p)
    def test_microtoi_repaired_only_in_exposure_pmf(self):
        h=self.history();pid="8400000"
        with self.assertRaisesRegex(F.ReplayBlocked,"EXPOSURE_BIN_INVALID"):
            F.build_params(pid,h)
        with tempfile.TemporaryDirectory() as d:
            m=self.candidate(d)
            model,info=m.build_params(pid,h)
        self.assertGreater(info["peer_games"],200)
        self.assertTrue(math.isfinite(model["rate_a"]))
        self.assertTrue(math.isfinite(model["rate_b"]))
        self.assertEqual(min(x for x,_ in model["exposure_pmf"]),0.5)
        peers=[r for k,rows in h.items() if k!=pid for r in rows]
        rate=sum(r["sog"] for r in peers)/sum(r["toi_minutes"] for r in peers)
        self.assertAlmostEqual(model["rate_a"],F.frozen.TAU_MINUTES*rate+sum(r["sog"] for r in h[pid]))
        self.assertEqual(model["rate_b"],F.frozen.TAU_MINUTES+sum(r["toi_minutes"] for r in h[pid]))
        self.assertAlmostEqual(sum(p for _,p in model["exposure_pmf"]),1)
    def test_boundary_and_zero_failure(self):
        with tempfile.TemporaryDirectory() as d:
            m=self.candidate(d)
            self.assertEqual(m.v2_microtoi_bin(0.05),0.5)
            self.assertEqual(m.v2_microtoi_bin(.249999),0.5)
            self.assertEqual(m.v2_microtoi_bin(.25),.5)
            self.assertEqual(m.v2_microtoi_bin(13.4),13.5)
            for bad in (0,-1,float("nan"),float("inf")):
                with self.assertRaises(F.frozen.ExperimentBlocked):
                    m.v2_microtoi_bin(bad)
    def test_original_frozen_research_gates_preserved(self):
        src=S.candidate_source(BASE)
        for literal in ('"no_pregame_source_certification":True',
                        '"no_original_book_quotes":True',
                        '"no_prospective_inference_or_production":True',
                        '"D2_original_line":',):
            self.assertIn(literal,src)
if __name__=="__main__":unittest.main()
