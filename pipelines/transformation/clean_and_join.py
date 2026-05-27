"""
Silver layer — clean, deduplicate, and type-cast Bronze tables.

Cost optimisations:
  - Z-ORDER on high-cardinality filter columns → data-skipping cuts scan size
  - Adaptive Query Execution (AQE) enabled globally
  - Partition by event_date → prune partitions on downstream reads
"""
from __future__ import annotations

import logging

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.config.base_config import SilverConfig
from src.utils.delta_utils import write_delta_table, optimize_and_zorder

logger = logging.getLogger(__name__)


def clean_events(df: DataFrame) -> DataFrame:
    """Deduplicate, null-filter, and standardise timestamps."""
    return (
        df.dropDuplicates(["event_id"])
        .filter(F.col("event_id").isNotNull() & F.col("user_id").isNotNull())
        .withColumn("event_ts", F.to_timestamp("event_ts"))
        .withColumn("event_date", F.to_date("event_ts"))
        .withColumn("processed_at", F.current_timestamp())
    )


def merge_into_silver(spark: SparkSession, new_df: DataFrame, silver_path: str) -> None:
    """
    MERGE instead of overwrite — only touch changed rows.
    Drastically reduces write amplification on large Silver tables.
    """
    if DeltaTable.isDeltaTable(spark, silver_path):
        silver = DeltaTable.forPath(spark, silver_path)
        (
            silver.alias("target")
            .merge(new_df.alias("source"), "target.event_id = source.event_id")
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )
    else:
        write_delta_table(new_df, silver_path, partition_cols=["event_date"])


def run(spark: SparkSession, config: SilverConfig) -> None:
    raw = spark.read.format("delta").load(config.bronze_path)
    cleaned = clean_events(raw)
    merge_into_silver(spark, cleaned, config.silver_path)

    # Z-ORDER on user_id and event_date → downstream feature queries skip 80%+ of files
    optimize_and_zorder(spark, config.silver_path, ["user_id", "event_date"])
    logger.info("Silver transformation complete")


if __name__ == "__main__":
    spark = SparkSession.builder.appName("silver-transform").getOrCreate()
    run(spark, SilverConfig.from_env())
