"""Unit tests — Gold feature computation."""
import pytest
from pyspark.sql import SparkSession
from pipelines.feature_engineering.compute_features import compute_user_features


@pytest.fixture(scope="session")
def spark():
    return (
        SparkSession.builder.master("local[1]")
        .appName("feature-tests")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )


def test_event_count_aggregation(spark):
    data = [
        {"user_id": "u1", "event_id": "e1", "event_ts": "2024-01-01 10:00:00", "session_id": "s1", "revenue": 10.0, "session_duration": 60.0},
        {"user_id": "u1", "event_id": "e2", "event_ts": "2024-01-01 11:00:00", "session_id": "s1", "revenue": 20.0, "session_duration": 90.0},
        {"user_id": "u2", "event_id": "e3", "event_ts": "2024-01-01 12:00:00", "session_id": "s2", "revenue":  5.0, "session_duration": 30.0},
    ]
    df     = compute_user_features(spark.createDataFrame(data))
    u1_row = df.filter(df.user_id == "u1").first()
    assert u1_row["event_count_7d"] == 2
    assert u1_row["revenue_7d"]     == 30.0


def test_no_null_revenue(spark):
    from pyspark.sql import functions as F
    data = [
        {"user_id": "u1", "event_id": "e1", "event_ts": "2024-01-01 10:00:00", "session_id": "s1", "revenue": None, "session_duration": 60.0},
    ]
    df = compute_user_features(spark.createDataFrame(data))
    assert df.filter(F.col("revenue_7d").isNull()).count() == 0
