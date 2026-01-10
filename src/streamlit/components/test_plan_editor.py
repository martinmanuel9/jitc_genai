"""
Test Plan Editor Component

Form-based editor for per-section updates with versioning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid
from typing import Dict, List, Tuple, Optional

import streamlit as st

from app_lib.api.client import api_client
from config.settings import config


GENERATED_TEST_PLAN_COLLECTION = "generated_test_plan"


@dataclass
class PlanDocument:
    document_id: str
    content: str
    metadata: Dict[str, object]


def _parse_sections(markdown: str) -> Tuple[str, List[Dict[str, str]]]:
    if not markdown:
        return "", []

    preamble_lines: List[str] = []
    sections: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None

    for line in markdown.splitlines():
        if line.startswith("## "):
            if current:
                current["content"] = current["content"].strip()
                sections.append(current)
            current = {"title": line[3:].strip(), "content": ""}
        else:
            if current is None:
                preamble_lines.append(line)
            else:
                current["content"] += f"{line}\n"

    if current:
        current["content"] = current["content"].strip()
        sections.append(current)

    preamble = "\n".join(preamble_lines).strip()
    if not sections:
        return preamble, [{"title": "Untitled Section", "content": markdown.strip()}]

    return preamble, sections


def _build_markdown(preamble: str, sections: List[Dict[str, str]]) -> str:
    parts: List[str] = []
    if preamble:
        parts.append(preamble.strip())

    for section in sections:
        title = section.get("title", "").strip() or "Untitled Section"
        content = section.get("content", "").strip()
        block = f"## {title}"
        if content:
            block = f"{block}\n\n{content}"
        parts.append(block)

    return "\n\n".join(parts).strip()


def _load_plan_documents() -> List[PlanDocument]:
    response = api_client.get(
        f"{config.fastapi_url}/api/vectordb/documents",
        params={"collection_name": GENERATED_TEST_PLAN_COLLECTION},
        timeout=30
    )
    ids = response.get("ids", [])
    documents = response.get("documents", [])
    metadatas = response.get("metadatas", [])

    plans: List[PlanDocument] = []
    for idx, doc_id in enumerate(ids):
        content = documents[idx] if idx < len(documents) else ""
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        plans.append(PlanDocument(document_id=doc_id, content=content or "", metadata=metadata or {}))

    return plans


def _find_plan_record(plan_key: str) -> Optional[Dict[str, object]]:
    response = api_client.get(
        f"{config.fastapi_url}/api/versioning/test-plans",
        timeout=30
    )
    for plan in response.get("plans", []):
        if plan.get("plan_key") == plan_key:
            return plan
    return None


def _get_latest_version(plan_id: int) -> Optional[Dict[str, object]]:
    response = api_client.get(
        f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions",
        timeout=30
    )
    versions = response.get("versions", [])
    return versions[0] if versions else None


def _save_new_version(
    plan_key: str,
    plan_title: str,
    base_document_id: str,
    base_metadata: Dict[str, object],
    updated_markdown: str
) -> None:
    plan_record = _find_plan_record(plan_key)
    base_version_id = None
    next_version = 1

    if plan_record:
        latest = _get_latest_version(plan_record["id"])
        if latest:
            base_version_id = latest["id"]
            next_version = int(latest.get("version_number", 0)) + 1
    else:
        create_plan = api_client.post(
            f"{config.fastapi_url}/api/versioning/test-plans",
            data={
                "plan_key": plan_key,
                "title": plan_title,
                "collection_name": GENERATED_TEST_PLAN_COLLECTION,
                "percent_complete": 0,
                "document_id": base_document_id,
                "based_on_version_id": None
            },
            timeout=30
        )
        plan_record = create_plan["plan"]
        base_version_id = create_plan["version"]["id"]
        next_version = int(create_plan["version"]["version_number"]) + 1

    if plan_record and plan_title and plan_title != plan_record.get("title"):
        api_client.put(
            f"{config.fastapi_url}/api/versioning/test-plans/{plan_record['id']}",
            data={"title": plan_title},
            timeout=30
        )

    new_doc_id = f"testplan_{uuid.uuid4().hex[:12]}"
    new_metadata = dict(base_metadata or {})
    new_metadata["title"] = plan_title
    new_metadata["plan_key"] = plan_key
    new_metadata["version_number"] = next_version
    new_metadata["based_on_document_id"] = base_document_id
    new_metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

    api_client.post(
        f"{config.fastapi_url}/api/vectordb/documents/add",
        data={
            "collection_name": GENERATED_TEST_PLAN_COLLECTION,
            "documents": [updated_markdown],
            "ids": [new_doc_id],
            "metadatas": [new_metadata]
        },
        timeout=30
    )

    api_client.post(
        f"{config.fastapi_url}/api/versioning/test-plans/{plan_record['id']}/versions",
        data={
            "document_id": new_doc_id,
            "based_on_version_id": base_version_id
        },
        timeout=30
    )

    st.success(f"Saved version {next_version} for this plan.")


def render_test_plan_editor() -> None:
    st.subheader("Edit Test Plan")

    try:
        plans = _load_plan_documents()
    except Exception as e:
        st.error(f"Failed to load test plans: {e}")
        return

    if not plans:
        st.info("No test plans found. Generate a test plan first.")
        return

    plan_options: Dict[str, PlanDocument] = {}
    for plan in plans:
        title = plan.metadata.get("title") or "Untitled Plan"
        label = f"{title} ({plan.document_id[:8]}...)"
        plan_options[label] = plan

    selected_label = st.selectbox(
        "Select a test plan to edit:",
        options=list(plan_options.keys()),
        key="plan_editor_select"
    )

    selected_plan = plan_options[selected_label]
    plan_title = st.text_input(
        "Plan Title",
        value=selected_plan.metadata.get("title", "Untitled Plan"),
        key=f"plan_editor_title_{selected_plan.document_id}"
    )

    preamble, sections = _parse_sections(selected_plan.content)
    section_labels = [
        f"{idx + 1}. {section.get('title') or 'Untitled Section'}"
        for idx, section in enumerate(sections)
    ]

    selected_section_label = st.selectbox(
        "Select Section",
        options=section_labels,
        key=f"plan_editor_section_select_{selected_plan.document_id}"
    )
    section_index = section_labels.index(selected_section_label)
    section = sections[section_index]

    with st.form("test_plan_editor_form"):
        section_title = st.text_input(
            "Section Title",
            value=section.get("title", ""),
            key=f"plan_editor_section_title_{selected_plan.document_id}_{section_index}"
        )
        section_content = st.text_area(
            "Section Content",
            value=section.get("content", ""),
            height=260,
            key=f"plan_editor_section_content_{selected_plan.document_id}_{section_index}"
        )
        submitted = st.form_submit_button("Save New Version")

    if submitted:
        if not section_title.strip():
            st.warning("Section title is required.")
            return

        sections[section_index]["title"] = section_title.strip()
        sections[section_index]["content"] = section_content.strip()
        updated_markdown = _build_markdown(preamble, sections)

        plan_key = selected_plan.metadata.get("plan_key") or selected_plan.document_id
        try:
            _save_new_version(
                plan_key=plan_key,
                plan_title=plan_title.strip() or "Untitled Plan",
                base_document_id=selected_plan.document_id,
                base_metadata=selected_plan.metadata,
                updated_markdown=updated_markdown
            )
            st.rerun()
        except Exception as e:
            st.error(f"Failed to save new version: {e}")
