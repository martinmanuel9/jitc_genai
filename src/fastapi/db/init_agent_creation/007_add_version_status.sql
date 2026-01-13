-- ============================================================================
-- ADD VERSION STATUS TO TEST PLAN VERSIONS
-- ============================================================================
-- Adds status tracking (draft/final/published) to test plan versions
-- and updated_at timestamp for version tracking.
--
-- Date: 2026-01-10
-- Version: 1.0
-- ============================================================================

-- ==========================================================================
-- CREATE VERSION STATUS ENUM TYPE
-- ==========================================================================
DO $$
BEGIN
    -- Create ENUM type if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'version_status') THEN
        CREATE TYPE version_status AS ENUM ('draft', 'final', 'published');
    END IF;
END$$;

-- ==========================================================================
-- ADD STATUS COLUMN TO test_plan_versions
-- ==========================================================================
-- Add status column with default 'draft'
ALTER TABLE test_plan_versions
ADD COLUMN IF NOT EXISTS status version_status DEFAULT 'draft';

-- Add updated_at column for version tracking
ALTER TABLE test_plan_versions
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ==========================================================================
-- CREATE INDEX FOR STATUS QUERIES
-- ==========================================================================
CREATE INDEX IF NOT EXISTS idx_test_plan_versions_status ON test_plan_versions(status);

-- ==========================================================================
-- ADD COLUMN COMMENTS
-- ==========================================================================
COMMENT ON COLUMN test_plan_versions.status IS 'Version status: draft (editable), final (locked), published (read-only)';
COMMENT ON COLUMN test_plan_versions.updated_at IS 'Timestamp when version was last modified';
