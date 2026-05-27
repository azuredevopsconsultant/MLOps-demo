"""Unit tests — Silver transformation logic."""
import pytest
from pyspark.sql import SparkSession
from pipelines.transformation.clean_and_join import clean_events


@pytest.fixture(scope="session")
def spark():
    return (
        SparkSession.builder.master("local[1]")
        .appName("unit-tests")
        .config("spark.sql.shuffle.partitions", "2")  # keep tests fast
        .getOrCreate()
    )


def test_deduplication(spark):
    data = [
        {"event_id": "e1", "event_ts": "2024-01-01 10:00:00", "user_id": "u1"},
        {"event_id": "e1", "event_ts": "2024-01-01 10:00:00", "user_id": "u1"},  # dup
        {"event_id": "e2", "event_ts": "2024-01-01 11:00:00", "user_id": "u2"},
    ]
    assert clean_events(spark.createDataFrame(data)).count() == 2


def test_null_event_id_filtered(spark):
    data = [
        {"event_id": None, "event_ts": "2024-01-01 10:00:00", "user_id": "u1"},
        {"event_id": "e1", "event_ts": "2024-01-01 10:00:00", "user_id": "u1"},
    ]
    assert clean_events(spark.createDataFrame(data)).count() == 1


def test_event_ts_cast_to_timestamp(spark):
    from pyspark.sql.types import TimestampType
    data = [{"event_id": "e1", "event_ts": "2024-01-01 10:00:00", "user_id": "u1"}]
    df   = clean_events(spark.createDataFrame(data))
    assert dict(df.dtypes)["event_ts"] == "timestamp"


def test_processed_at_column_added(spark):
    data = [{"event_id": "e1", "event_ts": "2024-01-01 10:00:00", "user_id": "u1"}]
    df   = clean_events(spark.createDataFrame(data))
    assert "processed_at" in df.columns
