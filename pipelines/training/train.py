"""
Model training with MLflow autologging + Hyperopt distributed tuning.

Cost optimisations:
  - Hyperopt SparkTrials → parallelises across cluster workers
  - max_evals capped by env var → dev runs fewer trials
  - Feature Store training set avoids re-reading Gold Delta (cached)
  - Cross-validation via cv=5 (not 10) for dev/staging
"""
from __future__ import annotations

import logging
import os

import mlflow
import mlflow.sklearn
from databricks.feature_store import FeatureStoreClient
from hyperopt import STATUS_OK, SparkTrials, fmin, hp, tpe
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score

from src.config.base_config import TrainingConfig
from src.utils.mlflow_utils import get_or_create_experiment

logger = logging.getLogger(__name__)

SEARCH_SPACE = {
    "n_estimators":     hp.choice("n_estimators", [100, 200, 300, 500]),
    "max_depth":        hp.quniform("max_depth", 3, 8, 1),
    "learning_rate":    hp.loguniform("learning_rate", -4, 0),
    "subsample":        hp.uniform("subsample", 0.6, 1.0),
    "min_samples_leaf": hp.quniform("min_samples_leaf", 1, 20, 1),
}


def train(config: TrainingConfig) -> str:
    """Train model; return MLflow run_id."""
    fs = FeatureStoreClient()
    training_set = fs.create_training_set(
        df=config.label_df,
        feature_lookups=config.feature_lookups,
        label=config.label_col,
        exclude_columns=config.exclude_cols,
    )
    pdf = training_set.load_df().toPandas()
    X, y = pdf.drop(columns=[config.label_col]), pdf[config.label_col]

    experiment_id = get_or_create_experiment(config.experiment_name)
    max_evals = int(os.environ.get("HYPEROPT_MAX_EVALS", "20"))
    cv_folds  = int(os.environ.get("CV_FOLDS", "5"))

    # SparkTrials → each trial runs on a separate worker → parallelism = free
    spark_trials = SparkTrials(parallelism=4)

    def objective(params: dict) -> dict:
        params = {**params, "max_depth": int(params["max_depth"]), "min_samples_leaf": int(params["min_samples_leaf"])}
        with mlflow.start_run(nested=True, experiment_id=experiment_id):
            mlflow.log_params(params)
            model = GradientBoostingClassifier(**params, random_state=42)
            auc   = cross_val_score(model, X, y, cv=cv_folds, scoring="roc_auc").mean()
            mlflow.log_metric("cv_roc_auc", auc)
        return {"loss": -auc, "status": STATUS_OK}

    with mlflow.start_run(experiment_id=experiment_id) as run:
        mlflow.autolog(log_model_signatures=True, log_input_examples=True)
        best = fmin(fn=objective, space=SEARCH_SPACE, algo=tpe.suggest, max_evals=max_evals, trials=spark_trials)
        best = {**best, "max_depth": int(best["max_depth"]), "min_samples_leaf": int(best["min_samples_leaf"])}
        final_model = GradientBoostingClassifier(**best, random_state=42).fit(X, y)
        fs.log_model(model=final_model, artifact_path="model", flavor=mlflow.sklearn, training_set=training_set)
        logger.info("Training complete. Run ID: %s  AUC: %.4f", run.info.run_id, -min(spark_trials.results, key=lambda r: r["loss"])["loss"])
        return run.info.run_id


def main() -> None:
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName("model-training").getOrCreate()
    train(TrainingConfig.from_env(spark))


if __name__ == "__main__":
    main()
