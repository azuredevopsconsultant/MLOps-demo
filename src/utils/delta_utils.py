"""
Delta Lake utility helpers.

Best practices encoded here so every pipeline gets them for free:
  - mergeSchema=true  → schema evolution without breaking pipelines
  - optimizeWrite     → Databricks auto-bins small files before write
  - autoCompact       → background compaction after write
  - dynamic partition overwrite → only touch changed partitions
"""
from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger(__name__)


def configure_delta_optimisations(spark: SparkSession) -> None:
    """Call once per session — enables cluster-wide Delta best practices."""
    confs = {
        "spark.sql.adaptive.enabled":                              "true",
        "spark.sql.adaptive.coalescePartitions.enabled":           "true",
        "spark.sql.adaptive.skewJoin.enabled":                     "true",
        "spark.databricks.delta.optimizeWrite.enabled":            "true",
        "spark.databricks.delta.autoCompact.enabled":              "true",
        "spark.databricks.delta.schema.autoMerge.enabled":         "true",
        "spark.sql.sources.partitionOverwriteMode":                "dynamic",
        "spark.databricks.delta.retentionDurationCheck.enabled":   "false",
    }
    for k, v in confs.items():
        spark.conf.set(k, v)


def write_delta_table(
    df: DataFrame,
    path: str,
    mode: str = "overwrite",
    partition_cols: list[str] | None = None,
    merge_schema: bool = True,
) -> None:
    writer = (
        df.write.format("delta")
        .mode(mode)
        .option("mergeSchema", str(merge_schema).lower())
        .option("optimizeWrite", "true")
    )
    if partition_cols:
        writer = writer.partitionBy(*partition_cols)
    writer.save(path)
    logger.info("Delta write complete → %s (mode=%s, rows=%s)", path, mode, df.count())


def optimize_and_zorder(spark: SparkSession, path: str, zorder_cols: list[str]) -> None:
    """
    OPTIMIZE + Z-ORDER: compacts files and co-locates data for fast filtering.
    Typically cuts read costs by 50-80% on high-cardinality filter columns.
    """
    cols = ", ".join(zorder_cols)
    logger.info("Running OPTIMIZE ZORDER BY (%s) on %s", cols, path)
    spark.sql(f"OPTIMIZE delta.`{path}` ZORDER BY ({cols})")


def vacuum(spark: SparkSession, path: str, retain_hours: int = 168) -> None:
    """
    Remove Delta log versions older than retain_hours.
    168h = 7 days — balances time-travel need vs storage cost.
    """
    logger.info("VACUUM %s (retain %dh)", path, retain_hours)
    spark.sql(f"SET spark.databricks.delta.retentionDurationCheck.enabled = false")
    spark.sql(f"VACUUM delta.`{path}` RETAIN {retain_hours} HOURS")
