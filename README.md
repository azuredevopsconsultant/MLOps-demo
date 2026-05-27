# MLOps Demo — Databricks + AWS

End-to-end MLOps platform on Databricks with AWS S3 as the storage backbone, following best practices for production ML systems with built-in cost optimisations.

## Architecture

```
S3 Raw → Bronze (Delta) → Silver (Delta) → Gold (Delta) → Feature Store
                                                                ↓
                                               Training (MLflow + Hyperopt)
                                                                ↓
                                               MLflow Model Registry
                                                      ↙        ↘
                                      Batch Inference      Real-time Serving
                                              ↓
                                     Lakehouse Monitoring (drift detection)
```

## Stack

| Layer | Tool |
|---|---|
| Storage | AWS S3 + Delta Lake (medallion) |
| Compute | Databricks (Spark 3.5, Photon) |
| Orchestration | Databricks Workflows (DABs) |
| Feature store | Databricks Feature Store |
| Experiment tracking | MLflow |
| CI/CD | GitHub Actions + Databricks Asset Bundles |
| IaC | Terraform (S3, IAM, Cost Budgets) |
| Monitoring | Databricks Lakehouse Monitoring |

## Cost optimisations

| Area | Strategy | Saving |
|---|---|---|
| Compute | SPOT_WITH_FALLBACK @ 80% bid | ~60% vs on-demand |
| Compute | Shared instance pool (0 idle min) | Eliminates cold-start DBU waste |
| Compute | availableNow trigger on Auto Loader | Cluster runs only while backlog exists |
| Compute | Autoscaling 2→N (not fixed N) | Scales down when idle |
| Storage | S3 Intelligent Tiering | Auto-moves cold data to IA/Glacier |
| Storage | OPTIMIZE + VACUUM weekly | Compacts files; reclaims stale versions |
| Storage | MERGE instead of overwrite | Writes only changed rows |
| Storage | Z-ORDER on filter columns | 50-80% scan reduction → fewer DBUs |
| Storage | Dynamic partition overwrite | Only rewrites changed partitions |
| Infra | AWS Budget alerts at 80%/100% | No surprise bills |
| CI/CD | cancel-in-progress on PRs | No wasted Actions minutes |
| Training | SparkTrials parallelism=4 | Faster HPO → less cluster uptime |
| Scheduling | Off-peak windows (02:00-06:00 UTC) | Spot availability highest, rates lowest |

## Quick start

```bash
# 1 — install deps
make install

# 2 — set credentials
export DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
export DATABRICKS_TOKEN=your-token

# 3 — deploy to dev
make deploy-dev

# 4 — run training
make train

# 5 — run tests
make test
```

## Medallion layers & MLOps engineer responsibility

| Layer | Written by | Read by | MLOps owns? |
|---|---|---|---|
| Bronze | MLOps (Auto Loader job) | Silver transform | Yes |
| Silver | MLOps (transform job) | Feature engineering | Yes |
| Gold | MLOps (feature job) | Training, Inference | Yes |
| Feature Store | MLOps (feature store writer) | Data scientists (read-only) | Yes |
| Predictions | MLOps (inference job) | BI / downstream | Yes |

Data scientists consume `fs.create_training_set()` — they never touch Bronze or Silver directly.

## Environments

| Env | Branch | Cluster | SPOT? | Max workers |
|---|---|---|---|---|
| dev | feature/* | i3.xlarge, 2 workers | No (dev speed) | 4 |
| staging | staging | i3.2xlarge, autoscale | Yes | 8 |
| prod | main | i3.4xlarge, autoscale | Yes (80% bid) | 20 |
