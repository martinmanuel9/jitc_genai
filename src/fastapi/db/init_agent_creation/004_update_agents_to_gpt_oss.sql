-- Update agent models to GPT-OSS for local deployments

UPDATE compliance_agents
SET model_name = 'gpt-oss:latest'
WHERE model_name LIKE 'gpt-4%';

UPDATE compliance_agents
SET agent_metadata = jsonb_set(
    COALESCE(agent_metadata::jsonb, '{}'::jsonb),
    '{model_variant}',
    '"gpt-oss:latest"',
    true
)::json
WHERE COALESCE(agent_metadata::jsonb, '{}'::jsonb) ? 'model_variant'
  AND COALESCE(agent_metadata::jsonb, '{}'::jsonb)->>'model_variant' LIKE 'gpt-4%';
