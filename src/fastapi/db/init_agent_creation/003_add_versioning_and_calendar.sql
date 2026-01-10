-- ============================================================================
-- VERSIONING, USERS, AND CALENDAR TABLES
-- ============================================================================
-- Adds user records, version tracking for documents/test plans/test cards,
-- and calendar events with simple recurrence fields.
--
-- Date: 2025-11-11
-- Version: 1.1
-- ============================================================================

-- ==========================================================================
-- TABLE: users
-- ==========================================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    email VARCHAR UNIQUE NOT NULL,
    org VARCHAR,
    role VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ==========================================================================
-- TABLE: test_plans
-- ==========================================================================
CREATE TABLE IF NOT EXISTS test_plans (
    id SERIAL PRIMARY KEY,
    plan_key VARCHAR UNIQUE NOT NULL,
    title VARCHAR,
    collection_name VARCHAR,
    percent_complete FLOAT DEFAULT 0 CHECK (percent_complete >= 0 AND percent_complete <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_test_plans_plan_key ON test_plans(plan_key);

-- ==========================================================================
-- TABLE: test_plan_versions
-- ==========================================================================
CREATE TABLE IF NOT EXISTS test_plan_versions (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES test_plans(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    document_id VARCHAR NOT NULL,
    based_on_version_id INTEGER REFERENCES test_plan_versions(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (plan_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_test_plan_versions_plan_id ON test_plan_versions(plan_id);
CREATE INDEX IF NOT EXISTS idx_test_plan_versions_version ON test_plan_versions(version_number);

-- ==========================================================================
-- TABLE: test_cards
-- ==========================================================================
CREATE TABLE IF NOT EXISTS test_cards (
    id SERIAL PRIMARY KEY,
    card_key VARCHAR UNIQUE NOT NULL,
    plan_id INTEGER REFERENCES test_plans(id) ON DELETE SET NULL,
    title VARCHAR,
    requirement_id VARCHAR,
    percent_complete FLOAT DEFAULT 0 CHECK (percent_complete >= 0 AND percent_complete <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_test_cards_card_key ON test_cards(card_key);
CREATE INDEX IF NOT EXISTS idx_test_cards_plan_id ON test_cards(plan_id);

-- ==========================================================================
-- TABLE: test_card_versions
-- ==========================================================================
CREATE TABLE IF NOT EXISTS test_card_versions (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES test_cards(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    document_id VARCHAR NOT NULL,
    plan_version_id INTEGER REFERENCES test_plan_versions(id) ON DELETE SET NULL,
    based_on_version_id INTEGER REFERENCES test_card_versions(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (card_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_test_card_versions_card_id ON test_card_versions(card_id);
CREATE INDEX IF NOT EXISTS idx_test_card_versions_version ON test_card_versions(version_number);

-- ==========================================================================
-- TABLE: document_versions
-- ==========================================================================
CREATE TABLE IF NOT EXISTS document_versions (
    id SERIAL PRIMARY KEY,
    document_key VARCHAR NOT NULL,
    document_id VARCHAR NOT NULL,
    collection_name VARCHAR NOT NULL,
    document_name VARCHAR,
    version_number INTEGER NOT NULL,
    based_on_version_id INTEGER REFERENCES document_versions(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_key, version_number)
);

CREATE INDEX IF NOT EXISTS idx_document_versions_key ON document_versions(document_key);

-- ==========================================================================
-- TABLE: calendar_events
-- ==========================================================================
CREATE TABLE IF NOT EXISTS calendar_events (
    id SERIAL PRIMARY KEY,
    title VARCHAR NOT NULL,
    description TEXT,
    start_at TIMESTAMP NOT NULL,
    end_at TIMESTAMP,
    timezone VARCHAR,
    owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    test_plan_id INTEGER REFERENCES test_plans(id) ON DELETE SET NULL,
    test_card_id INTEGER REFERENCES test_cards(id) ON DELETE SET NULL,
    recurrence_frequency VARCHAR,
    recurrence_interval INTEGER DEFAULT 1,
    recurrence_end_date DATE,
    percent_complete FLOAT DEFAULT 0 CHECK (percent_complete >= 0 AND percent_complete <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_owner ON calendar_events(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_start_at ON calendar_events(start_at);
