-- Create tower_anomaly_scores table for GNN link prediction results
-- This stores per-tower anomaly scores without modifying the existing towers table

CREATE TABLE IF NOT EXISTS tower_anomaly_scores (
    id SERIAL PRIMARY KEY,
    tower_id INTEGER NOT NULL REFERENCES towers(id) ON DELETE CASCADE,

    -- Model run metadata
    model_version VARCHAR(50) NOT NULL DEFAULT 'gnn-link-pred-v1',
    run_id VARCHAR(100),  -- e.g., 'gnn-link-pred-knn15-20251209'

    -- Anomaly scores (0-1 range, higher = more anomalous)
    anomaly_score REAL NOT NULL,  -- Combined score
    link_pred_error REAL,  -- How poorly the model predicts this tower's edges
    neighbor_inconsistency REAL,  -- How different this tower is from neighbors

    -- Percentile for quick filtering
    percentile REAL,  -- 0-100, computed after import

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Ensure one score per tower per model version
    UNIQUE(tower_id, model_version)
);

-- Index for fast geospatial queries via tower join
CREATE INDEX IF NOT EXISTS idx_anomaly_tower_id ON tower_anomaly_scores(tower_id);

-- Index for filtering by score
CREATE INDEX IF NOT EXISTS idx_anomaly_score ON tower_anomaly_scores(anomaly_score DESC);

-- Index for filtering by percentile
CREATE INDEX IF NOT EXISTS idx_anomaly_percentile ON tower_anomaly_scores(percentile DESC);

-- Index for model version queries
CREATE INDEX IF NOT EXISTS idx_anomaly_model_version ON tower_anomaly_scores(model_version);

-- Comment on table
COMMENT ON TABLE tower_anomaly_scores IS 'GNN-based anomaly scores for towers. Higher scores indicate unusual network topology patterns that may warrant investigation.';

COMMENT ON COLUMN tower_anomaly_scores.anomaly_score IS 'Combined anomaly score (0-1). Higher = more anomalous. Computed as 0.6*link_pred_error + 0.4*neighbor_inconsistency';
COMMENT ON COLUMN tower_anomaly_scores.link_pred_error IS 'How poorly the GNN predicts edges for this tower. High values may indicate missing connections.';
COMMENT ON COLUMN tower_anomaly_scores.neighbor_inconsistency IS 'How different this tower is from its spatial neighbors in embedding space.';
COMMENT ON COLUMN tower_anomaly_scores.percentile IS 'Percentile rank (0-100). A score of 95 means this tower is more anomalous than 95% of towers.';
