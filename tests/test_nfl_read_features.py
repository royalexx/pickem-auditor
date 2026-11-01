"""Read-aware training contracts; synthetic FTN/PBP, never real outcome claims."""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_read_features as reads
import nfl_context_data as data
import nfl_context_campaign as campaign
import nfl_context_model as model
import nhl_context_train as io
from nfl_context_fixture import season


def chart(raw):
    codes=[0,1,2,"CHK","DES","SD","unknown-code"]
    return [{"nflverse_game_id":p["game_id"],"nflverse_play_id":p["play_id"],
             "season":int(p["game_id"][:4]),"read_thrown":codes[int(p["play_id"])%len(codes)]} for p in raw["pbp"]]


def config():
    c=io.load_json(campaign.ROOT/"config/nfl_context_reads_full.json")
    c.update(seasons=[2023,2024,2025],train_from="2023-08-01T00:00:00Z",cutoff="2025-09-01T00:00:00Z",
             until="2026-02-01T00:00:00Z")
    return c


def bundles():
    result=[]
    for y in (2023,2024,2025):
        raw=season(y,rotate=True)
        b=data.normalize(raw,season=y,until=config()["until"])
        result.append(reads.join(b,raw["pbp"],chart(raw)))
    return result


class ReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundles=bundles()

    def test_reuses_dictionary_and_preserves_designed_unknown(self):
        self.assertEqual(reads.bucket(0),"first_read")
        self.assertEqual(reads.bucket(1),"second_read")
        self.assertEqual(reads.bucket("CHK"),"checkdown")
        self.assertEqual(reads.bucket("DES"),"designed")
        self.assertEqual(reads.bucket("unknown-code"),"unknown")
        self.assertGreater(self.bundles[0]["read_source"]["throw_buckets"]["designed"],0)

    def test_duplicate_chart_conflicts_fail(self):
        raw=season(2023,rotate=True);c=chart(raw);c.append({**c[0],"read_thrown":"different"})
        base=data.normalize(raw,season=2023,until=config()["until"])
        with self.assertRaisesRegex(ValueError,"duplicate_ftn"):reads.join(base,raw["pbp"],c)

    def test_actual_offensive_and_defensive_features_present(self):
        rows=data.examples(self.bundles,"targets",read_features=True)
        row=next(r for r in reversed(rows) if r["read_context"]["defense_comparable_targets"]>0)
        values=dict(zip(row["feature_names"],row["x"]))
        self.assertGreater(row["read_context"]["known_offense_targets"],0)
        self.assertTrue(any(values["defense_qb_adjusted_"+k] is not None for k in reads.KNOWN))
        self.assertIsNotNone(values["qb_mix_first_read"])
        self.assertIsNotNone(values["qb_mix_designed"])
        self.assertEqual(row["read_context"]["defense_adjustment_applied_as"],"learned_covariates_only_no_external_multiplier")

    def test_current_and_future_charting_and_qb_are_not_pregame_inputs(self):
        rows=data.examples(self.bundles,"targets")
        row=rows[len(rows)//2];original=reads.ReadHistory(self.bundles).features(row)
        changed=copy.deepcopy(self.bundles)
        for b in changed:
            for p in b["read_plays"]:
                if p["start_time"]>=row["start_time"]:
                    p["passer_player_id"]="future-quarterback"
                    if p["chart"]:p["chart"]["read_thrown"]="DES"
        self.assertEqual(original,reads.ReadHistory(changed).features(row))
        self.assertNotIn("future-quarterback",original[1]["passer_weights"])

    def test_charting_lag_and_missing_masks_are_explicit(self):
        rows=data.examples(self.bundles,"targets",read_features=True)
        first=rows[0];values=dict(zip(first["feature_names"],first["x"]))
        self.assertIsNone(values["qb_mix_first_read"])
        self.assertEqual(values["qb_mix_first_read_observed"],0.)
        self.assertFalse(first["read_context"]["historical_charting_publication_time_verified"])
        # A huge declared lag makes all charting unavailable, not valid zeros.
        row=rows[80];x,meta=reads.ReadHistory(self.bundles,lag_days=400).features(row)
        self.assertFalse(meta["offense_read_available"])
        self.assertIsNone(x[0])

    def test_single_full_fit_and_training_only_imputation(self):
        self.assertEqual(campaign.model_kinds(config()),("context",))
        with tempfile.TemporaryDirectory() as folder:
            report=campaign.freeze(folder,config(),self.bundles)
            self.assertEqual(report["models_to_fit"],["context"])
            self.assertTrue(report["full_available_training_history"])
            self.assertEqual(report["training_games"],64)
            self.assertGreater(report["read_coverage"]["training"]["both_fraction"],.5)
            d=io.load_json(Path(folder)/"context_design.json")
            self.assertTrue(d["read_features"])
            import numpy as np
            self.assertTrue(np.isfinite(d["x"]).all())
            self.assertEqual(d["feature_names"][-1],reads.FEATURE_NAMES[-1])

    def test_missing_charting_cannot_silently_train_plain_baseline(self):
        changed=copy.deepcopy(self.bundles)
        for b in changed:
            for p in b["read_plays"]:p["chart"]=None
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,"offensive_defensive_read_coverage"):
                campaign.freeze(folder,config(),changed)


@unittest.skipUnless(os.environ.get("RUN_NFL_READ_NUTS")=="1","opt-in read-model NUTS smoke")
class NumericalReads(unittest.TestCase):
    def test_read_model_samples_reloads_and_scores_missing_features(self):
        import arviz as az
        with tempfile.TemporaryDirectory() as folder:
            campaign.freeze(folder,config(),bundles())
            d=io.load_json(Path(folder)/"context_design.json")
            trace=model.fit(d,draws=25,tune=25,chains=2,cores=1)
            quality=model.diagnostics(trace)
            self.assertFalse(quality["posterior_sampling_ok"])
            self.assertNotEqual(quality["status"],"diagnostics_unavailable",quality)
            cache=model.cache(trace,d);rows=io.load_json(Path(folder)/"holdout_rows.json")
            # First new-season game has explicit missing read history.
            self.assertIsNone(rows[0]["x"][7])
            options=dict(line=5.5,draws=250,diagnostic={"posterior_sampling_ok":True})
            p=model.forecast(cache,d,rows[0],**options)
            self.assertAlmostEqual(sum(p[k] for k in ("q_over","q_under","q_push")),1.)
            trace.to_netcdf(Path(folder)/"posterior.nc")
            restored=az.from_netcdf(Path(folder)/"posterior.nc")
            self.assertEqual(p,model.forecast(model.cache(restored,d),d,rows[0],**options))
            with self.assertRaisesRegex(ValueError,"not_converged"):
                model.forecast(cache,d,rows[0],line=5.5,diagnostic=quality)
