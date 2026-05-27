# MLOps Databricks — End-to-End Execution Order

## Overview

```
PHASE 0  Infrastructure (Terraform + Workspace Admin) ← ONE-TIME SETUP
PHASE 1  Unity Catalog Bootstrap                      ← ONE-TIME PER ENV
PHASE 2  Governance (RBAC + Access Controls)          ← ONE-TIME, RE-RUN ON CHANGE
PHASE 3  First Data Load (Bronze → Silver → Gold)     ← FIRST RUN, THEN DAILY
PHASE 4  Feature Engineering                          ← FIRST RUN, THEN DAILY
PHASE 5  EDA & AutoML Baseline (optional)             ← MANUAL, EXPLORATORY
PHASE 6  Model Training → Register → Validate         ← FIRST RUN, THEN TRIGGERED
PHASE 7  Promote Model to Champion                    ← AFTER TRAINING PASSES
PHASE 8  Batch Inference                              ← DAILY (automated)
PHASE 9  Enable Scheduled Operations                  ← TURN ON AFTER PHASE 7
```

---

## PHASE 0 — Infrastructure (Terraform)

> **Who runs this:** Platform engineer / DevOps  
> **When:** Once per environment (dev / staging / prod)  
> **Where:** Your local machine or CI/CD runner — NOT in Databricks

### Step 0.1 — Configure Terraform variables

```bash
cd infrastructure/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with real values:
#   environment         = "staging"   # or "dev" / "prod"
#   aws_region          = "us-east-1"
#   databricks_host     = "https://adb-xxx.azuredatabricks.net"
#   databricks_token    = "<personal-access-token>"
#   databricks_account_id = "<account-id>"
#   metastore_id        = "<uc-metastore-id>"
```

### Step 0.2 — Provision AWS + Databricks resources

```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

**Resources created:**
- S3 buckets: `raw-data`, `processed-data`, `model-artifacts`
- IAM role for Unity Catalog credential passthrough
- DynamoDB table for Delta Lake S3 locking
- Unity Catalog: storage credential, external locations, catalog, schema

### Step 0.3 — Note Terraform outputs (needed in later steps)

```bash
terraform output
# delta_dynamodb_table → update databricks.yml variables.delta_dynamodb_table
# catalog_name         → confirms catalog was created
# raw_data_bucket      → used in 01_bronze_ingestion.py S3 path
```

---

## PHASE 1 — Unity Catalog Bootstrap

> **Who runs this:** Platform engineer (workspace admin role required)  
> **When:** Once per environment, AFTER Terraform apply  
> **Where:** Databricks workspace — run as a notebook or job

### Step 1.1 — Run the bootstrap notebook

**Option A — Interactive (recommended for first-time):**
1. Upload `src/setup/00_unity_catalog_bootstrap.py` to your workspace
2. Open notebook → click **Run All**
3. Set widgets: `catalog=dev_catalog`, `schema=mlops_demo`, `owner_group=mlops-platform-admins`

**Option B — Via Databricks CLI:**
```bash
databricks jobs create --json '{
  "name": "Bootstrap UC",
  "new_cluster": {"spark_version":"15.4.x-ml-scala2.12","node_type_id":"m5.large","num_workers":0},
  "notebook_task": {"notebook_path": "/Repos/mlops-demo/dev/src/setup/00_unity_catalog_bootstrap.py",
    "base_parameters": {"catalog":"dev_catalog","schema":"mlops_demo","owner_group":"mlops-platform-admins"}}
}'
databricks jobs run-now --job-id <id>
```

**What it creates:**
- Catalog: `dev_catalog` / `staging_catalog` / `prod_catalog`
- Schema: `mlops_demo`
- All 9 Delta tables pre-created with correct schemas + TBLPROPERTIES:
  - `bronze_customers` — raw ingested data
  - `silver_customers` — cleansed, quality-gated
  - `gold_customers_ml` — ML-ready features + labels
  - `churn_predictions` — daily batch predictions
  - `model_monitoring_log` — drift & performance results
  - `operational_monitoring_log` — job stats & costs
  - `serving_health_log` — endpoint latency probes
  - `retraining_trigger_log` — retraining events

### Step 1.2 — Verify bootstrap succeeded

```sql
-- Run in a Databricks SQL warehouse
SHOW TABLES IN dev_catalog.mlops_demo;
-- Should return 8 rows (all tables from step above)

DESCRIBE CATALOG dev_catalog;
-- Should show owner = mlops-platform-admins
```

---

## PHASE 2 — Governance (RBAC + Access Controls)

> **When:** After Phase 1, and any time group membership changes  
> **Databricks job:** `governance_job`

### Step 2.1 — Deploy the bundle (first time only)

```bash
# Authenticate CLI
export DATABRICKS_HOST=https://adb-xxx.azuredatabricks.net
export DATABRICKS_TOKEN=<pat>

# Validate the bundle config
databricks bundle validate -t dev

# Deploy jobs (registers all 11 jobs in the workspace)
databricks bundle deploy -t dev
```

### Step 2.2 — Run governance job

```bash
databricks bundle run governance_job -t dev
```

**What it does (2 tasks in sequence):**
1. `scim_provisioning` — creates RBAC groups, displays SCIM endpoint for IdP config
2. `delta_access_controls` — applies table-level GRANT SQL DDL:
   - Bronze: platform-admins + ml-engineers only (PII before masking)
   - Silver: ml-engineers read/write, data-scientists read
   - Gold: all groups read, ml-engineers write
   - Predictions: all groups read, ml-engineers write

**Verify grants:**
```sql
SHOW GRANTS ON CATALOG dev_catalog;
SHOW GRANTS ON TABLE dev_catalog.mlops_demo.bronze_customers;
```

---

## PHASE 3 — Data Ingestion (Bronze → Silver → Gold)

> **When:** After Phase 2 — first run to populate tables, then automated daily  
> **Databricks job:** `data_ingestion_job`  
> **Schedule (automated):** 05:00 UTC daily (set in batch_inference_job upstream trigger)

### Step 3.1 — Verify raw data is in S3

```bash
aws s3 ls s3://mlops-dev-<account_id>-raw-data/ --recursive | head -20
# Expect CSV files from your source system
```

### Step 3.2 — Run ingestion pipeline

```bash
databricks bundle run data_ingestion_job -t dev
```

**Task execution order (sequential, shared cluster):**

| Order | Task | Notebook | Output Table |
|-------|------|----------|-------------|
| 1st | `bronze_ingestion` | `01_bronze_ingestion.py` | `bronze_customers` |
| 2nd | `silver_cleansing` | `02_silver_cleansing.py` | `silver_customers` |
| 3rd | `gold_aggregation` | `03_gold_aggregation.py` | `gold_customers_ml` |

**Verify row counts after run:**
```sql
SELECT 'bronze' AS layer, COUNT(*) AS rows FROM dev_catalog.mlops_demo.bronze_customers
UNION ALL
SELECT 'silver', COUNT(*) FROM dev_catalog.mlops_demo.silver_customers
UNION ALL
SELECT 'gold',   COUNT(*) FROM dev_catalog.mlops_demo.gold_customers_ml;
-- silver should be ≥ 95% of bronze (DQ gate drops < 5%)
-- gold should equal silver (MERGE, all rows preserved)
```

**Check Gold table has required columns for training:**
```sql
DESCRIBE dev_catalog.mlops_demo.gold_customers_ml;
-- Must include: customer_id, label, spend_12m_avg, region_encoded, tier_encoded
```

---

## PHASE 4 — Feature Engineering

> **When:** After Phase 3 (Gold table populated)  
> **Databricks job:** `feature_engineering_job`

### Step 4.1 — Run feature engineering

```bash
databricks bundle run feature_engineering_job -t dev
```

**What it does:**
1. Reads `gold_customers_ml`
2. Computes 10 numeric features + timestamp
3. Writes to Feature Store table: `dev_catalog.mlops_demo.customer_churn_features`
4. Syncs Online Table: `customer_churn_features_online` (for real-time serving)
5. Runs OPTIMIZE + Z-ORDER on the feature table
6. Creates Lakehouse Monitor (drift detection baseline)

**Verify Feature Store:**
```sql
SELECT * FROM dev_catalog.mlops_demo.customer_churn_features LIMIT 5;
-- Must have: customer_id, feature_timestamp, tenure_months, monthly_spend, ... (10 features)
SELECT COUNT(DISTINCT customer_id) FROM dev_catalog.mlops_demo.customer_churn_features;
-- Should match gold row count
```

---

## PHASE 5 — EDA & AutoML Baseline (Optional)

> **When:** Before first training run, or when investigating data quality issues  
> **Databricks job:** `eda_job` — MANUAL TRIGGER ONLY (no schedule)

### Step 5.1 — Run EDA

```bash
databricks bundle run eda_job -t dev
```

**Task execution order:**
1. `exploratory_analysis` — class balance, null rates, feature correlations → logged to MLflow
2. `automl_baseline` — runs 10 AutoML trials, finds best hyperparameters → compare vs manual model

**View results in MLflow:**
```
Databricks UI → Experiments → /Shared/mlops-demo/dev/eda-analysis
Databricks UI → Experiments → /Shared/mlops-demo/dev/automl-baseline
```

**When to use:** If AutoML finds a significantly better model, copy its hyperparameters into `src/model_training/01_train_model.py` before running Phase 6.

---

## PHASE 6 — Model Training Pipeline (Databricks Recommended MLOps Workflow)

> **When:** After Phase 4 (features ready)  
> **Databricks job:** `model_training_job`  
> **Follows:** Databricks recommended workflow — Train & Tune → Evaluate → Compliance → Pre-deploy → Deploy

### Step 6.1 — Run training pipeline

```bash
databricks bundle run model_training_job -t dev
```

**Task execution order (5 tasks — matches diagram exactly):**

| Step | Task | Notebook | Diagram Label | What It Does |
|------|------|----------|---------------|-------------|
| 1 | `train_model` | `01_train_model.py` | Training and tuning + Evaluation | GBM train, MLflow autolog, SHAP, model card |
| 2 | `register_model` | `02_register_model.py` | (registration) | Register to UC Registry, tags compliance_status=PENDING_REVIEW |
| 3 | `compliance_check` | `03_compliance_check.py` | **Compliance checks** | Bias/fairness, prohibited features, SHAP present, parity gate |
| 4 | `validate_model` | `02_model_validation.py` | **Pre-deployment checks** | AUC/precision/recall gate on held-out validation set |
| 5 | `deploy_to_dev` | `04_deploy_to_dev.py` | **Deploy to dev** | Set challenger alias, create/update serving endpoint |

**On any gate failure:** Pipeline stops. The failed task updates the model version tag (`compliance_status=COMPLIANCE_FAILED` or `model_validation_status=FAILED`) for full audit trail. Fix the issue and re-run.

**Quality gates:**

| Gate | Dev/Staging | Prod |
|------|-------------|------|
| AUC | ≥ 0.75 | ≥ 0.78 |
| Precision | ≥ 0.60 | ≥ 0.62 |
| Recall | ≥ 0.55 | ≥ 0.57 |
| Performance parity gap | ≤ 0.10 | ≤ 0.08 |
| Required UC tags | All 10 tags | All 10 tags |
| SHAP artifacts | Must exist | Must exist |

**Check training results:**
```bash
# View in Databricks UI:
# Experiments → /Shared/mlops-demo/dev/churn-experiment → latest run
# Models → dev_catalog.mlops_demo.churn_classifier → latest version tags:
#   compliance_status      = APPROVED
#   model_validation_status = PASSED
#   deployment_stage       = DEPLOYED_TO_ENV
#   val_auc                = 0.82xx (or similar)

# Check model version tags via CLI
databricks models get-version --name dev_catalog.mlops_demo.churn_classifier --version 1
```

---

## PHASE 7 — Promote Model to Champion

> **When:** After Phase 6 validation passes  
> **Script:** `resources/promote_model.py`

### Step 7.1 — Run model promotion

```bash
python resources/promote_model.py \
  --catalog dev_catalog \
  --schema mlops_demo \
  --model-name churn_classifier
```

**What it does:**
1. Gets AUC from MLflow for challenger and champion (if exists)
2. If no champion OR challenger AUC > champion AUC → sets "champion" alias on challenger version
3. Prints decision: `PROMOTED` or `SKIPPED (champion retained)`

**Verify champion alias:**
```sql
-- In Databricks SQL
SHOW MODEL ALIASES FOR MODEL dev_catalog.mlops_demo.churn_classifier;
-- Should show: champion → version N, challenger → version N
```

---

## PHASE 8 — Batch Inference

> **When:** After Phase 7 (champion alias set)  
> **Databricks job:** `batch_inference_job`  
> **Schedule (automated):** 06:00 UTC daily

### Step 8.1 — First manual run

```bash
databricks bundle run batch_inference_job -t dev
```

**What it does:**
1. Loads model via `models:/{catalog}.{schema}.churn_classifier@champion`
2. Calls `FeatureEngineeringClient.score_batch()` — pulls features from Feature Store
3. Writes predictions to `churn_predictions` with columns:
   - `churn_probability` (0.0–1.0)
   - `churn_label` (0 or 1, threshold=0.5)
   - `risk_tier` (high/medium/low)

**Verify predictions:**
```sql
SELECT risk_tier, COUNT(*) AS customers, AVG(churn_probability) AS avg_prob
FROM dev_catalog.mlops_demo.churn_predictions
GROUP BY risk_tier
ORDER BY avg_prob DESC;
-- high tier should have avg_prob > 0.7
-- low  tier should have avg_prob < 0.3
```

---

## PHASE 9 — Enable Scheduled Operations

> **When:** After Phase 8 succeeds on first run  
> **Action:** All scheduled jobs are already defined in `databricks.yml` — they just need the workspace schedules activated

### Step 9.1 — Deploy to staging/prod

```bash
# Staging
databricks bundle deploy -t staging

# Production (requires manual approval in GitHub Actions)
git push origin main   # triggers GitHub Actions deploy-production workflow
```

### Step 9.2 — Automated daily schedule (all run in UTC)

| Time  | Job | Purpose |
|-------|-----|---------|
| 05:00 | (upstream data arrives in S3) | Your source system writes CSVs |
| 06:00 | `batch_inference_job` → runs daily if `data_ingestion_job` has run | Score champion model |
| 07:00 | `monitoring_job` | Drift + performance + freshness checks |
| 07:30 | `operational_monitoring_job` | Job stats + DBU costs |
| 08:00 | `trigger_retraining_job` | Check monitoring_log → trigger training if drift |
| Hourly | `serving_health_job` | Endpoint latency probe + auto-failover |
| Mon 02:00 | `scheduled_retraining_job` | Weekly full pipeline retraining |

> **Note:** `data_ingestion_job` has no schedule — trigger it before `batch_inference_job` by either adding an upstream trigger or scheduling it at 05:15 UTC.

### Step 9.3 — Add ingestion schedule to databricks.yml (if needed)

```yaml
# In databricks.yml, under data_ingestion_job
schedule:
  quartz_cron_expression: "0 15 5 * * ?"  # 05:15 UTC — before inference at 06:00
  timezone_id: "UTC"
```

---

## CI/CD Deployment Flow (GitHub Actions)

```
Push to dev    → unit tests + bundle validate
Push to staging → deploy staging + full pipeline + integration tests
Push to main   → manual approval → deploy prod + full pipeline + promote model + Slack
```

### Set GitHub Secrets before first CI/CD run:

```
DATABRICKS_HOST_DEV        = https://adb-xxx.azuredatabricks.net
DATABRICKS_TOKEN_DEV       = dapixxx
DATABRICKS_HOST_STAGING    = https://adb-yyy.azuredatabricks.net
DATABRICKS_TOKEN_STAGING   = dapixxx
DATABRICKS_HOST_PROD       = https://adb-zzz.azuredatabricks.net
DATABRICKS_TOKEN_PROD      = dapixxx
SLACK_WEBHOOK_URL          = https://hooks.slack.com/services/...   (optional)
```

---

## Environment-by-Environment Deployment Checklist

### Dev
- [ ] Phase 0: `terraform apply -var environment=dev`
- [ ] Phase 1: Run `00_unity_catalog_bootstrap.py` (catalog=dev_catalog)
- [ ] Phase 2: `databricks bundle deploy -t dev` → run `governance_job`
- [ ] Phase 3: Run `data_ingestion_job -t dev`
- [ ] Phase 4: Run `feature_engineering_job -t dev`
- [ ] Phase 6: Run `model_training_job -t dev`
- [ ] Phase 7: `python resources/promote_model.py --catalog dev_catalog ...`
- [ ] Phase 8: Run `batch_inference_job -t dev`

### Staging
- [ ] Phase 0: `terraform apply -var environment=staging`
- [ ] Phase 1: Run bootstrap (catalog=staging_catalog)
- [ ] Phase 2: `databricks bundle deploy -t staging` → run `governance_job`
- [ ] Phases 3–8: Run all jobs via staging CI/CD or manual CLI with `-t staging`
- [ ] Run integration tests: `pytest tests/integration/ -v`

### Production
- [ ] Phase 0: `terraform apply -var environment=prod`
- [ ] Phase 1: Run bootstrap (catalog=prod_catalog)
- [ ] Phase 2: Governance (run manually before first CI/CD deploy)
- [ ] Push to `main` branch → GitHub Actions handles Phases 3–7 automatically
- [ ] Verify Slack notification received
- [ ] Verify `churn_predictions` populated in `prod_catalog`

---

## Troubleshooting Quick Reference

| Symptom | Check |
|---------|-------|
| Bronze ingestion fails | S3 external location accessible? `SHOW EXTERNAL LOCATIONS` |
| Silver DQ gate fails | > 5% null customer_id or out-of-range age/spend in bronze |
| Gold MERGE fails on first run | Expected — gold table doesn't exist yet, auto-creates |
| Feature Store write fails | Feature table schema mismatch — DROP and recreate |
| Training AUC < threshold | Check gold label balance: `SELECT AVG(label) FROM gold_customers_ml` |
| Model alias not found | Run `promote_model.py` after training passes validation |
| Inference fails "model not found" | champion alias not set — run Phase 7 first |
| Monitoring job no baseline | First monitoring run creates baseline — no drift alerts on day 1 |
| Serving health fails | endpoint not deployed yet — check model_serving_endpoints in workspace |
