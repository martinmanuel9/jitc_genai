# JSON-Based Test Plan Generation

## Overview

The JSON-based test plan generation provides a more structured and flexible approach to creating and managing test plans. Instead of generating markdown directly, test plans are generated as JSON documents with well-defined schemas, making them easier to process, manipulate, and convert to different formats.

## Architecture

### Components

1. **JSONTestPlanService** (`services/json_test_plan_service.py`)
   - Converts test plans to/from JSON format
   - Extracts test cards from JSON structures
   - Validates JSON schemas
   - Converts JSON to markdown for export

2. **JSON Test Plan API** (`api/json_test_plan_api.py`)
   - `/api/json-test-plans/generate` - Generate JSON test plan
   - `/api/json-test-plans/extract-test-cards` - Extract test cards
   - `/api/json-test-plans/to-markdown` - Convert to markdown
   - `/api/json-test-plans/validate` - Validate structure
   - `/api/json-test-plans/merge` - Merge multiple plans
   - `/api/json-test-plans/schema` - Get JSON schema

3. **Streamlit Component** (`components/json_test_plan_generator.py`)
   - UI for generating JSON test plans
   - Test card extraction interface
   - JSON validation and schema viewing
   - Markdown export

## JSON Schema

### Structure

```json
{
  "test_plan": {
    "metadata": {
      "title": "string",
      "pipeline_id": "string",
      "doc_title": "string",
      "generated_at": "ISO datetime",
      "processing_status": "COMPLETED|FAILED|ABORTED",
      "total_sections": 0,
      "total_requirements": 0,
      "total_test_procedures": 0,
      "agent_set_id": 1,
      "agent_configuration": "string"
    },
    "sections": [
      {
        "section_id": "string",
        "section_title": "string",
        "section_index": 0,
        "synthesized_rules": "string",
        "actor_count": 0,
        "dependencies": ["string"],
        "conflicts": ["string"],
        "test_procedures": [
          {
            "id": "string",
            "requirement_id": "string",
            "title": "string",
            "objective": "string",
            "setup": "string",
            "steps": ["string"],
            "expected_results": "string",
            "pass_criteria": "string",
            "fail_criteria": "string",
            "type": "functional|performance|security|compliance",
            "priority": "low|medium|high|critical",
            "estimated_duration_minutes": 30
          }
        ]
      }
    ]
  }
}
```

## API Usage

### Generate JSON Test Plan

```bash
POST /api/json-test-plans/generate

{
  "source_collections": ["documents"],
  "source_doc_ids": ["doc_1", "doc_2"],
  "doc_title": "System Test Plan",
  "agent_set_id": 1,
  "sectioning_strategy": "auto",
  "chunks_per_section": 5
}
```

**Response:**
```json
{
  "success": true,
  "test_plan": { ... },
  "message": "Successfully generated JSON test plan with 5 sections",
  "processing_status": "COMPLETED"
}
```

### Extract Test Cards

```bash
POST /api/json-test-plans/extract-test-cards

{
  "test_plan": { ... }
}
```

**Response:**
```json
{
  "test_cards": [
    {
      "document_id": "testcard_pipeline_xyz_section_abc_proc_1",
      "test_id": "TC-1.1",
      "title": "Power Supply Test",
      "objective": "Verify power supply voltage",
      "steps": [...],
      "expected_results": "Voltage within tolerance",
      ...
    }
  ],
  "total_cards": 25,
  "section_ids": ["section_1", "section_2", ...]
}
```

### Convert to Markdown

```bash
POST /api/json-test-plans/to-markdown

{
  "test_plan": { ... }
}
```

**Response:**
```json
{
  "markdown": "# System Test Plan\n\n## Section 1\n...",
  "title": "System Test Plan"
}
```

### Validate JSON

```bash
POST /api/json-test-plans/validate

{
  "test_plan": { ... }
}
```

**Response:**
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": []
}
```

### Merge Test Plans

```bash
POST /api/json-test-plans/merge

[
  { "test_plan": { ... } },
  { "test_plan": { ... } }
]
```

## Workflow

### Step 1: Generate JSON Test Plan

1. Go to **Document Generator** or **JSON Test Plan Generator**
2. Select agent pipeline
3. Choose source documents
4. Click "Generate JSON Test Plan"
5. Wait for generation to complete

### Step 2: Extract Test Cards

1. In JSON Test Plan Generator, go to "Extract Test Cards" tab
2. Click "Extract Test Cards"
3. System generates individual test card documents
4. View test cards grouped by section

### Step 3: Save to ChromaDB

Test cards can be saved to ChromaDB for later use:

```python
from services.test_card_service import TestCardService

service = TestCardService()
result = service.save_test_cards_to_chromadb(
    test_cards=test_cards,
    collection_name="test_cards"
)
```

### Step 4: Export to Markdown (Optional)

For document sharing or display:

1. In JSON Test Plan Generator, go to "Export to Markdown" tab
2. Click "Convert to Markdown"
3. Download markdown file
4. Use for documentation, wikis, or email

## Benefits

### Structured Data
- Clear schema for processing
- Easier validation
- Better type safety

### Flexibility
- Convert to markdown, DOCX, PDF
- Extract test cards programmatically
- Merge multiple test plans
- Query specific sections

### Test Card Generation
- Direct conversion from JSON sections
- Better metadata preservation
- Easier filtering and searching
- Support for test execution tracking

### Scalability
- Process large test plans efficiently
- Stream sections independently
- Parallel processing possible
- Easier database integration

## Examples

### Python API Client

```python
import requests
import json

# Generate test plan
response = requests.post(
    "http://localhost:9020/api/json-test-plans/generate",
    json={
        "source_collections": ["documents"],
        "source_doc_ids": ["doc_1"],
        "doc_title": "API Test Plan",
        "agent_set_id": 1
    }
)

test_plan = response.json()["test_plan"]

# Extract test cards
response = requests.post(
    "http://localhost:9020/api/json-test-plans/extract-test-cards",
    json={"test_plan": test_plan}
)

test_cards = response.json()["test_cards"]

# Save to database or process
for card in test_cards:
    print(f"Test {card['test_id']}: {card['title']}")
```

### JavaScript/TypeScript

```javascript
// Generate test plan
const response = await fetch('http://localhost:9020/api/json-test-plans/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    source_collections: ['documents'],
    source_doc_ids: ['doc_1'],
    doc_title: 'API Test Plan',
    agent_set_id: 1
  })
});

const { test_plan } = await response.json();

// Extract test cards
const cardResponse = await fetch(
  'http://localhost:9020/api/json-test-plans/extract-test-cards',
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ test_plan })
  }
);

const { test_cards } = await cardResponse.json();
```

## Migration from Markdown

Existing markdown test plans can be converted to JSON format:

```python
from services.json_test_plan_service import JSONTestPlanService

# Parse markdown to JSON structure
# (Create conversion from existing markdown format)

markdown_content = """
# Test Plan

## Section 1
### Test Procedure 1
...
"""

# Use multi-agent service to structure and extract
# Then convert to JSON
```

## Performance Notes

- **Generation**: 20-30 minutes for large documents (depends on document size)
- **Test Card Extraction**: <1 second (local operation)
- **Validation**: <100ms
- **Markdown Export**: <1 second
- **Memory**: ~500MB for plans with 100+ sections

## Future Enhancements

1. **Direct JSON Input** - Accept JSON test plans from external systems
2. **Streaming Output** - Stream large plans to avoid memory issues
3. **Batch Processing** - Process multiple collections in parallel
4. **Format Export** - DOCX, PDF, HTML export from JSON
5. **Test Execution Tracking** - Store test execution results in JSON
6. **Compliance Reporting** - Generate compliance reports from JSON

## Troubleshooting

### Invalid JSON Error
- Check JSON structure against schema
- Use `/api/json-test-plans/validate` endpoint
- Review error messages for missing fields

### Test Card Extraction Fails
- Ensure test plan has sections with test_procedures
- Check that section_id is unique
- Validate JSON structure first

### Generation Times Out
- For large documents (>100MB), increase timeout
- Use source_doc_ids to process specific documents
- Split large collections into smaller chunks

## Support

For issues or questions:
1. Check validation results: `/api/json-test-plans/validate`
2. Review JSON schema: `/api/json-test-plans/schema`
3. Check API logs for detailed errors
4. Use `/api/json-test-plans/to-markdown` to verify content
