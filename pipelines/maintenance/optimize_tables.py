"""
Delta Lake maintenance — OPTIMIZE + VACUUM on all medallion tables.

Runs weekly on Sunday 03:00 UTC (cheapest off-peak window).
OPTIMIZE compacts small files → faster reads → lower scan cost.
VACUUM removes stale versions → lower S3 storage cost.

Cost note: retain_hours=168 (7 days) gives a safe time-travel window
while still recovering storage from deleted files promptly.
"""
from __future__ import annotations

import logging
import os

from pyspark.sql import SparkSession

from src.utils.delta_utils import optimize_and_zorder, vacuum

logger = logging.getLogger(__name__)

TABLES = {
    "bronze": (os.environ.get("BRONZE_DELTA_PATH", ""), []),
    "silver": (os.environ.get("SILVER_DELTA_PATH", ""), ["user_id", "event_date"]),
    "gold":   (os.environ.get("GOLD_DELTA_PATH",   ""), ["user_id"]),
    "preds":  (os.environ.get("PREDICTIONS_PATH",  ""), ["inference_date"]),
}


def run_maintenance(spark: SparkSession, retain_hours: int = 168) -> None:
    for name, (path, zorder_cols) in TABLES.items():
        if not path:
            logger.warning("Skipping %s — path not set", name)
            continue
        logger.info("Optimising %s at %s", name, path)
        if zorder_cols:
            optimize_and_zorder(spark, path, zorder_cols)
        else:
            spark.sql(f"OPTIMIZE delta.`{path}`")
        vacuum(spark, path, retain_hours=retain_hours)
        logger.info("Maintenance complete for %s", name)


if __name__ == "__main__":
    spark = SparkSession.builder.appName("delta-maintenance").getOrCreate()
    run_maintenance(spark)
