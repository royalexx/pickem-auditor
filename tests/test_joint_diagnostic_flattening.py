"""Regression coverage for diagnostic allocation; never builds or samples a model."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import joint_population_bayes as model
import joint_nhl_bayes as legacy_model


class DatasetDouble:
    def __init__(self,variables):
        self.data_vars=variables

    def to_array(self):
        raise AssertionError("diagnostic variables must never be broadcast together")


class Node:
    def __init__(self,dataset):
        self.dataset=dataset

    def to_dataset(self):
        return self.dataset


class TreeDouble:
    def __init__(self,datasets):
        self.subtree=[Node(dataset) for dataset in datasets]


@unittest.skipUnless(importlib.util.find_spec("numpy"),"diagnostic helper requires NumPy")
class DiagnosticFlatteningTests(unittest.TestCase):
    def test_legacy_nhl_helper_avoids_the_same_broadcast(self):
        dataset=DatasetDouble({"player":[[1.,2.],[3.,4.]],"opponent":[5.,6.,7.]})
        self.assertEqual(legacy_model._diagnostic_values(dataset),[1.,2.,3.,4.,5.,6.,7.])
        for invalid in (math.nan,math.inf,-math.inf):
            with self.assertRaisesRegex(ValueError,"nonfinite_arviz_diagnostic_result"):
                legacy_model._diagnostic_values(DatasetDouble({"invalid":[invalid]}))

    def test_distinct_variable_shapes_preserve_each_scalar_once(self):
        result=DatasetDouble({"player":[[1.,2.],[3.,4.]],
                              "opponent":[5.,6.,7.],"global":8.})
        self.assertEqual(model._to_values(result),[1.,2.,3.,4.,5.,6.,7.,8.])

    @unittest.skipUnless(importlib.util.find_spec("xarray"),"real Dataset check requires xarray")
    def test_real_heterogeneous_dataset_has_additive_allocation(self):
        import numpy as np
        import xarray as xr
        result=xr.Dataset({
            "player":(("players","effect"),np.arange(60.).reshape(30,2)),
            "opponent":(("opponents",),np.arange(32.)+100),
            "season":(("seasons",),np.array([300.,301.])),
            "population":(("positions",),np.arange(4.)+400)})
        expected=[v for variable in result.data_vars.values()
                  for v in np.asarray(variable).ravel().tolist()]
        values=model._to_values(result)
        self.assertEqual(len(values),98)
        self.assertEqual(values,expected)
        self.assertEqual((min(values),max(values)),(min(expected),max(expected)))

    def test_nested_tree_including_empty_root_is_supported(self):
        result=TreeDouble([DatasetDouble({}),DatasetDouble({"rhat":[1.,1.01]}),
                           DatasetDouble({"ess":[[400.],[800.]]})])
        self.assertEqual(model._to_values(result),[1.,1.01,400.,800.])

    def test_empty_dataset_or_tree_is_rejected(self):
        for result in (DatasetDouble({}),DatasetDouble({"empty":[]}),
                       TreeDouble([]),TreeDouble([DatasetDouble({})])):
            with self.subTest(result=type(result).__name__):
                with self.assertRaisesRegex(ValueError,"missing_or_invalid_posterior_diagnostic"):
                    model._to_values(result)

    def test_nonfinite_diagnostic_is_rejected_in_any_variable(self):
        for invalid in (math.nan,math.inf,-math.inf):
            for result in (DatasetDouble({"valid":[1.],"invalid":[invalid]}),
                           TreeDouble([DatasetDouble({"valid":[1.]}),
                                       DatasetDouble({"invalid":[invalid]})])):
                with self.subTest(invalid=invalid,result=type(result).__name__):
                    with self.assertRaisesRegex(ValueError,"missing_or_invalid_posterior_diagnostic"):
                        model._to_values(result)

    def test_unsupported_container_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"unsupported_arviz_results"):
            model._to_values(object())


if __name__=="__main__":
    unittest.main()
