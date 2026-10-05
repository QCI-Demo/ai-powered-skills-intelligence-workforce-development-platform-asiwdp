# ASIWDP Bias Evaluator

Model fairness and bias evaluation framework for the AI-Powered Skills Intelligence
& Workforce Development Platform.

## Overview

This module provides automated evaluation of ML model fairness across protected
demographic groups. It integrates with MLflow for model registry access and writes
results to PostgreSQL for audit and monitoring.

## Features

- **MLflow Integration**: Fetch serving model endpoints from the MLflow registry
- **Fairness Metrics**: Compute demographic parity, equal opportunity, equalized odds
- **Bias Index**: Aggregate metrics into a single actionable bias index
- **PostgreSQL Storage**: Persist results for audit trails and alerting
- **Threshold Enforcement**: Flag models that exceed bias threshold (≤ 0.05)

## Installation

```bash
pip install -e "libs/bias-evaluator[dev]"
```

## Usage

### As a Python module

```python
from asiwdp_bias import BiasEvaluator, BiasConfig

config = BiasConfig.from_env()
evaluator = BiasEvaluator(config)

# Run evaluation for all registered models
results = evaluator.evaluate_all_models(
    validation_data_path="data/validation.parquet",
    protected_attributes=["gender", "age_group", "ethnicity"]
)

# Check for threshold breaches
for result in results:
    if result.bias_index > 0.05:
        print(f"ALERT: Model {result.model_name} exceeds bias threshold!")
```

### As CLI

```bash
# Run bias evaluation
bias-evaluator evaluate \
    --validation-data data/validation.parquet \
    --protected-attrs gender,age_group,ethnicity

# Check specific model
bias-evaluator evaluate \
    --model-name recommendation-ranker \
    --model-version 3
```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `MLFLOW_TRACKING_URI` | MLflow tracking server URI | `http://localhost:5000` |
| `BIAS_DB_HOST` | PostgreSQL host | `localhost` |
| `BIAS_DB_PORT` | PostgreSQL port | `5432` |
| `BIAS_DB_NAME` | Database name | `asiwdp_monitoring` |
| `BIAS_DB_USER` | Database user | - |
| `BIAS_DB_PASSWORD` | Database password | - |
| `BIAS_THRESHOLD` | Maximum acceptable bias index | `0.05` |

## Metrics

### Demographic Parity Difference
Measures if positive prediction rates are equal across groups.

```
DPD = max(P(ŷ=1|G=g)) - min(P(ŷ=1|G=g)) for all groups g
```

### Equal Opportunity Difference
Measures if true positive rates are equal across groups.

```
EOD = max(TPR(G=g)) - min(TPR(G=g)) for all groups g
```

### Equalized Odds Difference
Combines TPR and FPR differences across groups.

### Bias Index
Weighted aggregate of all fairness metrics, normalized to [0,1].

```
bias_index = 0.4 * DPD + 0.4 * EOD + 0.2 * equalized_odds
```

## Database Schema

Results are stored in `model_bias_evaluations` table:

```sql
CREATE TABLE model_bias_evaluations (
    id UUID PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    evaluation_timestamp TIMESTAMPTZ NOT NULL,
    protected_attribute VARCHAR(100) NOT NULL,
    demographic_parity_diff FLOAT,
    equal_opportunity_diff FLOAT,
    equalized_odds_diff FLOAT,
    bias_index FLOAT NOT NULL,
    threshold_breached BOOLEAN NOT NULL,
    sample_count INTEGER,
    group_metrics JSONB,
    tenant_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Testing

```bash
pytest libs/bias-evaluator/tests -v
```

## License

Proprietary - ASIWDP Platform
