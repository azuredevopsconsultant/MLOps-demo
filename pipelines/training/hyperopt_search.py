"""Hyperopt search space definitions — centralised so all jobs share the same space."""
from hyperopt import hp

GBDT_SPACE = {
    "n_estimators":     hp.choice("n_estimators", [100, 200, 300, 500]),
    "max_depth":        hp.quniform("max_depth", 3, 10, 1),
    "learning_rate":    hp.loguniform("learning_rate", -5, 0),
    "subsample":        hp.uniform("subsample", 0.5, 1.0),
    "min_samples_leaf": hp.quniform("min_samples_leaf", 1, 20, 1),
}

XGBOOST_SPACE = {
    "n_estimators":   hp.choice("n_estimators", [100, 300, 500]),
    "max_depth":      hp.quniform("max_depth", 3, 10, 1),
    "eta":            hp.loguniform("eta", -4, 0),
    "subsample":      hp.uniform("subsample", 0.5, 1.0),
    "colsample_bytree": hp.uniform("colsample_bytree", 0.5, 1.0),
}
