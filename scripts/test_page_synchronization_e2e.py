#!/usr/bin/env python3
"""
End-to-End Test Script for Page Synchronization Feature

This script performs comprehensive testing of the page synchronization functionality
across the entire pipeline: document upload, chunk metadata, test plan generation,
and API endpoints.

Usage:
    python scripts/test_page_synchronization_e2e.py [--api-url URL] [--test-pdf PATH]

Options:
    --api-url       FastAPI URL (default: http://localhost:8000)
    --test-pdf      Path to test PDF file (default: use repo PDFs)
    --cleanup       Clean up test data after completion (default: true)
    --verbose       Enable verbose output
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from requests.exceptions import RequestException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class E2ETestRunner:
    """End-to-end test runner for page synchronization feature."""

    def __init__(self, api_url: str, cleanup: bool = True, verbose: bool = False):
        self.api_url = api_url.rstrip('/')
        self.cleanup = cleanup
        self.verbose = verbose
        self.test_collection = f"e2e_test_{int(time.time())}"
        self.test_results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }
        self.test_data = {
            'document_id': None,
            'test_plan_id': None,
            'collection_name': self.test_collection
        }

    def log_test(self, test_name: str, passed: bool, message: str = "", details: Optional[Dict] = None):
        """Log test result."""
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"

        log_msg = f"{symbol} [{status}] {test_name}"
        if message:
            log_msg += f": {message}"

        if passed:
            logger.info(log_msg)
            self.test_results['passed'].append(test_name)
        else:
            logger.error(log_msg)
            self.test_results['failed'].append(test_name)

        if self.verbose and details:
            logger.debug(f"Details: {json.dumps(details, indent=2)}")

    def log_warning(self, test_name: str, message: str):
        """Log test warning."""
        logger.warning(f"⚠ [WARN] {test_name}: {message}")
        self.test_results['warnings'].append(f"{test_name}: {message}")

    def check_api_health(self) -> bool:
        """Test 0: Check API health."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            passed = response.status_code == 200
            self.log_test("API Health Check", passed, "API is accessible" if passed else "API not accessible")
            return passed
        except Exception as e:
            self.log_test("API Health Check", False, f"Exception: {e}")
            return False

    def create_test_collection(self) -> bool:
        """Test 1: Create test collection."""
        try:
            response = requests.post(
                f"{self.api_url}/api/vectordb/collection/create",
                params={"collection_name": self.test_collection}
            )

            passed = response.status_code == 200
            self.log_test(
                "Create Test Collection",
                passed,
                f"Collection '{self.test_collection}' created" if passed else f"Failed: {response.text}"
            )
            return passed

        except Exception as e:
            self.log_test("Create Test Collection", False, f"Exception: {e}")
            return False

    def upload_test_document(self, pdf_path: Path) -> Tuple[bool, Optional[str]]:
        """Test 2: Upload test document with heading-based chunking."""
        try:
            logger.info(f"Uploading test PDF: {pdf_path.name}")

            with open(pdf_path, 'rb') as f:
                files = {'files': (pdf_path.name, f, 'application/pdf')}
                params = {
                    'collection_name': self.test_collection,
                    'chunk_size': 1000,
                    'chunk_overlap': 200,
                    'store_images': 'true',
                    'vision_models': 'llava_7b',
                    'enable_ocr': 'false'
                }

                response = requests.post(
                    f"{self.api_url}/api/vectordb/documents/upload-and-process",
                    files=files,
                    params=params,
                    timeout=300
                )

                if response.status_code == 200:
                    result = response.json()
                    job_id = result.get('job_id')

                    # Wait for job completion
                    logger.info(f"Job ID: {job_id}. Waiting for completion...")
                    success, doc_id = self.wait_for_job_completion(job_id)

                    if success:
                        self.test_data['document_id'] = doc_id
                        self.log_test("Upload Test Document", True, f"Document uploaded: {doc_id}")
                        return True, doc_id
                    else:
                        self.log_test("Upload Test Document", False, "Job processing failed")
                        return False, None
                else:
                    self.log_test("Upload Test Document", False, f"Upload failed: {response.text}")
                    return False, None

        except Exception as e:
            self.log_test("Upload Test Document", False, f"Exception: {e}")
            return False, None

    def wait_for_job_completion(self, job_id: str, timeout: int = 120) -> Tuple[bool, Optional[str]]:
        """Wait for ingestion job to complete."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    f"{self.api_url}/api/vectordb/job-status/{job_id}",
                    timeout=5
                )

                if response.status_code == 200:
                    status_data = response.json()
                    status = status_data.get('status', 'unknown')

                    if status == 'completed':
                        # Get document ID from result
                        result = status_data.get('result', {})
                        doc_ids = result.get('document_ids', [])
                        if doc_ids:
                            return True, doc_ids[0]
                        return True, None

                    elif status == 'failed':
                        logger.error(f"Job failed: {status_data.get('error')}")
                        return False, None

                    elif status in ['pending', 'processing']:
                        logger.debug(f"Job status: {status}")
                        time.sleep(5)
                        continue

                time.sleep(2)

            except Exception as e:
                logger.warning(f"Error checking job status: {e}")
                time.sleep(2)

        logger.error("Job timeout - document may still be processing")
        return False, None

    def verify_chunk_metadata(self) -> bool:
        """Test 3: Verify chunks have new metadata fields."""
        try:
            response = requests.get(
                f"{self.api_url}/api/vectordb/documents",
                params={"collection_name": self.test_collection}
            )

            if response.status_code != 200:
                self.log_test("Verify Chunk Metadata", False, f"Failed to fetch documents: {response.text}")
                return False

            documents = response.json().get('documents', [])
            if not documents:
                self.log_test("Verify Chunk Metadata", False, "No documents found in collection")
                return False

            # Get chunks for first document
            doc_id = documents[0].get('id', documents[0].get('document_id'))

            response = requests.get(
                f"{self.api_url}/api/vectordb/collection",
                params={"collection_name": self.test_collection}
            )

            if response.status_code != 200:
                self.log_test("Verify Chunk Metadata", False, f"Failed to fetch collection data: {response.text}")
                return False

            collection_data = response.json()
            chunks = collection_data.get('documents', [])
            metadatas = collection_data.get('metadatas', [])

            if not chunks or not metadatas:
                self.log_test("Verify Chunk Metadata", False, "No chunks found")
                return False

            # Check for required metadata fields
            required_fields = ['page_number', 'chunk_type']
            optional_fields = ['heading_text', 'heading_level', 'parent_heading']

            sample_metadata = metadatas[0] if metadatas else {}

            missing_required = [f for f in required_fields if f not in sample_metadata]
            present_optional = [f for f in optional_fields if f in sample_metadata]

            if missing_required:
                self.log_test(
                    "Verify Chunk Metadata",
                    False,
                    f"Missing required fields: {missing_required}"
                )
                return False

            # Verify page_number is numeric
            page_number = sample_metadata.get('page_number')
            if not isinstance(page_number, int):
                self.log_test(
                    "Verify Chunk Metadata",
                    False,
                    f"page_number is not numeric: {type(page_number)}"
                )
                return False

            details = {
                "total_chunks": len(chunks),
                "sample_metadata": sample_metadata,
                "optional_fields_present": present_optional
            }

            self.log_test(
                "Verify Chunk Metadata",
                True,
                f"Found {len(chunks)} chunks with correct metadata",
                details
            )

            # Warning if optional fields are missing
            if not present_optional:
                self.log_warning(
                    "Chunk Metadata",
                    "Optional heading fields not present - heading-based chunking may not be enabled"
                )

            return True

        except Exception as e:
            self.log_test("Verify Chunk Metadata", False, f"Exception: {e}")
            return False

    def generate_test_plan(self) -> Tuple[bool, Optional[Dict]]:
        """Test 4: Generate test plan with sectioning_strategy='with_hierarchy'."""
        try:
            logger.info("Generating test plan with heading-based sectioning...")

            config = {
                "source_collections": [self.test_collection],
                "doc_title": "E2E Test Plan",
                "agent_set_id": 1,
                "model_profile": "fast",
                "sectioning_strategy": "with_hierarchy"
            }

            response = requests.post(
                f"{self.api_url}/api/json-test-plans/generate",
                json=config,
                timeout=600
            )

            if response.status_code != 200:
                self.log_test("Generate Test Plan", False, f"Generation failed: {response.text}")
                return False, None

            result = response.json()

            if not result.get('success'):
                self.log_test("Generate Test Plan", False, f"Error: {result.get('error')}")
                return False, None

            test_plan = result.get('test_plan', {})

            if not test_plan:
                self.log_test("Generate Test Plan", False, "No test plan returned")
                return False, None

            # Store test plan ID if available
            if 'id' in test_plan:
                self.test_data['test_plan_id'] = test_plan['id']

            self.log_test("Generate Test Plan", True, "Test plan generated successfully")
            return True, test_plan

        except Exception as e:
            self.log_test("Generate Test Plan", False, f"Exception: {e}")
            return False, None

    def verify_test_plan_metadata(self, test_plan: Dict) -> bool:
        """Test 5: Verify test plan JSON has required metadata fields."""
        try:
            sections = test_plan.get('test_plan', {}).get('sections', [])

            if not sections:
                self.log_test("Verify Test Plan Metadata", False, "No sections in test plan")
                return False

            # Check required fields in sections
            required_fields = ['source_page', 'heading_level', 'source_section_key']
            optional_fields = ['parent_heading']

            sample_section = sections[0]
            missing_required = [f for f in required_fields if f not in sample_section]
            present_optional = [f for f in optional_fields if f in sample_section]

            if missing_required:
                self.log_test(
                    "Verify Test Plan Metadata",
                    False,
                    f"Missing required fields: {missing_required}",
                    {"sample_section": sample_section}
                )
                return False

            # Verify source_page is numeric
            source_page = sample_section.get('source_page')
            if not isinstance(source_page, int):
                self.log_test(
                    "Verify Test Plan Metadata",
                    False,
                    f"source_page is not numeric: {type(source_page)}"
                )
                return False

            # Verify heading_level is numeric
            heading_level = sample_section.get('heading_level')
            if not isinstance(heading_level, int):
                self.log_test(
                    "Verify Test Plan Metadata",
                    False,
                    f"heading_level is not numeric: {type(heading_level)}"
                )
                return False

            details = {
                "total_sections": len(sections),
                "sample_section_metadata": {
                    "source_page": source_page,
                    "heading_level": heading_level,
                    "has_parent_heading": 'parent_heading' in sample_section
                }
            }

            self.log_test(
                "Verify Test Plan Metadata",
                True,
                f"All {len(sections)} sections have correct metadata",
                details
            )

            # Warning if parent_heading is missing
            if not present_optional:
                self.log_warning(
                    "Test Plan Metadata",
                    "parent_heading field not present in sections"
                )

            return True

        except Exception as e:
            self.log_test("Verify Test Plan Metadata", False, f"Exception: {e}")
            return False

    def test_page_content_api(self) -> bool:
        """Test 6: Test /api/vectordb/documents/page-content endpoint."""
        try:
            if not self.test_data.get('document_id'):
                self.log_test("Test Page Content API", False, "No document ID available")
                return False

            # Test with page 1
            response = requests.get(
                f"{self.api_url}/api/vectordb/documents/page-content",
                params={
                    "collection_name": self.test_collection,
                    "document_id": self.test_data['document_id'],
                    "page_number": 1
                }
            )

            if response.status_code != 200:
                self.log_test("Test Page Content API", False, f"API call failed: {response.text}")
                return False

            result = response.json()

            # Verify response structure
            required_fields = ['page_number', 'document_id', 'headings']
            missing_fields = [f for f in required_fields if f not in result]

            if missing_fields:
                self.log_test(
                    "Test Page Content API",
                    False,
                    f"Missing fields in response: {missing_fields}"
                )
                return False

            headings = result.get('headings', [])

            if not headings:
                self.log_warning("Page Content API", "No headings found on page 1")

            # Verify heading structure
            if headings:
                sample_heading = headings[0]
                required_heading_fields = ['heading_text', 'heading_level', 'body_text']
                missing_heading_fields = [f for f in required_heading_fields if f not in sample_heading]

                if missing_heading_fields:
                    self.log_test(
                        "Test Page Content API",
                        False,
                        f"Missing fields in heading: {missing_heading_fields}"
                    )
                    return False

            details = {
                "page_number": result.get('page_number'),
                "total_headings": len(headings),
                "sample_heading": headings[0] if headings else None
            }

            self.log_test(
                "Test Page Content API",
                True,
                f"Page content API returned {len(headings)} heading(s)",
                details
            )

            return True

        except Exception as e:
            self.log_test("Test Page Content API", False, f"Exception: {e}")
            return False

    def cleanup_test_data(self) -> bool:
        """Clean up test collection and data."""
        if not self.cleanup:
            logger.info("Cleanup skipped (--no-cleanup flag)")
            return True

        try:
            logger.info("Cleaning up test data...")

            # Delete test collection
            response = requests.delete(
                f"{self.api_url}/api/vectordb/collection/{self.test_collection}"
            )

            if response.status_code == 200:
                logger.info(f"Deleted test collection: {self.test_collection}")
                return True
            else:
                logger.warning(f"Failed to delete test collection: {response.text}")
                return False

        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
            return False

    def print_summary(self):
        """Print test summary."""
        total_tests = len(self.test_results['passed']) + len(self.test_results['failed'])
        passed_count = len(self.test_results['passed'])
        failed_count = len(self.test_results['failed'])
        warnings_count = len(self.test_results['warnings'])

        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total Tests:  {total_tests}")
        print(f"Passed:       {passed_count} ✓")
        print(f"Failed:       {failed_count} ✗")
        print(f"Warnings:     {warnings_count} ⚠")
        print(f"Success Rate: {passed_count/total_tests*100:.1f}%" if total_tests > 0 else "N/A")
        print("="*70)

        if self.test_results['failed']:
            print("\nFailed Tests:")
            for test_name in self.test_results['failed']:
                print(f"  ✗ {test_name}")

        if self.test_results['warnings']:
            print("\nWarnings:")
            for warning in self.test_results['warnings']:
                print(f"  ⚠ {warning}")

        print("\n")

    def run_all_tests(self, pdf_path: Path):
        """Run all end-to-end tests."""
        logger.info("="*70)
        logger.info("STARTING END-TO-END TESTS")
        logger.info("="*70)

        # Test 0: API Health
        if not self.check_api_health():
            logger.error("API health check failed. Aborting tests.")
            return False

        # Test 1: Create Collection
        if not self.create_test_collection():
            logger.error("Failed to create test collection. Aborting tests.")
            return False

        # Test 2: Upload Document
        success, doc_id = self.upload_test_document(pdf_path)
        if not success:
            logger.error("Failed to upload document. Aborting tests.")
            self.cleanup_test_data()
            return False

        # Test 3: Verify Chunk Metadata
        self.verify_chunk_metadata()

        # Test 4: Generate Test Plan
        success, test_plan = self.generate_test_plan()
        if success and test_plan:
            # Test 5: Verify Test Plan Metadata
            self.verify_test_plan_metadata(test_plan)

        # Test 6: Test Page Content API
        self.test_page_content_api()

        # Cleanup
        self.cleanup_test_data()

        # Print Summary
        self.print_summary()

        # Return overall success
        return len(self.test_results['failed']) == 0


def main():
    parser = argparse.ArgumentParser(
        description='End-to-end test for page synchronization feature',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--api-url',
        type=str,
        default='http://localhost:8000',
        help='FastAPI URL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--test-pdf',
        type=Path,
        help='Path to test PDF file'
    )
    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Skip cleanup after tests (keep test data)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Find test PDF
    if args.test_pdf:
        pdf_path = args.test_pdf
    else:
        # Use repo PDFs as fallback
        repo_pdfs = [
            Path('/home/martinmlopez/repos/jitc_genai/rfc9293.pdf'),
            Path('/home/martinmlopez/repos/jitc_genai/disr_ipv6_50.pdf'),
            Path('/home/martinmlopez/repos/jitc_genai/ipv6v4_may09.pdf')
        ]

        pdf_path = next((p for p in repo_pdfs if p.exists()), None)

    if not pdf_path or not pdf_path.exists():
        logger.error(f"Test PDF not found: {pdf_path}")
        logger.error("Please specify a valid PDF file with --test-pdf")
        sys.exit(1)

    logger.info(f"Using test PDF: {pdf_path}")

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create test runner and execute
    runner = E2ETestRunner(
        api_url=args.api_url,
        cleanup=not args.no_cleanup,
        verbose=args.verbose
    )

    try:
        success = runner.run_all_tests(pdf_path)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n\nTests interrupted by user")
        runner.cleanup_test_data()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during tests: {e}", exc_info=True)
        runner.cleanup_test_data()
        sys.exit(1)


if __name__ == "__main__":
    main()
