-- Pipeline persistence schema (PostgreSQL 16+)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS modernization_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_code TEXT NOT NULL,
    generated_code TEXT,
    report JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failure', 'partial')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_modernization_history_created_at
    ON modernization_history (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_modernization_history_status
    ON modernization_history (status);

CREATE TABLE IF NOT EXISTS pipeline_evaluation_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    history_id UUID REFERENCES modernization_history(id) ON DELETE SET NULL,
    metric_name VARCHAR(64) NOT NULL,
    metric_value NUMERIC(12, 4) NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_evaluation_scores_history
    ON pipeline_evaluation_scores (history_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_evaluation_scores_metric
    ON pipeline_evaluation_scores (metric_name, created_at DESC);
