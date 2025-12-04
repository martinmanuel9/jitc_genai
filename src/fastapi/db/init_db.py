#!/usr/bin/env python3
"""
Database Initialization Module

Handles idempotent database initialization with migration tracking.
Safe to run on every startup - only applies new migrations.

Features:
- Migration tracking table to prevent re-running migrations
- Checksum validation to detect modified migrations
- Automatic rollback on failure
- Detailed logging
- Safe for both fresh deploys and restarts with existing data
"""

import os
import sys
import hashlib
import time
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError
from core.database import engine, SessionLocal
import logging

# Get logger without configuring (let uvicorn handle logging configuration)
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "init_agent_creation"


class MigrationTracker:
    """Tracks applied migrations in the database"""

    TRACKING_TABLE = "schema_migrations"

    def __init__(self):
        self.session = SessionLocal()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def ensure_tracking_table_exists(self) -> bool:
        """
        Ensure the migration tracking table exists.
        Creates it if it doesn't exist.

        Returns:
            bool: True if table exists or was created successfully
        """
        try:
            # Check if table exists
            inspector = inspect(engine)
            if self.TRACKING_TABLE in inspector.get_table_names():
                logger.info(f" Migration tracking table '{self.TRACKING_TABLE}' exists")
                return True

            # Create tracking table
            logger.info(f"Creating migration tracking table '{self.TRACKING_TABLE}'...")
            tracking_table_sql = MIGRATIONS_DIR / "000_create_migrations_table.sql"

            if not tracking_table_sql.exists():
                logger.error(f"Migration tracking table SQL not found: {tracking_table_sql}")
                return False

            with open(tracking_table_sql, 'r') as f:
                sql = f.read()

            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()

            logger.info(f" Created migration tracking table '{self.TRACKING_TABLE}'")
            return True

        except Exception as e:
            logger.error(f"Failed to create tracking table: {e}")
            return False

    def is_migration_applied(self, migration_name: str) -> bool:
        """
        Check if a migration has already been applied.

        Args:
            migration_name: Name of the migration file

        Returns:
            bool: True if migration was already applied successfully
        """
        try:
            result = self.session.execute(
                text(f"""
                    SELECT COUNT(*)
                    FROM {self.TRACKING_TABLE}
                    WHERE migration_name = :name AND status = 'success'
                """),
                {"name": migration_name}
            )
            count = result.scalar()
            return count > 0

        except Exception as e:
            logger.warning(f"Error checking migration status: {e}")
            return False

    def get_migration_checksum(self, migration_name: str) -> Optional[str]:
        """
        Get the stored checksum for a migration.

        Args:
            migration_name: Name of the migration file

        Returns:
            str: Checksum if found, None otherwise
        """
        try:
            result = self.session.execute(
                text(f"""
                    SELECT checksum
                    FROM {self.TRACKING_TABLE}
                    WHERE migration_name = :name
                """),
                {"name": migration_name}
            )
            row = result.fetchone()
            return row[0] if row else None

        except Exception as e:
            logger.warning(f"Error getting migration checksum: {e}")
            return None

    def record_migration(
        self,
        migration_name: str,
        checksum: str,
        execution_time_ms: int,
        status: str = 'success',
        error_message: Optional[str] = None
    ):
        """
        Record a migration in the tracking table.

        Args:
            migration_name: Name of the migration file
            checksum: Hash of migration content
            execution_time_ms: Time taken to execute in milliseconds
            status: 'success', 'failed', or 'pending'
            error_message: Error message if failed
        """
        try:
            self.session.execute(
                text(f"""
                    INSERT INTO {self.TRACKING_TABLE}
                    (migration_name, checksum, execution_time_ms, status, error_message)
                    VALUES (:name, :checksum, :time_ms, :status, :error)
                    ON CONFLICT (migration_name)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        error_message = EXCLUDED.error_message,
                        applied_at = CURRENT_TIMESTAMP,
                        execution_time_ms = EXCLUDED.execution_time_ms,
                        checksum = EXCLUDED.checksum
                """),
                {
                    "name": migration_name,
                    "checksum": checksum,
                    "time_ms": execution_time_ms,
                    "status": status,
                    "error": error_message
                }
            )
            self.session.commit()

        except Exception as e:
            logger.error(f"Failed to record migration: {e}")
            self.session.rollback()
            raise


def calculate_file_checksum(filepath: Path) -> str:
    """
    Calculate SHA-256 checksum of a file.

    Args:
        filepath: Path to the file

    Returns:
        str: Hex digest of the file's checksum
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_migration_files() -> List[Tuple[str, Path]]:
    """
    Get list of migration files in order.

    Returns:
        List of tuples (migration_name, filepath) sorted by name
    """
    if not MIGRATIONS_DIR.exists():
        logger.error(f"Migrations directory not found: {MIGRATIONS_DIR}")
        return []

    migrations = []
    for filepath in sorted(MIGRATIONS_DIR.glob("*.sql")):
        # Skip the tracking table creation (handled separately)
        if filepath.name.startswith("000_"):
            continue

        migrations.append((filepath.name, filepath))

    return migrations


def run_migration_file(
    migration_name: str,
    filepath: Path,
    tracker: MigrationTracker
) -> bool:
    """
    Run a single migration file if not already applied.

    Args:
        migration_name: Name of the migration
        filepath: Path to the migration SQL file
        tracker: MigrationTracker instance

    Returns:
        bool: True if migration was applied or already exists, False on failure
    """
    # Calculate checksum
    checksum = calculate_file_checksum(filepath)

    # Check if already applied
    if tracker.is_migration_applied(migration_name):
        # Verify checksum matches
        stored_checksum = tracker.get_migration_checksum(migration_name)
        if stored_checksum != checksum:
            logger.warning(
                f"  Migration '{migration_name}' has been modified! "
                f"Stored checksum: {stored_checksum}, Current: {checksum}"
            )
            # In production, you might want to fail here or require manual intervention
        else:
            logger.info(f"Skipping '{migration_name}' (already applied)")
        return True

    # Run the migration
    logger.info(f"Running migration: {migration_name}")

    try:
        start_time = time.time()

        with open(filepath, 'r') as f:
            sql = f.read()

        with engine.connect() as conn:
            # Execute migration
            conn.execute(text(sql))
            conn.commit()

        execution_time_ms = int((time.time() - start_time) * 1000)

        # Record success
        tracker.record_migration(
            migration_name,
            checksum,
            execution_time_ms,
            status='success'
        )

        logger.info(f" Migration completed: {migration_name} ({execution_time_ms}ms)")
        return True

    except SQLAlchemyError as e:
        error_msg = str(e)
        logger.error(f" Migration failed: {migration_name}")
        logger.error(f"  Error: {error_msg}")

        # Record failure
        try:
            tracker.record_migration(
                migration_name,
                checksum,
                0,
                status='failed',
                error_message=error_msg[:500]  # Truncate long errors
            )
        except Exception as record_error:
            logger.error(f"Failed to record migration failure: {record_error}")

        return False


def initialize_database(force: bool = False) -> bool:
    """
    Initialize database with all migrations.
    Idempotent - safe to run multiple times.

    Args:
        force: If True, re-run all migrations (dangerous!)

    Returns:
        bool: True if initialization successful
    """
    logger.info("=" * 70)
    logger.info("DATABASE INITIALIZATION")
    logger.info("=" * 70)

    try:
        # Step 1: Ensure migration tracking table exists
        with MigrationTracker() as tracker:
            if not tracker.ensure_tracking_table_exists():
                logger.error("Failed to initialize migration tracking")
                return False

            # Step 2: Get all migration files
            migrations = get_migration_files()

            if not migrations:
                logger.warning("No migration files found")
                return True

            logger.info(f"Found {len(migrations)} migration(s) to process")

            # Step 3: Run each migration
            success_count = 0
            skip_count = 0
            fail_count = 0

            for migration_name, filepath in migrations:
                if force or not tracker.is_migration_applied(migration_name):
                    if run_migration_file(migration_name, filepath, tracker):
                        success_count += 1
                    else:
                        fail_count += 1
                        logger.error(f"Stopping at first failure: {migration_name}")
                        break
                else:
                    skip_count += 1

            # Step 4: Summary
            logger.info("=" * 70)
            logger.info("MIGRATION SUMMARY")
            logger.info("=" * 70)
            logger.info(f" Applied: {success_count}")
            logger.info(f" Skipped: {skip_count} (already applied)")
            logger.info(f" Failed: {fail_count}")
            logger.info("=" * 70)

            if fail_count > 0:
                logger.error("Database initialization failed")
                return False

            logger.info(" Database initialization completed successfully")
            return True

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False


def verify_migrations() -> dict:
    """
    Verify the state of all migrations.

    Returns:
        dict: Summary of migration states
    """
    with MigrationTracker() as tracker:
        if not tracker.ensure_tracking_table_exists():
            return {"error": "Migration tracking table doesn't exist"}

        migrations = get_migration_files()
        summary = {
            "total": len(migrations),
            "applied": 0,
            "pending": 0,
            "failed": 0,
            "modified": 0,
            "migrations": []
        }

        for migration_name, filepath in migrations:
            is_applied = tracker.is_migration_applied(migration_name)
            checksum = calculate_file_checksum(filepath)
            stored_checksum = tracker.get_migration_checksum(migration_name)

            state = {
                "name": migration_name,
                "applied": is_applied,
                "checksum_match": checksum == stored_checksum if stored_checksum else None
            }

            if is_applied:
                summary["applied"] += 1
                if checksum != stored_checksum:
                    summary["modified"] += 1
                    state["warning"] = "Modified after application"
            else:
                summary["pending"] += 1

            summary["migrations"].append(state)

        return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database initialization and migration management")
    parser.add_argument("--force", action="store_true", help="Force re-run all migrations (DANGEROUS)")
    parser.add_argument("--verify", action="store_true", help="Verify migration state without running")

    args = parser.parse_args()

    if args.verify:
        # Verify migrations
        summary = verify_migrations()
        print("\n" + "=" * 70)
        print("MIGRATION VERIFICATION")
        print("=" * 70)
        print(f"Total migrations: {summary['total']}")
        print(f"Applied: {summary['applied']}")
        print(f"Pending: {summary['pending']}")
        print(f"Failed: {summary['failed']}")
        print(f"Modified: {summary['modified']}")
        print("=" * 70)

        for migration in summary["migrations"]:
            status = "" if migration["applied"] else "⏳"
            print(f"{status} {migration['name']}")
            if migration.get("warning"):
                print(f"    {migration['warning']}")

        sys.exit(0)
    else:
        # Run initialization
        success = initialize_database(force=args.force)
        sys.exit(0 if success else 1)
