"""NBA V2.5 S statistical conditional count laws; research-only."""
from .model import (SFError, FittedS, Prediction, fit, predict, conditional_pmf,
                    predict_conditional, exact_triplet)
__all__ = ["SFError", "FittedS", "Prediction", "fit", "predict",
           "conditional_pmf", "predict_conditional", "exact_triplet"]