-- PlasticAgentNet: Initial schema for Supabase Postgres
-- Tables: episodes, nodes, edges, artifacts, messages, events, controller_actions

-- ============================================================
-- updated_at trigger function
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- episodes
-- ============================================================
CREATE TABLE episodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task            TEXT NOT NULL,
    repo_path       TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','completed','failed')),
    budget_config   JSONB NOT NULL DEFAULT '{}',
    rounds_completed INT NOT NULL DEFAULT 0,
    tokens_used     INT NOT NULL DEFAULT 0,
    branch_scores   JSONB NOT NULL DEFAULT '{}',
    terminated_reason TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_episodes_status ON episodes (status);
CREATE INDEX idx_episodes_created ON episodes (created_at DESC);

CREATE TRIGGER episodes_updated_at
    BEFORE UPDATE ON episodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- nodes
-- ============================================================
CREATE TABLE nodes (
    id              TEXT PRIMARY KEY,
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    template        TEXT NOT NULL,
    persona         JSONB NOT NULL DEFAULT '{}',
    model_tier      TEXT NOT NULL DEFAULT 'haiku',
    branch_id       TEXT NOT NULL DEFAULT 'main',
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','done','pruned','merged')),
    round_created   INT NOT NULL DEFAULT 0,
    rounds_active   INT NOT NULL DEFAULT 0,
    tokens_used     INT NOT NULL DEFAULT 0,
    contribution_score FLOAT NOT NULL DEFAULT 0.0,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_nodes_episode ON nodes (episode_id);
CREATE INDEX idx_nodes_branch ON nodes (episode_id, branch_id);
CREATE INDEX idx_nodes_status ON nodes (episode_id, status);

CREATE TRIGGER nodes_updated_at
    BEFORE UPDATE ON nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- edges
-- ============================================================
CREATE TABLE edges (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    source_node     TEXT NOT NULL,
    target_node     TEXT NOT NULL,
    weight          FLOAT NOT NULL DEFAULT 1.0,
    message_types   JSONB NOT NULL DEFAULT '[]',
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_edges_episode ON edges (episode_id);
CREATE INDEX idx_edges_source ON edges (episode_id, source_node);
CREATE INDEX idx_edges_target ON edges (episode_id, target_node);
CREATE UNIQUE INDEX idx_edges_unique ON edges (episode_id, source_node, target_node);

CREATE TRIGGER edges_updated_at
    BEFORE UPDATE ON edges
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- artifacts
-- ============================================================
CREATE TABLE artifacts (
    id              TEXT PRIMARY KEY,
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    artifact_type   TEXT NOT NULL,
    producer_node   TEXT NOT NULL DEFAULT '',
    branch_id       TEXT NOT NULL DEFAULT 'main',
    round_produced  INT NOT NULL DEFAULT 0,
    content         JSONB NOT NULL DEFAULT '{}',
    summary         TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_artifacts_episode ON artifacts (episode_id);
CREATE INDEX idx_artifacts_branch ON artifacts (episode_id, branch_id);
CREATE INDEX idx_artifacts_type ON artifacts (episode_id, artifact_type);
CREATE INDEX idx_artifacts_producer ON artifacts (episode_id, producer_node);

-- ============================================================
-- messages
-- ============================================================
CREATE TABLE messages (
    id              TEXT PRIMARY KEY,
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    message_type    TEXT NOT NULL,
    sender          TEXT NOT NULL DEFAULT '',
    receiver        TEXT NOT NULL DEFAULT '',
    payload         JSONB NOT NULL DEFAULT '{}',
    round_sent      INT NOT NULL DEFAULT 0,
    ttl             INT NOT NULL DEFAULT 3,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_episode ON messages (episode_id);
CREATE INDEX idx_messages_receiver ON messages (episode_id, receiver);

-- ============================================================
-- events (append-only log)
-- ============================================================
CREATE TABLE events (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    round           INT,
    payload         JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_events_episode ON events (episode_id);
CREATE INDEX idx_events_type ON events (episode_id, event_type);
CREATE INDEX idx_events_created ON events (episode_id, created_at);

-- ============================================================
-- controller_actions
-- ============================================================
CREATE TABLE controller_actions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    action_type     TEXT NOT NULL,
    target_node     TEXT NOT NULL DEFAULT '',
    payload         JSONB NOT NULL DEFAULT '{}',
    reason          TEXT NOT NULL DEFAULT '',
    round           INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ctrl_actions_episode ON controller_actions (episode_id);
CREATE INDEX idx_ctrl_actions_round ON controller_actions (episode_id, round);

-- ============================================================
-- Enable Realtime on key tables
-- ============================================================
ALTER PUBLICATION supabase_realtime ADD TABLE episodes;
ALTER PUBLICATION supabase_realtime ADD TABLE nodes;
ALTER PUBLICATION supabase_realtime ADD TABLE edges;
ALTER PUBLICATION supabase_realtime ADD TABLE artifacts;
ALTER PUBLICATION supabase_realtime ADD TABLE events;
ALTER PUBLICATION supabase_realtime ADD TABLE controller_actions;
