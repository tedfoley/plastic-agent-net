-- PlasticAgentNet: Row-Level Security policies
-- Public read on all tables, service role write

-- Enable RLS on all tables
ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE controller_actions ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Public read: anyone with anon key can SELECT
-- ============================================================
CREATE POLICY "public_read_episodes" ON episodes
    FOR SELECT USING (true);

CREATE POLICY "public_read_nodes" ON nodes
    FOR SELECT USING (true);

CREATE POLICY "public_read_edges" ON edges
    FOR SELECT USING (true);

CREATE POLICY "public_read_artifacts" ON artifacts
    FOR SELECT USING (true);

CREATE POLICY "public_read_messages" ON messages
    FOR SELECT USING (true);

CREATE POLICY "public_read_events" ON events
    FOR SELECT USING (true);

CREATE POLICY "public_read_controller_actions" ON controller_actions
    FOR SELECT USING (true);

-- ============================================================
-- Service role write: only service_role can INSERT/UPDATE/DELETE
-- (service_role bypasses RLS by default, but explicit policies
--  make intent clear and support future role changes)
-- ============================================================
CREATE POLICY "service_write_episodes" ON episodes
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_write_nodes" ON nodes
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_write_edges" ON edges
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_write_artifacts" ON artifacts
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_write_messages" ON messages
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_write_events" ON events
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_write_controller_actions" ON controller_actions
    FOR ALL USING (auth.role() = 'service_role');
