import os
import contextlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_context_model as model


class Layout(unittest.TestCase):
    def test_progress_logs_phase_at_intervals_and_last_draw_without_unicode(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            for index,last,tuning in ((0,False,True),(249,False,True),(349,True,False)):
                model.sampling_progress(None,SimpleNamespace(chain=2,draw_idx=index,is_last=last,tuning=tuning))
        self.assertEqual(output.getvalue().splitlines(),[
            "NUTS_PROGRESS chain=2 iteration=250 phase=warmup",
            "NUTS_PROGRESS chain=2 iteration=350 phase=posterior"])
        output.getvalue().encode("ascii")

    def test_training_counts_select_parameterization_without_holdout(self):
        d={"players":["sparse","established"],"positions":["WR","TE"],
           "player_position":{"sparse":"WR","established":"TE"},
           "player_idx":[0,1,1,1,1,1],"position_idx":[0,1,1,1,1,1]}
        positions,centered=model.workload_layout(d)
        self.assertEqual(positions.tolist(),[0,1]);self.assertEqual(centered.tolist(),[False,True])
        d["position_idx"][0]=1
        with self.assertRaisesRegex(ValueError,"indices_inconsistent"):model.workload_layout(d)


@unittest.skipUnless(os.environ.get("RUN_NFL_MIXED_NUMERICAL")=="1","opt-in PyTensor prior equivalence")
class PriorEquivalence(unittest.TestCase):
    def test_correlated_prior_density_and_predictors_are_unchanged(self):
        import numpy as np
        import pytensor
        import pytensor.tensor as pt
        from scipy.stats import norm,multivariate_normal
        raw=pt.dvector();rate=pt.dvector();population=pt.dvector();chol=pt.dmatrix()
        mask=np.array([False,True])
        z,effect=model.workload_coordinates(raw,rate,population,chol,mask)
        evaluate=pytensor.function([raw,rate,population,chol],[z,effect])
        for offdiag in (-.3,0.,.3):
            l=np.array([[.6,0.],[offdiag,.4]]);mu=np.array([-1.2,-1.5])
            values=np.array([.7,-1.1]);zr=np.array([-.2,.5])
            z,e=evaluate(values,zr,mu,l)
            np.testing.assert_allclose(z[:,0],np.where(mask,(values-mu)/l[0,0],values))
            np.testing.assert_allclose(e,z@l.T)
            # Transform the new raw-coordinate density back to the old effects.
            new_logp=norm.logpdf(values,np.where(mask,mu,0.),np.where(mask,l[0,0],1.))+norm.logpdf(zr)
            jacobian=np.where(mask,l[1,1],l[0,0]*l[1,1])
            old_logp=multivariate_normal.logpdf(e,mean=[0.,0.],cov=l@l.T)
            np.testing.assert_allclose(new_logp-np.log(jacobian),old_logp,atol=1e-12)
            np.testing.assert_allclose(mu+e[:,0],np.where(mask,values,mu+l[0,0]*values))
