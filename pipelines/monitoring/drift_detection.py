"""
Databricks Lakehouse Monitoring — feature and prediction drift.

Runs weekly on a single i3.xlarge (cheapest viable config).
Alerts fire to PagerDuty / Slack via webhook if drift > threshold.
"""
from __future__ import annotations

import logging
import os

import requests
from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)

ALERT_WEBHOOK = os.environ.get("ALERT_WEBHOOK_URL", "")
DRIFT_THRESHOLD = float(os.environ.get("DRIFT_THRESHOLD", "0.05"))


def create_or_refresh_monitor(
    table_name: str,
    baseline_table: str,
    output_schema: str = "mlops_monitoring",
) -> None:
    w = WorkspaceClient()
    w.quality_monitors.create(
        table_name=table_name,
        assets_dir=f"/Workspace/monitoring/{table_name.replace('.', '_')}",
        output_schema_name=output_schema,
        inference_log={
            "timestamp_col":  "scored_at",
            "model_id_col":   "model_version",
            "prediction_col": "prediction",
            "label_col":      "ground_truth",
            "problem_type":   "PROBLEM_TYPE_CLASSIFICATION",
        },
        baseline_table_name=baseline_table,
    )
    logger.info("Monitor created/refreshed for table: %s", table_name)


def check_and_alert(js_divergence: float, table_name: str) -> None:
    if js_divergence > DRIFT_THRESHOLD and ALERT_WEBHOOK:
        payload = {
            "text": f":warning: *Drift Alert* — `{table_name}`\n"
                    f"JS divergence `{js_divergence:.4f}` > threshold `{DRIFT_THRESHOLD}`\n"
                    f"Action: inspect monitor dashboard and consider retraining."
        }
        requests.post(ALERT_WEBHOOK, json=payload, timeout=5)
        logger.warning("Drift alert sent for %s (%.4f)", table_name, js_divergence)
