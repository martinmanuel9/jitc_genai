#!/usr/bin/env python3
"""
Re-ingestion Script for Heading-Based Chunking Migration

This script re-ingests all documents with heading-based chunking enabled.
It lists all collections, backs up metadata, deletes collections, and
re-uploads PDFs from the document_backup directory.

Usage:
    python scripts/reingest_all_documents.py [--dry-run] [--backup-dir PATH]

Options:
    --dry-run       Preview actions without executing
    --backup-dir    Directory containing PDF backups (default: ./document_backup)
    --api-url       FastAPI URL (default: http://localhost:8000)
    --collection    Only process specific collection (default: all)
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import requests
from requests.exceptions import RequestException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ReingestionManager:
    """Manages document re-ingestion with heading-based chunking."""

    def __init__(self, api_url: str, backup_dir: Path, dry_run: bool = False):
        self.api_url = api_url.rstrip('/')
        self.backup_dir = backup_dir
        self.dry_run = dry_run
        self.stats = {
            'collections_deleted': 0,
            'documents_reingested': 0,
            'errors': 0
        }

    def check_api_health(self) -> bool:
        """Check if FastAPI is accessible."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except RequestException as e:
            logger.error(f"API health check failed: {e}")
            return False

    def get_all_collections(self) -> List[str]:
        """Get list of all ChromaDB collections."""
        try:
            response = requests.get(f"{self.api_url}/api/vectordb/collections")
            response.raise_for_status()
            collections = response.json().get("collections", [])
            logger.info(f"Found {len(collections)} collections")
            return collections
        except RequestException as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def get_documents_in_collection(self, collection_name: str) -> List[Dict]:
        """Get all documents in a collection."""
        try:
            response = requests.get(
                f"{self.api_url}/api/vectordb/documents",
                params={"collection_name": collection_name}
            )
            response.raise_for_status()
            return response.json().get("documents", [])
        except RequestException as e:
            logger.error(f"Failed to list documents in '{collection_name}': {e}")
            return []

    def backup_collection_metadata(self, collection_name: str) -> Optional[Dict]:
        """Backup collection metadata to JSON file."""
        try:
            documents = self.get_documents_in_collection(collection_name)

            backup_data = {
                "collection_name": collection_name,
                "document_count": len(documents),
                "documents": documents,
                "backup_timestamp": datetime.now().isoformat()
            }

            # Save to backup directory
            backup_file = self.backup_dir / f"{collection_name}_metadata_backup.json"

            if not self.dry_run:
                with open(backup_file, 'w') as f:
                    json.dump(backup_data, f, indent=2)
                logger.info(f"Backed up metadata for '{collection_name}' to {backup_file}")
            else:
                logger.info(f"[DRY RUN] Would backup metadata for '{collection_name}' to {backup_file}")

            return backup_data

        except Exception as e:
            logger.error(f"Failed to backup metadata for '{collection_name}': {e}")
            return None

    def delete_collection(self, collection_name: str) -> bool:
        """Delete a ChromaDB collection."""
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would delete collection: {collection_name}")
                return True

            response = requests.delete(f"{self.api_url}/api/vectordb/collection/{collection_name}")
            response.raise_for_status()
            logger.info(f"Deleted collection: {collection_name}")
            self.stats['collections_deleted'] += 1
            return True

        except RequestException as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            self.stats['errors'] += 1
            return False

    def create_collection(self, collection_name: str) -> bool:
        """Create a new ChromaDB collection."""
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would create collection: {collection_name}")
                return True

            response = requests.post(
                f"{self.api_url}/api/vectordb/collection/create",
                params={"collection_name": collection_name}
            )
            response.raise_for_status()
            logger.info(f"Created collection: {collection_name}")
            return True

        except RequestException as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            self.stats['errors'] += 1
            return False

    def reingest_document(self, pdf_path: Path, collection_name: str) -> bool:
        """Upload and process a document with heading-based chunking."""
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would reingest: {pdf_path.name} -> {collection_name}")
                return True

            with open(pdf_path, 'rb') as f:
                files = {'files': (pdf_path.name, f, 'application/pdf')}
                params = {
                    'collection_name': collection_name,
                    'chunk_size': 1000,
                    'chunk_overlap': 200,
                    'store_images': 'true',
                    'vision_models': 'llava_7b',
                    'enable_ocr': 'false'
                }

                logger.info(f"Uploading: {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")

                response = requests.post(
                    f"{self.api_url}/api/vectordb/documents/upload-and-process",
                    files=files,
                    params=params,
                    timeout=300  # 5 minute timeout
                )
                response.raise_for_status()

                result = response.json()
                job_id = result.get('job_id')
                logger.info(f"Document uploaded successfully. Job ID: {job_id}")
                self.stats['documents_reingested'] += 1
                return True

        except RequestException as e:
            logger.error(f"Failed to reingest '{pdf_path.name}': {e}")
            self.stats['errors'] += 1
            return False
        except Exception as e:
            logger.error(f"Unexpected error reingesting '{pdf_path.name}': {e}")
            self.stats['errors'] += 1
            return False

    def find_pdfs_in_backup(self) -> List[Path]:
        """Find all PDF files in backup directory."""
        if not self.backup_dir.exists():
            logger.error(f"Backup directory not found: {self.backup_dir}")
            return []

        pdfs = list(self.backup_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdfs)} PDF files in {self.backup_dir}")
        return sorted(pdfs)

    def run_migration(self, target_collection: Optional[str] = None):
        """Execute full migration process."""
        logger.info("="*70)
        logger.info("DOCUMENT RE-INGESTION MIGRATION")
        logger.info("="*70)

        if self.dry_run:
            logger.warning("DRY RUN MODE - No changes will be made")

        # Check API health
        logger.info("\n1. Checking API health...")
        if not self.check_api_health():
            logger.error("API is not accessible. Aborting migration.")
            return False

        # Verify backup directory
        logger.info("\n2. Verifying backup directory...")
        pdfs = self.find_pdfs_in_backup()
        if not pdfs:
            logger.error("No PDF files found in backup directory. Aborting migration.")
            return False

        # List collections
        logger.info("\n3. Listing existing collections...")
        collections = self.get_all_collections()

        # Filter system collections
        system_collections = {'_system', 'chroma_internal'}
        user_collections = [c for c in collections if c not in system_collections]

        if target_collection:
            if target_collection not in user_collections:
                logger.error(f"Collection '{target_collection}' not found")
                return False
            user_collections = [target_collection]

        logger.info(f"Will process {len(user_collections)} collection(s): {', '.join(user_collections)}")

        # Backup and delete collections
        logger.info("\n4. Backing up and deleting collections...")
        for collection_name in user_collections:
            logger.info(f"\n  Processing collection: {collection_name}")

            # Backup metadata
            self.backup_collection_metadata(collection_name)

            # Delete collection
            if not self.delete_collection(collection_name):
                logger.warning(f"Failed to delete '{collection_name}', skipping...")
                continue

        # Re-create collections and re-ingest documents
        logger.info("\n5. Re-ingesting documents with heading-based chunking...")

        # Assume we want to recreate the same collection structure
        # For simplicity, use 'uploaded_documents' as default collection
        default_collection = "uploaded_documents"

        if not self.dry_run:
            if default_collection not in self.get_all_collections():
                self.create_collection(default_collection)

        for pdf_path in pdfs:
            logger.info(f"\n  Processing: {pdf_path.name}")
            self.reingest_document(pdf_path, default_collection)

        # Print summary
        logger.info("\n" + "="*70)
        logger.info("MIGRATION SUMMARY")
        logger.info("="*70)
        logger.info(f"Collections deleted: {self.stats['collections_deleted']}")
        logger.info(f"Documents re-ingested: {self.stats['documents_reingested']}")
        logger.info(f"Errors encountered: {self.stats['errors']}")
        logger.info("="*70)

        if self.dry_run:
            logger.info("\nDRY RUN COMPLETE - No actual changes were made")
            logger.info("Run without --dry-run to execute the migration")
        else:
            logger.info("\nMIGRATION COMPLETE")

            if self.stats['errors'] > 0:
                logger.warning(f"\n{self.stats['errors']} error(s) occurred. Check logs for details.")

        return True


def main():
    parser = argparse.ArgumentParser(
        description='Re-ingest all documents with heading-based chunking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview actions without executing'
    )
    parser.add_argument(
        '--backup-dir',
        type=Path,
        default=Path('./document_backup'),
        help='Directory containing PDF backups (default: ./document_backup)'
    )
    parser.add_argument(
        '--api-url',
        type=str,
        default='http://localhost:8000',
        help='FastAPI URL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--collection',
        type=str,
        help='Only process specific collection (default: all collections)'
    )

    args = parser.parse_args()

    # Ensure backup directory exists
    if not args.dry_run and not args.backup_dir.exists():
        logger.error(f"Backup directory does not exist: {args.backup_dir}")
        logger.info("Please create it and add your PDF backups before running.")
        sys.exit(1)

    # Create manager and run migration
    manager = ReingestionManager(
        api_url=args.api_url,
        backup_dir=args.backup_dir,
        dry_run=args.dry_run
    )

    try:
        success = manager.run_migration(target_collection=args.collection)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n\nMigration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during migration: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
