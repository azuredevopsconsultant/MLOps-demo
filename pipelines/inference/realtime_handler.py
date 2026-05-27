"""
Real-time scoring handler for Databricks Model Serving.

Loaded once at startup (load_context) and called per request (predict).
Stateless — safe for horizontal scaling.
"""
from __future__ import annotations

import mlflow

_model = None


def load_context(context):
    global _model
    _model = mlflow.pyfunc.load_model(context.artifacts["model"])


def predict(context, model_input):
    if _model is None:
        raise RuntimeError("Model not loaded — was load_context called?")
    return _model.predict(model_input)
