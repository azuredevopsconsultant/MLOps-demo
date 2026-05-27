"""Auto Loader helper — reusable stream builder with cost-aware defaults."""
from __future__ import annotations
from pyspark.sql import SparkSession
from pyspark.sql.streaming import StreamingQuery


def build_autoloader_stream(
    spark: SparkSession,
    source_path: str,
    bronze_path: str,
    schema_path: str,
    checkpoint_path: str,
    file_format: str = "json",
    max_files_per_trigger: int = 1000,
) -> StreamingQuery:
    """
    Start an Auto Loader stream.

    availableNow=True means the cluster only pays while there is backlog.
    useNotifications skips the expensive LIST-all-files polling.
    """
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", file_format)
        .option("cloudFiles.schemaLocation", schema_path)
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.useNotifications", "true")
        .option("cloudFiles.maxFilesPerTrigger", str(max_files_per_trigger))
        .load(source_path)
        .writeStream.format("delta")
        .option("checkpointLocation", checkpoint_path)
        .option("mergeSchema", "true")
        .partitionBy("event_date")
        .trigger(availableNow=True)
        .start(bronze_path)
    )
