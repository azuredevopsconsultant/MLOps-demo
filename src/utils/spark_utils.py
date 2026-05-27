"""Spark session factory with Delta + best-practice defaults baked in."""
from __future__ import annotations

from pyspark.sql import SparkSession
from src.utils.delta_utils import configure_delta_optimisations


def get_spark(app_name: str = "mlops-demo") -> SparkSession:
    """
    Returns a SparkSession with:
      - Delta Lake extensions enabled
      - AQE enabled (automatic partition coalescing + skew join)
      - Delta optimiseWrite + autoCompact enabled
    """
    spark = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .getOrCreate()
    )
    configure_delta_optimisations(spark)
    return spark
