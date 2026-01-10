"""
JSON Test Plan Integration Examples

Demonstrates how to integrate JSON test plans into existing workflows.
"""

# Example 1: Basic Generation and Test Card Extraction
# ============================================================================

def example_basic_workflow():
    """
    Basic workflow: Generate JSON test plan and extract test cards
    """
    import requests
    import json
    
    API_BASE = "http://localhost:9020/api"
    
    # Step 1: Generate JSON test plan
    print("Step 1: Generating JSON test plan...")
    response = requests.post(
        f"{API_BASE}/json-test-plans/generate",
        json={
            "source_collections": ["documents"],
            "source_doc_ids": ["doc_1"],
            "doc_title": "System Integration Test Plan",
            "agent_set_id": 1,
            "sectioning_strategy": "auto",
            "chunks_per_section": 5
        },
        timeout=600
    )
    
    if not response.json().get("success"):
        print(f"Failed: {response.json().get('error')}")
        return
    
    test_plan = response.json()["test_plan"]
    metadata = test_plan["test_plan"]["metadata"]
    print(f"✓ Generated test plan with {metadata['total_sections']} sections")
    
    # Step 2: Validate JSON structure
    print("\nStep 2: Validating JSON structure...")
    response = requests.post(
        f"{API_BASE}/json-test-plans/validate",
        json={"test_plan": test_plan}
    )
    
    if response.json().get("is_valid"):
        print("✓ JSON structure is valid")
    else:
        print(f"✗ Validation errors: {response.json().get('errors')}")
        return
    
    # Step 3: Extract test cards
    print("\nStep 3: Extracting test cards...")
    response = requests.post(
        f"{API_BASE}/json-test-plans/extract-test-cards",
        json={"test_plan": test_plan}
    )
    
    test_cards = response.json()["test_cards"]
    print(f"✓ Extracted {len(test_cards)} test cards")
    
    # Step 4: Save to database (example)
    print("\nStep 4: Saving test cards to database...")
    for card in test_cards[:3]:
        print(f"  - {card['test_id']}: {card['title']}")
    
    if len(test_cards) > 3:
        print(f"  ... and {len(test_cards) - 3} more")
    
    return test_plan, test_cards


# Example 2: Markdown Export
# ============================================================================

def example_markdown_export(test_plan):
    """
    Export JSON test plan to markdown format
    """
    import requests
    
    API_BASE = "http://localhost:9020/api"
    
    print("Converting JSON test plan to markdown...")
    response = requests.post(
        f"{API_BASE}/json-test-plans/to-markdown",
        json={"test_plan": test_plan}
    )
    
    markdown = response.json()["markdown"]
    title = response.json()["title"]
    
    # Save to file
    with open(f"/tmp/{title}.md", "w") as f:
        f.write(markdown)
    
    print(f"✓ Saved to /tmp/{title}.md")
    return markdown


# Example 3: Merge Multiple Test Plans
# ============================================================================

def example_merge_test_plans(test_plan_1, test_plan_2):
    """
    Merge multiple JSON test plans into one
    """
    import requests
    
    API_BASE = "http://localhost:9020/api"
    
    print("Merging test plans...")
    response = requests.post(
        f"{API_BASE}/json-test-plans/merge",
        json=[test_plan_1, test_plan_2]
    )
    
    if response.json().get("success"):
        merged_plan = response.json()["test_plan"]
        metadata = merged_plan["test_plan"]["metadata"]
        print(f"✓ Merged into {metadata['total_sections']} total sections")
        return merged_plan
    else:
        print(f"✗ Merge failed: {response.json().get('error')}")
        return None


# Example 4: Processing Test Cards
# ============================================================================

def example_process_test_cards(test_cards):
    """
    Process extracted test cards for various purposes
    """
    
    # Group by section
    cards_by_section = {}
    for card in test_cards:
        section_id = card["section_id"]
        if section_id not in cards_by_section:
            cards_by_section[section_id] = []
        cards_by_section[section_id].append(card)
    
    print(f"Grouped {len(test_cards)} cards into {len(cards_by_section)} sections")
    
    # Filter by priority
    critical_cards = [c for c in test_cards if c.get("priority") == "critical"]
    print(f"Found {len(critical_cards)} critical test cards")
    
    # Filter by type
    functional_cards = [c for c in test_cards if c.get("test_type") == "functional"]
    print(f"Found {len(functional_cards)} functional test cards")
    
    # Analyze duration
    total_duration = sum(c.get("estimated_duration_minutes", 0) for c in test_cards)
    avg_duration = total_duration / len(test_cards) if test_cards else 0
    print(f"Average test duration: {avg_duration:.1f} minutes")
    
    return cards_by_section


# Example 5: Direct JSON Processing (without API)
# ============================================================================

def example_direct_json_processing():
    """
    Use JSONTestPlanService directly in Python code
    """
    from services.json_test_plan_service import JSONTestPlanService
    from services.multi_agent_test_plan_service import FinalTestPlan, CriticResult
    
    # Create example CriticResult
    critic_result = CriticResult(
        section_title="Power Management",
        synthesized_rules="All power management functions must operate correctly",
        dependencies=["System boot"],
        conflicts=["High temperature operation"],
        test_procedures=[
            {
                "id": "proc_1",
                "requirement_id": "REQ-4.2.1",
                "title": "Verify Power Supply Voltage",
                "objective": "Ensure power supply maintains stable voltage",
                "setup": "Connect oscilloscope to power rail",
                "steps": ["Apply power", "Measure voltage"],
                "expected_results": "Voltage within ±5%",
                "pass_criteria": "Voltage stable",
                "fail_criteria": "Voltage varies >5%",
                "type": "functional",
                "priority": "high",
                "estimated_duration_minutes": 30
            }
        ],
        actor_count=3
    )
    
    # Convert to JSON section
    section = JSONTestPlanService.critic_result_to_json_section(
        critic_result,
        section_index=0
    )
    
    print(f"Created JSON section: {section['section_title']}")
    print(f"Test procedures: {len(section['test_procedures'])}")
    
    return section


# Example 6: Streamlit Integration
# ============================================================================

def example_streamlit_component():
    """
    Example of using JSON test plans in Streamlit
    """
    import streamlit as st
    from config.settings import config
    from app_lib.api.client import api_client
    
    # Generate test plan
    response = api_client.post(
        f"{config.fastapi_url}/api/json-test-plans/generate",
        data={
            "source_collections": ["documents"],
            "source_doc_ids": ["doc_1"],
            "doc_title": "My Test Plan",
            "agent_set_id": 1
        }
    )
    
    if response.get("success"):
        test_plan = response["test_plan"]
        
        # Display metrics
        metadata = test_plan["test_plan"]["metadata"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Sections", metadata["total_sections"])
        col2.metric("Requirements", metadata["total_requirements"])
        col3.metric("Test Procedures", metadata["total_test_procedures"])
        
        # Extract and display test cards
        response = api_client.post(
            f"{config.fastapi_url}/api/json-test-plans/extract-test-cards",
            data={"test_plan": test_plan}
        )
        
        test_cards = response["test_cards"]
        st.write(f"Extracted {len(test_cards)} test cards")
        
        # Display as table
        st.dataframe(
            [
                {
                    "Test ID": c["test_id"],
                    "Title": c["title"],
                    "Type": c.get("test_type"),
                    "Duration": f"{c.get('estimated_duration_minutes')} min"
                }
                for c in test_cards[:10]
            ]
        )


# Example 7: Save Test Cards to ChromaDB
# ============================================================================

def example_save_to_chromadb(test_cards):
    """
    Save extracted test cards to ChromaDB
    """
    from services.test_card_service import TestCardService
    
    service = TestCardService()
    
    # Convert test cards to ChromaDB format
    documents = []
    metadatas = []
    ids = []
    
    for card in test_cards:
        documents.append(card["title"])
        metadatas.append({
            "test_id": card["test_id"],
            "test_type": card.get("test_type"),
            "priority": card.get("priority"),
            "section_id": card.get("section_id")
        })
        ids.append(card["document_id"])
    
    # Save to ChromaDB
    result = service.save_test_cards_to_chromadb(test_cards, "test_cards")
    print(f"Saved to ChromaDB: {result}")


# Example 8: Database Integration
# ============================================================================

def example_database_integration(test_plan, test_cards):
    """
    Save JSON test plan and test cards to database
    """
    from sqlalchemy import create_engine, Column, String, Integer, JSON, DateTime
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
    import json
    from datetime import datetime
    
    # Define models
    Base = declarative_base()
    
    class TestPlan(Base):
        __tablename__ = "test_plans"
        
        id = Column(String, primary_key=True)
        title = Column(String)
        pipeline_id = Column(String)
        total_sections = Column(Integer)
        total_procedures = Column(Integer)
        json_data = Column(JSON)
        created_at = Column(DateTime)
    
    class TestCard(Base):
        __tablename__ = "test_cards"
        
        id = Column(String, primary_key=True)
        test_id = Column(String)
        title = Column(String)
        test_plan_id = Column(String)
        json_data = Column(JSON)
        created_at = Column(DateTime)
    
    # Example: Would create database session and save
    # This is pseudocode as it requires actual database setup
    # session.add(TestPlan(...))
    # session.add(TestCard(...))
    # session.commit()


# Main execution example
# ============================================================================

if __name__ == "__main__":
    print("JSON Test Plan Integration Examples")
    print("=" * 50)
    
    try:
        # Run basic workflow
        print("\n1. BASIC WORKFLOW")
        print("-" * 50)
        test_plan, test_cards = example_basic_workflow()
        
        # Export to markdown
        print("\n2. MARKDOWN EXPORT")
        print("-" * 50)
        markdown = example_markdown_export(test_plan)
        
        # Process test cards
        print("\n3. PROCESS TEST CARDS")
        print("-" * 50)
        cards_by_section = example_process_test_cards(test_cards)
        
        # Direct JSON processing
        print("\n4. DIRECT JSON PROCESSING")
        print("-" * 50)
        section = example_direct_json_processing()
        
        print("\n✓ All examples completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
