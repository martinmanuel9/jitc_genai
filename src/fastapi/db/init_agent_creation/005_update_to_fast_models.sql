-- ============================================================================
-- MIGRATION: Update agents to use faster models
-- ============================================================================
-- This migration updates all agents from gpt-oss:latest (20.9B params) to
-- llama3.2:3b (3.2B params) for significantly faster inference.
--
-- Model comparison:
--   gpt-oss:latest  - 20.9B params, 13.8GB disk, slow on CPU
--   llama3.2:3b     - 3.2B params, 2GB disk, ~6x faster on CPU
--   phi3:mini       - 3.8B params, 2.3GB disk, good quality alternative
--
-- Date: 2026-01-10
-- Version: 1.0
-- ============================================================================

-- Update all test plan generation agents to use llama3.2:3b
UPDATE compliance_agents
SET
    model_name = 'llama3.2:3b',
    agent_metadata = jsonb_set(
        COALESCE(agent_metadata::jsonb, '{}'::jsonb),
        '{model_variant}',
        '"llama3.2:3b"',
        true
    )::json,
    updated_at = CURRENT_TIMESTAMP
WHERE model_name = 'gpt-oss:latest'
  AND workflow_type = 'test_plan_generation';

-- Update all document analysis agents to use llama3.2:3b
UPDATE compliance_agents
SET
    model_name = 'llama3.2:3b',
    agent_metadata = jsonb_set(
        COALESCE(agent_metadata::jsonb, '{}'::jsonb),
        '{model_variant}',
        '"llama3.2:3b"',
        true
    )::json,
    updated_at = CURRENT_TIMESTAMP
WHERE model_name = 'gpt-oss:latest'
  AND workflow_type = 'document_analysis';

-- Update any remaining agents using gpt-oss:latest
UPDATE compliance_agents
SET
    model_name = 'llama3.2:3b',
    updated_at = CURRENT_TIMESTAMP
WHERE model_name = 'gpt-oss:latest';

-- Update agent set descriptions to reflect faster models
UPDATE agent_sets
SET
    description = REPLACE(description, 'GPT-OSS', 'Llama 3.2'),
    updated_at = CURRENT_TIMESTAMP
WHERE description LIKE '%GPT-OSS%';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    gpt_oss_count INTEGER;
    llama_count INTEGER;
    total_agents INTEGER;
BEGIN
    SELECT COUNT(*) INTO gpt_oss_count FROM compliance_agents WHERE model_name = 'gpt-oss:latest';
    SELECT COUNT(*) INTO llama_count FROM compliance_agents WHERE model_name = 'llama3.2:3b';
    SELECT COUNT(*) INTO total_agents FROM compliance_agents;

    RAISE NOTICE '========================================';
    RAISE NOTICE 'FAST MODEL MIGRATION COMPLETE';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Total Agents: %', total_agents;
    RAISE NOTICE '  - Using llama3.2:3b: %', llama_count;
    RAISE NOTICE '  - Using gpt-oss:latest: %', gpt_oss_count;
    RAISE NOTICE '========================================';

    IF gpt_oss_count > 0 THEN
        RAISE WARNING 'Some agents still use gpt-oss:latest!';
    ELSE
        RAISE NOTICE 'All agents migrated to fast model!';
    END IF;
    RAISE NOTICE '========================================';
END $$;
