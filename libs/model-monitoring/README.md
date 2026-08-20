# ASIWDP Model Monitoring Library

Automated bias and fairness monitoring for ML models in the AI-Powered Skills
Intelligence & Workforce Development Platform.

## Features

- **Bias Evaluation**: Compute fairness metrics (demographic parity, equal opportunity)
  across protected attribute groups
- **Bias Index Aggregation**: Aggregate metrics into a single bias index (0-1 scale)
- **Threshold Enforcement**: Configurable bias threshold (default ≤ 0.05)
- **MLflow Integration**: Fetch production models from MLflow registry
- **PostgreSQL Storage**: Persist evaluation results for audit and historical analysis
- **Alerting**: Webhook-based alerts for threshold breaches
- **CI/CD Integration**: Gate model promotion based on bias evaluation results

## Installation

```bash
# Core only
pip install -e .

# With MLflow support
pip install -e ".[mlflow]"

# With database support
pip install -e ".[db]"

# Full installation
pip install -e ".[full]"

# Development
pip install -e ".[dev]"
```

## Usage

### Configuration

Set environment variables:

```bash
export BIAS_THRESHOLD=0.05
export BIAS_PROTECTED_ATTRIBUTES=gender,age_group,ethnicity,disability_status
export MLFLOW_TRACKING_URI=http://mlflow:5000
export BIAS_MONITORING_DATABASE_URL=postgresql://user:pass@host:5432/db
export BIAS_ALERT_ENABLED=true
export BIAS_ALERT_WEBHOOK_URL=https://alerts.example.com/webhook
```

### Programmatic Usage

```python
from model_monitoring import BiasEvaluator, BiasMonitoringConfig, BiasMetricsRepository

# Load configuration
config = BiasMonitoringConfig.from_env()

# Initialize evaluator
evaluator = BiasEvaluator(config)

# Evaluate a specific model
result = evaluator.evaluate_model(
    model_name="skill-gap-predictor",
    model_version="1",
    model_uri="models:/skill-gap-predictor/1",
    validation_data="data/validation.parquet",
    target_column="target",
)

print(f"Bias Index: {result.bias_index:.4f}")
print(f"Threshold Breached: {result.threshold_breached}")

# Store results
repository = BiasMetricsRepository(config)
repository.save_evaluation_result(result)
```

### Nightly Evaluation

Run nightly evaluation for all production models:

```bash
nightly-bias-eval data/validation.parquet --target-column target
```

### CI/CD Gate Check

Check if a model passes the bias gate before promotion:

```bash
bias-gate-check skill-gap-predictor 2 --output-json
```

## Fairness Metrics

The framework computes the following metrics per protected attribute group:

| Metric | Description |
|--------|-------------|
| Demographic Parity | Difference in positive prediction rate from overall rate |
| Equal Opportunity | Difference in true positive rate from overall TPR |
| Positive Rate | Rate of positive predictions for the group |
| True Positive Rate | TPR for the group |
| False Positive Rate | FPR for the group |

## Bias Index Calculation

The bias index aggregates metrics using weighted combination:

```
bias_index = 0.4 * max_demographic_parity_diff
           + 0.4 * max_equal_opportunity_diff
           + 0.2 * scaled_positive_rate_variance
```

A bias index ≤ 0.05 is required for model promotion (configurable).

## Database Schema

The framework creates two tables:

- `bias_evaluation_results`: Main evaluation records
- `fairness_metrics`: Per-group fairness metrics

See `model_monitoring/db.py` for full schema.

## Testing

```bash
pytest tests/ -v
```

## License

Proprietary - ASIWDP Platform
