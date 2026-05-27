# MLOps on Databricks — End-to-End Project

A production-grade MLOps pipeline implementing the full lifecycle for a **customer churn classifier** on Databricks + AWS.

## Architecture

```
Raw S3 → Bronze → Silver → Gold → Feature Store → Train → Registry → Serve → Monitor → Retrain
```

| Layer | Tool | What it does |
|-------|------|--------------|
| Ingestion | Databricks Autoloader | Incremental S3 → Delta Bronze |
| Quality   | Delta Live Tables     | DQ checks, Silver cleansing |
| Features  | Feature Engineering Client | Feature Store tables, time-travel |
| Training  | MLflow + sklearn      | Experiment tracking, autolog |
| Registry  | Unity Catalog Model Registry | Versioning, aliases, AUC gate |
| CI/CD     | GitHub Actions + Asset Bundles | lint → test → staging → prod |
| Serving   | Databricks Model Serving | REST endpoint, A/B, autoscale |
| Monitoring| Lakehouse Monitoring  | Drift alerts, auto-retrain trigger |

## Quick Start

### 1. Clone and set up
```bash
git clone https://github.com/YOUR_ORG/mlops-databricks
cd mlops-databricks
pip install -r requirements-dev.txt
```

### 2. Run unit tests locally
```bash
pytest tests/unit/ -v --cov=src
```

### 3. Configure GitHub secrets
In your GitHub repo → Settings → Secrets, add:
- `DATABRICKS_HOST_DEV` / `_STAGING` / `_PROD`
- `DATABRICKS_TOKEN_DEV` / `_STAGING` / `_PROD`
- `SLACK_WEBHOOK_URL` (optional)

### 4. Configure workspaces
Edit `databricks.yml` — set workspace hosts for each target environment.

### 5. Deploy to dev
```bash
databricks auth login
databricks bundle deploy --target dev
databricks bundle run data_ingestion_job --target dev
databricks bundle run feature_engineering_job --target dev
databricks bundle run model_training_job --target dev
```

## Branch → Environment Mapping

| Branch    | Environment | Trigger                       |
|-----------|-------------|-------------------------------|
| `dev`     | Development | Push (validate only)          |
| `staging` | Staging     | Merge → full staging pipeline |
| `main`    | Production  | Merge → requires manual approval |

## Project Structure

```
mlops-databricks/
├── databricks.yml                    ← Asset Bundle (jobs, experiments, serving)
├── requirements-dev.txt
├── src/
│   ├── data_ingestion/
│   │   ├── 01_bronze_ingestion.py    ← Autoloader → Bronze Delta
│   │   ├── 02_silver_cleansing.py    ← DQ checks → Silver Delta
│   │   └── 03_gold_aggregation.py    ← ML-ready Gold table
│   ├── feature_engineering/
│   │   └── 01_compute_features.py    ← Feature Store write + monitoring
│   ├── model_training/
│   │   ├── 01_train_model.py         ← MLflow training + autolog
│   │   └── 02_register_model.py      ← UC Model Registry + AUC gate
│   └── model_inference/
│       └── 01_batch_inference.py     ← Scheduled batch scoring
├── resources/
│   └── promote_model.py              ← Challenger → champion promotion
├── tests/
│   ├── unit/
│   │   └── test_pipeline.py          ← Pure Python, no cluster needed
│   └── integration/                  ← Runs against staging cluster
└── .github/workflows/
    └── mlops_cicd.yml                ← Full CI/CD pipeline
```

## Key Best Practices Implemented

- **AUC gate** in registration: model blocked if AUC < 0.75
- **Challenger/champion** aliasing with automated promotion
- **Feature consistency**: same Feature Store lookup at training and inference
- **Data quality threshold**: pipeline fails if DQ failure rate > 5%
- **Environment isolation**: dev / staging / prod Unity Catalog catalogs
- **Blue-green deployment**: configured in Asset Bundle serving endpoint
- **Manual approval gate**: GitHub environment protection on `production`
