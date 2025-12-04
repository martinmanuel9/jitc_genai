-- Migration: Create migration tracking table
-- Date: 2025-11-08
-- Description: Track which migrations have been applied to prevent re-running
--              This ensures idempotent database initialization

-- Create migrations tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64),
    status VARCHAR(20) DEFAULT 'success' CHECK (status IN ('success', 'failed', 'pending')),
    error_message TEXT,
    execution_time_ms INTEGER
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS ix_schema_migrations_migration_name ON schema_migrations(migration_name);
CREATE INDEX IF NOT EXISTS ix_schema_migrations_status ON schema_migrations(status);

-- Add comment
COMMENT ON TABLE schema_migrations IS 'Tracks which database migrations have been applied';
COMMENT ON COLUMN schema_migrations.migration_name IS 'Unique identifier for the migration file';
COMMENT ON COLUMN schema_migrations.checksum IS 'Hash of migration content to detect modifications';
COMMENT ON COLUMN schema_migrations.status IS 'Status of migration: success, failed, or pending';
