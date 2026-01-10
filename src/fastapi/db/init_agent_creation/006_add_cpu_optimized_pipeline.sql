-- Migration: Add CPU-Optimized Pipeline for systems without GPU
-- This pipeline uses a single actor instead of 3, cutting LLM calls by 50%

-- Check if CPU-Optimized Pipeline already exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM agent_sets WHERE name = 'CPU-Optimized Pipeline') THEN
        INSERT INTO agent_sets (name, description, set_type, set_config, is_active, is_system_default, usage_count, created_at, updated_at)
        VALUES (
            'CPU-Optimized Pipeline',
            'Single actor for faster CPU processing - 2 LLM calls per section instead of 4',
            'sequence',
            '{
              "stages": [
                {
                  "stage_name": "actor",
                  "agent_ids": [1],
                  "execution_mode": "sequential",
                  "description": "Single actor analyzes sections"
                },
                {
                  "stage_name": "critic",
                  "agent_ids": [5],
                  "execution_mode": "sequential",
                  "description": "Critic synthesizes into test procedures"
                }
              ]
            }',
            true,
            false,
            0,
            NOW(),
            NOW()
        );
        RAISE NOTICE 'Created CPU-Optimized Pipeline agent set';
    ELSE
        RAISE NOTICE 'CPU-Optimized Pipeline already exists, skipping';
    END IF;
END $$;
