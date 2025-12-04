-- ============================================================================
-- FIX: Reduce max_tokens for agents to prevent context length errors
-- ============================================================================
-- Issue: Agents configured with max_tokens=4000 cause context length errors
--        when combined with large inputs (actor outputs for critic agent)
--
-- Solution: Reduce max_tokens to reasonable values:
--   - Actor agents: 2500 tokens (allows more input context)
--   - Critic agent: 2000 tokens (receives large inputs from actors)
--   - QA agents: 2000 tokens (receives large inputs for analysis)
--
-- Date: 2025-11-10
-- Version: 1.1
-- ============================================================================

-- Update Actor Agent max_tokens
UPDATE compliance_agents
SET
    max_tokens = 2500,
    updated_at = CURRENT_TIMESTAMP
WHERE
    agent_type = 'actor'
    AND is_system_default = TRUE;

-- Update Critic Agent max_tokens (most critical - receives large inputs)
UPDATE compliance_agents
SET
    max_tokens = 2000,
    updated_at = CURRENT_TIMESTAMP
WHERE
    agent_type = 'critic'
    AND is_system_default = TRUE;

-- Update Contradiction Detection Agent max_tokens
UPDATE compliance_agents
SET
    max_tokens = 2000,
    updated_at = CURRENT_TIMESTAMP
WHERE
    agent_type = 'contradiction'
    AND is_system_default = TRUE;

-- Update Gap Analysis Agent max_tokens
UPDATE compliance_agents
SET
    max_tokens = 2000,
    updated_at = CURRENT_TIMESTAMP
WHERE
    agent_type = 'gap_analysis'
    AND is_system_default = TRUE;

-- Verification
DO $$
DECLARE
    actor_tokens INTEGER;
    critic_tokens INTEGER;
    contradiction_tokens INTEGER;
    gap_tokens INTEGER;
BEGIN
    SELECT max_tokens INTO actor_tokens
    FROM compliance_agents
    WHERE agent_type = 'actor' AND is_system_default = TRUE
    LIMIT 1;

    SELECT max_tokens INTO critic_tokens
    FROM compliance_agents
    WHERE agent_type = 'critic' AND is_system_default = TRUE
    LIMIT 1;

    SELECT max_tokens INTO contradiction_tokens
    FROM compliance_agents
    WHERE agent_type = 'contradiction' AND is_system_default = TRUE
    LIMIT 1;

    SELECT max_tokens INTO gap_tokens
    FROM compliance_agents
    WHERE agent_type = 'gap_analysis' AND is_system_default = TRUE
    LIMIT 1;

    RAISE NOTICE '========================================';
    RAISE NOTICE 'AGENT MAX_TOKENS UPDATE COMPLETE';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Actor Agent max_tokens: %', actor_tokens;
    RAISE NOTICE 'Critic Agent max_tokens: %', critic_tokens;
    RAISE NOTICE 'Contradiction Agent max_tokens: %', contradiction_tokens;
    RAISE NOTICE 'Gap Analysis Agent max_tokens: %', gap_tokens;
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Agents updated to prevent context length errors';
    RAISE NOTICE '========================================';
END $$;
