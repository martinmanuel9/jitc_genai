# Testing Checklist: Page-Level Test Plan Synchronization

## Overview

This document provides a comprehensive manual testing checklist for validating the page-level test plan synchronization feature implementation across all phases.

**Version:** 1.0
**Date:** 2026-01-11
**Related:** Implementation Plan (tingly-dancing-hammock.md)

---

## Table of Contents

1. [Phase 1: Document Ingestion](#phase-1-document-ingestion)
2. [Phase 2: Test Plan Generation](#phase-2-test-plan-generation)
3. [Phase 3: API Endpoints](#phase-3-api-endpoints)
4. [Phase 4: Editor UI](#phase-4-editor-ui)
5. [Phase 5: End-to-End Verification](#phase-5-end-to-end-verification)
6. [Regression Testing](#regression-testing)
7. [Performance Testing](#performance-testing)
8. [Test Results Template](#test-results-template)

---

## Phase 1: Document Ingestion

### Test 1.1: Heading Detection

**Objective:** Verify headings are correctly detected from PDF documents

**Prerequisites:**
- PDF with numbered sections (e.g., MIL-STD, RFC, IEEE standard)
- FastAPI running with `USE_HEADING_BASED_CHUNKING=true`

**Steps:**
1. Upload a test PDF via Streamlit UI
2. Wait for ingestion to complete
3. Query ChromaDB for chunks:
   ```bash
   curl "http://localhost:8000/api/vectordb/collection?collection_name=uploaded_documents"
   ```
4. Examine chunk metadata

**Expected Results:**
- [ ] Chunks have `chunk_type` field with values "heading" or "body_text"
- [ ] Heading chunks have `heading_text` populated
- [ ] Heading chunks have `heading_level` between 1-6
- [ ] Numbered sections detected (e.g., "1.0", "1.1", "1.1.1")
- [ ] ALL CAPS headings detected
- [ ] Parent-child relationships captured in `parent_heading` field

**Pass Criteria:** At least 80% of document headings correctly detected

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL / PARTIAL
Issues:
```

---

### Test 1.2: Page Number Storage

**Objective:** Verify page numbers are stored as numeric integers

**Steps:**
1. Query chunk metadata from previous test
2. Check `page_number` field type and values

**Expected Results:**
- [ ] `page_number` field exists in all chunks
- [ ] `page_number` is numeric integer (not string)
- [ ] Page numbers start at 1 (not 0)
- [ ] Page numbers are sequential and accurate

**Example Validation:**
```python
# In chunk metadata
assert isinstance(metadata['page_number'], int)
assert metadata['page_number'] >= 1
```

**Pass Criteria:** All chunks have valid numeric page numbers

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 1.3: Heading-Body Separation

**Objective:** Verify headings and body text are stored as separate chunks

**Steps:**
1. Select a page with at least one heading
2. Query chunks for that page
3. Verify separation

**Expected Results:**
- [ ] Each heading has a separate chunk with `chunk_type="heading"`
- [ ] Body text has separate chunk with `chunk_type="body_text"`
- [ ] Body chunks reference their heading via `parent_heading`
- [ ] No duplicate content between heading and body chunks

**Pass Criteria:** Clean separation between headings and body text

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 1.4: Heading Hierarchy

**Objective:** Verify parent-child heading relationships are preserved

**Steps:**
1. Find a document section with nested headings (H1 > H2 > H3)
2. Query chunks for that section
3. Examine `parent_heading` field

**Expected Results:**
- [ ] H2 chunks have `parent_heading` pointing to parent H1
- [ ] H3 chunks have `parent_heading` pointing to parent H2
- [ ] Top-level H1 chunks have `parent_heading` as null or empty
- [ ] Hierarchy is consistent and logical

**Example:**
```
H1: "1. Introduction" (parent: null)
  H2: "1.1 Purpose" (parent: "1. Introduction")
    H3: "1.1.1 Scope" (parent: "1.1 Purpose")
```

**Pass Criteria:** Hierarchy correctly preserved for nested headings

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 1.5: Image Association

**Objective:** Verify images are correctly associated with chunks

**Steps:**
1. Upload PDF with images
2. Check image metadata in chunks

**Expected Results:**
- [ ] Images associated with correct chunks based on position
- [ ] `has_images` flag set correctly
- [ ] Image metadata includes `char_offset` and `page_number`

**Pass Criteria:** Images correctly associated with parent chunks

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

## Phase 2: Test Plan Generation

### Test 2.1: Section Extraction with Metadata

**Objective:** Verify test plan generation preserves page and heading metadata

**Prerequisites:**
- Document successfully ingested with heading-based chunking
- Agent set configured

**Steps:**
1. Generate test plan via Streamlit UI or API:
   ```bash
   curl -X POST "http://localhost:8000/api/json-test-plans/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "source_collections": ["uploaded_documents"],
       "doc_title": "Test Plan",
       "agent_set_id": 1,
       "model_profile": "fast",
       "sectioning_strategy": "with_hierarchy"
     }'
   ```
2. Wait for generation to complete
3. Retrieve generated test plan JSON

**Expected Results:**
- [ ] Test plan sections created from document sections
- [ ] Each section has `source_page` field (numeric)
- [ ] Each section has `heading_level` field (1-6)
- [ ] Each section has `parent_heading` field (if applicable)
- [ ] Each section has `source_section_key` field
- [ ] Section titles match actual heading text (not full keys)

**Pass Criteria:** All sections have complete structured metadata

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 2.2: Page Number Accuracy

**Objective:** Verify source page numbers are accurate

**Steps:**
1. Select a test plan section
2. Note the `source_page` value
3. Open the source PDF manually
4. Navigate to that page
5. Verify the section content matches

**Expected Results:**
- [ ] `source_page` matches actual PDF page number
- [ ] Section content is from correct page
- [ ] No off-by-one errors

**Pass Criteria:** 100% accuracy for sampled sections

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 2.3: Heading Level Preservation

**Objective:** Verify heading levels are correctly preserved

**Steps:**
1. Compare source document heading levels to test plan
2. Check consistency

**Expected Results:**
- [ ] H1 headings in source have `heading_level=1` in test plan
- [ ] H2 headings have `heading_level=2`
- [ ] H3 headings have `heading_level=3`
- [ ] Levels are consistent throughout test plan

**Pass Criteria:** Heading levels match source document

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 2.4: Multi-Document Test Plans

**Objective:** Verify test plans from multiple source documents

**Steps:**
1. Generate test plan from 2+ documents
2. Check metadata

**Expected Results:**
- [ ] Sections from each document are included
- [ ] `source_document` field correctly identifies source
- [ ] Page numbers are per-document (not global)
- [ ] No mixing of content from different documents

**Pass Criteria:** Clean separation of multi-document content

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

## Phase 3: API Endpoints

### Test 3.1: Page Content API - Basic Functionality

**Objective:** Test `/api/vectordb/documents/page-content` endpoint

**Steps:**
1. Get a valid document ID and page number
2. Call the endpoint:
   ```bash
   curl "http://localhost:8000/api/vectordb/documents/page-content?collection_name=uploaded_documents&document_id=doc_abc&page_number=5"
   ```
3. Examine response

**Expected Results:**
- [ ] Status code 200
- [ ] Response has `page_number`, `document_id`, `headings` fields
- [ ] `headings` is an array
- [ ] Each heading has `heading_text`, `heading_level`, `body_text`

**Pass Criteria:** API returns correct structure

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 3.2: Page Content API - Edge Cases

**Objective:** Test API with edge cases

**Test Cases:**
1. **Invalid page number:** Page 999
   - [ ] Returns 404 with appropriate error message

2. **Invalid document ID:** Non-existent ID
   - [ ] Returns 404 with appropriate error message

3. **Invalid collection:** Non-existent collection
   - [ ] Returns 404 with appropriate error message

4. **Page with no headings:** Cover page or blank page
   - [ ] Returns empty headings array (not error)

5. **First page:** Page 1
   - [ ] Returns correct content

6. **Last page:** Maximum page number
   - [ ] Returns correct content

**Pass Criteria:** All edge cases handled gracefully

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 3.3: Page Content API - Performance

**Objective:** Verify API performance

**Steps:**
1. Call API for pages with varying content density
2. Measure response time

**Expected Results:**
- [ ] Response time < 1 second for typical pages
- [ ] Response time < 3 seconds for dense pages (many headings)
- [ ] No timeout errors

**Pass Criteria:** Acceptable performance for all page types

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Response times:
```

---

## Phase 4: Editor UI

### Test 4.1: Page Slider Display

**Objective:** Verify page selection slider appears and works

**Prerequisites:**
- Test plan with page metadata generated
- Streamlit UI accessible

**Steps:**
1. Navigate to Test Plan Editor in Streamlit
2. Select a test plan
3. Select a version
4. Look for page slider (Step 3 in UI)

**Expected Results:**
- [ ] Page slider appears between version selection and section selection
- [ ] Slider shows correct page range (1 to max page)
- [ ] Current page number displayed
- [ ] Section count for current page displayed
- [ ] Slider is interactive and responsive

**Pass Criteria:** Page slider fully functional

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 4.2: Section Filtering by Page

**Objective:** Verify sections are filtered when page is selected

**Steps:**
1. Select page 5 on slider
2. Observe section list
3. Select different page (e.g., page 3)
4. Observe section list updates

**Expected Results:**
- [ ] Only sections from selected page are shown
- [ ] Section count updates correctly
- [ ] Changing pages updates section list immediately
- [ ] No sections from other pages are visible

**Pass Criteria:** Perfect filtering by page number

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 4.3: Hierarchical Section Display

**Objective:** Verify sections show heading hierarchy

**Steps:**
1. Select a page with nested headings
2. Examine section list display

**Expected Results:**
- [ ] H1 headings have no indentation
- [ ] H2 headings indented with 2 spaces
- [ ] H3 headings indented with 4 spaces
- [ ] Hierarchy is visually clear
- [ ] Parent headings labeled (if shown)

**Example:**
```
Section 1
  Section 1.1
    Section 1.1.1
  Section 1.2
```

**Pass Criteria:** Clear visual hierarchy

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 4.4: Source Content Loading

**Objective:** Verify source document content loads for selected page

**Steps:**
1. Select a page
2. Select a section
3. Observe left panel (Source Document)

**Expected Results:**
- [ ] Source content loads and displays
- [ ] Content is from correct page
- [ ] Headings formatted with markdown (# ## ###)
- [ ] Content is readable and properly formatted
- [ ] Loading indicators shown during fetch

**Pass Criteria:** Source content displays correctly

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 4.5: Metadata Badges

**Objective:** Verify metadata badges display correctly

**Steps:**
1. Select a section
2. Observe metadata badges in right panel

**Expected Results:**
- [ ] Page number badge visible (e.g., "Page 5")
- [ ] Heading level badge visible (e.g., "Level H2")
- [ ] Parent heading badge visible (if applicable)
- [ ] Badges are styled and readable
- [ ] Information is accurate

**Pass Criteria:** All metadata badges correct

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 4.6: Backward Compatibility

**Objective:** Verify editor handles old test plans gracefully

**Steps:**
1. Load a test plan created before migration (if available)
2. Observe UI behavior

**Expected Results:**
- [ ] UI doesn't crash
- [ ] Warning message displayed: "No page information available"
- [ ] Falls back to section-only view
- [ ] User can still view and edit sections

**Pass Criteria:** Graceful degradation for old plans

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

## Phase 5: End-to-End Verification

### Test 5.1: Complete Workflow

**Objective:** Test entire workflow from upload to edit

**Steps:**
1. **Upload Document**
   - Upload a test PDF via UI
   - Wait for completion
   - [ ] Document successfully ingested

2. **Verify Chunks**
   - Check ChromaDB metadata
   - [ ] Chunks have correct metadata

3. **Generate Test Plan**
   - Generate test plan from uploaded document
   - Use `sectioning_strategy="with_hierarchy"`
   - [ ] Test plan generated successfully

4. **Verify Test Plan JSON**
   - Check JSON structure
   - [ ] Has required metadata fields

5. **Open in Editor**
   - Open test plan in side-by-side editor
   - [ ] Editor loads correctly

6. **Navigate by Page**
   - Use page slider to navigate
   - [ ] Filtering works correctly

7. **Edit Section**
   - Select a section
   - Make edits
   - Save changes
   - [ ] Edits persist

8. **Export**
   - Export test plan to DOCX
   - [ ] Export successful

**Pass Criteria:** Complete workflow successful with no errors

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

### Test 5.2: Multi-User Concurrent Editing

**Objective:** Test concurrent editing scenarios

**Steps:**
1. Open same test plan in two browser windows
2. Edit different sections in each window
3. Save changes

**Expected Results:**
- [ ] Both edits persist correctly
- [ ] No data loss
- [ ] Version numbers increment
- [ ] No race conditions

**Pass Criteria:** Concurrent edits handled correctly

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

## Regression Testing

### Test R.1: Existing Features Still Work

**Objective:** Ensure new changes don't break existing functionality

**Checklist:**
- [ ] Document upload without heading-based chunking still works
- [ ] Old test plan generation (without hierarchy) still works
- [ ] Document export to DOCX still works
- [ ] Test card extraction still works
- [ ] Agent pipeline still functions
- [ ] Redis caching still works
- [ ] Image processing still works
- [ ] OCR (if enabled) still works

**Pass Criteria:** All existing features functional

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

## Performance Testing

### Test P.1: Large Document Performance

**Objective:** Test system with large documents

**Test Documents:**
- Small: < 50 pages
- Medium: 50-200 pages
- Large: 200-500 pages
- Very Large: > 500 pages

**Metrics to Measure:**
- [ ] Upload time
- [ ] Ingestion time
- [ ] Test plan generation time
- [ ] Editor loading time
- [ ] Page content API response time

**Expected Results:**
- [ ] Small docs: < 2 minutes total
- [ ] Medium docs: < 10 minutes total
- [ ] Large docs: < 30 minutes total
- [ ] UI remains responsive
- [ ] No memory errors

**Pass Criteria:** Acceptable performance for all document sizes

**Notes:**
```
Tested by: __________
Date: __________
Document size: _____ pages
Upload time: _____ minutes
Generation time: _____ minutes
Result: PASS / FAIL
Issues:
```

---

### Test P.2: Multiple Concurrent Jobs

**Objective:** Test system under load

**Steps:**
1. Upload 5 documents simultaneously
2. Generate 3 test plans concurrently
3. Monitor system resources

**Expected Results:**
- [ ] All jobs complete successfully
- [ ] No jobs fail or timeout
- [ ] System remains stable
- [ ] Reasonable resource usage

**Pass Criteria:** System handles concurrent load

**Notes:**
```
Tested by: __________
Date: __________
Result: PASS / FAIL
Issues:
```

---

## Test Results Template

### Summary Report

```
Testing Date: __________
Tested By: __________
Environment: Development / Staging / Production
Version: __________

Overall Results:
- Total Tests: _____
- Passed: _____
- Failed: _____
- Warnings: _____
- Success Rate: _____%

Critical Issues:
1.
2.
3.

Non-Critical Issues:
1.
2.
3.

Recommendations:
1.
2.
3.

Sign-off:
Tester: __________
Date: __________

Approval:
Reviewer: __________
Date: __________
```

---

## Appendix: Sample Test Data

### Sample Documents
- **MIL-STD-188-203-1A.pdf** - Military standard with numbered sections
- **RFC 9293** - Internet standard with structured format
- **IEEE 802.11** - Technical specification with hierarchy

### Sample Test Cases
- **Simple Document:** 10 pages, 5 headings, no nesting
- **Complex Document:** 100 pages, 50 headings, 3 levels of nesting
- **Edge Case Document:** No headings, all body text
- **Mixed Content:** Text, images, tables, diagrams

---

**End of Testing Checklist**
