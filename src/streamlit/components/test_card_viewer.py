"""
Test Card Viewer Component - Enhanced
Generate and execute test cards from test plans.

Features:
- WYSIWYG rich text editing for individual test cards
- Document-like styling
- Version management
"""

import streamlit as st
import pandas as pd
import json
import uuid
import re
from typing import Dict, List, Optional, Tuple
from config.settings import config
from app_lib.api.client import api_client
from datetime import datetime, timezone
from components.job_status_monitor import JobStatusMonitor
from streamlit_quill import st_quill
from components.shared_styles import (
    get_sidebyside_css,
    PANEL_HEIGHT,
    TEXT_AREA_STANDARD
)


def _markdown_to_document_html(text: str) -> str:
    """
    Convert markdown/plain text to document-style HTML with proper headings.
    Renders like Google Docs or Microsoft Word.
    """
    if not text:
        return "<p style='color: #888;'>No content</p>"

    # If already HTML, return as-is with styling wrapper
    if text.strip().startswith("<"):
        return f'<div class="doc-content">{text}</div>'

    lines = text.split('\n')
    html_parts = []
    in_list = False
    list_type = None

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_list:
                html_parts.append(f'</{list_type}>')
                in_list = False
            html_parts.append('<br>')
            continue

        # Headings (### H3, ## H2, # H1)
        if stripped.startswith('### '):
            if in_list:
                html_parts.append(f'</{list_type}>')
                in_list = False
            heading_text = stripped[4:]
            html_parts.append(f'<h4 style="font-size: 1.0em; font-weight: 600; color: #333; margin: 16px 0 8px 0; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px;">{heading_text}</h4>')
        elif stripped.startswith('## '):
            if in_list:
                html_parts.append(f'</{list_type}>')
                in_list = False
            heading_text = stripped[3:]
            html_parts.append(f'<h3 style="font-size: 1.1em; font-weight: 600; color: #222; margin: 18px 0 10px 0; border-bottom: 1px solid #ccc; padding-bottom: 4px;">{heading_text}</h3>')
        elif stripped.startswith('# '):
            if in_list:
                html_parts.append(f'</{list_type}>')
                in_list = False
            heading_text = stripped[2:]
            html_parts.append(f'<h2 style="font-size: 1.2em; font-weight: 700; color: #111; margin: 20px 0 12px 0; border-bottom: 2px solid #333; padding-bottom: 6px;">{heading_text}</h2>')

        # Numbered list (1. item)
        elif re.match(r'^\d+\.\s', stripped):
            item_text = re.sub(r'^\d+\.\s', '', stripped)
            item_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', item_text)
            item_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', item_text)
            if not in_list or list_type != 'ol':
                if in_list:
                    html_parts.append(f'</{list_type}>')
                html_parts.append('<ol style="margin: 8px 0; padding-left: 24px;">')
                in_list = True
                list_type = 'ol'
            html_parts.append(f'<li style="margin: 4px 0; line-height: 1.5;">{item_text}</li>')

        # Bullet list (* item or - item)
        elif stripped.startswith('* ') or stripped.startswith('- '):
            item_text = stripped[2:]
            item_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', item_text)
            item_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', item_text)
            if not in_list or list_type != 'ul':
                if in_list:
                    html_parts.append(f'</{list_type}>')
                html_parts.append('<ul style="margin: 8px 0; padding-left: 24px;">')
                in_list = True
                list_type = 'ul'
            html_parts.append(f'<li style="margin: 4px 0; line-height: 1.5;">{item_text}</li>')

        # Regular paragraph
        else:
            if in_list:
                html_parts.append(f'</{list_type}>')
                in_list = False
            para_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', stripped)
            para_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', para_text)
            html_parts.append(f'<p style="margin: 8px 0; line-height: 1.6; text-align: justify;">{para_text}</p>')

    if in_list:
        html_parts.append(f'</{list_type}>')

    return ''.join(html_parts)


def TestCardViewer():
    """
    Test Cards workflow:
    1. Generate - Create test cards from test plans
    2. Edit & Review - Edit test card content and export
    3. Execute - Track test execution status (final step)
    """
    st.header("Test Cards")

    # Three-step workflow tabs
    tab1, tab2, tab3 = st.tabs([
        "1. Generate",
        "2. Edit & Review",
        "3. Execute"
    ])

    with tab1:
        render_test_card_generator()

    with tab2:
        render_test_card_editor()

    with tab3:
        render_test_card_executor()


def _list_test_plans() -> Tuple[List[str], List[dict], Dict[str, dict]]:
    """List test plans from both draft and published collections (deduplicated)"""
    all_doc_ids = []
    all_metadatas = []
    seen_plan_keys = set()  # Track plan_key/plan_id to avoid duplicates
    seen_titles = set()  # Also track by title as fallback

    # Load from test_plan_drafts FIRST (preferred - user-edited versions)
    # Collection may not exist yet - suppress 404 errors
    draft_plans = []  # Collect all drafts first, then pick the most recent
    try:
        draft_response = api_client.get(
            f"{config.fastapi_url}/api/vectordb/documents",
            params={"collection_name": "test_plan_drafts"},
            timeout=None,
            show_errors=False
        )
        if draft_response:
            draft_ids = draft_response.get("ids", [])
            draft_metas = draft_response.get("metadatas", [])

            # Filter to ONLY include full test plan documents (not section chunks)
            for idx, doc_id in enumerate(draft_ids):
                meta = draft_metas[idx] if idx < len(draft_metas) else {}
                # Must be explicitly marked as full test plan - sections have type="test_plan_section"
                if meta.get("type") == "test_plan_full":
                    meta["_doc_id"] = doc_id
                    meta["_source"] = "draft"
                    meta["_status"] = "DRAFT"
                    draft_plans.append(meta)
    except Exception:
        # Silently handle - collection may not exist yet
        pass

    # Sort drafts by updated_at (most recent first) to keep the latest version
    draft_plans.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    # Deduplicate drafts by plan_key, plan_id, OR title
    for meta in draft_plans:
        doc_id = meta.pop("_doc_id")
        plan_key = meta.get("plan_key") or meta.get("plan_id")
        title = meta.get("title", "").strip().lower()

        # Check if we've seen this plan before (by key or title)
        if plan_key and plan_key in seen_plan_keys:
            continue
        if not plan_key and title and title in seen_titles:
            continue

        # Track this plan
        if plan_key:
            seen_plan_keys.add(plan_key)
        if title:
            seen_titles.add(title)

        all_doc_ids.append(doc_id)
        all_metadatas.append(meta)

    # Load from generated_test_plan (original generated plans)
    # Skip if already in drafts (user has edited version)
    try:
        generated_response = api_client.get(
            f"{config.fastapi_url}/api/vectordb/documents",
            params={"collection_name": "generated_test_plan"},
            timeout=None,
            show_errors=False
        )
        if generated_response:
            gen_ids = generated_response.get("ids", [])
            gen_metas = generated_response.get("metadatas", [])

            for idx, doc_id in enumerate(gen_ids):
                meta = gen_metas[idx] if idx < len(gen_metas) else {}

                # Check for duplicates - by key or title
                plan_key = meta.get("plan_key") or meta.get("plan_id")
                title = meta.get("title", "").strip().lower()

                if plan_key and plan_key in seen_plan_keys:
                    continue
                if not plan_key and title and title in seen_titles:
                    continue

                # Track this plan
                if plan_key:
                    seen_plan_keys.add(plan_key)
                if title:
                    seen_titles.add(title)

                meta["_source"] = "generated"
                # Default to DRAFT - user must explicitly publish
                meta["_status"] = meta.get("status", "DRAFT").upper()
                if meta["_status"] not in ["DRAFT", "FINAL", "PUBLISHED"]:
                    meta["_status"] = "DRAFT"
                all_doc_ids.append(doc_id)
                all_metadatas.append(meta)
    except Exception:
        # Silently handle - collection may not exist yet
        pass

    metadata_map = {
        doc_id: (all_metadatas[idx] if idx < len(all_metadatas) else {})
        for idx, doc_id in enumerate(all_doc_ids)
    }
    return all_doc_ids, all_metadatas, metadata_map


def _fetch_plan_records() -> List[dict]:
    response = api_client.get(
        f"{config.fastapi_url}/api/versioning/test-plans",
        timeout=30
    )
    return response.get("plans", [])


def _find_plan_record(plan_key: str, plans: List[dict]) -> Optional[dict]:
    for plan in plans:
        if plan.get("plan_key") == plan_key:
            return plan
    return None


def _list_plan_versions(plan_id: int) -> List[dict]:
    response = api_client.get(
        f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions",
        timeout=30
    )
    return response.get("versions", [])


def _ensure_plan_context(plan_key: str, plan_title: str, plan_doc_id: str) -> Tuple[dict, dict]:
    plans = _fetch_plan_records()
    plan = _find_plan_record(plan_key, plans)

    if not plan:
        created = api_client.post(
            f"{config.fastapi_url}/api/versioning/test-plans",
            data={
                "plan_key": plan_key,
                "title": plan_title,
                "collection_name": "generated_test_plan",
                "percent_complete": 0,
                "document_id": plan_doc_id,
                "based_on_version_id": None
            },
            timeout=30
        )
        return created["plan"], created["version"]

    versions = _list_plan_versions(plan["id"])
    for version in versions:
        if version.get("document_id") == plan_doc_id:
            return plan, version

    base_version_id = versions[0]["id"] if versions else None
    new_version = api_client.post(
        f"{config.fastapi_url}/api/versioning/test-plans/{plan['id']}/versions",
        data={
            "document_id": plan_doc_id,
            "based_on_version_id": base_version_id
        },
        timeout=30
    )
    return plan, new_version


def _list_cards_for_plan(plan_id: int) -> List[dict]:
    response = api_client.get(
        f"{config.fastapi_url}/api/versioning/test-cards",
        params={"plan_id": plan_id},
        timeout=30
    )
    return response.get("cards", [])


def _list_card_versions(card_id: int) -> List[dict]:
    response = api_client.get(
        f"{config.fastapi_url}/api/versioning/test-cards/{card_id}/versions",
        timeout=30
    )
    return response.get("versions", [])


def _get_latest_doc_ids_for_plan(plan_id: int) -> List[str]:
    latest_doc_ids: List[str] = []
    cards = _list_cards_for_plan(plan_id)
    for card in cards:
        versions = _list_card_versions(card["id"])
        if versions:
            latest_doc_ids.append(versions[0]["document_id"])
    return latest_doc_ids


def _filter_latest_cards(cards: List[dict], plan_id: Optional[int]) -> List[dict]:
    if not plan_id:
        return cards

    latest_doc_ids = _get_latest_doc_ids_for_plan(plan_id)
    if not latest_doc_ids:
        return cards

    latest_set = set(latest_doc_ids)
    return [card for card in cards if card.get("document_id") in latest_set]


def _build_updated_metadata(card: dict, updates: dict) -> dict:
    base = dict(card.get("metadata") or {})

    for field in [
        "test_plan_id",
        "test_plan_title",
        "section_title",
        "test_id",
        "test_title",
        "requirement_id",
        "requirement_text",
        "execution_status",
        "executed_by",
        "executed_at",
        "execution_duration_minutes",
        "passed",
        "failed",
        "notes",
        "actual_results",
    ]:
        if field not in base and field in card:
            base[field] = card[field]

    if "document_name" in updates:
        base["document_name"] = updates["document_name"]
        base["test_title"] = updates["document_name"]
    if "requirement_text" in updates:
        base["requirement_text"] = updates["requirement_text"]
    if "execution_status" in updates:
        base["execution_status"] = updates["execution_status"]
    if "passed" in updates:
        base["passed"] = updates["passed"]
    if "failed" in updates:
        base["failed"] = updates["failed"]
    if "notes" in updates:
        base["notes"] = updates["notes"]
    if "executed_by" in updates:
        base["executed_by"] = updates["executed_by"]
    if "executed_at" in updates:
        base["executed_at"] = updates["executed_at"]
    if "execution_duration_minutes" in updates:
        base["execution_duration_minutes"] = updates["execution_duration_minutes"]
    if "actual_results" in updates:
        base["actual_results"] = updates["actual_results"]

    return base


def _create_test_card_version(
    card: dict,
    updates: dict,
    updated_content: str,
    plan_key: str,
    plan_title: str,
    plan_doc_id: str
) -> None:
    plan, plan_version = _ensure_plan_context(plan_key, plan_title, plan_doc_id)
    plan_id = plan["id"]
    plan_version_id = plan_version["id"]

    existing_cards = _list_cards_for_plan(plan_id)
    card_map = {item.get("card_key"): item for item in existing_cards if item.get("card_key")}

    test_id = card.get("test_id") or card.get("document_id")
    requirement_id = card.get("requirement_id") or ""
    preferred_key = f"{plan_key}:{requirement_id or test_id}"
    fallback_key = f"{plan_key}:{test_id}"

    existing = card_map.get(preferred_key) or card_map.get(fallback_key)
    base_version_id = None
    card_id = None

    if existing:
        card_id = existing["id"]
        versions = _list_card_versions(card_id)
        base_version_id = versions[0]["id"] if versions else None

    new_doc_id = f"testcard_{plan_doc_id}_{test_id}_{uuid.uuid4().hex[:8]}"
    metadata = _build_updated_metadata(card, updates)
    metadata["test_plan_id"] = plan_doc_id
    metadata["test_plan_title"] = plan_title
    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

    api_client.post(
        f"{config.fastapi_url}/api/vectordb/documents/add",
        data={
            "collection_name": "test_cards",
            "documents": [updated_content],
            "ids": [new_doc_id],
            "metadatas": [metadata]
        },
        timeout=30
    )

    if not existing:
        api_client.post(
            f"{config.fastapi_url}/api/versioning/test-cards",
            data={
                "card_key": preferred_key,
                "plan_id": plan_id,
                "title": metadata.get("document_name") or card.get("document_name") or test_id,
                "requirement_id": requirement_id or test_id,
                "percent_complete": 0,
                "document_id": new_doc_id,
                "based_on_version_id": None,
                "plan_version_id": plan_version_id
            },
            timeout=30
        )
        return

    api_client.post(
        f"{config.fastapi_url}/api/versioning/test-cards/{card_id}/versions",
        data={
            "document_id": new_doc_id,
            "based_on_version_id": base_version_id,
            "plan_version_id": plan_version_id
        },
        timeout=30
    )


def _record_test_card_versions(
    job_id: str,
    result_response: dict,
    plan_key: str,
    plan_title: str,
    plan_doc_id: str
) -> None:
    if st.session_state.get("testcard_versions_recorded", {}).get(job_id):
        return

    plan, plan_version = _ensure_plan_context(plan_key, plan_title, plan_doc_id)
    plan_id = plan["id"]
    plan_version_id = plan_version["id"]

    existing_cards = _list_cards_for_plan(plan_id)
    card_map = {card.get("card_key"): card for card in existing_cards if card.get("card_key")}

    test_cards = result_response.get("test_cards", [])
    for card in test_cards:
        test_id = card.get("test_id") or card.get("document_id")
        requirement_id = card.get("requirement_id") or ""
        preferred_key = f"{plan_key}:{requirement_id or test_id}"
        fallback_key = f"{plan_key}:{test_id}"
        document_id = card.get("document_id")
        document_name = card.get("document_name") or test_id

        existing = card_map.get(preferred_key) or card_map.get(fallback_key)
        if not existing:
            try:
                api_client.post(
                    f"{config.fastapi_url}/api/versioning/test-cards",
                    data={
                        "card_key": preferred_key,
                        "plan_id": plan_id,
                        "title": document_name,
                        "requirement_id": requirement_id or test_id,
                        "percent_complete": 0,
                        "document_id": document_id,
                        "based_on_version_id": None,
                        "plan_version_id": plan_version_id
                    },
                    timeout=30,
                    show_errors=False  # Handle 409 gracefully
                )
            except Exception as e:
                # 409 Conflict means card already exists - skip and continue
                # This can happen when card was created with different plan association
                if "409" in str(e) or "Conflict" in str(e):
                    pass  # Card already exists, continue to next
                else:
                    raise  # Re-raise other errors
            continue

        versions = _list_card_versions(existing["id"])
        if any(v.get("document_id") == document_id for v in versions):
            continue

        base_version_id = versions[0]["id"] if versions else None
        api_client.post(
            f"{config.fastapi_url}/api/versioning/test-cards/{existing['id']}/versions",
            data={
                "document_id": document_id,
                "based_on_version_id": base_version_id,
                "plan_version_id": plan_version_id
            },
            timeout=30
        )

    recorded = st.session_state.get("testcard_versions_recorded", {})
    recorded[job_id] = True
    st.session_state.testcard_versions_recorded = recorded


def _build_regen_baseline(test_cards: List[dict]) -> Dict[str, Dict[str, dict]]:
    by_req: Dict[str, dict] = {}
    by_test: Dict[str, dict] = {}
    for card in test_cards:
        baseline = {
            "execution_status": card.get("execution_status", "not_executed"),
            "passed": card.get("passed", False),
            "failed": card.get("failed", False),
            "notes": card.get("notes", ""),
            "executed_by": card.get("executed_by", ""),
            "executed_at": card.get("executed_at", ""),
            "execution_duration_minutes": card.get("execution_duration_minutes", 0),
            "actual_results": card.get("actual_results", "")
        }
        requirement_id = card.get("requirement_id") or ""
        test_id = card.get("test_id") or ""
        if requirement_id:
            by_req[requirement_id] = baseline
        if test_id:
            by_test[test_id] = baseline
    return {"by_req": by_req, "by_test": by_test}


def _apply_regen_baseline(job_id: str, result_response: dict) -> None:
    baseline_map = st.session_state.get("testcard_regen_baseline", {}).get(job_id)
    if not baseline_map:
        return

    updates = []
    for card in result_response.get("test_cards", []):
        requirement_id = card.get("requirement_id") or ""
        test_id = card.get("test_id") or ""
        prior = baseline_map["by_req"].get(requirement_id) or baseline_map["by_test"].get(test_id)
        if not prior:
            continue

        update_fields = {}
        if prior.get("execution_status") and prior.get("execution_status") != "not_executed":
            update_fields["execution_status"] = prior["execution_status"]
        if "passed" in prior:
            update_fields["passed"] = prior["passed"]
        if "failed" in prior:
            update_fields["failed"] = prior["failed"]
        if prior.get("notes") is not None:
            update_fields["notes"] = prior["notes"]
        if prior.get("executed_by") is not None:
            update_fields["executed_by"] = prior["executed_by"]
        if prior.get("executed_at") is not None:
            update_fields["executed_at"] = prior["executed_at"]
        if "execution_duration_minutes" in prior:
            update_fields["execution_duration_minutes"] = prior["execution_duration_minutes"]
        if prior.get("actual_results") is not None:
            update_fields["actual_results"] = prior["actual_results"]

        if update_fields:
            updates.append({
                "document_id": card.get("document_id"),
                "updates": update_fields
            })

    if not updates:
        return

    api_client.post(
        f"{config.fastapi_url}/api/doc_gen/test-cards/bulk-update",
        data={
            "collection_name": "test_cards",
            "updates": updates
        },
        timeout=30
    )


def render_test_card_generator():
    """Generate test cards from a test plan - simplified workflow"""
    st.subheader("Generate Test Cards")

    try:
        doc_ids, metadatas, metadata_map = _list_test_plans()

        if not doc_ids:
            st.info("No test plans found. Generate a test plan first using the Document Generator.")
            return

        plan_options = {}
        for doc_id, m in zip(doc_ids, metadatas):
            status = m.get('_status', 'UNKNOWN')
            title = m.get('title', 'Untitled')
            status_badge = "[DRAFT]" if status == "DRAFT" else "[Published]"
            label = f"{status_badge} {title} ({doc_id[:8]}...)"
            plan_options[label] = doc_id

        # Step 1: Select Test Plan
        st.markdown("### Select Test Plan")
        selected_plan = st.selectbox(
            "Choose a test plan:",
            list(plan_options.keys()),
            key="selected_test_plan",
            label_visibility="collapsed"
        )

        if not selected_plan:
            return

        selected_doc_id = plan_options[selected_plan]
        selected_metadata = metadata_map.get(selected_doc_id, {})
        plan_key = selected_metadata.get("plan_key") or selected_doc_id
        plan_title = selected_metadata.get("title", "Untitled Plan")
        # Track if this is a draft or published plan
        plan_source = selected_metadata.get("_source", "published")
        plan_collection = "test_plan_drafts" if plan_source == "draft" else "generated_test_plan"

        plan_record = _find_plan_record(plan_key, _fetch_plan_records())
        plan_versions = _list_plan_versions(plan_record["id"]) if plan_record else []
        selected_plan_version = None

        # Show selected plan info
        status_label = "DRAFT" if plan_source == "draft" else "Published"
        st.info(f"**{plan_title}** ({status_label})")

        if plan_versions:
            version_options = {
                f"v{v['version_number']} ({v['document_id'][:8]}...)": v
                for v in plan_versions
            }
            selected_version_label = st.selectbox(
                "Select Version",
                options=list(version_options.keys()),
                key="selected_test_plan_version"
            )
            selected_plan_version = version_options[selected_version_label]

        plan_doc_id_for_generation = (
            selected_plan_version["document_id"]
            if selected_plan_version
            else selected_doc_id
        )
        plan_doc_metadata = metadata_map.get(plan_doc_id_for_generation, selected_metadata)
        plan_title = plan_doc_metadata.get("title", plan_title)
        plan_key = plan_doc_metadata.get("plan_key") or plan_key

        # After version selection, update collection - edited versions are in test_plan_drafts
        # Check if the document exists in test_plan_drafts (preferred for edited versions)
        if selected_plan_version:
            try:
                draft_check = api_client.get(
                    f"{config.fastapi_url}/api/vectordb/documents",
                    params={"collection_name": "test_plan_drafts"},
                    timeout=10,
                    show_errors=False
                )
                draft_ids = draft_check.get("ids", []) if draft_check else []
                if plan_doc_id_for_generation in draft_ids:
                    plan_collection = "test_plan_drafts"
            except Exception:
                pass  # Keep original collection

        # Show plan details
        with st.expander("Test Plan Details"):
            st.text(f"Document ID: {plan_doc_id_for_generation}")
            st.text(f"Generated: {plan_doc_metadata.get('generated_at', 'N/A')}")
            st.text(f"Sections: {plan_doc_metadata.get('total_sections', 0)}")
            st.text(f"Requirements: {plan_doc_metadata.get('total_requirements', 0)}")
            if selected_plan_version:
                st.text(f"Plan Version: v{selected_plan_version['version_number']}")

        st.markdown("---")

        # Resume Existing Test Card Generation
        with st.expander("Resume Existing Test Card Generation", expanded=False):
            st.write("If you refreshed the page or came back later, you can resume your test card generation here.")

            try:
                jobs_response = api_client.get(
                    f"{config.endpoints.doc_gen}/list-test-card-jobs",
                    timeout=10
                )
                jobs = jobs_response.get("jobs", [])

                if jobs:
                    st.write(f"**Select from {len(jobs)} recent job(s):**")

                    # Create a table of jobs
                    for job in jobs[:10]:  # Show last 10
                        status = job.get("status", "unknown")
                        job_id = job.get("job_id", "")
                        test_plan_title = job.get("test_plan_title", "Untitled")
                        created_at = job.get("created_at", "")
                        test_cards_generated = job.get("test_cards_generated", "0")

                        # Calculate elapsed time
                        try:
                            from datetime import datetime
                            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            elapsed = datetime.now() - created.replace(tzinfo=None)
                            minutes = int(elapsed.total_seconds() / 60)
                            if minutes < 60:
                                time_str = f"{minutes}m ago"
                            else:
                                hours = minutes // 60
                                time_str = f"{hours}h {minutes % 60}m ago"
                        except:
                            time_str = created_at[:19] if created_at else "Unknown"

                        # Status emoji
                        status_emoji = {
                            "completed": "✅",
                            "processing": "⏳",
                            "queued": "📝",
                            "failed": "❌",
                            "initializing": "⏳"
                        }.get(status.lower(), "❓")

                        col1, col2, col3 = st.columns([4, 3, 2])
                        with col1:
                            st.write(f"{status_emoji} **{test_plan_title}**")
                            st.caption(f"{job_id[:25]}...")
                        with col2:
                            st.write(f"**{status.upper()}**")
                            st.caption(f"{time_str} | {test_cards_generated} cards")
                        with col3:
                            button_label = "View" if status.lower() == "completed" else "Resume"
                            button_type = "primary" if status.lower() in ["processing", "queued", "initializing"] else "secondary"
                            if st.button(button_label, key=f"resume_testcard_{job_id}", type=button_type, use_container_width=True):
                                st.session_state.testcard_job_id = job_id
                                st.session_state.testcard_job_status = status
                                st.rerun()

                        st.markdown("---")

                else:
                    st.info("No test card generation jobs found. Start a new generation below.")

            except Exception as e:
                st.warning(f"Could not load test card jobs: {e}")
                st.info("Start a new generation below.")

        st.markdown("---")

        # Step 2: Select Test Procedures to Convert
        st.markdown("### Select Test Procedures")
        st.caption("Choose which test procedures from the test plan should be converted to test cards.")

        # Fetch test plan JSON to get procedures
        selected_procedures = []
        test_plan_sections = []

        try:
            # Fetch the test plan document from ChromaDB
            test_plan_response = api_client.get(
                f"{config.fastapi_url}/api/vectordb/documents",
                params={"collection_name": plan_collection},
                timeout=30,
                show_errors=False
            )

            if test_plan_response:
                plan_ids = test_plan_response.get("ids", [])
                plan_docs = test_plan_response.get("documents", [])

                # Find the test plan document
                for idx, doc_id in enumerate(plan_ids):
                    if doc_id == plan_doc_id_for_generation:
                        content = plan_docs[idx] if idx < len(plan_docs) else ""
                        if content:
                            try:
                                test_plan_data = json.loads(content) if isinstance(content, str) else content
                                test_plan_sections = test_plan_data.get("test_plan", {}).get("sections", [])
                            except json.JSONDecodeError:
                                pass
                        break

            if test_plan_sections:
                # Initialize selection state if not exists
                selection_key = f"proc_selection_{plan_doc_id_for_generation}"
                if selection_key not in st.session_state:
                    st.session_state[selection_key] = {}

                # Calculate totals for reviewed sections only
                reviewed_sections_list = [s for s in test_plan_sections if s.get("reviewed", False)]
                reviewed_count = len(reviewed_sections_list)
                reviewed_procedures = sum(len(s.get("test_procedures", [])) for s in reviewed_sections_list)
                reviewed_with_content = sum(
                    1 for s in reviewed_sections_list
                    if s.get("test_procedures") or s.get("synthesized_rules")
                )

                # Check if this is a "legacy" test plan without structured procedures
                has_structured_procedures = reviewed_procedures > 0

                if reviewed_count == 0:
                    st.warning("⚠️ No reviewed sections found. Go to **Tab 3 (Edit Test Plan)** to mark sections as 'Reviewed' before generating test cards.")
                elif has_structured_procedures:
                    st.success(f"✅ Showing {reviewed_count} reviewed section(s) with {reviewed_procedures} test procedures available for conversion.")
                else:
                    # Legacy test plan - procedures will be extracted from synthesized_rules
                    st.info(f"ℹ️ Showing {reviewed_count} reviewed section(s) (content-based - no structured procedures). Test cards will be generated from section content.")

                # Select All / Deselect All buttons (only for reviewed sections)
                if reviewed_count > 0:
                    select_cols = st.columns([1, 1, 3])
                    with select_cols[0]:
                        if st.button("Select All", key="select_all_procedures", type="primary", use_container_width=True):
                            # Iterate original list to keep indices consistent with display loop
                            for section_idx, section in enumerate(test_plan_sections):
                                if not section.get("reviewed", False):
                                    continue  # Skip non-reviewed
                                # Use consistent section_id logic (with fallback using original index)
                                section_id = section.get("section_id", f"section_{section_idx}")
                                procedures = section.get("test_procedures", [])
                                if procedures:
                                    for proc in procedures:
                                        proc_id = proc.get("id", "")
                                        st.session_state[selection_key][f"{section_id}_{proc_id}"] = True
                                else:
                                    # No procedures - select entire section for content-based generation
                                    st.session_state[selection_key][f"{section_id}_section"] = True
                            st.rerun()

                    with select_cols[1]:
                        if st.button("Deselect All", key="deselect_all_procedures", use_container_width=True):
                            st.session_state[selection_key] = {}
                            st.rerun()

                # Display ONLY reviewed sections with procedure checkboxes
                for section_idx, section in enumerate(test_plan_sections):
                    section_id = section.get("section_id", f"section_{section_idx}")
                    section_title = section.get("section_title", f"Section {section_idx + 1}")
                    is_reviewed = section.get("reviewed", False)
                    procedures = section.get("test_procedures", [])
                    has_content = bool(section.get("synthesized_rules", "").strip())

                    # Only show reviewed sections - skip non-reviewed
                    if not is_reviewed:
                        continue

                    # Skip sections with no procedures AND no content
                    if not procedures and not has_content:
                        continue

                    if procedures:
                        # Section with structured procedures
                        with st.expander(f"📋 {section_title} ({len(procedures)} procedures) - ✓ Reviewed", expanded=False):
                            # Select all in section
                            section_select_key = f"select_section_{section_id}"
                            section_all_selected = all(
                                st.session_state[selection_key].get(f"{section_id}_{proc.get('id', '')}", False)
                                for proc in procedures
                            )

                            if st.checkbox(
                                f"Select all in this section",
                                value=section_all_selected,
                                key=section_select_key
                            ):
                                for proc in procedures:
                                    proc_id = proc.get("id", "")
                                    st.session_state[selection_key][f"{section_id}_{proc_id}"] = True

                            st.markdown("---")

                            # Individual procedure checkboxes
                            for proc in procedures:
                                proc_id = proc.get("id", "")
                                proc_title = proc.get("title", "Untitled")[:60]
                                proc_priority = proc.get("priority", "medium")
                                steps_count = len(proc.get("steps", []))

                                checkbox_key = f"proc_{section_id}_{proc_id}"
                                is_selected = st.session_state[selection_key].get(f"{section_id}_{proc_id}", False)

                                col_check, col_info = st.columns([3, 1])
                                with col_check:
                                    selected = st.checkbox(
                                        f"**{proc_id}**: {proc_title}",
                                        value=is_selected,
                                        key=checkbox_key
                                    )
                                    if selected != is_selected:
                                        st.session_state[selection_key][f"{section_id}_{proc_id}"] = selected

                                with col_info:
                                    st.caption(f"{steps_count} steps | {proc_priority}")

                                # Add to selected list (user selection controls what gets converted)
                                if selected:
                                    selected_procedures.append({
                                        "section_id": section_id,
                                        "section_title": section_title,
                                        "procedure_id": proc_id,
                                        "procedure": proc
                                    })
                    else:
                        # Section without structured procedures - allow selecting entire section
                        section_select_key = f"section_select_{section_id}"
                        is_section_selected = st.session_state[selection_key].get(f"{section_id}_section", False)

                        with st.expander(f"📄 {section_title} (content-based) - ✓ Reviewed", expanded=False):
                            st.info("This section has content but no structured procedures. Test cards will be extracted from section content.")

                            # Preview of section content
                            content_preview = section.get("synthesized_rules", "")[:300]
                            if content_preview:
                                st.caption(f"Content preview: {content_preview}...")

                            # Single checkbox for entire section
                            selected = st.checkbox(
                                f"Generate test cards from this section",
                                value=is_section_selected,
                                key=section_select_key
                            )
                            if selected != is_section_selected:
                                st.session_state[selection_key][f"{section_id}_section"] = selected

                            # Add to selected list (user selection controls what gets converted)
                            if selected:
                                selected_procedures.append({
                                    "section_id": section_id,
                                    "section_title": section_title,
                                    "procedure_id": "section",  # Special marker for section-level selection
                                    "procedure": {
                                        "id": "section",
                                        "title": section_title,
                                        "content": section.get("synthesized_rules", "")
                                    }
                                })

                # Show selection summary
                st.markdown("---")
                if selected_procedures:
                    # Count procedures vs sections
                    proc_count = sum(1 for p in selected_procedures if p['procedure_id'] != 'section')
                    section_count = sum(1 for p in selected_procedures if p['procedure_id'] == 'section')

                    if proc_count > 0 and section_count > 0:
                        st.success(f"**{proc_count}** procedure(s) and **{section_count}** section(s) selected for conversion")
                    elif section_count > 0:
                        st.success(f"**{section_count}** section(s) selected for content-based test card generation")
                    else:
                        st.success(f"**{proc_count}** procedure(s) selected for conversion")

                    # Preview table
                    with st.expander("Preview Selected Items", expanded=False):
                        preview_data = []
                        for p in selected_procedures[:20]:  # Limit preview to 20
                            if p['procedure_id'] == 'section':
                                # Section-level selection
                                preview_data.append({
                                    "Type": "Section",
                                    "ID": p['section_id'][:15],
                                    "Title": p['section_title'][:40],
                                    "Source": "Content-based"
                                })
                            else:
                                # Procedure-level selection
                                preview_data.append({
                                    "Type": "Procedure",
                                    "ID": p['procedure_id'][:15],
                                    "Title": p['procedure'].get('title', '')[:40],
                                    "Source": p['section_title'][:20]
                                })

                        if preview_data:
                            preview_df = pd.DataFrame(preview_data)
                            st.dataframe(preview_df, use_container_width=True, hide_index=True)

                        if len(selected_procedures) > 20:
                            st.caption(f"...and {len(selected_procedures) - 20} more")
                else:
                    st.warning("No procedures or sections selected. Select at least one item to generate test cards.")

            else:
                st.info("Could not load test plan sections. Using default generation (all procedures).")
                # Set flag to generate all procedures
                selected_procedures = None

        except Exception as e:
            st.warning(f"Could not load test plan structure: {e}")
            st.info("Will generate test cards for all procedures.")
            selected_procedures = None

        st.markdown("---")

        # Step 3: Generate Test Cards
        st.markdown("### Generate Test Cards")

        col1, col2 = st.columns([3, 1])

        existing_count = 0
        baseline_payload = None
        try:
            existing_cards = api_client.post(
                f"{config.endpoints.doc_gen}/query-test-cards",
                data={
                    "test_plan_id": plan_doc_id_for_generation,
                    "collection_name": "test_cards"
                },
                timeout=30,
                show_errors=False
            )
            existing_count = existing_cards.get("total_count", 0) if existing_cards else 0
            cards_for_baseline = existing_cards.get("test_cards", []) if existing_cards else []
            if plan_record:
                cards_for_baseline = _filter_latest_cards(cards_for_baseline, plan_record["id"])
            baseline_payload = _build_regen_baseline(cards_for_baseline) if cards_for_baseline else None
        except Exception:
            existing_count = 0
            baseline_payload = None

        confirm_regen = True
        if existing_count:
            st.warning(f"{existing_count} existing test cards found for this plan.")
            confirm_regen = st.checkbox(
                "Regenerate and carry over execution status/results/notes",
                key=f"confirm_testcard_regen_{plan_doc_id_for_generation}"
            )
            st.caption(
                "Carries: execution status, pass/fail, notes, executed by/at, duration, actual results."
            )

        with col1:
            # Determine button label and whether generation is allowed
            if selected_procedures is None:
                # Fallback mode - generate all
                button_label = "Generate All Test Cards"
                can_generate = True
            elif len(selected_procedures) > 0:
                button_label = f"Generate {len(selected_procedures)} Test Card(s)"
                can_generate = True
            else:
                button_label = "Select Procedures First"
                can_generate = False

            if st.button(button_label, type="primary", use_container_width=True, disabled=not can_generate):
                if existing_count and not confirm_regen:
                    st.error("Please confirm regeneration to continue.")
                    return
                with st.spinner("Submitting generation request..."):
                    try:
                        # Build request data
                        request_data = {
                            "test_plan_id": plan_doc_id_for_generation,
                            "collection_name": plan_collection,
                            "format": "markdown_table"
                        }

                        # Add selected procedures if user made selections
                        if selected_procedures is not None and len(selected_procedures) > 0:
                            request_data["selected_procedures"] = [
                                {
                                    "section_id": p["section_id"],
                                    "procedure_id": p["procedure_id"]
                                }
                                for p in selected_procedures
                            ]

                        response = api_client.post(
                            f"{config.endpoints.doc_gen}/generate-test-cards-from-plan-async",
                            data=request_data,
                            timeout=30
                        )

                        job_id = response.get("job_id")
                        st.session_state.testcard_job_id = job_id
                        st.session_state.testcard_job_status = "queued"
                        st.session_state.selected_test_plan_id = plan_doc_id_for_generation
                        contexts = st.session_state.get("testcard_job_contexts", {})
                        contexts[job_id] = {
                            "plan_key": plan_key,
                            "plan_title": plan_title,
                            "plan_doc_id": plan_doc_id_for_generation,
                            "plan_collection": plan_collection,
                            "selected_procedures_count": len(selected_procedures) if selected_procedures else "all"
                        }
                        st.session_state.testcard_job_contexts = contexts
                        if existing_count and baseline_payload:
                            baselines = st.session_state.get("testcard_regen_baseline", {})
                            baselines[job_id] = baseline_payload
                            st.session_state.testcard_regen_baseline = baselines
                        st.rerun()

                    except Exception as e:
                        st.error(f"Failed to start test card generation: {str(e)}")

        # Check for active job
        if st.session_state.get("testcard_job_id"):
            job_id = st.session_state.testcard_job_id

            # Define completion handler for test card generation
            def on_test_card_completed(result_response):
                test_cards_count = result_response.get("test_cards_generated", 0)
                st.success(f"Generated {test_cards_count} test cards successfully")

                # Show which sections were included (only reviewed sections generate test cards)
                test_cards_list = result_response.get("test_cards", [])
                if test_cards_list:
                    sections_with_cards = set(card.get("section_title", "Unknown") for card in test_cards_list)
                    if sections_with_cards:
                        st.info(f"📋 Test cards generated for {len(sections_with_cards)} reviewed section(s): {', '.join(sorted(sections_with_cards)[:5])}{'...' if len(sections_with_cards) > 5 else ''}")

                context = st.session_state.get("testcard_job_contexts", {}).get(job_id, {})
                plan_key_context = context.get("plan_key") or result_response.get("test_plan_id", "")
                plan_title_context = context.get("plan_title") or result_response.get("test_plan_title", "Untitled Plan")
                plan_doc_context = context.get("plan_doc_id") or result_response.get("test_plan_id", "")

                try:
                    _apply_regen_baseline(job_id=job_id, result_response=result_response)
                    baselines = st.session_state.get("testcard_regen_baseline", {})
                    if job_id in baselines:
                        baselines.pop(job_id, None)
                        st.session_state.testcard_regen_baseline = baselines
                except Exception as e:
                    st.warning(f"Test card regeneration merge failed: {e}")

                try:
                    _record_test_card_versions(
                        job_id=job_id,
                        result_response=result_response,
                        plan_key=plan_key_context,
                        plan_title=plan_title_context,
                        plan_doc_id=plan_doc_context
                    )
                except Exception as e:
                    # Versioning is for tracking only - test cards were still generated successfully
                    st.warning(f"Test card versioning note: {e} (Test cards were generated successfully - versioning is optional)")

                st.markdown("---")

                # Step 3: Export to DOCX
                st.markdown("### Export Test Cards")

                if st.button("Export to DOCX", type="secondary", use_container_width=True, key="export_completed_cards"):
                    try:
                        # Call export endpoint
                        import requests
                        export_response = requests.post(
                            f"{config.fastapi_url}/api/doc_gen/test-cards/export-docx",
                            json={
                                "test_plan_id": st.session_state.get("selected_test_plan_id", selected_doc_id),
                                "collection_name": "test_cards"
                            },
                            timeout=60
                        )

                        if export_response.status_code == 200:
                            # Provide download buttons - match test plan style
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            docx_filename = f"test_cards_{timestamp}.docx"

                            download_col1, download_col2 = st.columns(2)

                            with download_col1:
                                # DOCX download
                                st.download_button(
                                    label="Download DOCX",
                                    data=export_response.content,
                                    file_name=docx_filename,
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    type="primary",
                                    use_container_width=True,
                                    key="download_export_cards_docx"
                                )

                            with download_col2:
                                # Markdown download
                                try:
                                    markdown_response = requests.post(
                                        f"{config.fastapi_url}/api/doc_gen/test-cards/export-markdown",
                                        json={
                                            "test_plan_id": st.session_state.get("selected_test_plan_id", selected_doc_id),
                                            "collection_name": "test_cards"
                                        },
                                        timeout=60
                                    )

                                    if markdown_response.status_code == 200:
                                        md_filename = f"test_cards_{timestamp}.md"
                                        st.download_button(
                                            label="Download Markdown",
                                            data=markdown_response.content,
                                            file_name=md_filename,
                                            mime="text/markdown",
                                            type="secondary",
                                            use_container_width=True,
                                            key="download_export_cards_md"
                                        )
                                    else:
                                        st.warning("Markdown export unavailable")
                                except Exception as e:
                                    st.warning(f"Markdown export failed: {e}")
                        else:
                            st.error(f"Export failed: {export_response.text}")

                    except Exception as e:
                        st.error(f"Export failed: {str(e)}")

            # Define clear handler
            def on_clear():
                if "testcard_job_id" in st.session_state:
                    del st.session_state.testcard_job_id
                if "testcard_job_status" in st.session_state:
                    del st.session_state.testcard_job_status

            # Use the reusable JobStatusMonitor component
            monitor = JobStatusMonitor(
                job_id=job_id,
                session_key="testcard",
                status_endpoint=f"{config.endpoints.doc_gen}/test-card-generation-status/{{job_id}}",
                result_endpoint=f"{config.endpoints.doc_gen}/test-card-generation-result/{{job_id}}",
                job_name="Test Card Generation",
                show_metrics=True,
                show_elapsed_time=True,
                allow_cancel=False,
                on_completed=on_test_card_completed,
                on_clear=on_clear,
                auto_refresh_interval=5,  # Refresh every 5 seconds
                auto_clear_on_complete=False  # Keep results visible
            )
            monitor.render()

    except Exception as e:
        st.error(f"Failed to load test plans: {str(e)}")


def render_test_card_editor():
    """Edit and review test cards - Step 2 in workflow"""
    st.subheader("Edit & Review Test Cards")
    st.caption("Edit test card content, procedures, and requirements. Export when ready.")

    try:
        # Fetch all test plans (both draft and published for editing)
        doc_ids, metadatas, metadata_map = _list_test_plans()

        if not doc_ids:
            st.info("No test plans found. Generate a test plan first.")
            return

        # Select test plan with status badges
        plan_options = {}
        for doc_id, m in zip(doc_ids, metadatas):
            status = m.get('_status', 'UNKNOWN')
            title = m.get('title', 'Untitled')
            status_badge = "[DRAFT]" if status == "DRAFT" else "[Published]"
            label = f"{status_badge} {title} ({doc_id[:20]}...)"
            plan_options[label] = doc_id

        selected_plan = st.selectbox(
            "Select test plan:",
            list(plan_options.keys()),
            key="editor_test_plan"
        )

        if not selected_plan:
            return

        selected_doc_id = plan_options[selected_plan]
        selected_metadata = metadata_map.get(selected_doc_id, {})
        plan_key = selected_metadata.get("plan_key") or selected_doc_id
        plan_title = selected_metadata.get("title", "Untitled Plan")
        plan_source = selected_metadata.get("_source", "published")
        plan_record = _find_plan_record(plan_key, _fetch_plan_records())

        # Show selected plan info
        status_label = "DRAFT" if plan_source == "draft" else "Published"
        st.info(f"**{plan_title}** ({status_label})")

        # Query test cards for this test plan
        cards_response = api_client.post(
            f"{config.endpoints.doc_gen}/query-test-cards",
            data={
                "test_plan_id": selected_doc_id,
                "collection_name": "test_cards"
            },
            timeout=30
        )

        test_cards = cards_response.get("test_cards", [])
        total_count = cards_response.get("total_count", 0)
        if plan_record:
            test_cards = _filter_latest_cards(test_cards, plan_record["id"])

        # Deduplicate by test_id - keep most recent (by updated_at or created_at)
        seen_test_ids = {}
        for card in test_cards:
            test_id = card.get("test_id", "")
            if not test_id:
                # No test_id - include as-is
                seen_test_ids[card.get("document_id", "")] = card
                continue

            # Check if we've seen this test_id before
            existing = seen_test_ids.get(test_id)
            if existing:
                # Keep the more recent one (compare updated_at or document_id as fallback)
                existing_updated = existing.get("updated_at", existing.get("created_at", ""))
                card_updated = card.get("updated_at", card.get("created_at", ""))
                if card_updated > existing_updated:
                    seen_test_ids[test_id] = card
            else:
                seen_test_ids[test_id] = card

        test_cards = list(seen_test_ids.values())
        # Sort by test_id for consistent ordering
        test_cards.sort(key=lambda c: c.get("test_id", ""))
        total_count = len(test_cards)

        if not test_cards:
            st.info("No test cards found for this test plan. Generate test cards first in the Generate tab.")
            return

        st.success(f"Found {total_count} test cards")

        # Export section at top
        st.markdown("### Export Test Cards")
        export_col1, export_col2 = st.columns(2)

        with export_col1:
            if st.button("Export to DOCX", use_container_width=True, type="primary", key="editor_export_docx"):
                try:
                    import requests
                    export_response = requests.post(
                        f"{config.fastapi_url}/api/doc_gen/test-cards/export-docx",
                        json={
                            "test_plan_id": selected_doc_id,
                            "collection_name": "test_cards"
                        },
                        timeout=60
                    )

                    if export_response.status_code == 200:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"test_cards_{timestamp}.docx"
                        st.download_button(
                            label="Download DOCX",
                            data=export_response.content,
                            file_name=filename,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="editor_download_docx"
                        )
                    else:
                        st.error(f"Export failed: {export_response.text}")
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")

        with export_col2:
            if st.button("Export to Markdown", use_container_width=True, type="secondary", key="editor_export_md"):
                try:
                    import requests
                    export_response = requests.post(
                        f"{config.fastapi_url}/api/doc_gen/test-cards/export-markdown",
                        json={
                            "test_plan_id": selected_doc_id,
                            "collection_name": "test_cards"
                        },
                        timeout=60
                    )

                    if export_response.status_code == 200:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"test_cards_{timestamp}.md"
                        st.download_button(
                            label="Download Markdown",
                            data=export_response.content,
                            file_name=filename,
                            mime="text/markdown",
                            use_container_width=True,
                            key="editor_download_md"
                        )
                    else:
                        st.error(f"Export failed: {export_response.text}")
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")

        st.markdown("---")

        # Edit individual test card with WYSIWYG editor
        st.markdown("### Edit Test Card")

        card_options = {
            f"{card.get('test_id', 'N/A')} - {card.get('document_name', 'N/A')}": card
            for card in test_cards
        }

        selected_card_key = st.selectbox(
            "Select a test card to edit:",
            list(card_options.keys()),
            key="editor_selected_card"
        )

        if selected_card_key:
            selected_card = card_options[selected_card_key]

            # Store original values to detect changes
            original_values = {
                "test_title": selected_card.get("document_name", ""),
                "requirement_text": selected_card.get("requirement_text", ""),
                "procedures": selected_card.get("content", selected_card.get("content_preview", "")),
            }

            # Header with test info
            info_cols = st.columns([2, 2, 1])
            with info_cols[0]:
                st.caption(f"Test ID: {selected_card.get('test_id', 'N/A')}")
            with info_cols[1]:
                st.caption(f"Requirement: {selected_card.get('requirement_id', 'N/A')}")

            # Editable title
            edited_title = st.text_input(
                "Test Title",
                value=original_values["test_title"],
                key="editor_test_title",
                placeholder="Test Card Title"
            )

            # Parse markdown table to extract structured fields
            def parse_test_card_table(markdown_table):
                fields = {
                    "procedures": "",
                    "expected_results": "",
                    "acceptance_criteria": "",
                    "dependencies": ""
                }
                if not markdown_table or not markdown_table.strip():
                    return fields
                try:
                    lines = markdown_table.strip().split('\n')
                    if len(lines) >= 3:
                        data_row = lines[2] if len(lines) > 2 else ""
                        cells = [cell.strip() for cell in data_row.split('|')]
                        if len(cells) >= 7:
                            fields["procedures"] = cells[3] if len(cells) > 3 else ""
                            fields["expected_results"] = cells[4] if len(cells) > 4 else ""
                            fields["acceptance_criteria"] = cells[5] if len(cells) > 5 else ""
                            fields["dependencies"] = cells[6] if len(cells) > 6 else ""
                except Exception:
                    pass
                return fields

            parsed_fields = parse_test_card_table(original_values["procedures"])
            editor_key = f"editor_{selected_card.get('document_id', 'unknown')}"

            # Requirement (WYSIWYG)
            st.markdown('<div style="font-size: 0.85em; color: #666; margin-bottom: 4px;">Requirement Being Tested</div>', unsafe_allow_html=True)
            requirement_text = original_values["requirement_text"]
            requirement_html = _markdown_to_document_html(requirement_text) if requirement_text and not requirement_text.strip().startswith("<") else requirement_text

            edited_requirement_html = st_quill(
                value=requirement_html,
                html=True,
                toolbar=[['bold', 'italic', 'underline'], [{'list': 'ordered'}, {'list': 'bullet'}], ['clean']],
                key=f"quill_req_{editor_key}",
                placeholder="Enter the requirement being tested..."
            )

            # Test Procedures (WYSIWYG)
            st.markdown('<div style="font-size: 0.85em; color: #666; margin: 12px 0 4px 0;">Test Procedures & Steps</div>', unsafe_allow_html=True)
            procedures_text = parsed_fields.get("procedures", "")
            procedures_html = _markdown_to_document_html(procedures_text) if procedures_text and not procedures_text.strip().startswith("<") else procedures_text

            edited_procedures_html = st_quill(
                value=procedures_html,
                html=True,
                toolbar=[[{'header': [1, 2, 3, False]}], ['bold', 'italic', 'underline'], [{'list': 'ordered'}, {'list': 'bullet'}], [{'indent': '-1'}, {'indent': '+1'}], ['clean']],
                key=f"quill_proc_{editor_key}",
                placeholder="Enter test procedures and steps..."
            )

            # Expected Results (WYSIWYG)
            st.markdown('<div style="font-size: 0.85em; color: #666; margin: 12px 0 4px 0;">Expected Results</div>', unsafe_allow_html=True)
            expected_text = parsed_fields.get("expected_results", "")
            expected_html = _markdown_to_document_html(expected_text) if expected_text and not expected_text.strip().startswith("<") else expected_text

            edited_expected_html = st_quill(
                value=expected_html,
                html=True,
                toolbar=[['bold', 'italic'], [{'list': 'ordered'}, {'list': 'bullet'}], ['clean']],
                key=f"quill_expected_{editor_key}",
                placeholder="Enter expected results..."
            )

            # Acceptance Criteria and Dependencies
            col1, col2 = st.columns(2)
            with col1:
                st.markdown('<div style="font-size: 0.85em; color: #666; margin-bottom: 4px;">Acceptance Criteria</div>', unsafe_allow_html=True)
                edited_acceptance_criteria = st.text_area(
                    "Acceptance Criteria",
                    value=parsed_fields["acceptance_criteria"],
                    height=80,
                    key=f"editor_acceptance_{editor_key}",
                    label_visibility="collapsed"
                )

            with col2:
                st.markdown('<div style="font-size: 0.85em; color: #666; margin-bottom: 4px;">Dependencies</div>', unsafe_allow_html=True)
                edited_dependencies = st.text_area(
                    "Dependencies",
                    value=parsed_fields["dependencies"],
                    height=80,
                    key=f"editor_dependencies_{editor_key}",
                    label_visibility="collapsed"
                )

            # Save button
            st.markdown("")
            if st.button("Save Changes", type="primary", use_container_width=True, key=f"save_{editor_key}"):
                edited_requirement = edited_requirement_html or requirement_text
                edited_procedures_text = edited_procedures_html or procedures_text
                edited_expected_results = edited_expected_html or expected_text

                procedures_changed = (
                    edited_procedures_text != parsed_fields["procedures"] or
                    edited_expected_results != parsed_fields["expected_results"] or
                    edited_acceptance_criteria != parsed_fields["acceptance_criteria"] or
                    edited_dependencies != parsed_fields["dependencies"]
                )

                changes_detected = (
                    edited_title != original_values["test_title"] or
                    edited_requirement != original_values["requirement_text"] or
                    procedures_changed
                )

                if changes_detected:
                    try:
                        update_payload = {
                            "document_name": edited_title,
                            "requirement_text": edited_requirement,
                        }
                        updated_content = selected_card.get("content") or selected_card.get("content_preview", "")

                        if procedures_changed:
                            test_id = selected_card.get("test_id", "")
                            reconstructed_table = f"""| Test ID | Test Title | Procedures | Expected Results | Acceptance Criteria | Dependencies | Executed | Pass | Fail | Notes |
|---------|------------|------------|------------------|---------------------|--------------|----------|------|------|-------|
| {test_id} | {edited_title} | {edited_procedures_text} | {edited_expected_results} | {edited_acceptance_criteria} | {edited_dependencies} | (not_executed) | (False) | (False) |  |"""
                            updated_content = reconstructed_table

                        _create_test_card_version(
                            card=selected_card,
                            updates=update_payload,
                            updated_content=updated_content,
                            plan_key=plan_key,
                            plan_title=plan_title,
                            plan_doc_id=selected_doc_id
                        )
                        st.success("Test card updated successfully! New version created.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to save changes: {str(e)}")
                else:
                    st.info("No changes detected")

    except Exception as e:
        st.error(f"Failed to load test cards: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


def render_test_card_executor():
    """Execute and track test cards - Step 3: Final step for tracking test execution"""
    st.subheader("Execute Test Cards")
    st.caption("Track test execution status, pass/fail results, and notes. Only PUBLISHED test cards can be executed.")

    try:
        # Fetch all test plans (any status - we filter on TEST CARD publish status, not test plan status)
        doc_ids, metadatas, metadata_map = _list_test_plans()

        if not doc_ids:
            st.info("No test plans found. Generate a test plan first.")
            return

        # Select test plan (any status - execution is based on test card publish status)
        plan_options = {}
        for doc_id, m in zip(doc_ids, metadatas):
            title = m.get('title', 'Untitled')
            status = m.get('_status', 'DRAFT')
            status_badge = "[DRAFT]" if status == "DRAFT" else "[Published]"
            label = f"{status_badge} {title} ({doc_id[:20]}...)"
            plan_options[label] = doc_id

        selected_plan = st.selectbox(
            "Select test plan:",
            list(plan_options.keys()),
            key="executor_test_plan"
        )

        if not selected_plan:
            return

        selected_doc_id = plan_options[selected_plan]
        selected_metadata = metadata_map.get(selected_doc_id, {})
        plan_key = selected_metadata.get("plan_key") or selected_doc_id
        plan_title = selected_metadata.get("title", "Untitled Plan")
        plan_source = selected_metadata.get("_source", "published")
        plan_record = _find_plan_record(plan_key, _fetch_plan_records())

        # Show selected plan info
        status_label = "DRAFT" if plan_source == "draft" else "Published"
        st.info(f"**{plan_title}** ({status_label})")

        # Query test cards for this test plan
        cards_response = api_client.post(
            f"{config.endpoints.doc_gen}/query-test-cards",
            data={
                "test_plan_id": selected_doc_id,
                "collection_name": "test_cards"
            },
            timeout=30
        )

        all_test_cards = cards_response.get("test_cards", [])
        if plan_record:
            all_test_cards = _filter_latest_cards(all_test_cards, plan_record["id"])

        # Deduplicate by test_id - keep most recent (by updated_at or created_at)
        seen_test_ids = {}
        for card in all_test_cards:
            test_id = card.get("test_id", "")
            if not test_id:
                seen_test_ids[card.get("document_id", "")] = card
                continue
            existing = seen_test_ids.get(test_id)
            if existing:
                existing_updated = existing.get("updated_at", existing.get("created_at", ""))
                card_updated = card.get("updated_at", card.get("created_at", ""))
                if card_updated > existing_updated:
                    seen_test_ids[test_id] = card
            else:
                seen_test_ids[test_id] = card
        all_test_cards = list(seen_test_ids.values())
        all_test_cards.sort(key=lambda c: c.get("test_id", ""))

        if not all_test_cards:
            st.info("No test cards found. Generate test cards in **Tab 1 (Generate)** first.")
            return

        # Filter to only PUBLISHED test cards for execution
        # Only published test cards can be executed - they must go through the full review workflow
        # Workflow: DRAFT → REVIEWED → PUBLISHED (only PUBLISHED cards are executable)
        test_cards = []
        draft_count = 0
        reviewed_count = 0
        for card in all_test_cards:
            # Check both top-level and nested metadata for review_status
            review_status = card.get("review_status")
            if not review_status and isinstance(card.get("metadata"), dict):
                review_status = card.get("metadata", {}).get("review_status")
            review_status = review_status or "DRAFT"

            if review_status == "PUBLISHED":
                test_cards.append(card)
            elif review_status == "REVIEWED":
                reviewed_count += 1
            else:
                draft_count += 1

        total_all_count = len(all_test_cards)
        total_count = len(test_cards)

        if not test_cards:
            pending_msg = []
            if draft_count > 0:
                pending_msg.append(f"{draft_count} DRAFT")
            if reviewed_count > 0:
                pending_msg.append(f"{reviewed_count} REVIEWED")

            st.warning(
                f"No published test cards found. "
                f"({', '.join(pending_msg)} card(s) pending). "
                f"Go to **Tab 2 (Edit & Review)** and click **Publish** to make test cards available for execution."
            )

            # Debug: Show what review_status values we're seeing
            with st.expander("Debug: Test Card Review Status", expanded=False):
                st.markdown(f"**Total cards found:** {len(all_test_cards)}")
                st.markdown(f"**Draft:** {draft_count} | **Reviewed:** {reviewed_count} | **Published:** {len(test_cards)}")

                if all_test_cards:
                    st.markdown("**Sample card data (first 3):**")
                    for i, card in enumerate(all_test_cards[:3]):
                        top_level_status = card.get("review_status", "NOT_SET")
                        nested_status = card.get("metadata", {}).get("review_status", "NOT_SET") if isinstance(card.get("metadata"), dict) else "NO_METADATA"
                        st.code(f"Card {i+1}: top-level={top_level_status}, nested={nested_status}, title={card.get('document_name', 'N/A')[:30]}")

            return

        # Show info about filtered cards
        pending_total = draft_count + reviewed_count
        if pending_total > 0:
            st.info(f"Showing {total_count} published test cards ready for execution. {pending_total} card(s) pending (Draft: {draft_count}, Reviewed: {reviewed_count}).")

        # Summary metrics
        executed = sum(1 for c in test_cards if c.get("execution_status") not in [None, "not_executed", ""])
        passed = sum(1 for c in test_cards if str(c.get("passed", "")).lower() == "true")
        failed = sum(1 for c in test_cards if str(c.get("failed", "")).lower() == "true")

        metric_cols = st.columns(5)
        with metric_cols[0]:
            st.metric("Published", total_count, help="Only published test cards can be executed")
        with metric_cols[1]:
            st.metric("Executed", executed)
        with metric_cols[2]:
            st.metric("Passed", passed)
        with metric_cols[3]:
            st.metric("Failed", failed)
        with metric_cols[4]:
            completion_rate = (executed / total_count * 100) if total_count > 0 else 0
            st.metric("Progress", f"{completion_rate:.0f}%")

        st.markdown("---")

        # Execution tracking table (simplified - execution fields only)
        cards_data = []
        card_id_map = {}
        cards_by_id = {card.get("document_id"): card for card in test_cards}

        for idx, card in enumerate(test_cards):
            card_id_map[idx] = card.get("document_id", "")
            cards_data.append({
                "Test ID": card.get("test_id", "N/A"),
                "Test Title": card.get("document_name", "N/A")[:40] + "..." if len(card.get("document_name", "")) > 40 else card.get("document_name", "N/A"),
                "Review": card.get("review_status", "REVIEWED"),
                "Status": card.get("execution_status", "not_executed"),
                "Pass": str(card.get("passed", "false")).lower() == "true",
                "Fail": str(card.get("failed", "false")).lower() == "true",
                "Notes": card.get("notes", "")
            })

        df = pd.DataFrame(cards_data)

        # Configure columns - execution tracking only
        column_config = {
            "Test ID": st.column_config.TextColumn("Test ID", disabled=True, width="small"),
            "Test Title": st.column_config.TextColumn("Test Title", disabled=True, width="medium"),
            "Review": st.column_config.TextColumn("Review", disabled=True, width="small", help="Review status - REVIEWED or PUBLISHED"),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["not_executed", "in_progress", "completed", "failed"],
                required=True
            ),
            "Pass": st.column_config.CheckboxColumn("Pass"),
            "Fail": st.column_config.CheckboxColumn("Fail"),
            "Notes": st.column_config.TextColumn("Notes", width="large")
        }

        edited_df = st.data_editor(
            df,
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            key="execution_tracker"
        )

        # Save execution results
        if st.button("Save Execution Results", type="primary", use_container_width=True):
            updated_count = 0
            errors = []
            for idx in range(len(df)):
                if idx < len(edited_df):
                    original = df.iloc[idx]
                    edited = edited_df.iloc[idx]

                    # Only check execution-related fields
                    execution_changed = (
                        original["Status"] != edited["Status"] or
                        original["Pass"] != edited["Pass"] or
                        original["Fail"] != edited["Fail"] or
                        original["Notes"] != edited["Notes"]
                    )

                    if execution_changed:
                        document_id = card_id_map.get(idx)
                        if document_id:
                            card = cards_by_id.get(document_id, {})
                            updates = {
                                "execution_status": str(edited["Status"]),
                                "passed": str(edited["Pass"]).lower(),
                                "failed": str(edited["Fail"]).lower(),
                                "notes": str(edited["Notes"]),
                                "executed_at": datetime.now(timezone.utc).isoformat()
                            }
                            updated_content = card.get("content") or card.get("content_preview", "")
                            try:
                                _create_test_card_version(
                                    card=card,
                                    updates=updates,
                                    updated_content=updated_content,
                                    plan_key=plan_key,
                                    plan_title=plan_title,
                                    plan_doc_id=selected_doc_id
                                )
                                updated_count += 1
                            except Exception as e:
                                errors.append(f"{document_id[:8]}...: {e}")

            if updated_count and not errors:
                st.success(f"Saved execution results for {updated_count} test cards")
                st.rerun()
            elif errors:
                st.error("Some updates failed: " + "; ".join(errors))
            else:
                st.info("No changes detected")

    except Exception as e:
        st.error(f"Failed to load test cards: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
