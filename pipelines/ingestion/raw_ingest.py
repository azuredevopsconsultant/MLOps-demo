"""
Bronze layer — raw ingestion from S3 via Databricks Auto Loader.

Cost optimisations:
  - availableNow=True trigger → cluster runs only while files exist, then stops
  - cloudFiles.maxFilesPerTrigger → caps memory per micro-batch
  - optimizeWrite + autoCompact → fewer small files → cheaper future reads
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from pyspark.sql import SparkSession

from src.config.base_config import BronzeConfig
from src.utils.delta_utils import write_delta_table, configure_delta_optimisations

logger = logging.getLogger(__name__)


@dataclass
class BronzeIngestJob:
    config: BronzeConfig
    spark: SparkSession

    def run(self) -> None:
        configure_delta_optimisations(self.spark)
        logger.info("Starting bronze ingestion from %s", self.config.source_path)

        df = (
            self.spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("cloudFiles.schemaLocation", self.config.schema_path)
            .option("cloudFiles.inferColumnTypes", "true")
            .option("cloudFiles.maxFilesPerTrigger", "1000")   # bound batch size
            .option("cloudFiles.useNotifications", "true")     # S3 SQS events → no polling cost
            .load(self.config.source_path)
        )

        query = (
            df.writeStream
            .format("delta")
            .option("checkpointLocation", self.config.checkpoint_path)
            .option("mergeSchema", "true")
            .partitionBy("event_date")
            .trigger(availableNow=True)   # process backlog then terminate
            .start(self.config.bronze_path)
        )
        query.awaitTermination()
        logger.info("Bronze ingestion complete")


def main() -> None:
    spark = SparkSession.builder.appName("bronze-ingest").getOrCreate()
    BronzeIngestJob(config=BronzeConfig.from_env(), spark=spark).run()


if __name__ == "__main__":
    main()
