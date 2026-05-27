"""
Pydantic-validated, environment-driven configs for every pipeline stage.

All paths are injected via Databricks job parameters or environment variables —
no hard-coded paths anywhere in the codebase.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


def _req(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(f"Required env var '{key}' is not set")
    return val


@dataclass
class BronzeConfig:
    source_path:    str
    bronze_path:    str
    schema_path:    str
    checkpoint_path: str

    @classmethod
    def from_env(cls) -> "BronzeConfig":
        return cls(
            source_path=    _req("BRONZE_SOURCE_PATH"),
            bronze_path=    _req("BRONZE_DELTA_PATH"),
            schema_path=    _req("BRONZE_SCHEMA_PATH"),
            checkpoint_path=_req("BRONZE_CHECKPOINT_PATH"),
        )


@dataclass
class SilverConfig:
    bronze_path: str
    silver_path: str

    @classmethod
    def from_env(cls) -> "SilverConfig":
        return cls(bronze_path=_req("BRONZE_DELTA_PATH"), silver_path=_req("SILVER_DELTA_PATH"))


@dataclass
class GoldConfig:
    silver_path: str
    gold_path:   str

    @classmethod
    def from_env(cls) -> "GoldConfig":
        return cls(silver_path=_req("SILVER_DELTA_PATH"), gold_path=_req("GOLD_DELTA_PATH"))


@dataclass
class TrainingConfig:
    experiment_name: str
    label_col:       str
    feature_lookups: list  = field(default_factory=list)
    exclude_cols:    list  = field(default_factory=list)
    label_df:        Any   = None

    @classmethod
    def from_env(cls, spark: Any = None) -> "TrainingConfig":
        return cls(
            experiment_name=os.environ.get("MLFLOW_EXPERIMENT_NAME", "/mlops-demo/training"),
            label_col=      os.environ.get("LABEL_COL", "label"),
        )


@dataclass
class InferenceConfig:
    model_name:       str
    gold_path:        str
    predictions_path: str

    @classmethod
    def from_env(cls, spark: Any = None) -> "InferenceConfig":
        return cls(
            model_name=      _req("MODEL_NAME"),
            gold_path=       _req("GOLD_DELTA_PATH"),
            predictions_path=_req("PREDICTIONS_PATH"),
        )
