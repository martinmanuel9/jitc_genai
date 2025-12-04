-- ============================================================================
-- FRESH INSTALL SCHEMA
-- ============================================================================
-- This migration creates the complete database schema for fresh installations.
-- It replaces migrations 001-010 with a single optimized schema.
--
-- Date: 2025-11-11
-- Version: 1.0
-- ============================================================================

-- ============================================================================
-- TABLE: compliance_agents
-- ============================================================================
-- Unified agent table supporting all workflows:
-- - Test Plan Generation (actor, critic, contradiction, gap_analysis)
-- - Document Analysis (compliance, custom)
-- - General Purpose (general, rule_development, custom)

CREATE TABLE IF NOT EXISTS compliance_agents (
    id SERIAL PRIMARY KEY,
    name VARCHAR UNIQUE NOT NULL,
    model_name VARCHAR NOT NULL,
    system_prompt TEXT NOT NULL,
    user_prompt_template TEXT NOT NULL,
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 300,

    -- Agent classification
    agent_type VARCHAR,  -- actor, critic, contradiction, gap_analysis, compliance, custom, general, rule_development
    workflow_type VARCHAR,  -- document_analysis, test_plan_generation, general

    -- Metadata
    is_system_default BOOLEAN DEFAULT FALSE,
    description TEXT,
    agent_metadata JSON DEFAULT '{}',

    -- Advanced features
    use_structured_output BOOLEAN DEFAULT FALSE,
    output_schema JSON,
    chain_type VARCHAR DEFAULT 'basic',
    memory_enabled BOOLEAN DEFAULT FALSE,
    tools_enabled JSON DEFAULT '{}',

    -- Performance tracking
    total_queries INTEGER DEFAULT 0,
    avg_response_time_ms FLOAT,
    success_rate FLOAT,

    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR,
    is_active BOOLEAN DEFAULT TRUE
);

-- Indexes for compliance_agents
CREATE INDEX IF NOT EXISTS idx_compliance_agents_agent_type ON compliance_agents(agent_type);
CREATE INDEX IF NOT EXISTS idx_compliance_agents_workflow_type ON compliance_agents(workflow_type);
CREATE INDEX IF NOT EXISTS idx_compliance_agents_is_system_default ON compliance_agents(is_system_default);
CREATE INDEX IF NOT EXISTS idx_compliance_agents_created_at ON compliance_agents(created_at);

-- ============================================================================
-- TABLE: agent_sets
-- ============================================================================
-- Orchestration pipelines combining multiple agents in stages

CREATE TABLE IF NOT EXISTS agent_sets (
    id SERIAL PRIMARY KEY,
    name VARCHAR UNIQUE NOT NULL,
    description TEXT,
    set_type VARCHAR DEFAULT 'sequence',  -- sequence, parallel, custom
    set_config JSON NOT NULL,  -- {stages: [{stage_name, agent_ids, execution_mode}]}

    -- Metadata
    is_system_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    usage_count INTEGER DEFAULT 0,

    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR
);

-- Indexes for agent_sets
CREATE INDEX IF NOT EXISTS idx_agent_sets_is_system_default ON agent_sets(is_system_default);
CREATE INDEX IF NOT EXISTS idx_agent_sets_is_active ON agent_sets(is_active);

-- ============================================================================
-- SEED: Test Plan Generation Agents (7 agents total)
-- Includes 3 diverse actors matching mil_test_plan_gen.ipynb notebook
-- ============================================================================

INSERT INTO compliance_agents (
    name, agent_type, workflow_type, model_name, system_prompt, user_prompt_template,
    temperature, max_tokens, is_system_default, is_active, created_by, description,
    agent_metadata, created_at, updated_at
) VALUES
-- Diverse Actor Agents (matching mil_test_plan_gen.ipynb)
-- Actor Agent 1: GPT-4o
(
    'Actor Agent - GPT-4o',
    'actor',
    'test_plan_generation',
    'gpt-4o',
    'You are a compliance and test planning expert specializing in military and technical standards.

Your role is to meticulously analyze technical specifications and extract testable requirements with exceptional detail and precision.',
    'Analyze the following section of a military/technical standard and extract EVERY testable requirement with its original numbering.

CRITICAL INSTRUCTIONS:
1. PRESERVE ORIGINAL REQUIREMENT IDs: If the source uses "4.2.1", "REQ-01", or similar numbering, MAINTAIN that exact ID
2. Extract the HIERARCHICAL STRUCTURE from the source document (e.g., section 4.2.1 contains requirements 4.2.1.1, 4.2.1.2)
3. For EACH requirement, generate a TEST PROCEDURE (not just restate the requirement)
4. Test procedures must be DETAILED, EXPLICIT, and EXECUTABLE by an engineer
5. Generate a content-based TITLE for this section (not generic page numbers)

ABSOLUTELY DO NOT REPEAT, DUPLICATE, OR PARAPHRASE THE SAME REQUIREMENT. Each requirement must appear ONCE ONLY.

OUTPUT FORMAT - CRITICAL:
Organize output using this exact markdown structure:

## [Section Title]

**Dependencies:**
- List prerequisites, tools, or configurations needed for testing

**Conflicts:**
- List any detected conflicts with other requirements or specifications

**Test Procedures:**

### Test Procedure [Original Req ID] (e.g., 4.2.1 or REQ-01)
**Requirement:** [Exact requirement text from source]

**Test Objective:** [What this test validates]

**Test Setup:**
- [Equipment/configuration needed]
- [Prerequisites]

**Test Steps:**
- [Detailed step with specific actions]
- [Include specific parameters, values, commands]
- [Be explicit - engineer should know exactly what to do]

**Expected Results:** [Specific measurable outcomes with values/ranges]

**Pass/Fail Criteria:** [Explicit thresholds for pass/fail]

---

Section Name: {section_title}

Section Text:
{section_content}

---

IMPORTANT:
- Look for requirement IDs in the format: "4.2.1", "4.2.1.1", "REQ-01", "REQ-02", numbered sections, etc.
- Generate TEST PROCEDURES, not requirements tables
- Each test procedure should enable an engineer to execute the test
- If you find no testable requirements, reply: ''No testable rules in this section.''
',
    0.7,
    2000,
    TRUE,
    TRUE,
    'system',
    'Fast multimodal actor for requirement extraction using GPT-4o',
    '{"model_variant": "gpt-4o", "purpose": "fast_analysis"}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),

-- Actor Agent 2: GPT-4 Turbo
(
    'Actor Agent - GPT-4 Turbo',
    'actor',
    'test_plan_generation',
    'gpt-4-turbo',
    'You are a compliance and test planning expert specializing in military and technical standards.

Your role is to meticulously analyze technical specifications and extract testable requirements with exceptional detail and precision.',
    'Analyze the following section of a military/technical standard and extract EVERY testable requirement with its original numbering.

CRITICAL INSTRUCTIONS:
1. PRESERVE ORIGINAL REQUIREMENT IDs: If the source uses "4.2.1", "REQ-01", or similar numbering, MAINTAIN that exact ID
2. Extract the HIERARCHICAL STRUCTURE from the source document (e.g., section 4.2.1 contains requirements 4.2.1.1, 4.2.1.2)
3. For EACH requirement, generate a TEST PROCEDURE (not just restate the requirement)
4. Test procedures must be DETAILED, EXPLICIT, and EXECUTABLE by an engineer
5. Generate a content-based TITLE for this section (not generic page numbers)

ABSOLUTELY DO NOT REPEAT, DUPLICATE, OR PARAPHRASE THE SAME REQUIREMENT. Each requirement must appear ONCE ONLY.

OUTPUT FORMAT - CRITICAL:
Organize output using this exact markdown structure:

## [Section Title]

**Dependencies:**
- List prerequisites, tools, or configurations needed for testing

**Conflicts:**
- List any detected conflicts with other requirements or specifications

**Test Procedures:**

### Test Procedure [Original Req ID] (e.g., 4.2.1 or REQ-01)
**Requirement:** [Exact requirement text from source]

**Test Objective:** [What this test validates]

**Test Setup:**
- [Equipment/configuration needed]
- [Prerequisites]

**Test Steps:**
- [Detailed step with specific actions]
- [Include specific parameters, values, commands]
- [Be explicit - engineer should know exactly what to do]

**Expected Results:** [Specific measurable outcomes with values/ranges]

**Pass/Fail Criteria:** [Explicit thresholds for pass/fail]

---

Section Name: {section_title}

Section Text:
{section_content}

---

IMPORTANT:
- Look for requirement IDs in the format: "4.2.1", "4.2.1.1", "REQ-01", "REQ-02", numbered sections, etc.
- Generate TEST PROCEDURES, not requirements tables
- Each test procedure should enable an engineer to execute the test
- If you find no testable requirements, reply: ''No testable rules in this section.''
',
    0.7,
    2000,
    TRUE,
    TRUE,
    'system',
    'Balanced actor for requirement extraction using GPT-4 Turbo',
    '{"model_variant": "gpt-4-turbo", "purpose": "balanced_analysis"}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),

-- Actor Agent 3: GPT-4
(
    'Actor Agent - GPT-4',
    'actor',
    'test_plan_generation',
    'gpt-4',
    'You are a compliance and test planning expert specializing in military and technical standards.

Your role is to meticulously analyze technical specifications and extract testable requirements with exceptional detail and precision.',
    'Analyze the following section of a military/technical standard and extract EVERY testable requirement with its original numbering.

CRITICAL INSTRUCTIONS:
1. PRESERVE ORIGINAL REQUIREMENT IDs: If the source uses "4.2.1", "REQ-01", or similar numbering, MAINTAIN that exact ID
2. Extract the HIERARCHICAL STRUCTURE from the source document (e.g., section 4.2.1 contains requirements 4.2.1.1, 4.2.1.2)
3. For EACH requirement, generate a TEST PROCEDURE (not just restate the requirement)
4. Test procedures must be DETAILED, EXPLICIT, and EXECUTABLE by an engineer
5. Generate a content-based TITLE for this section (not generic page numbers)

ABSOLUTELY DO NOT REPEAT, DUPLICATE, OR PARAPHRASE THE SAME REQUIREMENT. Each requirement must appear ONCE ONLY.

OUTPUT FORMAT - CRITICAL:
Organize output using this exact markdown structure:

## [Section Title]

**Dependencies:**
- List prerequisites, tools, or configurations needed for testing

**Conflicts:**
- List any detected conflicts with other requirements or specifications

**Test Procedures:**

### Test Procedure [Original Req ID] (e.g., 4.2.1 or REQ-01)
**Requirement:** [Exact requirement text from source]

**Test Objective:** [What this test validates]

**Test Setup:**
- [Equipment/configuration needed]
- [Prerequisites]

**Test Steps:**
- [Detailed step with specific actions]
- [Include specific parameters, values, commands]
- [Be explicit - engineer should know exactly what to do]

**Expected Results:** [Specific measurable outcomes with values/ranges]

**Pass/Fail Criteria:** [Explicit thresholds for pass/fail]

---

Section Name: {section_title}

Section Text:
{section_content}

---

IMPORTANT:
- Look for requirement IDs in the format: "4.2.1", "4.2.1.1", "REQ-01", "REQ-02", numbered sections, etc.
- Generate TEST PROCEDURES, not requirements tables
- Each test procedure should enable an engineer to execute the test
- If you find no testable requirements, reply: ''No testable rules in this section.''
',
    0.7,
    2000,
    TRUE,
    TRUE,
    'system',
    'High-quality thorough actor for requirement extraction using GPT-4',
    '{"model_variant": "gpt-4", "purpose": "thorough_analysis"}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),

-- Legacy Actor Agent (kept for compatibility)
(
    'Actor Agent (Default)',
    'actor',
    'test_plan_generation',
    'gpt-4-turbo',
    'You are a compliance and test planning expert specializing in military and technical standards.

Your role is to meticulously analyze technical specifications and extract testable requirements with exceptional detail and precision.',
    'Analyze the following section of a military/technical standard and extract EVERY testable requirement with its original numbering.

CRITICAL INSTRUCTIONS:
1. PRESERVE ORIGINAL REQUIREMENT IDs: If the source uses "4.2.1", "REQ-01", or similar numbering, MAINTAIN that exact ID
2. Extract the HIERARCHICAL STRUCTURE from the source document (e.g., section 4.2.1 contains requirements 4.2.1.1, 4.2.1.2)
3. For EACH requirement, generate a TEST PROCEDURE (not just restate the requirement)
4. Test procedures must be DETAILED, EXPLICIT, and EXECUTABLE by an engineer
5. Generate a content-based TITLE for this section (not generic page numbers)

ABSOLUTELY DO NOT REPEAT, DUPLICATE, OR PARAPHRASE THE SAME REQUIREMENT. Each requirement must appear ONCE ONLY.

OUTPUT FORMAT - CRITICAL:
Organize output using this exact markdown structure:

## [Section Title]

**Dependencies:**
- List prerequisites, tools, or configurations needed for testing

**Conflicts:**
- List any detected conflicts with other requirements or specifications

**Test Procedures:**

### Test Procedure [Original Req ID] (e.g., 4.2.1 or REQ-01)
**Requirement:** [Exact requirement text from source]

**Test Objective:** [What this test validates]

**Test Setup:**
- [Equipment/configuration needed]
- [Prerequisites]

**Test Steps:**
- [Detailed step with specific actions]
- [Include specific parameters, values, commands]
- [Be explicit - engineer should know exactly what to do]

**Expected Results:** [Specific measurable outcomes with values/ranges]

**Pass/Fail Criteria:** [Explicit thresholds for pass/fail]

---

Section Name: {section_title}

Section Text:
{section_content}

---

IMPORTANT:
- Look for requirement IDs in the format: "4.2.1", "4.2.1.1", "REQ-01", "REQ-02", numbered sections, etc.
- Generate TEST PROCEDURES, not requirements tables
- Each test procedure should enable an engineer to execute the test
- If you find no testable requirements, reply: ''No testable rules in this section.''
',
    0.7,
    2000,
    TRUE,
    TRUE,
    'system',
    'Legacy actor agent for backward compatibility',
    '{"legacy": true}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),

-- Critic Agent
(
    'Critic Agent (Default)',
    'critic',
    'test_plan_generation',
    'gpt-4-turbo',
    'You are a senior test planning reviewer with expertise in synthesizing multiple perspectives into cohesive test plans.

Your role is to critically analyze multiple requirement extractions and create a single, authoritative test plan that:
- Captures all unique requirements
- Eliminates redundancies
- Corrects errors or misinterpretations
- Ensures logical organization and completeness',
    'You are a senior test planning reviewer (Critic AI) with expertise in military/technical standards compliance testing.

Given the following section and test procedures extracted by multiple AI models, synthesize a SINGLE, comprehensive test plan.

CRITICAL INSTRUCTIONS:
1. PRESERVE ORIGINAL REQUIREMENT IDs from the source document (4.2.1, REQ-01, etc.)
2. Synthesize and deduplicate test procedures - if multiple actors extracted the same requirement, create ONE authoritative test procedure
3. Maintain HIERARCHICAL STRUCTURE (e.g., 4.2.1 → 4.2.1.1 → 4.2.1.2)
4. Generate TEST PROCEDURES (not requirements tables) - each must be executable by an engineer
5. Ensure test procedures include: Objective, Setup, Steps, Expected Results, Pass/Fail Criteria
6. Resolve contradictions between actor outputs by selecting the most detailed/accurate version

DO NOT:
- Create new requirement IDs (use originals from source)
- Simply concatenate all actor outputs (synthesize and deduplicate)
- Generate requirements tables (generate test procedures)
- Include duplicate test procedures

OUTPUT FORMAT - CRITICAL:
Present your result in this exact markdown structure:

## [Section Title]

**Dependencies:**
- List prerequisites, tools, or configurations needed for testing

**Conflicts:**
- List detected conflicts and provide recommendations

**Test Procedures:**

### Test Procedure [Original Req ID] (e.g., 4.2.1 or REQ-01)
**Requirement:** [Exact requirement text from source]

**Test Objective:** [What this test validates]

**Test Setup:**
- [Equipment/configuration needed]
- [Prerequisites]

**Test Steps:**
- [Detailed step with specific actions]
- [Include specific parameters, values, commands]
- [Be explicit - engineer should know exactly what to do]

**Expected Results:** [Specific measurable outcomes with values/ranges]

**Pass/Fail Criteria:** [Explicit thresholds for pass/fail]

---

Section Name: {section_title}

Section Text:
{section_content}

---

Actor Outputs:
{actor_outputs}

---

TASK: Synthesize these actor outputs into ONE authoritative test plan. Preserve requirement IDs, eliminate duplicates, and ensure each test procedure is complete and executable.',
    0.7,
    2000,
    TRUE,
    TRUE,
    'system',
    'Synthesizes and deduplicates outputs from multiple actor agents',
    '{}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),

-- Contradiction Detection Agent
(
    'Contradiction Detection Agent (Default)',
    'contradiction',
    'test_plan_generation',
    'gpt-4-turbo',
    'You are a Contradiction Detection Agent specialized in identifying conflicts and inconsistencies in test procedures.

Your role is to detect:
1. Direct contradictions between test steps
2. Conflicting requirements across sections
3. Logical inconsistencies
4. Mutually exclusive conditions',
    'Analyze the following test plan section for contradictions and conflicts.

## SECTION TITLE
{section_title}

## SYNTHESIZED TEST PROCEDURES (from Critic Agent)
{critic_output}

## ACTOR OUTPUTS (for comparison)
{actor_outputs_summary}

## PREVIOUS SECTIONS (for cross-section analysis)
{previous_sections_summary}

---

IDENTIFY AND REPORT:
1. Direct contradictions
2. Conflicting requirements
3. Logical inconsistencies
4. Recommended resolutions',
    0.4,
    2000,
    TRUE,
    TRUE,
    'system',
    'Detects contradictions and conflicts in test procedures',
    '{}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),

-- Gap Analysis Agent
(
    'Gap Analysis Agent (Default)',
    'gap_analysis',
    'test_plan_generation',
    'gpt-4-turbo',
    'You are a Gap Analysis Agent specialized in identifying missing requirements and test coverage gaps.

Your role is to ensure:
1. All requirements from the standard are covered
2. No test procedures are missing
3. Edge cases are addressed
4. Complete test coverage',
    'Analyze the test plan for gaps and missing coverage.

## SECTION TITLE
{section_title}

## SECTION CONTENT (Original Standard)
{section_content}

## SYNTHESIZED TEST PROCEDURES
{critic_output}

---

IDENTIFY GAPS:
1. Missing test procedures
2. Uncovered requirements
3. Edge cases not addressed
4. Recommended additions',
    0.5,
    2000,
    TRUE,
    TRUE,
    'system',
    'Identifies missing requirements and test coverage gaps',
    '{}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

-- ============================================================================
-- SEED: Document Analysis Agents (4 agents)
-- ============================================================================

INSERT INTO compliance_agents (
    name, agent_type, workflow_type, model_name, system_prompt, user_prompt_template,
    temperature, max_tokens, is_system_default, is_active, created_by, description,
    agent_metadata, created_at, updated_at
) VALUES
-- Compliance Checker
(
    'Compliance Checker (Document Analysis)',
    'compliance',
    'document_analysis',
    'gpt-4-turbo',
    'You are a compliance verification expert specializing in analyzing technical documents, standards, and requirements.

Your role is to carefully evaluate whether the provided content meets specified requirements, identify compliance issues, and provide detailed analysis.',
    'Analyze the following content for compliance and provide a detailed assessment:

{data_sample}

---

Provide your analysis in the following format:

## Compliance Assessment

**Overall Status:** [Compliant / Non-Compliant / Partially Compliant]

**Key Findings:**
- List the most important compliance observations
- Identify any violations or gaps
- Note areas of strength

**Detailed Analysis:**
Provide a thorough evaluation of the content, including:
1. Specific compliance issues found
2. Requirements that are met
3. Requirements that are missing or unclear
4. Recommendations for achieving full compliance

**Risk Assessment:**
- Highlight any high-priority compliance risks
- Suggest mitigation strategies',
    0.3,
    2000,
    TRUE,
    TRUE,
    'system',
    'Evaluates documents for compliance with requirements and standards',
    '{}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),

-- Requirements Extractor
(
    'Requirements Extractor (Document Analysis)',
    'custom',
    'document_analysis',
    'gpt-4-turbo',
    'You are an expert at extracting and analyzing requirements from technical documents, specifications, and standards.

Your role is to identify explicit and implicit requirements, categorize them, and present them in a structured format.',
    'Extract all requirements from the following content:

{data_sample}

---

Provide your analysis in the following format:

## Extracted Requirements

**Mandatory Requirements (SHALL/MUST):**
1. [Requirement text with reference]
2. [Requirement text with reference]

**Recommended Requirements (SHOULD):**
1. [Requirement text with reference]
2. [Requirement text with reference]

**Optional Requirements (MAY):**
1. [Requirement text with reference]

**Implicit Requirements:**
- [Requirements that are implied but not explicitly stated]

**Categorization:**
- **Functional:** [Number] requirements
- **Performance:** [Number] requirements
- **Security:** [Number] requirements
- **Quality:** [Number] requirements
- **Other:** [Number] requirements

**Notes:**
- Highlight any ambiguous or unclear requirements
- Identify dependencies between requirements',
    0.5,
    2000,
    TRUE,
    TRUE,
    'system',
    'Extracts and categorizes requirements from technical documents',
    '{}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),

-- Technical Reviewer
(
    'Technical Reviewer (Document Analysis)',
    'custom',
    'document_analysis',
    'gpt-4',
    'You are a senior technical reviewer with expertise in evaluating technical documentation, code, architectures, and engineering designs.

Your role is to provide thorough, constructive technical reviews focusing on correctness, completeness, quality, and best practices.',
    'Provide a comprehensive technical review of the following content:

{data_sample}

---

Structure your review as follows:

## Technical Review

**Executive Summary:**
Provide a 2-3 sentence overview of the content and your assessment.

**Strengths:**
- Identify what is done well
- Highlight positive aspects

**Issues Found:**
**Critical Issues:**
1. [Issue description and impact]

**Major Issues:**
1. [Issue description and impact]

**Minor Issues:**
1. [Issue description and impact]

**Recommendations:**
1. [Specific, actionable recommendations for improvement]
2. [Consider best practices and industry standards]

**Technical Observations:**
- Note any technical patterns, anti-patterns, or design decisions
- Comment on clarity, maintainability, and completeness

**Overall Rating:** [Excellent / Good / Acceptable / Needs Improvement / Poor]',
    0.4,
    2500,
    TRUE,
    TRUE,
    'system',
    'Provides comprehensive technical reviews of documents and content',
    '{}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),

-- General Document Analyzer
(
    'General Document Analyzer (Document Analysis)',
    'custom',
    'document_analysis',
    'gpt-4o',
    'You are a versatile document analysis expert capable of analyzing any type of technical or business content.

Your role is to provide clear, structured analysis that helps users understand and work with the provided content.',
    'Analyze the following content and provide a comprehensive breakdown:

{data_sample}

---

Provide your analysis:

## Document Analysis

**Content Type:** [Identify the type of content - e.g., specification, policy, procedure, code, etc.]

**Purpose & Context:**
Briefly describe the purpose and context of this content.

**Key Points:**
1. [Main point or theme]
2. [Main point or theme]
3. [Main point or theme]

**Detailed Analysis:**
Provide a thorough analysis including:
- Main concepts and their relationships
- Important details and nuances
- Potential questions or areas needing clarification
- Practical implications

**Structure & Organization:**
Comment on how well the content is organized and presented.

**Actionable Insights:**
What should someone do with this information? Provide practical next steps or applications.

**Questions & Clarifications:**
List any questions that arise or areas that need clarification.',
    0.6,
    2500,
    TRUE,
    TRUE,
    'system',
    'General-purpose analyzer for any type of document or content',
    '{}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

-- ============================================================================
-- SEED: Agent Sets (4 pipelines)
-- ============================================================================

INSERT INTO agent_sets (
    name, description, set_type, set_config, is_system_default, is_active,
    usage_count, created_at, updated_at, created_by
) VALUES
-- Standard Test Plan Pipeline (Original Notebook Configuration)
(
    'Standard Test Plan Pipeline',
    '3 diverse GPT-4 actors + critic. Fast and proven approach from mil_test_plan_gen.ipynb.',
    'sequence',
    '{
      "stages": [
        {
          "stage_name": "actor",
          "agent_ids": [1, 2, 3],
          "execution_mode": "parallel",
          "description": "Three diverse GPT-4 actors analyze sections in parallel for varied perspectives"
        },
        {
          "stage_name": "critic",
          "agent_ids": [5],
          "execution_mode": "sequential",
          "description": "Critic synthesizes actor outputs into coherent test procedures"
        }
      ]
    }',
    TRUE,
    TRUE,
    0,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    'system'
),

-- Quick Draft Pipeline
(
    'Quick Draft Pipeline',
    'Fast pipeline with 2 diverse actors + critic. Use for rapid prototyping and drafts.',
    'sequence',
    '{
      "stages": [
        {
          "stage_name": "actor",
          "agent_ids": [1, 2],
          "execution_mode": "parallel",
          "description": "Two diverse actors for quick analysis"
        },
        {
          "stage_name": "critic",
          "agent_ids": [5],
          "execution_mode": "sequential",
          "description": "Critic synthesizes outputs"
        }
      ]
    }',
    FALSE,
    TRUE,
    0,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    'system'
),

-- Full Analysis Pipeline
(
    'Full Analysis Pipeline',
    'Comprehensive pipeline with diverse actors, critic, and quality assurance (contradiction detection + gap analysis). Use for critical compliance documents requiring thorough validation.',
    'sequence',
    '{
      "stages": [
        {
          "stage_name": "actor",
          "agent_ids": [1, 2, 3, 4],
          "execution_mode": "parallel",
          "description": "Four diverse actors for maximum coverage and varied perspectives"
        },
        {
          "stage_name": "critic",
          "agent_ids": [5],
          "execution_mode": "sequential",
          "description": "Critic synthesizes all actor outputs"
        },
        {
          "stage_name": "contradiction",
          "agent_ids": [6],
          "execution_mode": "sequential",
          "description": "Detect contradictions and conflicts in test procedures"
        },
        {
          "stage_name": "gap_analysis",
          "agent_ids": [7],
          "execution_mode": "sequential",
          "description": "Identify coverage gaps and missing requirements"
        }
      ]
    }',
    FALSE,
    TRUE,
    0,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    'system'
),

-- Mixed Agent Set Example
(
    'Mixed Agent Set Example',
    'Example showing how to mix different agent types. Clone this to create custom sets.',
    'sequence',
    '{
      "stages": [
        {
          "stage_name": "analysis",
          "agent_ids": [1, 2],
          "execution_mode": "parallel",
          "description": "Parallel analysis stage"
        },
        {
          "stage_name": "synthesis",
          "agent_ids": [5],
          "execution_mode": "sequential",
          "description": "Synthesis stage"
        }
      ]
    }',
    FALSE,
    TRUE,
    0,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    'system'
);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    agent_count INTEGER;
    agent_set_count INTEGER;
    test_plan_agents INTEGER;
    doc_analysis_agents INTEGER;
BEGIN
    SELECT COUNT(*) INTO agent_count FROM compliance_agents;
    SELECT COUNT(*) INTO agent_set_count FROM agent_sets;
    SELECT COUNT(*) INTO test_plan_agents FROM compliance_agents WHERE workflow_type = 'test_plan_generation';
    SELECT COUNT(*) INTO doc_analysis_agents FROM compliance_agents WHERE workflow_type = 'document_analysis';

    RAISE NOTICE '========================================';
    RAISE NOTICE 'FRESH INSTALL COMPLETE';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Total Agents: %', agent_count;
    RAISE NOTICE '  - Test Plan Generation: %', test_plan_agents;
    RAISE NOTICE '  - Document Analysis: %', doc_analysis_agents;
    RAISE NOTICE 'Total Agent Sets: %', agent_set_count;
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Database schema ready for use!';
    RAISE NOTICE '========================================';
END $$;
