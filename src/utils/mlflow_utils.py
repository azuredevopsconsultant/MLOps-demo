"""MLflow tracking, registry, and experiment helpers."""
from __future__ import annotations

import logging

import mlflow
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)


def get_or_create_experiment(name: str) -> str:
    """Return experiment_id, creating the experiment if it does not exist."""
    client = MlflowClient()
    exp    = client.get_experiment_by_name(name)
    if exp:
        return exp.experiment_id
    exp_id = client.create_experiment(name)
    logger.info("Created MLflow experiment '%s' (id=%s)", name, exp_id)
    return exp_id


def get_production_model_uri(model_name: str) -> str:
    versions = MlflowClient().get_latest_versions(model_name, stages=["Production"])
    if not versions:
        raise ValueError(f"No Production model registered for '{model_name}'")
    return f"models:/{model_name}/Production"


def transition_model_stage(
    model_name: str,
    version: int | str,
    stage: str,
    archive_existing: bool = True,
) -> None:
    MlflowClient().transition_model_version_stage(
        name=model_name,
        version=str(version),
        stage=stage,
        archive_existing_versions=archive_existing,
    )
    logger.info("Model '%s' v%s → %s", model_name, version, stage)


def log_dataset_info(spark_df, name: str, tags: dict | None = None) -> None:
    """Log dataset row count and schema to the active MLflow run."""
    mlflow.log_param(f"{name}_row_count", spark_df.count())
    mlflow.log_param(f"{name}_columns",   len(spark_df.columns))
    if tags:
        mlflow.set_tags(tags)
