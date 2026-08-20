# Model Quality, Fairness, and Bias Monitoring Design

## Overview

This document describes the automated evaluation framework for monitoring model
quality, fairness, and bias in the ASIWDP platform. The framework runs nightly
to assess model performance, compute fairness metrics across protected groups,
and enforce bias thresholds.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Nightly Scheduler (GitHub Actions)                │
│                              (runs at 2:00 AM UTC)                       │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Nightly Runner                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │ Load Validation │───▶│  Fetch Models   │───▶│ Run Evaluations │     │
│  │     Data        │    │  from MLflow    │    │                 │     │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
        ┌───────────────────┐ ┌───────────────┐ ┌───────────────────┐
        │ BiasMetricsRepo   │ │ AlertService  │ │  CI/CD Gate       │
        │ (PostgreSQL)      │ │ (Webhooks)    │ │  Integration      │
        └───────────────────┘ └───────────────┘ └───────────────────┘
```

## Components

### 1. BiasEvaluator (`bias_evaluator.py`)

Core evaluation engine that:
- Fetches production models from MLflow registry
- Loads validation data with protected attributes
- Computes fairness metrics per demographic group
- Aggregates metrics into a single bias index

### 2. BiasMetricsRepository (`db.py`)

PostgreSQL persistence layer for:
- Storing evaluation results for audit
- Querying historical trends
- Supporting CI/CD gate checks

### 3. AlertService (`alerts.py`)

Notification service that:
- Sends webhook alerts on threshold breaches
- Includes severity classification
- Reports worst disparities for investigation

### 4. CI/CD Gate (`cicd_gate.py`)

Pipeline integration that:
- Checks if models pass bias requirements
- Blocks promotion of biased models
- Provides JSON output for automation

## Fairness Metrics

The framework computes the following metrics for each protected attribute group:

| Metric | Formula | Description |
|--------|---------|-------------|
| Demographic Parity Difference | \|P(ŷ=1\|G=g) - P(ŷ=1)\| | Difference in positive prediction rate from overall rate |
| Equal Opportunity Difference | \|TPR_g - TPR_overall\| | Difference in true positive rate from overall TPR |
| Positive Rate | P(ŷ=1\|G=g) | Rate of positive predictions for group |
| True Positive Rate | P(ŷ=1\|y=1,G=g) | Recall for group |
| False Positive Rate | P(ŷ=1\|y=0,G=g) | FPR for group |

## Bias Index Calculation

The bias index aggregates individual metrics into a single score (0-1, lower is better):

```
bias_index = 0.4 × max_demographic_parity_diff
           + 0.4 × max_equal_opportunity_diff  
           + 0.2 × scaled_positive_rate_variance
```

The weights prioritize:
1. **Demographic Parity (40%)**: Ensures similar prediction rates across groups
2. **Equal Opportunity (40%)**: Ensures similar recall across groups
3. **Rate Variance (20%)**: Penalizes high variability in predictions

## Threshold Enforcement

The default bias threshold is **≤ 0.05** (configurable via `BIAS_THRESHOLD`).

When exceeded:
1. Result is flagged as `threshold_breached=True`
2. Alert is sent via configured webhook
3. Model promotion is blocked in CI/CD pipeline

## Protected Attributes

Default protected attributes (configurable):
- `gender`
- `age_group`
- `ethnicity`
- `disability_status`

## Database Schema

### bias_evaluation_results

| Column | Type | Description |
|--------|------|-------------|
| evaluation_id | UUID | Primary key |
| model_name | VARCHAR(255) | Model name from MLflow |
| model_version | VARCHAR(50) | Model version |
| evaluation_timestamp | TIMESTAMPTZ | When evaluation ran |
| bias_index | NUMERIC(10,6) | Aggregated bias score |
| threshold_breached | BOOLEAN | Whether threshold exceeded |
| overall_accuracy | NUMERIC(10,6) | Model accuracy |
| metadata | JSONB | Additional context |
| created_at | TIMESTAMPTZ | Record creation time |

### fairness_metrics

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| evaluation_id | UUID | FK to evaluation |
| attribute_name | VARCHAR(100) | Protected attribute name |
| group_value | VARCHAR(255) | Group value |
| sample_size | INTEGER | Samples in group |
| positive_rate | NUMERIC(10,6) | Positive prediction rate |
| true_positive_rate | NUMERIC(10,6) | TPR |
| false_positive_rate | NUMERIC(10,6) | FPR |
| demographic_parity_diff | NUMERIC(10,6) | DP difference |
| equal_opportunity_diff | NUMERIC(10,6) | EO difference |
| created_at | TIMESTAMPTZ | Record creation time |

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| BIAS_THRESHOLD | 0.05 | Maximum acceptable bias index |
| BIAS_PROTECTED_ATTRIBUTES | gender,age_group,ethnicity,disability_status | Comma-separated list |
| MLFLOW_TRACKING_URI | - | MLflow server URL |
| BIAS_MONITORING_DATABASE_URL | - | PostgreSQL connection string |
| BIAS_ALERT_ENABLED | true | Enable webhook alerts |
| BIAS_ALERT_WEBHOOK_URL | - | Alert webhook endpoint |

## Usage

### Nightly Evaluation

```bash
# Run with default settings
nightly-bias-eval /path/to/validation.parquet

# Dry run (no persistence)
nightly-bias-eval /path/to/validation.parquet --dry-run --verbose
```

### CI/CD Gate Check

```bash
# Check specific model
bias-gate-check skill-gap-predictor 2 --output-json

# Exit code: 0 = passed, 1 = failed
```

### Programmatic Usage

```python
from model_monitoring import BiasEvaluator, BiasMonitoringConfig

config = BiasMonitoringConfig.from_env()
evaluator = BiasEvaluator(config)

result = evaluator.evaluate_model(
    model_name="skill-gap-predictor",
    model_version="2",
    model_uri="models:/skill-gap-predictor/2",
    validation_data="data/validation.parquet",
)

if result.threshold_breached:
    print(f"Bias detected: {result.bias_index:.4f}")
```

## Alert Payload

```json
{
  "alert_type": "BIAS_THRESHOLD_BREACH",
  "severity": "HIGH",
  "model_name": "skill-gap-predictor",
  "model_version": "2",
  "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T02:30:00Z",
  "bias_index": 0.08,
  "threshold": 0.05,
  "overall_accuracy": 0.85,
  "worst_disparities": [
    {
      "attribute": "gender",
      "group": "F",
      "demographic_parity_diff": 0.15,
      "equal_opportunity_diff": 0.08
    }
  ],
  "message": "Model skill-gap-predictor v2 exceeded bias threshold..."
}
```

## Integration with Model Promotion

The bias gate is integrated into the model deployment pipeline:

1. **Training completes** → Model registered in MLflow
2. **Nightly evaluation** → Bias metrics computed and stored
3. **Promotion requested** → CI/CD workflow calls `bias-gate-check`
4. **Gate passes** → Model promoted to Production stage
5. **Gate fails** → Promotion blocked, alert sent

This ensures no model with bias exceeding the threshold can be deployed to production.
