"""
JSON Test Plan Editor Component

Form-based editor for JSON test plans with per-section editing and versioning.
Allows users to edit section titles, requirements, and test procedures in a structured form.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import streamlit as st

from app_lib.api.client import api_client
from config.settings import config


# Collection name for JSON test plans
JSON_TEST_PLAN_COLLECTION = "json_test_plans"


@dataclass
class JSONTestPlan:
    """Represents a JSON test plan document"""
    document_id: str
    test_plan: Dict[str, Any]
    metadata: Dict[str, Any]


def _load_json_test_plans() -> List[JSONTestPlan]:
    """Load all JSON test plans from ChromaDB"""
    try:
        response = api_client.get(
            f"{config.fastapi_url}/api/vectordb/documents",
            params={"collection_name": JSON_TEST_PLAN_COLLECTION},
            timeout=30
        )

        ids = response.get("ids", [])
        documents = response.get("documents", [])
        metadatas = response.get("metadatas", [])

        plans: List[JSONTestPlan] = []
        for idx, doc_id in enumerate(ids):
            content = documents[idx] if idx < len(documents) else "{}"
            metadata = metadatas[idx] if idx < len(metadatas) else {}

            # Parse JSON content
            try:
                test_plan = json.loads(content) if content else {}
            except json.JSONDecodeError:
                test_plan = {}

            plans.append(JSONTestPlan(
                document_id=doc_id,
                test_plan=test_plan,
                metadata=metadata or {}
            ))

        return plans
    except Exception as e:
        st.error(f"Failed to load JSON test plans: {e}")
        return []


def _find_plan_record(plan_key: str) -> Optional[Dict[str, Any]]:
    """Find existing plan record in versioning system"""
    try:
        response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-plans",
            timeout=30
        )
        for plan in response.get("plans", []):
            if plan.get("plan_key") == plan_key:
                return plan
        return None
    except Exception:
        return None


def _get_latest_version(plan_id: int) -> Optional[Dict[str, Any]]:
    """Get the latest version of a test plan"""
    try:
        response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions",
            timeout=30
        )
        versions = response.get("versions", [])
        return versions[0] if versions else None
    except Exception:
        return None


def _save_json_test_plan(
    plan_key: str,
    plan_title: str,
    base_document_id: str,
    base_metadata: Dict[str, Any],
    updated_test_plan: Dict[str, Any]
) -> bool:
    """
    Save a new version of the JSON test plan.

    Args:
        plan_key: Unique key for the test plan
        plan_title: Title of the test plan
        base_document_id: Document ID this version is based on
        base_metadata: Original metadata
        updated_test_plan: The updated JSON test plan structure

    Returns:
        True if save was successful
    """
    try:
        # Find or create plan record
        plan_record = _find_plan_record(plan_key)
        base_version_id = None
        next_version = 1

        if plan_record:
            latest = _get_latest_version(plan_record["id"])
            if latest:
                base_version_id = latest["id"]
                next_version = int(latest.get("version_number", 0)) + 1
        else:
            # Create new plan record
            create_response = api_client.post(
                f"{config.fastapi_url}/api/versioning/test-plans",
                data={
                    "plan_key": plan_key,
                    "title": plan_title,
                    "collection_name": JSON_TEST_PLAN_COLLECTION,
                    "percent_complete": 0,
                    "document_id": base_document_id,
                    "based_on_version_id": None
                },
                timeout=30
            )
            plan_record = create_response["plan"]
            base_version_id = create_response["version"]["id"]
            next_version = int(create_response["version"]["version_number"]) + 1

        # Update plan title if changed
        if plan_record and plan_title and plan_title != plan_record.get("title"):
            api_client.put(
                f"{config.fastapi_url}/api/versioning/test-plans/{plan_record['id']}",
                data={"title": plan_title},
                timeout=30
            )

        # Create new document in ChromaDB
        new_doc_id = f"jsonplan_{uuid.uuid4().hex[:12]}"
        new_metadata = dict(base_metadata or {})
        new_metadata["title"] = plan_title
        new_metadata["plan_key"] = plan_key
        new_metadata["version_number"] = next_version
        new_metadata["based_on_document_id"] = base_document_id
        new_metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        new_metadata["format"] = "json"

        # Update metadata in test plan
        if "test_plan" in updated_test_plan and "metadata" in updated_test_plan["test_plan"]:
            updated_test_plan["test_plan"]["metadata"]["title"] = plan_title
            updated_test_plan["test_plan"]["metadata"]["version"] = next_version

        # Save to ChromaDB
        api_client.post(
            f"{config.fastapi_url}/api/vectordb/documents/add",
            data={
                "collection_name": JSON_TEST_PLAN_COLLECTION,
                "documents": [json.dumps(updated_test_plan)],
                "ids": [new_doc_id],
                "metadatas": [new_metadata]
            },
            timeout=30
        )

        # Create version record
        api_client.post(
            f"{config.fastapi_url}/api/versioning/test-plans/{plan_record['id']}/versions",
            data={
                "document_id": new_doc_id,
                "based_on_version_id": base_version_id
            },
            timeout=30
        )

        st.success(f"Saved version {next_version} of '{plan_title}'")
        return True

    except Exception as e:
        st.error(f"Failed to save test plan: {e}")
        return False


def _render_test_procedure_editor(
    procedure: Dict[str, Any],
    proc_idx: int,
    section_idx: int,
    key_prefix: str
) -> Dict[str, Any]:
    """
    Render form fields for editing a single test procedure.

    Returns the updated procedure dictionary.
    """
    with st.expander(f"Test {proc_idx + 1}: {procedure.get('title', 'Untitled')}", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input(
                "Title",
                value=procedure.get("title", ""),
                key=f"{key_prefix}_proc_{proc_idx}_title"
            )

            requirement_id = st.text_input(
                "Requirement ID",
                value=procedure.get("requirement_id", ""),
                key=f"{key_prefix}_proc_{proc_idx}_req_id"
            )

            test_type = st.selectbox(
                "Test Type",
                options=["functional", "integration", "performance", "security", "compliance"],
                index=["functional", "integration", "performance", "security", "compliance"].index(
                    procedure.get("type", "functional")
                ) if procedure.get("type") in ["functional", "integration", "performance", "security", "compliance"] else 0,
                key=f"{key_prefix}_proc_{proc_idx}_type"
            )

            priority = st.selectbox(
                "Priority",
                options=["high", "medium", "low"],
                index=["high", "medium", "low"].index(
                    procedure.get("priority", "medium")
                ) if procedure.get("priority") in ["high", "medium", "low"] else 1,
                key=f"{key_prefix}_proc_{proc_idx}_priority"
            )

        with col2:
            estimated_duration = st.number_input(
                "Est. Duration (minutes)",
                min_value=1,
                max_value=480,
                value=procedure.get("estimated_duration_minutes", 30),
                key=f"{key_prefix}_proc_{proc_idx}_duration"
            )

        objective = st.text_area(
            "Objective",
            value=procedure.get("objective", ""),
            height=80,
            key=f"{key_prefix}_proc_{proc_idx}_objective"
        )

        setup = st.text_area(
            "Setup Instructions",
            value=procedure.get("setup", ""),
            height=80,
            key=f"{key_prefix}_proc_{proc_idx}_setup"
        )

        # Steps - convert list to text for editing
        steps_list = procedure.get("steps", [])
        steps_text = "\n".join(steps_list) if isinstance(steps_list, list) else str(steps_list)
        steps_input = st.text_area(
            "Steps (one per line)",
            value=steps_text,
            height=120,
            key=f"{key_prefix}_proc_{proc_idx}_steps"
        )

        expected_results = st.text_area(
            "Expected Results",
            value=procedure.get("expected_results", ""),
            height=80,
            key=f"{key_prefix}_proc_{proc_idx}_expected"
        )

        col1, col2 = st.columns(2)
        with col1:
            pass_criteria = st.text_area(
                "Pass Criteria",
                value=procedure.get("pass_criteria", ""),
                height=60,
                key=f"{key_prefix}_proc_{proc_idx}_pass"
            )
        with col2:
            fail_criteria = st.text_area(
                "Fail Criteria",
                value=procedure.get("fail_criteria", ""),
                height=60,
                key=f"{key_prefix}_proc_{proc_idx}_fail"
            )

        # Return updated procedure
        return {
            "id": procedure.get("id", f"proc_{section_idx}_{proc_idx}"),
            "requirement_id": requirement_id,
            "title": title,
            "objective": objective,
            "setup": setup,
            "steps": [s.strip() for s in steps_input.split("\n") if s.strip()],
            "expected_results": expected_results,
            "pass_criteria": pass_criteria,
            "fail_criteria": fail_criteria,
            "type": test_type,
            "priority": priority,
            "estimated_duration_minutes": estimated_duration
        }


def _render_section_editor(
    section: Dict[str, Any],
    section_idx: int,
    key_prefix: str
) -> Dict[str, Any]:
    """
    Render form fields for editing a single section.

    Returns the updated section dictionary.
    """
    st.markdown(f"### Section {section_idx + 1}")

    col1, col2 = st.columns([3, 1])

    with col1:
        section_title = st.text_input(
            "Section Title",
            value=section.get("section_title", ""),
            key=f"{key_prefix}_section_{section_idx}_title"
        )

    with col2:
        st.text_input(
            "Section ID",
            value=section.get("section_id", ""),
            disabled=True,
            key=f"{key_prefix}_section_{section_idx}_id"
        )

    synthesized_rules = st.text_area(
        "Requirements / Synthesized Rules",
        value=section.get("synthesized_rules", ""),
        height=150,
        key=f"{key_prefix}_section_{section_idx}_rules",
        help="The requirements or rules extracted for this section"
    )

    # Dependencies and conflicts
    col1, col2 = st.columns(2)
    with col1:
        deps_list = section.get("dependencies", [])
        deps_text = ", ".join(deps_list) if isinstance(deps_list, list) else str(deps_list)
        dependencies_input = st.text_input(
            "Dependencies (comma-separated)",
            value=deps_text,
            key=f"{key_prefix}_section_{section_idx}_deps"
        )

    with col2:
        conflicts_list = section.get("conflicts", [])
        conflicts_text = ", ".join(conflicts_list) if isinstance(conflicts_list, list) else str(conflicts_list)
        conflicts_input = st.text_input(
            "Conflicts (comma-separated)",
            value=conflicts_text,
            key=f"{key_prefix}_section_{section_idx}_conflicts"
        )

    # Test procedures
    st.markdown("#### Test Procedures")

    test_procedures = section.get("test_procedures", [])
    updated_procedures = []

    if not test_procedures:
        st.info("No test procedures in this section. Click 'Add Test Procedure' to create one.")

    for proc_idx, procedure in enumerate(test_procedures):
        updated_proc = _render_test_procedure_editor(
            procedure, proc_idx, section_idx, key_prefix
        )
        updated_procedures.append(updated_proc)

    # Add new procedure button
    add_proc_key = f"{key_prefix}_section_{section_idx}_add_proc"
    if st.button("+ Add Test Procedure", key=add_proc_key):
        new_proc = {
            "id": f"proc_{section_idx}_{len(test_procedures)}",
            "requirement_id": "",
            "title": "New Test Procedure",
            "objective": "",
            "setup": "",
            "steps": [],
            "expected_results": "",
            "pass_criteria": "",
            "fail_criteria": "",
            "type": "functional",
            "priority": "medium",
            "estimated_duration_minutes": 30
        }
        updated_procedures.append(new_proc)
        st.rerun()

    st.divider()

    # Return updated section
    return {
        "section_id": section.get("section_id", f"section_{section_idx}"),
        "section_title": section_title,
        "section_index": section_idx,
        "synthesized_rules": synthesized_rules,
        "actor_count": section.get("actor_count", 0),
        "dependencies": [d.strip() for d in dependencies_input.split(",") if d.strip()],
        "conflicts": [c.strip() for c in conflicts_input.split(",") if c.strip()],
        "test_procedures": updated_procedures
    }


def render_json_test_plan_editor() -> None:
    """
    Main entry point for the JSON Test Plan Editor.

    Provides a form-based interface for editing JSON test plans with:
    - Section-by-section editing
    - Test procedure editing within each section
    - Version auto-increment on save
    """
    st.subheader("JSON Test Plan Editor")

    st.info("""
    Edit your test plan sections and test procedures using the form below.
    Changes are saved as new versions with automatic version numbering.
    """)

    # Check for test plan in session state first (from generator)
    session_plan = st.session_state.get("json_test_plan")

    # Also try to load from ChromaDB
    stored_plans = _load_json_test_plans()

    # Combine options
    plan_options: Dict[str, Dict[str, Any]] = {}

    # Add session plan if available
    if session_plan and session_plan.get("test_plan", {}).get("metadata"):
        metadata = session_plan["test_plan"]["metadata"]
        label = f"[Current Session] {metadata.get('title', 'Untitled')} (unsaved)"
        plan_options[label] = {
            "source": "session",
            "test_plan": session_plan,
            "document_id": metadata.get("pipeline_id", "session_plan"),
            "metadata": metadata
        }

    # Add stored plans
    for plan in stored_plans:
        if plan.test_plan and plan.test_plan.get("test_plan"):
            title = plan.metadata.get("title") or plan.test_plan.get("test_plan", {}).get("metadata", {}).get("title", "Untitled")
            version = plan.metadata.get("version_number", 1)
            label = f"{title} (v{version}) - {plan.document_id[:8]}..."
            plan_options[label] = {
                "source": "chromadb",
                "test_plan": plan.test_plan,
                "document_id": plan.document_id,
                "metadata": plan.metadata
            }

    if not plan_options:
        st.warning("No JSON test plans available. Generate a test plan first using the 'JSON Test Plan Generator' tab.")
        return

    # Plan selection
    selected_label = st.selectbox(
        "Select a test plan to edit:",
        options=list(plan_options.keys()),
        key="json_plan_editor_select"
    )

    selected = plan_options[selected_label]
    test_plan_data = selected["test_plan"]
    base_document_id = selected["document_id"]
    base_metadata = selected["metadata"]

    # Extract test plan structure
    test_plan = test_plan_data.get("test_plan", {})
    metadata = test_plan.get("metadata", {})
    sections = test_plan.get("sections", [])

    # Plan title editor
    plan_title = st.text_input(
        "Test Plan Title",
        value=metadata.get("title", "Untitled Test Plan"),
        key="json_plan_editor_title"
    )

    # Display metadata
    with st.expander("Plan Metadata", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Sections", metadata.get("total_sections", len(sections)))
        with col2:
            st.metric("Total Requirements", metadata.get("total_requirements", 0))
        with col3:
            st.metric("Total Test Procedures", metadata.get("total_test_procedures", 0))
        with col4:
            st.metric("Status", metadata.get("processing_status", "N/A"))

        st.text(f"Pipeline ID: {metadata.get('pipeline_id', 'N/A')}")
        st.text(f"Generated: {metadata.get('generated_at', 'N/A')}")

    # Section navigation
    if not sections:
        st.warning("This test plan has no sections. The plan may not have been generated correctly.")

        # Allow adding a section
        if st.button("+ Add First Section", key="add_first_section"):
            sections.append({
                "section_id": f"section_{uuid.uuid4().hex[:8]}",
                "section_title": "New Section",
                "section_index": 0,
                "synthesized_rules": "",
                "actor_count": 0,
                "dependencies": [],
                "conflicts": [],
                "test_procedures": []
            })
            test_plan_data["test_plan"]["sections"] = sections
            st.session_state["json_test_plan"] = test_plan_data
            st.rerun()
        return

    # Section tabs
    section_labels = [
        f"{idx + 1}. {section.get('section_title', 'Section')[:30]}..."
        for idx, section in enumerate(sections)
    ]

    # Use selectbox for section navigation (more compact)
    col1, col2 = st.columns([4, 1])
    with col1:
        selected_section_idx = st.selectbox(
            "Select Section to Edit",
            options=range(len(sections)),
            format_func=lambda x: section_labels[x],
            key="json_plan_section_select"
        )

    with col2:
        st.write("")  # Spacing
        st.write("")
        if st.button("+ Add Section", key="add_new_section"):
            new_section = {
                "section_id": f"section_{uuid.uuid4().hex[:8]}",
                "section_title": "New Section",
                "section_index": len(sections),
                "synthesized_rules": "",
                "actor_count": 0,
                "dependencies": [],
                "conflicts": [],
                "test_procedures": []
            }
            sections.append(new_section)
            test_plan_data["test_plan"]["sections"] = sections
            st.session_state["json_test_plan"] = test_plan_data
            st.rerun()

    # Edit selected section
    key_prefix = f"json_editor_{base_document_id}"

    with st.form("json_test_plan_editor_form"):
        updated_section = _render_section_editor(
            sections[selected_section_idx],
            selected_section_idx,
            key_prefix
        )

        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            save_button = st.form_submit_button("Save New Version", type="primary")

        with col2:
            save_current = st.form_submit_button("Save Section Changes", type="secondary")

        with col3:
            if st.form_submit_button("Delete Section", type="secondary"):
                if len(sections) > 1:
                    sections.pop(selected_section_idx)
                    # Reindex remaining sections
                    for idx, sec in enumerate(sections):
                        sec["section_index"] = idx
                    test_plan_data["test_plan"]["sections"] = sections
                    st.session_state["json_test_plan"] = test_plan_data
                    st.rerun()
                else:
                    st.warning("Cannot delete the last section.")

    if save_button or save_current:
        # Update the section in the test plan
        sections[selected_section_idx] = updated_section

        # Recalculate metadata
        total_sections = len(sections)
        total_procedures = sum(len(s.get("test_procedures", [])) for s in sections)

        updated_test_plan = {
            "test_plan": {
                "metadata": {
                    **metadata,
                    "title": plan_title,
                    "total_sections": total_sections,
                    "total_requirements": total_procedures,
                    "total_test_procedures": total_procedures,
                },
                "sections": sections
            }
        }

        if save_current:
            # Just update session state
            st.session_state["json_test_plan"] = updated_test_plan
            st.success("Section changes saved to session. Use 'Save New Version' to persist.")
        else:
            # Save as new version
            plan_key = base_metadata.get("plan_key") or base_document_id
            success = _save_json_test_plan(
                plan_key=plan_key,
                plan_title=plan_title,
                base_document_id=base_document_id,
                base_metadata=base_metadata,
                updated_test_plan=updated_test_plan
            )

            if success:
                st.session_state["json_test_plan"] = updated_test_plan
                st.rerun()


def render_json_section_viewer() -> None:
    """
    Read-only viewer for JSON test plan sections.
    Useful for reviewing generated plans before editing.
    """
    st.subheader("Section Viewer")

    test_plan = st.session_state.get("json_test_plan", {})

    if not test_plan or not test_plan.get("test_plan"):
        st.info("No test plan loaded. Generate or select a test plan first.")
        return

    sections = test_plan.get("test_plan", {}).get("sections", [])

    if not sections:
        st.warning("Test plan has no sections.")
        return

    for section in sections:
        with st.expander(f"Section {section.get('section_index', 0) + 1}: {section.get('section_title', 'Untitled')}", expanded=False):
            st.markdown(f"**Section ID**: `{section.get('section_id')}`")

            if section.get("synthesized_rules"):
                st.markdown("**Requirements:**")
                st.markdown(section.get("synthesized_rules"))

            procedures = section.get("test_procedures", [])
            if procedures:
                st.markdown(f"**Test Procedures ({len(procedures)}):**")
                for proc in procedures:
                    st.markdown(f"- **{proc.get('title')}** ({proc.get('priority', 'medium')} priority)")
            else:
                st.info("No test procedures in this section.")

            if section.get("dependencies"):
                st.markdown(f"**Dependencies**: {', '.join(section.get('dependencies'))}")

            if section.get("conflicts"):
                st.markdown(f"**Conflicts**: {', '.join(section.get('conflicts'))}")


if __name__ == "__main__":
    render_json_test_plan_editor()
