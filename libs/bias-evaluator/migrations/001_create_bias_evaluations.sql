-- Bias Evaluation Schema Migration
-- Creates the model_bias_evaluations table for storing fairness audit results

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS public;

-- Create the model_bias_evaluations table
CREATE TABLE IF NOT EXISTS public.model_bias_evaluations (
    id UUID PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    model_stage VARCHAR(50),
    evaluation_timestamp TIMESTAMPTZ NOT NULL,
    overall_bias_index FLOAT NOT NULL,
    threshold FLOAT NOT NULL,
    threshold_breached BOOLEAN NOT NULL,
    total_samples INTEGER NOT NULL,
    protected_attributes JSONB NOT NULL,
    attribute_evaluations JSONB NOT NULL,
    tenant_id VARCHAR(100),
    run_id VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_bias_eval_model_name 
    ON public.model_bias_evaluations(model_name);

CREATE INDEX IF NOT EXISTS idx_bias_eval_timestamp 
    ON public.model_bias_evaluations(evaluation_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_bias_eval_threshold_breached 
    ON public.model_bias_evaluations(threshold_breached);

CREATE INDEX IF NOT EXISTS idx_bias_eval_tenant_id 
    ON public.model_bias_evaluations(tenant_id);

CREATE INDEX IF NOT EXISTS idx_bias_eval_model_version 
    ON public.model_bias_evaluations(model_name, model_version);

-- Add comments for documentation
COMMENT ON TABLE public.model_bias_evaluations IS 
    'Stores ML model fairness and bias evaluation results for audit and monitoring';

COMMENT ON COLUMN public.model_bias_evaluations.overall_bias_index IS 
    'Aggregated bias index across all protected attributes (0-1 scale)';

COMMENT ON COLUMN public.model_bias_evaluations.threshold IS 
    'Maximum acceptable bias index at time of evaluation';

COMMENT ON COLUMN public.model_bias_evaluations.threshold_breached IS 
    'True if overall_bias_index exceeds threshold';

COMMENT ON COLUMN public.model_bias_evaluations.attribute_evaluations IS 
    'Per-protected-attribute breakdown with group metrics';
