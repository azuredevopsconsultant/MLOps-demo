"""
Batch inference — score Gold features and write predictions to Delta.

Cost optimisations:
  - dynamic partition overwrite → only rewrite today's predictions
  - ZORDER on user_id → fast downstream BI lookups
  - cluster autoscale 1-6 workers vs fixed 8
"""
from __future__ import annotations

import logging
from datetime import date

from databricks.feature_store import FeatureStoreClient
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.utils.delta_utils import write_delta_table, optimize_and_zorder

logger = logging.getLogger(__name__)


def run_batch_inference(
    spark: SparkSession,
    model_uri: str,
    entity_df: DataFrame,
    output_path: str,
    inference_date: str | None = None,
) -> None:
    inference_date = inference_date or str(date.today())
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")

    fs          = FeatureStoreClient()
    predictions = fs.score_batch(model_uri=model_uri, df=entity_df)
    predictions = predictions.withColumn("inference_date", F.lit(inference_date))

    write_delta_table(predictions, output_path, partition_cols=["inference_date"])
    optimize_and_zorder(spark, output_path, ["user_id"])
    logger.info("Batch inference complete for %s. Output: %s", inference_date, output_path)


if __name__ == "__main__":
    import os
    from src.config.base_config import InferenceConfig
    spark  = SparkSession.builder.appName("batch-inference").getOrCreate()
    config = InferenceConfig.from_env(spark)
    entity = spark.read.format("delta").load(config.gold_path)
    run_batch_inference(spark, f"models:/{config.model_name}/Production", entity, config.predictions_path)
