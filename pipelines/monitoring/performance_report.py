"""Weekly model performance report — reads Lakehouse Monitor output tables."""
from __future__ import annotations

import logging

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from pipelines.monitoring.drift_detection import check_and_alert

logger = logging.getLogger(__name__)


def run_report(spark: SparkSession, monitor_schema: str, predictions_table: str) -> None:
    """Read monitor output and trigger alerts if thresholds are breached."""
    drift_df = (
        spark.read.table(f"{monitor_schema}.drift_metrics")
        .filter(F.col("window") == "WEEK")
        .orderBy(F.col("window_start").desc())
        .limit(1)
    )
    row = drift_df.first()
    if not row:
        logger.warning("No drift metrics found — monitor may not have run yet.")
        return

    js_divergence = row["js_divergence"]
    check_and_alert(js_divergence, predictions_table)

    perf_df = (
        spark.read.table(f"{monitor_schema}.model_quality_profile_metrics")
        .orderBy(F.col("window_start").desc())
        .limit(1)
    )
    logger.info("Weekly report complete. JS divergence: %.4f", js_divergence)
    perf_df.show(truncate=False)
