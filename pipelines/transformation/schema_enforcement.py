"""Schema enforcement and data-quality gate on Silver tables."""
from __future__ import annotations
from pyspark.sql import DataFrame
from pyspark.sql.types import StructType


def enforce_schema(df: DataFrame, expected: StructType) -> DataFrame:
    """Cast to expected types; raise on missing non-nullable columns."""
    missing = {f.name for f in expected if not f.nullable} - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    for field in expected:
        if field.name in df.columns:
            df = df.withColumn(field.name, df[field.name].cast(field.dataType))
    return df


def assert_null_rate(df: DataFrame, col: str, max_null_pct: float = 0.01) -> None:
    """Raise if null rate in `col` exceeds `max_null_pct`."""
    total = df.count()
    nulls = df.filter(df[col].isNull()).count()
    rate  = nulls / total if total > 0 else 0
    if rate > max_null_pct:
        raise ValueError(f"{col} null rate {rate:.2%} exceeds threshold {max_null_pct:.2%}")
