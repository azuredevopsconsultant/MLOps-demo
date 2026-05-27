.PHONY: install lint test test-unit test-dq train deploy-dev deploy-staging deploy-prod maintain clean

install:
	pip install -e ".[dev]" --quiet
	pre-commit install

lint:
	ruff check src/ pipelines/ tests/
	mypy src/ pipelines/ --ignore-missing-imports
	bandit -r src/ pipelines/ -ll -q

test:
	pytest tests/ -v --cov=src --cov=pipelines --cov-report=term-missing --cov-fail-under=80

test-unit:
	pytest tests/unit -v

test-dq:
	pytest tests/data_quality -v

# ── Databricks jobs ────────────────────────────────────────────
deploy-dev:
	databricks bundle deploy --target dev -C databricks/asset_bundles

deploy-staging:
	databricks bundle deploy --target staging -C databricks/asset_bundles

deploy-prod:
	databricks bundle deploy --target prod -C databricks/asset_bundles

train:
	databricks bundle run training_job --target dev -C databricks/asset_bundles

infer:
	databricks bundle run batch_inference_job --target dev -C databricks/asset_bundles

maintain:
	databricks bundle run maintenance_job --target prod -C databricks/asset_bundles

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true
