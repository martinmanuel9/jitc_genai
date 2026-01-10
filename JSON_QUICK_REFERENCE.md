# JSON Test Plan - Quick Reference

## Installation & Setup

No additional installation needed! The JSON test plan system is fully integrated.

### Access Points

1. **Streamlit UI**: `Streamlit App → JSON Test Plan Generator`
2. **REST API**: `http://localhost:9020/api/json-test-plans/`
3. **Python SDK**: Import `JSONTestPlanService` from `services.json_test_plan_service`

## Quick Start (5 Minutes)

### 1. Generate JSON Test Plan (Streamlit)
```
1. Go to Document Generator
2. Select agent pipeline
3. Choose source documents
4. Click "Generate Documents (Background)"
5. Or use new JSON Test Plan Generator tab
```

### 2. Extract Test Cards (Streamlit)
```
1. JSON Test Plan Generator → Extract Test Cards tab
2. Click "Extract Test Cards"
3. View test cards by section
```

### 3. Export to Markdown (Streamlit)
```
1. JSON Test Plan Generator → Export to Markdown tab
2. Click "Convert to Markdown"
3. Download MD file
```

## API Quick Reference

### Generate JSON Test Plan
```bash
curl -X POST http://localhost:9020/api/json-test-plans/generate \
  -H "Content-Type: application/json" \
  -d '{
    "source_collections": ["documents"],
    "source_doc_ids": ["doc_1"],
    "doc_title": "My Test Plan",
    "agent_set_id": 1
  }'
```

### Extract Test Cards
```bash
curl -X POST http://localhost:9020/api/json-test-plans/extract-test-cards \
  -H "Content-Type: application/json" \
  -d '{"test_plan": <json_test_plan_object>}'
```

### Convert to Markdown
```bash
curl -X POST http://localhost:9020/api/json-test-plans/to-markdown \
  -H "Content-Type: application/json" \
  -d '{"test_plan": <json_test_plan_object>}'
```

### Validate JSON
```bash
curl -X POST http://localhost:9020/api/json-test-plans/validate \
  -H "Content-Type: application/json" \
  -d '{"test_plan": <json_test_plan_object>}'
```

### Get JSON Schema
```bash
curl http://localhost:9020/api/json-test-plans/schema
```

### Merge Test Plans
```bash
curl -X POST http://localhost:9020/api/json-test-plans/merge \
  -H "Content-Type: application/json" \
  -d '[<test_plan_1>, <test_plan_2>]'
```

## Python Quick Start

```python
import requests

# Generate
response = requests.post(
    'http://localhost:9020/api/json-test-plans/generate',
    json={
        'source_collections': ['documents'],
        'source_doc_ids': ['doc_1'],
        'doc_title': 'Test Plan',
        'agent_set_id': 1
    }
)
test_plan = response.json()['test_plan']

# Extract test cards
response = requests.post(
    'http://localhost:9020/api/json-test-plans/extract-test-cards',
    json={'test_plan': test_plan}
)
test_cards = response.json()['test_cards']
```

## JSON Structure (Simplified)

```json
{
  "test_plan": {
    "metadata": {
      "title": "Test Plan Title",
      "total_sections": 5,
      "total_test_procedures": 25
    },
    "sections": [
      {
        "section_title": "Power Management",
        "test_procedures": [
          {
            "id": "proc_1",
            "title": "Test Name",
            "objective": "What to test",
            "steps": ["Step 1", "Step 2"],
            "expected_results": "What should happen",
            "priority": "high"
          }
        ]
      }
    ]
  }
}
```

## Test Card Object

Each extracted test card contains:
- `document_id` - Unique identifier
- `test_id` - Human readable ID (TC-1.1)
- `title` - Test name
- `objective` - What to test
- `setup` - Test environment setup
- `steps` - Test steps as list
- `expected_results` - Expected outcome
- `pass_criteria` - Pass condition
- `fail_criteria` - Fail condition
- `test_type` - functional/performance/security/compliance
- `priority` - low/medium/high/critical
- `estimated_duration_minutes` - Duration estimate

## Common Tasks

### Task 1: Generate Test Plan and Extract Cards
```python
import requests

# Generate
response = requests.post('http://localhost:9020/api/json-test-plans/generate', 
    json={'source_collections': ['docs'], 'source_doc_ids': ['doc_1'], 
          'doc_title': 'Plan', 'agent_set_id': 1})
test_plan = response.json()['test_plan']

# Extract
response = requests.post('http://localhost:9020/api/json-test-plans/extract-test-cards',
    json={'test_plan': test_plan})
test_cards = response.json()['test_cards']

# Use
for card in test_cards:
    print(f"{card['test_id']}: {card['title']}")
```

### Task 2: Validate Before Processing
```python
response = requests.post('http://localhost:9020/api/json-test-plans/validate',
    json={'test_plan': test_plan})

if response.json()['is_valid']:
    print("Valid!")
else:
    print(f"Errors: {response.json()['errors']}")
```

### Task 3: Export to Markdown
```python
response = requests.post('http://localhost:9020/api/json-test-plans/to-markdown',
    json={'test_plan': test_plan})

markdown = response.json()['markdown']
with open('test_plan.md', 'w') as f:
    f.write(markdown)
```

### Task 4: Process by Priority
```python
critical = [c for c in test_cards if c['priority'] == 'critical']
high = [c for c in test_cards if c['priority'] == 'high']

print(f"Critical: {len(critical)}, High: {len(high)}")
```

### Task 5: Group by Section
```python
by_section = {}
for card in test_cards:
    section = card['section_id']
    if section not in by_section:
        by_section[section] = []
    by_section[section].append(card)

for section, cards in by_section.items():
    print(f"{section}: {len(cards)} cards")
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Invalid JSON error | Run `/validate` endpoint to see specific errors |
| Test cards empty | Check test procedures in JSON sections |
| Generation timeout | Use smaller document sets or wait longer |
| API not responding | Check FastAPI service is running on port 9020 |
| Streamlit not loading | Refresh page or restart Streamlit app |

## Performance

- **Generate**: 20-30 minutes (document dependent)
- **Extract cards**: <1 second
- **Validate**: <100ms
- **To markdown**: <1 second
- **Merge plans**: <1 second

## Files

- **Service**: `src/fastapi/services/json_test_plan_service.py`
- **API**: `src/fastapi/api/json_test_plan_api.py`
- **UI**: `src/streamlit/components/json_test_plan_generator.py`
- **Guide**: `JSON_TEST_PLAN_GUIDE.md`
- **Examples**: `JSON_INTEGRATION_EXAMPLES.py`

## Next Steps

1. **Try Streamlit**: Open JSON Test Plan Generator
2. **Generate Plan**: Create first JSON test plan
3. **Extract Cards**: Convert to test cards
4. **Integrate**: Use API in your application
5. **Customize**: Extend JSON schema for your needs

## Support Resources

- **JSON_TEST_PLAN_GUIDE.md** - Complete documentation
- **JSON_INTEGRATION_EXAMPLES.py** - Code examples
- **JSON_IMPLEMENTATION_SUMMARY.md** - Implementation details
- **API Endpoint**: `/api/json-test-plans/schema` - View schema

## Best Practices

1. ✓ Always validate JSON before processing
2. ✓ Use sectioning strategy that fits your documents
3. ✓ Process test cards by priority for resource allocation
4. ✓ Export to markdown for stakeholder review
5. ✓ Store test cards in ChromaDB for reuse
6. ✓ Merge multiple plans for comprehensive testing
7. ✓ Monitor generation progress in Streamlit UI

## Tips & Tricks

- Use smaller document sets for faster generation
- Group test cards by priority for test execution order
- Filter by test_type for compliance or performance testing
- Export markdown for stakeholder reviews
- Merge plans from different sources for comprehensive testing
- Validate before any programmatic processing

---

**Ready to start?** Go to Streamlit → JSON Test Plan Generator
