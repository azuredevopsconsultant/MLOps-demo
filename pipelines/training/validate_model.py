"""
Champion/challenger validation.

Promotes candidate to Staging only if:
  (a) metric > production champion * (1 + improvement_pct)
  OR
  (b) no prod model exists AND metric > min_threshold
"""
from __future__ import annotations

import logging

import mlflow
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)


def validate_and_promote(
    run_id: str,
    model_name: str,
    metric_key: str = "cv_roc_auc",
    min_threshold: float = 0.70,
    improvement_pct: float = 0.01,
) -> bool:
    client           = MlflowClient()
    candidate_metric = client.get_run(run_id).data.metrics.get(metric_key, 0)
    prod_versions    = client.get_latest_versions(model_name, stages=["Production"])

    if prod_versions:
        prod_metric = client.get_run(prod_versions[0].run_id).data.metrics.get(metric_key, 0)
        passes      = candidate_metric >= prod_metric * (1 + improvement_pct)
        logger.info("Candidate %s=%.4f vs champion=%.4f. Passes: %s", metric_key, candidate_metric, prod_metric, passes)
    else:
        passes = candidate_metric >= min_threshold
        logger.info("No champion — min-threshold check: %s (%.4f >= %.2f)", passes, candidate_metric, min_threshold)

    if passes:
        mv = mlflow.register_model(f"runs:/{run_id}/model", model_name)
        client.transition_model_version_stage(name=model_name, version=mv.version, stage="Staging", archive_existing_versions=False)
        logger.info("Model v%s promoted to Staging as '%s'", mv.version, model_name)
    return passes
