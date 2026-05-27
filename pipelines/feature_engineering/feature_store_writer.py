"""Write Gold features to Databricks Feature Store — online + offline."""
from __future__ import annotations
from databricks.feature_store import FeatureStoreClient, FeatureLookup
from pyspark.sql import DataFrame


def write_to_feature_store(
    df: DataFrame,
    table_name: str,
    primary_keys: list[str],
    timestamp_keys: list[str] | None = None,
    description: str = "",
    mode: str = "merge",
) -> None:
    """
    Upsert features into the Feature Store.

    mode="merge" → only writes changed rows → lower S3 write cost.
    """
    fs = FeatureStoreClient()
    if not fs.table_exists(table_name):
        fs.create_table(
            name=table_name,
            primary_keys=primary_keys,
            timestamp_keys=timestamp_keys or [],
            df=df,
            description=description,
        )
    else:
        fs.write_table(name=table_name, df=df, mode=mode)


def build_feature_lookups(feature_table: str, feature_names: list[str], lookup_key: str) -> list[FeatureLookup]:
    return [FeatureLookup(table_name=feature_table, feature_names=feature_names, lookup_key=lookup_key)]
