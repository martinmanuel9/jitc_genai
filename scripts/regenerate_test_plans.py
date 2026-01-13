#!/usr/bin/env python3
"""
Test Plan Regeneration Script for Metadata Migration

This script regenerates all existing test plans with the new metadata structure
including heading-level information and page-based metadata.

Usage:
    python scripts/regenerate_test_plans.py [--dry-run] [--api-url URL]

Options:
    --dry-run       Preview actions without executing
    --api-url       FastAPI URL (default: http://localhost:8000)
    --plan-id       Only regenerate specific test plan by ID
    --backup        Create backup before regeneration (default: true)
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests.exceptions import RequestException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class TestPlanRegenerationManager:
    """Manages test plan regeneration with new metadata structure."""

    def __init__(self, api_url: str, dry_run: bool = False, create_backup: bool = True):
        self.api_url = api_url.rstrip('/')
        self.dry_run = dry_run
        self.create_backup = create_backup
        self.stats = {
            'plans_processed': 0,
            'plans_regenerated': 0,
            'plans_backed_up': 0,
            'errors': 0
        }
        self.backup_dir = Path('./test_plan_backups')

    def check_api_health(self) -> bool:
        """Check if FastAPI is accessible."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except RequestException as e:
            logger.error(f"API health check failed: {e}")
            return False

    def get_all_test_plans(self) -> List[Dict]:
        """Get list of all test plans."""
        try:
            response = requests.get(
                f"{self.api_url}/api/versioning/test-plans",
                params={"skip": 0, "limit": 1000}
            )
            response.raise_for_status()
            data = response.json()
            plans = data.get("plans", [])
            logger.info(f"Found {len(plans)} test plan(s)")
            return plans

        except RequestException as e:
            logger.error(f"Failed to fetch test plans: {e}")
            return []

    def get_test_plan_details(self, plan_id: int) -> Optional[Dict]:
        """Get detailed information about a specific test plan."""
        try:
            response = requests.get(f"{self.api_url}/api/versioning/test-plans/{plan_id}")
            response.raise_for_status()
            return response.json()

        except RequestException as e:
            logger.error(f"Failed to fetch test plan {plan_id}: {e}")
            return None

    def get_test_plan_versions(self, plan_id: int) -> List[Dict]:
        """Get all versions of a test plan."""
        try:
            response = requests.get(
                f"{self.api_url}/api/versioning/test-plans/{plan_id}/versions"
            )
            response.raise_for_status()
            data = response.json()
            return data.get("versions", [])

        except RequestException as e:
            logger.error(f"Failed to fetch versions for plan {plan_id}: {e}")
            return []

    def get_document_content(self, document_id: int) -> Optional[Dict]:
        """Get document content by ID."""
        try:
            response = requests.get(
                f"{self.api_url}/api/versioning/documents/{document_id}"
            )
            response.raise_for_status()
            return response.json()

        except RequestException as e:
            logger.error(f"Failed to fetch document {document_id}: {e}")
            return None

    def backup_test_plan(self, plan_id: int, plan_data: Dict) -> bool:
        """Backup test plan to JSON file."""
        try:
            if not self.create_backup:
                return True

            # Create backup directory if it doesn't exist
            if not self.dry_run:
                self.backup_dir.mkdir(parents=True, exist_ok=True)

            # Include all versions in backup
            versions = self.get_test_plan_versions(plan_id)

            backup_data = {
                "plan": plan_data,
                "versions": versions,
                "backup_timestamp": datetime.now().isoformat()
            }

            backup_file = self.backup_dir / f"test_plan_{plan_id}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            if not self.dry_run:
                with open(backup_file, 'w') as f:
                    json.dump(backup_data, f, indent=2)
                logger.info(f"Backed up test plan {plan_id} to {backup_file}")
                self.stats['plans_backed_up'] += 1
            else:
                logger.info(f"[DRY RUN] Would backup test plan {plan_id} to {backup_file}")

            return True

        except Exception as e:
            logger.error(f"Failed to backup test plan {plan_id}: {e}")
            return False

    def extract_generation_config(self, plan_data: Dict) -> Optional[Dict]:
        """
        Extract configuration needed to regenerate the test plan.

        This extracts source collections, document IDs, agent set, and other
        parameters from the existing plan metadata.
        """
        try:
            # Get the latest version to extract document content
            versions = self.get_test_plan_versions(plan_data.get('id'))
            if not versions:
                logger.error("No versions found for test plan")
                return None

            latest_version = max(versions, key=lambda v: v.get('version_number', 0))
            document_id = latest_version.get('document_id')

            if not document_id:
                logger.error("No document_id found in latest version")
                return None

            # Get document content to extract test plan JSON
            doc_content = self.get_document_content(document_id)
            if not doc_content:
                logger.error(f"Could not fetch document {document_id}")
                return None

            # Parse test plan JSON from document content
            content_json_str = doc_content.get('content_json')
            if not content_json_str:
                logger.error("No content_json found in document")
                return None

            test_plan_json = json.loads(content_json_str)

            # Extract metadata from test plan
            metadata = test_plan_json.get('metadata', {})

            # Build configuration
            config = {
                "doc_title": plan_data.get('title', 'Regenerated Test Plan'),
                "source_collections": metadata.get('source_collections', []),
                "source_doc_ids": metadata.get('source_doc_ids', []),
                "agent_set_id": metadata.get('agent_set_id', 1),
                "model_profile": metadata.get('model_profile', 'balanced'),
                "sectioning_strategy": "with_hierarchy",  # NEW: Use heading-based strategy
                "chunks_per_section": metadata.get('chunks_per_section')
            }

            # Validate required fields
            if not config['source_collections'] and not config['source_doc_ids']:
                logger.warning("No source collections or doc IDs found. Using defaults.")
                config['source_collections'] = ['uploaded_documents']

            logger.info(f"Extracted config: {json.dumps(config, indent=2)}")
            return config

        except Exception as e:
            logger.error(f"Failed to extract configuration: {e}", exc_info=True)
            return None

    def delete_test_plan(self, plan_id: int) -> bool:
        """Delete a test plan and all its versions."""
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would delete test plan {plan_id}")
                return True

            response = requests.delete(f"{self.api_url}/api/versioning/test-plans/{plan_id}")
            response.raise_for_status()
            logger.info(f"Deleted test plan {plan_id}")
            return True

        except RequestException as e:
            logger.error(f"Failed to delete test plan {plan_id}: {e}")
            self.stats['errors'] += 1
            return False

    def regenerate_test_plan(self, config: Dict) -> Optional[Dict]:
        """Generate new test plan with updated metadata structure."""
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would regenerate test plan with config: {json.dumps(config, indent=2)}")
                return {"success": True, "message": "Dry run - no actual generation"}

            logger.info("Starting test plan generation...")
            response = requests.post(
                f"{self.api_url}/api/json-test-plans/generate",
                json=config,
                timeout=600  # 10 minute timeout
            )
            response.raise_for_status()

            result = response.json()

            if result.get('success'):
                logger.info("Test plan regenerated successfully")
                self.stats['plans_regenerated'] += 1
                return result
            else:
                logger.error(f"Generation failed: {result.get('error', 'Unknown error')}")
                self.stats['errors'] += 1
                return None

        except RequestException as e:
            logger.error(f"Failed to regenerate test plan: {e}")
            self.stats['errors'] += 1
            return None
        except Exception as e:
            logger.error(f"Unexpected error during regeneration: {e}", exc_info=True)
            self.stats['errors'] += 1
            return None

    def process_test_plan(self, plan: Dict) -> bool:
        """Process a single test plan: backup, delete, regenerate."""
        plan_id = plan.get('id')
        plan_title = plan.get('title', 'Unknown')

        logger.info(f"\n{'='*70}")
        logger.info(f"Processing Test Plan: {plan_title} (ID: {plan_id})")
        logger.info(f"{'='*70}")

        self.stats['plans_processed'] += 1

        # Step 1: Get full plan details
        logger.info("1. Fetching plan details...")
        plan_details = self.get_test_plan_details(plan_id)
        if not plan_details:
            logger.error("Failed to fetch plan details. Skipping.")
            self.stats['errors'] += 1
            return False

        # Step 2: Backup
        logger.info("2. Creating backup...")
        if not self.backup_test_plan(plan_id, plan_details):
            logger.warning("Backup failed. Proceeding with caution...")

        # Step 3: Extract configuration
        logger.info("3. Extracting generation configuration...")
        config = self.extract_generation_config(plan_details)
        if not config:
            logger.error("Failed to extract configuration. Skipping regeneration.")
            self.stats['errors'] += 1
            return False

        # Step 4: Delete old plan
        logger.info("4. Deleting old test plan...")
        if not self.delete_test_plan(plan_id):
            logger.error("Failed to delete old plan. Skipping regeneration.")
            return False

        # Step 5: Regenerate with new metadata
        logger.info("5. Regenerating test plan with heading-based metadata...")
        result = self.regenerate_test_plan(config)

        if result:
            logger.info(f"Successfully regenerated test plan: {plan_title}")
            return True
        else:
            logger.error(f"Failed to regenerate test plan: {plan_title}")
            return False

    def run_regeneration(self, target_plan_id: Optional[int] = None):
        """Execute full regeneration process."""
        logger.info("="*70)
        logger.info("TEST PLAN REGENERATION MIGRATION")
        logger.info("="*70)

        if self.dry_run:
            logger.warning("DRY RUN MODE - No changes will be made")

        # Check API health
        logger.info("\n1. Checking API health...")
        if not self.check_api_health():
            logger.error("API is not accessible. Aborting regeneration.")
            return False

        # Get test plans
        logger.info("\n2. Fetching test plans...")
        if target_plan_id:
            plan = self.get_test_plan_details(target_plan_id)
            if not plan:
                logger.error(f"Test plan {target_plan_id} not found")
                return False
            plans = [plan]
        else:
            plans = self.get_all_test_plans()

        if not plans:
            logger.warning("No test plans found to regenerate")
            return True

        logger.info(f"\nWill process {len(plans)} test plan(s)")

        # Confirm if not dry run
        if not self.dry_run and not target_plan_id:
            logger.warning("\nWARNING: This will DELETE and REGENERATE all test plans!")
            logger.warning("Backups will be created, but manual edits will be lost.")
            confirm = input("\nType 'YES' to continue: ")
            if confirm != "YES":
                logger.info("Operation cancelled by user")
                return False

        # Process each plan
        logger.info("\n3. Processing test plans...\n")
        for idx, plan in enumerate(plans, 1):
            logger.info(f"\n[{idx}/{len(plans)}] Processing...")
            self.process_test_plan(plan)

            # Brief pause between regenerations to avoid overload
            if not self.dry_run and idx < len(plans):
                time.sleep(2)

        # Print summary
        logger.info("\n" + "="*70)
        logger.info("REGENERATION SUMMARY")
        logger.info("="*70)
        logger.info(f"Plans processed: {self.stats['plans_processed']}")
        logger.info(f"Plans backed up: {self.stats['plans_backed_up']}")
        logger.info(f"Plans regenerated: {self.stats['plans_regenerated']}")
        logger.info(f"Errors encountered: {self.stats['errors']}")
        logger.info("="*70)

        if self.dry_run:
            logger.info("\nDRY RUN COMPLETE - No actual changes were made")
            logger.info("Run without --dry-run to execute the regeneration")
        else:
            logger.info("\nREGENERATION COMPLETE")

            if self.stats['errors'] > 0:
                logger.warning(f"\n{self.stats['errors']} error(s) occurred. Check logs for details.")

        return True


def main():
    parser = argparse.ArgumentParser(
        description='Regenerate test plans with new metadata structure',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview actions without executing'
    )
    parser.add_argument(
        '--api-url',
        type=str,
        default='http://localhost:8000',
        help='FastAPI URL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--plan-id',
        type=int,
        help='Only regenerate specific test plan by ID'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backups (not recommended)'
    )

    args = parser.parse_args()

    # Create manager and run regeneration
    manager = TestPlanRegenerationManager(
        api_url=args.api_url,
        dry_run=args.dry_run,
        create_backup=not args.no_backup
    )

    try:
        success = manager.run_regeneration(target_plan_id=args.plan_id)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n\nRegeneration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during regeneration: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
