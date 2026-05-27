"""
Gold layer — compute ML-ready user features with 7-day rolling windows.

Cost optimisations:
  - Write only changed partitions (dynamic partition overwrite)
  - AQE coalesces small shuffle partitions automatically
  - Z-ORDER on user_id for fast Feature Store lookups
"""
from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.utils.delta_utils import optimize_and_zorder

logger = logging.getLogger(__name__)


def compute_user_features(silver_df: DataFrame, feature_date: str | None = None) -> DataFrame:
    """
    Aggregate 7-day rolling user behaviour features.

    Args:
        silver_df: Cleaned Silver events DataFrame.
        feature_date: If set, only compute features for this date (incremental).
    """
    if feature_date:
        silver_df = silver_df.filter(F.col("event_date") >= F.date_sub(F.lit(feature_date), 7))

    return (
        silver_df.groupBy("user_id", F.to_date("event_ts").alias("feature_date"))
        .agg(
            F.count("event_id").alias("event_count_7d"),
            F.countDistinct("session_id").alias("session_count_7d"),
            F.coalesce(F.sum("revenue"), F.lit(0.0)).alias("revenue_7d"),
            F.coalesce(F.avg("session_duration"), F.lit(0.0)).alias("avg_session_duration_7d"),
            F.count_distinct("device_type").alias("device_variety_7d"),
        )
        .withColumn("processed_at", F.current_timestamp())
    )


def run_incremental(spark: SparkSession, silver_path: str, gold_path: str, feature_date: str) -> None:
    """Incremental Gold update — only recomputes the last 7 days."""
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    silver_df = spark.read.format("delta").load(silver_path)
    features  = compute_user_features(silver_df, feature_date)
    features.write.format("delta").mode("overwrite").partitionBy("feature_date").save(gold_path)
    optimize_and_zorder(spark, gold_path, ["user_id"])
    logger.info("Gold features written for %s", feature_date)


if __name__ == "__main__":
    import os
    spark = SparkSession.builder.appName("feature-engineering").getOrCreate()
    run_incremental(
        spark,
        silver_path=os.environ["SILVER_DELTA_PATH"],
        gold_path=os.environ["GOLD_DELTA_PATH"],
        feature_date=os.environ.get("FEATURE_DATE", str(__import__("datetime").date.today())),
    )
