-- PlasticAgentNet: Postgres scoring function
-- Mirrors Python control/scoring.py compute_branch_score()

CREATE OR REPLACE FUNCTION compute_branch_score(
    p_episode_id UUID,
    p_branch_id TEXT,
    p_current_round INT
) RETURNS FLOAT AS $$
DECLARE
    verif_score FLOAT := 0.0;
    avg_contrib FLOAT := 0.0;
    node_count INT := 0;
BEGIN
    -- Latest verification score for this branch
    SELECT COALESCE((content->>'overall_score')::FLOAT, 0.0)
    INTO verif_score
    FROM artifacts
    WHERE episode_id = p_episode_id
      AND branch_id = p_branch_id
      AND artifact_type = 'verification'
    ORDER BY round_produced DESC
    LIMIT 1;

    -- Average node contribution on this branch
    SELECT COALESCE(AVG(contribution_score), 0.0), COUNT(*)
    INTO avg_contrib, node_count
    FROM nodes
    WHERE episode_id = p_episode_id
      AND branch_id = p_branch_id
      AND status NOT IN ('pruned', 'merged');

    IF node_count = 0 THEN
        RETURN 0.0;
    END IF;

    -- Weighted: 70% verification, 30% average contribution
    RETURN 0.7 * COALESCE(verif_score, 0.0) + 0.3 * avg_contrib;
END;
$$ LANGUAGE plpgsql STABLE;
