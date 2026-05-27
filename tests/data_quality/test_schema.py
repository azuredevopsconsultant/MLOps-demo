"""Data quality tests — schema enforcement."""
import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType
from pipelines.transformation.schema_enforcement import enforce_schema, assert_null_rate


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.master("local[1]").appName("dq-tests").getOrCreate()


EXPECTED = StructType([
    StructField("event_id", StringType(), nullable=False),
    StructField("user_id",  StringType(), nullable=False),
])


def test_enforce_schema_passes(spark):
    df = spark.createDataFrame([{"event_id": "e1", "user_id": "u1", "extra": "x"}])
    assert "event_id" in enforce_schema(df, EXPECTED).columns


def test_missing_required_col_raises(spark):
    df = spark.createDataFrame([{"event_id": "e1"}])
    with pytest.raises(ValueError, match="Missing required columns"):
        enforce_schema(df, EXPECTED)


def test_null_rate_passes(spark):
    data = [{"col": "v"}] * 100
    assert_null_rate(spark.createDataFrame(data), "col", max_null_pct=0.01)


def test_null_rate_fails(spark):
    data = [{"col": None}] * 10 + [{"col": "v"}] * 90
    with pytest.raises(ValueError, match="null rate"):
        assert_null_rate(spark.createDataFrame(data), "col", max_null_pct=0.05)
