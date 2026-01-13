# Migration Guide: Heading-Based Chunking & Page Synchronization

## Overview

This guide provides step-by-step instructions for migrating your existing document ingestion and test plan system to the new **heading-based chunking** and **page synchronization** architecture.

**Version:** 1.0
**Date:** 2026-01-11
**Estimated Migration Time:** 2-4 hours (depending on data volume)

---

## Table of Contents

1. [Why Migration is Needed](#why-migration-is-needed)
2. [What Has Changed](#what-has-changed)
3. [Prerequisites](#prerequisites)
4. [Pre-Migration Checklist](#pre-migration-checklist)
5. [Migration Steps](#migration-steps)
6. [Post-Migration Verification](#post-migration-verification)
7. [Rollback Procedure](#rollback-procedure)
8. [Known Limitations](#known-limitations)
9. [Troubleshooting](#troubleshooting)
10. [Support](#support)

---

## Why Migration is Needed

The original implementation had several limitations:

### Previous Architecture Issues

1. **Headings and Body Combined**: Page-based chunks contained headings and body text as a single blob, making it impossible to navigate by heading independently.

2. **Page Metadata Lost**: Page numbers were stored in ChromaDB but discarded during test plan generation, breaking page-based navigation in the UI.

3. **No Hierarchical Structure**: Heading levels and parent-child relationships were not preserved, limiting document structure understanding.

4. **Brittle Section Matching**: Page numbers were extracted via regex from strings like "Page 5", which breaks if section naming changes.

### New Architecture Benefits

1. **Separate Heading and Body Chunks**: Each heading and its body text are stored as separate chunks with rich metadata.

2. **Page-First Navigation**: Editor UI can filter sections by page number, showing all content from a specific page.

3. **Hierarchical Metadata**: Heading levels (H1-H6) and parent-child relationships are preserved throughout the pipeline.

4. **Structured Numeric Fields**: Page numbers and heading levels are stored as integers, not parsed from strings.

5. **Perfect Synchronization**: Source documents and test plans maintain page → heading → body hierarchy.

---

## What Has Changed

### Backend Changes

#### Document Ingestion Service
- **New**: `extract_headings_from_text()` function for heading detection
- **New**: `heading_based_chunking()` replaces page-based chunking
- **Modified**: Chunk metadata now includes:
  - `chunk_type`: "heading" or "body_text"
  - `heading_text`: The heading text
  - `heading_level`: 1-6 (H1-H6)
  - `parent_heading`: Parent heading text
  - `page_number`: Numeric integer (not string)

#### Test Plan Generation Service
- **New**: `SectionWithMetadata` dataclass
- **Modified**: `_extract_sections_with_hierarchy()` preserves page and heading metadata
- **Modified**: CriticResult objects now attach metadata for JSON conversion

#### JSON Test Plan Service
- **Modified**: `critic_result_to_json_section()` uses structured metadata
- **New fields in JSON**:
  - `source_page`: Numeric page number
  - `heading_level`: 1-6
  - `parent_heading`: Parent heading text

#### API Endpoints
- **New**: `/api/vectordb/documents/page-content` - Get all content from a specific page

### Frontend Changes

#### Side-by-Side Editor
- **New**: Page selection slider (step 3 in UI)
- **Modified**: Section selection filtered by page
- **New**: `_load_source_page_content()` function
- **New**: Metadata badges showing page, level, parent heading
- **New**: Hierarchical section display with indentation

### Environment Variables

- **New**: `USE_HEADING_BASED_CHUNKING=true` - Enable heading-based chunking (recommended)

---

## Prerequisites

Before starting migration:

1. **Backup All Data**
   - Export existing test plans to DOCX
   - Create database backup
   - Copy all PDF documents to `./document_backup/` directory

2. **System Requirements**
   - FastAPI server running
   - ChromaDB accessible
   - PostgreSQL database accessible
   - Python 3.9+ with `requests` library

3. **Access Requirements**
   - API admin access
   - Database admin credentials
   - File system write permissions

---

## Pre-Migration Checklist

Complete these tasks before starting migration:

- [ ] **Backup existing documents**
  ```bash
  mkdir -p ./document_backup
  # Copy all PDFs to this directory
  ```

- [ ] **Export existing test plans**
  ```bash
  # Use Streamlit UI to export all test plans to DOCX
  # Save to ./test_plan_exports/ directory
  ```

- [ ] **Create database backup**
  ```bash
  pg_dump -U postgres rag_memory > backup_$(date +%Y%m%d).sql
  ```

- [ ] **Verify API health**
  ```bash
  curl http://localhost:8000/health
  ```

- [ ] **Set environment variable**
  ```bash
  echo "USE_HEADING_BASED_CHUNKING=true" >> .env
  ```

- [ ] **Restart services**
  ```bash
  docker-compose restart fastapi
  ```

- [ ] **Test scripts in dry-run mode** (see Migration Steps)

---

## Migration Steps

### Step 1: Backup Verification

Ensure all backups are in place:

```bash
# Check document backup
ls -lh ./document_backup/*.pdf

# Check test plan exports
ls -lh ./test_plan_exports/*.docx

# Check database backup
ls -lh backup_*.sql
```

### Step 2: Test Migration Scripts (Dry Run)

Run all scripts in dry-run mode to preview changes:

```bash
# Test re-ingestion script
python scripts/reingest_all_documents.py --dry-run

# Test regeneration script
python scripts/regenerate_test_plans.py --dry-run
```

Review the output carefully. Ensure:
- All collections are identified correctly
- All PDFs are found in backup directory
- No critical errors are reported

### Step 3: Re-ingest Documents

Execute document re-ingestion with heading-based chunking:

```bash
# Run re-ingestion (WARNING: This deletes existing collections)
python scripts/reingest_all_documents.py --backup-dir ./document_backup
```

**What this does:**
1. Lists all ChromaDB collections
2. Backs up collection metadata to JSON files
3. Deletes all user collections (keeps system collections)
4. Re-creates default collection
5. Re-uploads all PDFs from backup directory with heading-based chunking
6. Reports progress and errors

**Expected Output:**
```
Collections deleted: 3
Documents re-ingested: 12
Errors encountered: 0
```

**Time estimate:** 10-30 minutes depending on document count and size

### Step 4: Verify Document Ingestion

Run verification checks:

```bash
# Check ChromaDB collections
curl http://localhost:8000/api/vectordb/collections

# Check document metadata
curl "http://localhost:8000/api/vectordb/collection?collection_name=uploaded_documents"
```

Verify chunks have new metadata fields:
- `chunk_type`: "heading" or "body_text"
- `heading_text`: Present for heading chunks
- `heading_level`: Numeric 1-6
- `page_number`: Numeric integer

### Step 5: Regenerate Test Plans

Execute test plan regeneration with new metadata:

```bash
# Run regeneration (WARNING: This deletes existing test plans)
python scripts/regenerate_test_plans.py --backup
```

**What this does:**
1. Lists all existing test plans
2. Backs up each plan with all versions to JSON files
3. Extracts generation configuration from each plan
4. Deletes old test plan
5. Regenerates with `sectioning_strategy="with_hierarchy"`
6. Reports progress and errors

**Expected Output:**
```
Plans processed: 5
Plans backed up: 5
Plans regenerated: 5
Errors encountered: 0
```

**Time estimate:** 20-60 minutes depending on plan count and size

**Note:** Backups are saved to `./test_plan_backups/`

### Step 6: Verify Test Plan Generation

Check that regenerated plans have new metadata:

```bash
# Get test plan list
curl http://localhost:8000/api/versioning/test-plans

# Get specific plan details
curl http://localhost:8000/api/versioning/test-plans/1
```

Verify sections have:
- `source_page`: Numeric page number
- `heading_level`: Numeric 1-6
- `parent_heading`: Parent heading text (if applicable)

### Step 7: Test Page Content API

Verify new API endpoint works:

```bash
# Test page content endpoint
curl "http://localhost:8000/api/vectordb/documents/page-content?collection_name=uploaded_documents&document_id=doc_123&page_number=5"
```

Expected response:
```json
{
  "page_number": 5,
  "document_id": "doc_123",
  "headings": [
    {
      "heading_text": "5.1 Requirements",
      "heading_level": 2,
      "body_text": "The system shall..."
    }
  ]
}
```

### Step 8: Verify Editor UI

1. Open Streamlit UI: `http://localhost:8501`
2. Navigate to "Test Plan Editor"
3. Select a test plan
4. Verify new UI elements:
   - Page selection slider appears
   - Sections are filtered by page
   - Metadata badges show page, level, parent
   - Source content loads for selected page

### Step 9: Run End-to-End Tests

Execute comprehensive test suite:

```bash
# Run E2E tests
python scripts/test_page_synchronization_e2e.py --test-pdf ./document_backup/sample.pdf
```

**Expected Results:**
```
Total Tests:  6
Passed:       6 ✓
Failed:       0 ✗
Warnings:     0 ⚠
Success Rate: 100.0%
```

If any tests fail, review the logs and fix issues before proceeding.

---

## Post-Migration Verification

### Manual Testing Checklist

#### Phase 1: Document Ingestion
- [ ] Upload a new PDF via UI
- [ ] Verify chunks in ChromaDB have `chunk_type`, `heading_text`, `heading_level`
- [ ] Confirm `page_number` is numeric (not string)
- [ ] Check headings and body text are separate chunks

#### Phase 2: Test Plan Generation
- [ ] Generate new test plan from migrated document
- [ ] Check JSON structure has `heading_level`, `parent_heading`, `source_page`
- [ ] Verify `source_page` is numeric
- [ ] Confirm section titles match actual headings

#### Phase 3: API Endpoints
- [ ] Test `/api/vectordb/documents/page-content` endpoint
- [ ] Verify it returns headings grouped by page
- [ ] Check hierarchy is preserved

#### Phase 4: Editor UI
- [ ] Open test plan in side-by-side editor
- [ ] Verify page slider shows correct range
- [ ] Select different pages, confirm sections filter correctly
- [ ] Check section list shows indentation for heading levels
- [ ] Verify source content loads for selected page
- [ ] Confirm metadata badges display correctly

#### Phase 5: End-to-End
- [ ] Upload document → Generate test plan → Edit in UI
- [ ] Navigate by page → Select section → Edit → Save
- [ ] Verify edits persist correctly
- [ ] Export test plan to DOCX

---

## Rollback Procedure

If critical issues occur, follow this rollback procedure:

### Step 1: Stop Services

```bash
docker-compose stop fastapi streamlit
```

### Step 2: Restore Database

```bash
# Restore PostgreSQL backup
psql -U postgres rag_memory < backup_YYYYMMDD.sql
```

### Step 3: Restore ChromaDB Collections

```bash
# Manual restoration required
# Re-upload original PDFs without heading-based chunking
# Set USE_HEADING_BASED_CHUNKING=false in .env
```

### Step 4: Restore Test Plans

```bash
# Use backup JSON files in ./test_plan_backups/
# Re-create test plans via API or UI
```

### Step 5: Restart Services

```bash
docker-compose up -d
```

### Step 6: Verify Rollback

```bash
# Check API health
curl http://localhost:8000/health

# Verify test plans exist
curl http://localhost:8000/api/versioning/test-plans
```

---

## Known Limitations

### Heading Detection Accuracy

**Issue:** Heading detection relies on heuristics (numbered sections, ALL CAPS, font size). Some document formats may not be detected correctly.

**Workaround:**
- Test with your specific document formats before full migration
- Manually annotate headings if necessary
- Adjust heading detection patterns in `extract_headings_from_text()`

### Re-ingestion Time

**Issue:** Re-ingesting large document sets can take hours.

**Mitigation:**
- Run migration during off-hours
- Process documents in batches using `--collection` flag
- Monitor progress logs

### Manual Edits Lost

**Issue:** Test plans that were manually edited will lose those edits during regeneration.

**Mitigation:**
- Export all test plans to DOCX before migration
- Review exported documents
- Manually re-apply critical edits after migration

### Backward Compatibility

**Issue:** Old test plans created before migration won't have new metadata fields.

**Mitigation:**
- Editor UI checks for field existence and falls back gracefully
- Display warning: "This test plan was created with old format"
- Recommend regenerating old plans

---

## Troubleshooting

### Problem: Re-ingestion Script Fails

**Symptoms:**
- Script exits with error
- Documents not uploaded

**Solutions:**
1. Check API is running: `curl http://localhost:8000/health`
2. Verify PDF files exist: `ls ./document_backup/*.pdf`
3. Check ChromaDB is accessible
4. Review FastAPI logs: `docker logs jitc_genai_fastapi_1`
5. Run with `--dry-run` to identify issues

### Problem: Test Plan Regeneration Fails

**Symptoms:**
- Plans not regenerated
- Configuration extraction errors

**Solutions:**
1. Check test plans exist: `curl http://localhost:8000/api/versioning/test-plans`
2. Verify source documents are re-ingested
3. Check agent sets are configured
4. Review generation logs in FastAPI
5. Try regenerating single plan: `--plan-id 1`

### Problem: Page Content API Returns 404

**Symptoms:**
- API call fails
- "No content found" error

**Solutions:**
1. Verify document exists in collection
2. Check page number is valid
3. Ensure re-ingestion completed successfully
4. Check chunk metadata has `page_number` field
5. Review vectordb_api.py logs

### Problem: Editor UI Missing Page Slider

**Symptoms:**
- Page slider doesn't appear
- "No page information" warning

**Solutions:**
1. Verify test plan has `source_page` in sections
2. Regenerate test plan with new metadata
3. Check JSON structure manually
4. Clear browser cache
5. Restart Streamlit: `docker-compose restart streamlit`

### Problem: Metadata Fields Missing

**Symptoms:**
- Chunks don't have `heading_text`, `heading_level`
- Test plan sections missing metadata

**Solutions:**
1. Verify `USE_HEADING_BASED_CHUNKING=true` in .env
2. Restart FastAPI service
3. Re-ingest documents
4. Check heading detection in logs
5. Validate PDF format is supported

---

## Support

### Documentation
- **Implementation Plan:** `/home/martinmlopez/.claude/plans/tingly-dancing-hammock.md`
- **Testing Checklist:** `/home/martinmlopez/repos/jitc_genai/docs/TESTING_CHECKLIST.md`

### Scripts
- **Re-ingestion:** `/home/martinmlopez/repos/jitc_genai/scripts/reingest_all_documents.py`
- **Regeneration:** `/home/martinmlopez/repos/jitc_genai/scripts/regenerate_test_plans.py`
- **E2E Tests:** `/home/martinmlopez/repos/jitc_genai/scripts/test_page_synchronization_e2e.py`

### Logs
- **FastAPI:** `docker logs jitc_genai_fastapi_1`
- **Streamlit:** `docker logs jitc_genai_streamlit_1`
- **ChromaDB:** `docker logs jitc_genai_chromadb_1`

### Contact
For additional support, consult the system documentation or contact your system administrator.

---

## Appendix A: Migration Checklist Summary

```
Pre-Migration:
□ Backup documents to ./document_backup/
□ Export test plans to DOCX
□ Create database backup
□ Set USE_HEADING_BASED_CHUNKING=true
□ Restart services
□ Test scripts in dry-run mode

Migration:
□ Run reingest_all_documents.py
□ Verify document ingestion
□ Run regenerate_test_plans.py
□ Verify test plan generation
□ Test page content API
□ Verify editor UI
□ Run E2E tests

Post-Migration:
□ Complete manual testing checklist
□ Verify all features working
□ Document any issues
□ Archive backups
```

---

## Appendix B: Environment Variables

```bash
# Enable heading-based chunking (REQUIRED)
USE_HEADING_BASED_CHUNKING=true

# Optional: Adjust chunking parameters
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Optional: Vision model selection
VISION_MODELS=llava_7b,granite_vision_2b

# Optional: Enable OCR
ENABLE_OCR=false
```

---

**End of Migration Guide**
