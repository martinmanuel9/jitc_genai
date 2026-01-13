"""
JSON Test Plan Side-by-Side Editor

Displays the original source document on the left and the editable test plan on the right.
This makes it easier for users to compare and align their edits with the source material.

Note: JSON is used internally for LLM processing. Users see and edit clean, formatted documents.
"""

from __future__ import annotations

import json
import uuid
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

import streamlit as st
from streamlit_quill import st_quill

from app_lib.api.client import api_client
from config.settings import config
from components.review_workflow import (
    render_status_badge,
    render_status_actions,
    render_progress_tracker,
    ReviewStatus,
    STATUS_CONFIG
)
from components.shared_styles import (
    get_sidebyside_css,
    PANEL_HEIGHT,
    TEXT_AREA_STANDARD,
    get_section_progress_html
)


def _markdown_to_html(text: str) -> str:
    """Convert markdown to clean HTML for display (user-friendly)"""
    if not text:
        return ""

    # Convert markdown to HTML
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)  # Bold
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)  # Italic
    text = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)  # H3
    text = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)  # H2
    text = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)  # H1
    text = re.sub(r'^\* (.*?)$', r'<li>\1</li>', text, flags=re.MULTILINE)  # List items
    text = re.sub(r'^\d+\. (.*?)$', r'<li>\1</li>', text, flags=re.MULTILINE)  # Numbered lists

    # Wrap consecutive <li> items in <ul>
    text = re.sub(r'(<li>.*?</li>\s*)+', r'<ul>\g<0></ul>', text, flags=re.DOTALL)

    # Convert newlines to <br> for paragraphs
    text = text.replace('\n\n', '</p><p>')
    text = f'<p>{text}</p>'

    return text


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
            # Apply inline formatting
            item_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', item_text)
            item_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', item_text)
            if not in_list or list_type != 'ol':
                if in_list:
                    html_parts.append(f'</{list_type}>')
                html_parts.append('<ol style="margin: 8px 0; padding-left: 24px; color: #333;">')
                in_list = True
                list_type = 'ol'
            html_parts.append(f'<li style="margin: 4px 0; line-height: 1.5; color: #333;">{item_text}</li>')

        # Bullet list (* item or - item)
        elif stripped.startswith('* ') or stripped.startswith('- '):
            item_text = stripped[2:]
            # Apply inline formatting
            item_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', item_text)
            item_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', item_text)
            if not in_list or list_type != 'ul':
                if in_list:
                    html_parts.append(f'</{list_type}>')
                html_parts.append('<ul style="margin: 8px 0; padding-left: 24px; color: #333;">')
                in_list = True
                list_type = 'ul'
            html_parts.append(f'<li style="margin: 4px 0; line-height: 1.5; color: #333;">{item_text}</li>')

        # Regular paragraph
        else:
            if in_list:
                html_parts.append(f'</{list_type}>')
                in_list = False
            # Apply inline formatting
            para_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', stripped)
            para_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', para_text)
            html_parts.append(f'<p style="margin: 8px 0; line-height: 1.6; text-align: justify; color: #333;">{para_text}</p>')

    if in_list:
        html_parts.append(f'</{list_type}>')

    return ''.join(html_parts)


def _render_formatted_text(text: str, as_html: bool = True):
    """Render text in a user-friendly way (no markdown syntax visible)"""
    if not text:
        st.info("No content")
        return

    if as_html:
        # Convert markdown to HTML and render
        html = _markdown_to_html(text)
        st.markdown(html, unsafe_allow_html=True)
    else:
        # Just display as plain text with newlines
        st.text(text)


def _load_source_page_content(collection_name: str, document_id: str, page_number: int) -> Optional[str]:
    """
    Load source content for a specific page using the new API endpoint.

    Args:
        collection_name: ChromaDB collection name
        document_id: Document ID
        page_number: Page number (int)

    Returns:
        HTML-formatted content styled like a document
    """
    try:
        response = api_client.get(
            f"{config.fastapi_url}/api/vectordb/documents/page-content",
            params={
                "collection_name": collection_name,
                "document_id": document_id,
                "page_number": page_number
            },
            timeout=60
        )

        if not response:
            return None

        # API returns chunks grouped by heading
        headings = response.get("headings", [])

        if not headings:
            return "<p style='color: #888;'>No content found for this page</p>"

        # Build HTML with document-like styling (smaller headings)
        content_parts = []
        for heading in headings:
            level = heading.get("heading_level", 1)
            heading_text = heading.get("heading_text", "")
            body_text = heading.get("body_text", "")

            # Map heading levels to smaller font sizes
            font_sizes = {1: "1.1em", 2: "1.0em", 3: "0.95em", 4: "0.9em", 5: "0.85em", 6: "0.8em"}
            font_size = font_sizes.get(level, "0.9em")

            # Add heading with smaller, document-like styling
            content_parts.append(
                f'<div style="font-size: {font_size}; font-weight: 600; color: #333; '
                f'margin-top: 12px; margin-bottom: 6px; border-bottom: 1px solid #e0e0e0; '
                f'padding-bottom: 4px;">{heading_text}</div>'
            )

            # Add body text with document-like paragraph styling
            if body_text:
                # Clean up and format body text
                paragraphs = body_text.strip().split('\n\n')
                for para in paragraphs:
                    if para.strip():
                        content_parts.append(
                            f'<p style="font-size: 0.85em; line-height: 1.5; color: #444; '
                            f'margin: 6px 0; text-align: justify;">{para.strip()}</p>'
                        )

        return "".join(content_parts)

    except Exception as e:
        st.error(f"Failed to load page content: {e}")
        return None


def _load_source_document_sections(collection_name: str, document_id: str = None) -> Dict[str, str]:
    """
    Load and reconstruct source document sections (LEGACY - for backward compatibility)

    Args:
        collection_name: ChromaDB collection name
        document_id: Optional specific document ID

    Returns:
        Dictionary mapping section titles to content
    """
    try:
        if document_id:
            # Try to reconstruct specific document
            response = api_client.get(
                f"{config.fastapi_url}/api/vectordb/documents/reconstruct/{document_id}",
                params={"collection_name": collection_name},
                timeout=60
            )

            if response and "sections" in response:
                sections = {}
                for section in response["sections"]:
                    title = section.get("heading", section.get("title", f"Section {len(sections) + 1}"))
                    content = section.get("text", "")
                    sections[title] = content
                return sections

        # Fallback: Get all documents and group by section metadata
        response = api_client.get(
            f"{config.fastapi_url}/api/vectordb/documents",
            params={"collection_name": collection_name},
            timeout=60
        )

        if not response:
            return {}

        metadatas = response.get("metadatas", [])
        documents = response.get("documents", [])

        sections = {}
        for idx, meta in enumerate(metadatas):
            if meta and idx < len(documents):
                section_title = (
                    meta.get("section_title") or
                    meta.get("heading") or
                    meta.get("title") or
                    f"Section {meta.get('page_number', idx + 1)}"
                )

                if section_title not in sections:
                    sections[section_title] = ""
                sections[section_title] += documents[idx] + "\n\n"

        return sections

    except Exception as e:
        st.error(f"Failed to load source document: {e}")
        return {}


def _load_test_plan_from_version(plan_id: int, version_id: int) -> Optional[Dict[str, Any]]:
    """
    Load test plan content from a specific version.

    Loads from ChromaDB collection "test_plan_drafts" where:
    - Full test plan is stored with document_id matching version.document_id
    - Individual sections are stored with document_id_section_{idx} for editing

    Args:
        plan_id: Test plan ID
        version_id: Version ID

    Returns:
        Complete test plan JSON structure
    """
    try:
        # Get version info
        versions_response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions"
        )

        version = None
        for v in versions_response.get("versions", []):
            if v["id"] == version_id:
                version = v
                break

        if not version:
            st.warning("Version not found")
            return None

        # Get test plan to find collection
        plan_response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}"
        )
        primary_collection = plan_response.get("collection_name", "test_plan_drafts")

        # Try multiple collections - document might be in drafts or generated
        collections_to_try = [primary_collection]
        if primary_collection != "test_plan_drafts":
            collections_to_try.append("test_plan_drafts")
        if primary_collection != "generated_test_plan":
            collections_to_try.append("generated_test_plan")

        full_doc_id = version["document_id"]
        collection_name = primary_collection  # Track which collection we found it in

        # Search for the document in each collection
        ids = []
        documents = []
        metadatas = []

        for try_collection in collections_to_try:
            try:
                doc_response = api_client.get(
                    f"{config.fastapi_url}/api/vectordb/documents",
                    params={"collection_name": try_collection},
                    show_errors=False
                )
                if doc_response:
                    try_ids = doc_response.get("ids", [])
                    if full_doc_id in try_ids:
                        # Found it in this collection
                        ids = try_ids
                        documents = doc_response.get("documents", [])
                        metadatas = doc_response.get("metadatas", [])
                        collection_name = try_collection
                        break
            except Exception:
                continue

        # If not found by exact ID, load from primary collection for section reconstruction
        if not ids:
            try:
                doc_response = api_client.get(
                    f"{config.fastapi_url}/api/vectordb/documents",
                    params={"collection_name": primary_collection},
                    show_errors=False
                )
                if doc_response:
                    ids = doc_response.get("ids", [])
                    documents = doc_response.get("documents", [])
                    metadatas = doc_response.get("metadatas", [])
            except Exception:
                pass

        for idx, doc_id in enumerate(ids):
            if doc_id == full_doc_id:
                content = documents[idx] if idx < len(documents) else ""

                if not content or not content.strip():
                    st.error(f"Document {version['document_id']} is empty")
                    return None

                if isinstance(content, str):
                    # Try to parse as JSON
                    try:
                        parsed = json.loads(content)
                        # Verify structure
                        if not isinstance(parsed, dict):
                            st.error(f"Document content is not a JSON object")
                            with st.expander("Show raw content"):
                                st.code(content[:1000], language="json")
                            return None

                        # Successfully loaded full test plan
                        return parsed
                    except json.JSONDecodeError as e:
                        st.error(f"Invalid JSON in document {version['document_id']}: {str(e)}")
                        with st.expander("Show raw content (first 1000 chars)"):
                            st.code(content[:1000])
                        return None
                else:
                    # Already parsed
                    return content if isinstance(content, dict) else None

        # If we didn't find the full document, try to reconstruct from individual sections
        st.info(f"Full document not found, attempting to reconstruct from section documents...")

        section_docs = []
        for idx, doc_id in enumerate(ids):
            meta = metadatas[idx] if idx < len(metadatas) else {}

            # Check if this is a section document for our version
            if (meta.get("version_id") == str(version_id) and
                meta.get("type") == "test_plan_section"):

                section_content = documents[idx] if idx < len(documents) else ""
                if section_content:
                    try:
                        section_json = json.loads(section_content)
                        section_docs.append((int(meta.get("section_index", 0)), section_json))
                    except json.JSONDecodeError:
                        pass

        if section_docs:
            # Sort by section index
            section_docs.sort(key=lambda x: x[0])
            sections = [s[1] for s in section_docs]

            # Reconstruct test plan structure
            return {
                "test_plan": {
                    "metadata": {
                        "title": plan_response.get("title", "Test Plan"),
                        "plan_id": plan_id,
                        "version_id": version_id,
                        "version_number": version.get("version_number", 1),
                        "status": version.get("status", "draft"),
                        "total_sections": len(sections)
                    },
                    "sections": sections
                }
            }

        st.warning(f"Document {version['document_id']} not found in collection {collection_name}")
        return None

    except Exception as e:
        st.error(f"Failed to load test plan: {e}")
        import traceback
        with st.expander("Show error details"):
            st.code(traceback.format_exc())
        return None


def render_sidebyside_editor():
    """Render side-by-side editor with source document and test plan - Simplified Layout"""

    # =========================================================================
    # Load plans from both versioning API AND ChromaDB drafts
    # =========================================================================
    all_plans = []
    seen_plan_keys = set()
    seen_plan_ids = set()
    seen_titles = set()

    # Load versioned plans with deduplication
    versioned_plans = []
    try:
        plans_response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-plans",
            timeout=None,
            show_errors=False
        )
        raw_versioned = plans_response.get("plans", []) if plans_response else []
        for plan in raw_versioned:
            plan_key = plan.get("plan_key", "")
            plan_id = plan.get("id")
            title = plan.get("title", "").strip().lower()

            # Skip duplicates
            if plan_key and plan_key in seen_plan_keys:
                continue
            if plan_id and plan_id in seen_plan_ids:
                continue
            if title and title in seen_titles:
                continue

            # Track seen values
            if plan_key:
                seen_plan_keys.add(plan_key)
            if plan_id:
                seen_plan_ids.add(plan_id)
            if title:
                seen_titles.add(title)

            plan["_source"] = "versioned"
            # Status is on version, not plan - default to DRAFT (all new plans start as draft)
            plan["_status"] = "DRAFT"
            versioned_plans.append(plan)
            all_plans.append(plan)
    except Exception:
        # Silently handle - no versioned plans yet is expected
        pass

    # Load drafts from ChromaDB (collection may not exist yet)
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

            for idx, doc_id in enumerate(draft_ids):
                meta = draft_metas[idx] if idx < len(draft_metas) else {}
                # ONLY include full test plan documents - sections have type="test_plan_section"
                if meta.get("type") == "test_plan_full":
                    plan_key = meta.get("plan_key") or doc_id
                    plan_id = str(meta.get("plan_id", ""))
                    title = meta.get("title", "").strip().lower()

                    # Skip if already in versioned plans (match by plan_key, plan_id, or title)
                    if plan_key and plan_key in seen_plan_keys:
                        continue
                    if plan_id and plan_id in seen_plan_ids:
                        continue
                    if title and title in seen_titles:
                        continue

                    # Track seen values
                    if plan_key:
                        seen_plan_keys.add(plan_key)
                    if plan_id:
                        seen_plan_ids.add(plan_id)
                    if title:
                        seen_titles.add(title)

                    # Create a plan-like object for drafts
                    draft_plan = {
                        "id": None,  # No versioning ID
                        "plan_key": plan_key,
                        "title": meta.get("title", "Untitled Draft"),
                        "document_id": doc_id,
                        "_source": "draft",
                        "_status": "DRAFT",
                        "_metadata": meta
                    }
                    all_plans.append(draft_plan)
    except Exception:
        # Silently handle - collection may not exist yet
        pass

    if not all_plans:
        st.info("No test plans available. Generate a test plan first using the JSON Test Plan Generator.")
        return

    # Header row with title, plan selector, version, and settings
    col_title, col_plan, col_version, col_settings = st.columns([2, 3, 2, 1])

    with col_title:
        st.markdown("##### Select Test Plan")

    with col_plan:
        selected_plan = st.selectbox(
            "Test Plan",
            options=all_plans,
            format_func=lambda p: f"[{p.get('_status', 'Unknown')}] {p.get('title', 'Untitled')}",
            key="sidebyside_plan_selector",
            label_visibility="collapsed"
        )

    if not selected_plan:
        return

    is_draft = selected_plan.get("_source") == "draft"
    plan_id = selected_plan.get("id")

    # For drafts, we don't have versions - load directly
    if is_draft:
        with col_version:
            st.markdown("**Draft** (not versioned)")

        with col_settings:
            with st.popover("⚙️"):
                st.caption("Draft plans are not yet versioned")

        # Load draft content directly from ChromaDB
        document_id = selected_plan.get("document_id")
        version_id = None
        version_status = "draft"

        # Fetch draft content
        try:
            draft_docs = api_client.get(
                f"{config.fastapi_url}/api/vectordb/documents",
                params={"collection_name": "test_plan_drafts"},
                timeout=None
            )
            test_plan_data = None
            for idx, doc_id in enumerate(draft_docs.get("ids", [])):
                if doc_id == document_id:
                    content = draft_docs.get("documents", [])[idx] if idx < len(draft_docs.get("documents", [])) else None
                    if content:
                        try:
                            test_plan_data = json.loads(content) if isinstance(content, str) else content
                        except:
                            test_plan_data = {"test_plan": {"sections": []}}
                    break
        except Exception as e:
            st.error(f"Failed to load draft: {e}")
            return

    else:
        # Load versions for versioned plans
        versions_response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions"
        )
        versions = versions_response.get("versions", [])

        if not versions:
            st.info("No versions available for this test plan")
            return

        with col_version:
            if len(versions) == 1:
                selected_version = versions[0]
                status_text = selected_version.get('status', 'draft')
                st.markdown(f"**v{selected_version['version_number']}** ({status_text})")
            else:
                selected_version = st.selectbox(
                    "Version",
                    options=versions,
                    format_func=lambda v: f"v{v['version_number']} ({v.get('status', 'draft')})",
                    key="sidebyside_version_selector",
                    label_visibility="collapsed"
                )

        with col_settings:
            # Settings popover - only for danger zone actions
            with st.popover("⚙️"):
                st.markdown("**Danger Zone:**")

                if st.button("🗑️ Delete Version", key="delete_version_btn"):
                    try:
                        result = api_client.delete(
                            f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions/{selected_version['id']}"
                        )
                        st.success("Deleted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

                if st.button("🗑️ Delete Plan", key="delete_plan_btn"):
                    try:
                        result = api_client.delete(
                            f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}"
                        )
                        st.success("Deleted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

        # Map old status names to new unified statuses
        raw_status = selected_version.get("status", "draft").upper()
        if raw_status == "FINAL":
            current_status = "REVIEWED"
        elif raw_status == "PUBLISHED":
            current_status = "PUBLISHED"
        else:
            current_status = "DRAFT"

        if not selected_version:
            return

        version_id = selected_version["id"]
        version_status = selected_version.get("status", "draft")

        # Load test plan content for versioned plans
        test_plan_data = _load_test_plan_from_version(plan_id, version_id)

    if not test_plan_data:
        st.error("Failed to load test plan content")
        return

    if "test_plan" not in test_plan_data:
        st.error("Invalid test plan structure. Please regenerate.")
        return

    test_plan = test_plan_data.get("test_plan", {})
    sections = test_plan.get("sections", [])

    if not isinstance(sections, list) or not sections:
        st.info("No sections in this test plan")
        return

    # =========================================================================
    # REVIEW PROGRESS & STATUS (Inline - Consistent with Test Card Editor)
    # =========================================================================

    # Progress metrics row (section-level review tracking)
    total_sections = len(sections)
    reviewed_sections = sum(1 for s in sections if s.get("reviewed", False))
    review_progress = reviewed_sections / total_sections if total_sections > 0 else 0

    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric("Sections", total_sections, help="Total sections in test plan")
    with metric_cols[1]:
        st.metric("Reviewed", reviewed_sections, help="Sections marked as reviewed")
    with metric_cols[2]:
        remaining = total_sections - reviewed_sections
        st.metric("Remaining", remaining, help="Sections pending review")
    with metric_cols[3]:
        pct = int(review_progress * 100)
        st.metric("Progress", f"{pct}%", help="Section review completion")

    # Progress bar
    if total_sections > 0:
        if review_progress == 0:
            progress_text = "No sections reviewed yet"
        elif review_progress < 1.0:
            progress_text = f"{reviewed_sections}/{total_sections} sections reviewed"
        else:
            progress_text = "All sections reviewed!"
        st.progress(review_progress, text=progress_text)

    # Status badge and action buttons row (only for versioned plans)
    if not is_draft:
        st.markdown("---")
        st.markdown("**Test Plan Status:**")

        status_row = st.columns([1, 1, 1, 1])

        with status_row[0]:
            render_status_badge(current_status, size="normal")

        # Define status change handler for test plans
        def handle_plan_status_change(new_status: str) -> bool:
            try:
                api_status = new_status.lower()
                if new_status == "REVIEWED":
                    api_status = "final"
                result = api_client.patch(
                    f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions/{version_id}/status",
                    data={"status": api_status}
                )
                return True
            except Exception as e:
                st.error(f"Failed to update status: {e}")
                return False

        with status_row[1]:
            if st.button(
                "Reviewed",
                key="review_plan_btn",
                disabled=current_status != "DRAFT",
                use_container_width=True,
                help="Mark this test plan as reviewed"
            ):
                if handle_plan_status_change("REVIEWED"):
                    st.success("Marked as Reviewed!")
                    st.rerun()

        with status_row[2]:
            if st.button(
                "Publish",
                key="publish_plan_btn",
                disabled=current_status == "PUBLISHED",
                use_container_width=True,
                help="Publish this test plan"
            ):
                if handle_plan_status_change("PUBLISHED"):
                    st.success("Published!")
                    st.rerun()

        with status_row[3]:
            # Can only reset REVIEWED to DRAFT (not PUBLISHED - that's final)
            can_reset = current_status == "REVIEWED"
            if st.button(
                "Draft",
                key="reset_plan_btn",
                disabled=not can_reset,
                use_container_width=True,
                help="Reset reviewed version to draft (published versions are final)"
            ):
                if handle_plan_status_change("DRAFT"):
                    st.success("Reset to Draft!")
                    st.rerun()

    # =========================================================================
    # EXTRACT SOURCE COLLECTION (auto-detect from test plan metadata)
    # =========================================================================
    source_collection = None
    metadata = test_plan.get("metadata", {})
    source_collections_str = metadata.get("source_collections")
    if source_collections_str:
        try:
            source_collections = json.loads(source_collections_str) if isinstance(source_collections_str, str) else source_collections_str
            if source_collections and len(source_collections) > 0:
                source_collection = source_collections[0]
        except:
            pass

    # Fallback: fetch from ChromaDB metadata
    if not source_collection:
        try:
            plan_collection = selected_plan.get("collection_name", "test_plan_drafts")
            chromadb_docs = api_client.get(
                f"{config.fastapi_url}/api/vectordb/documents",
                params={"collection_name": plan_collection},
                timeout=10,
                show_errors=False
            )
            for meta in chromadb_docs.get("metadatas", []):
                if meta.get("type") == "test_plan_full" and meta.get("source_collections"):
                    try:
                        sc = json.loads(meta["source_collections"]) if isinstance(meta["source_collections"], str) else meta["source_collections"]
                        if sc and len(sc) > 0:
                            source_collection = sc[0]
                            break
                    except:
                        pass
        except:
            pass

    # Final fallback: try to find collection containing the source document
    if not source_collection and sections:
        # Get source document ID from sections
        source_doc_id = None
        for s in sections:
            if s.get("source_document"):
                source_doc_id = s.get("source_document")
                break

        if source_doc_id:
            try:
                # Get all available collections
                collections_response = api_client.get(
                    f"{config.fastapi_url}/api/vectordb/collections",
                    timeout=10,
                    show_errors=False
                )
                available_collections = collections_response.get("collections", [])

                # Exclude output collections - look in source collections only
                output_collections = {"test_plan_drafts", "generated_test_plan", "json_test_plans", "generated_documents", "test_cards"}
                source_collections_to_check = [c for c in available_collections if c not in output_collections]

                # Check each collection for the source document
                for coll in source_collections_to_check:
                    try:
                        docs_response = api_client.get(
                            f"{config.fastapi_url}/api/vectordb/documents",
                            params={"collection_name": coll},
                            timeout=10,
                            show_errors=False
                        )
                        doc_ids = docs_response.get("ids", [])
                        doc_metadatas = docs_response.get("metadatas", [])

                        # Check if source document exists in this collection
                        for i, doc_id in enumerate(doc_ids):
                            meta = doc_metadatas[i] if i < len(doc_metadatas) else {}
                            doc_name = meta.get("document_name", "")

                            if source_doc_id == doc_id or source_doc_id == doc_name or source_doc_id in doc_id or doc_id in source_doc_id:
                                source_collection = coll
                                break

                        if source_collection:
                            break
                    except:
                        continue
            except:
                pass

    # Note: source_collection may still be None if not found - this is handled gracefully below

    # =========================================================================
    # EXTRACT SOURCE DOCUMENTS (unique documents from sections)
    # =========================================================================
    source_documents = sorted(set(s.get("source_document") for s in sections if s.get("source_document")))
    doc_state_key = f"doc_{plan_id}_{version_id}"

    # Initialize source document selection
    if doc_state_key not in st.session_state or st.session_state[doc_state_key] not in source_documents:
        st.session_state[doc_state_key] = source_documents[0] if source_documents else None

    selected_doc = st.session_state[doc_state_key]

    # Filter sections by selected source document
    if selected_doc:
        doc_sections = [s for s in sections if s.get("source_document") == selected_doc]
    else:
        doc_sections = sections

    # Extract unique page numbers for selected document
    pages = sorted(set(s.get("source_page") for s in doc_sections if s.get("source_page") is not None))

    # Use plan-specific session state key for page selection
    page_state_key = f"page_{plan_id}_{version_id}"

    # =========================================================================
    # MAIN LAYOUT: Left (Source + Page Nav) | Right (Section Dropdown + Editor)
    # =========================================================================

    # Apply shared CSS for consistent side-by-side layout
    st.markdown(get_sidebyside_css(), unsafe_allow_html=True)

    # Create two main columns
    left_col, right_col = st.columns([1, 1])

    # =========================================================================
    # LEFT COLUMN: Source Document Selector + Page Navigation + Content
    # =========================================================================
    with left_col:
        # Source Document Selector (if multiple documents)
        if len(source_documents) > 1:
            selected_doc = st.selectbox(
                "Source Document",
                options=source_documents,
                index=source_documents.index(selected_doc) if selected_doc in source_documents else 0,
                key=f"doc_select_{doc_state_key}",
                format_func=lambda d: d[:50] + "..." if len(d) > 50 else d
            )
            if selected_doc != st.session_state[doc_state_key]:
                st.session_state[doc_state_key] = selected_doc
                # Reset page when document changes
                if page_state_key in st.session_state:
                    del st.session_state[page_state_key]
                st.rerun()
        elif source_documents:
            st.caption(f"Document: {source_documents[0][:40]}...")

        # Page selector (simple dropdown, no buttons)
        if pages:
            total_pages = len(pages)

            # Initialize page state
            if page_state_key not in st.session_state or st.session_state[page_state_key] not in pages:
                st.session_state[page_state_key] = pages[0]

            current_page = st.session_state[page_state_key]
            current_idx = pages.index(current_page) if current_page in pages else 0

            # Simple page dropdown
            selected_page = st.selectbox(
                "Page",
                options=pages,
                index=current_idx,
                format_func=lambda p: f"Page {p} of {total_pages}",
                key=f"page_select_{page_state_key}"
            )

            # Update session state if changed
            if selected_page != st.session_state[page_state_key]:
                st.session_state[page_state_key] = selected_page
                st.rerun()
        else:
            st.caption("No page information available")
            selected_page = None

        # Filter sections by selected page AND document
        if selected_page:
            page_sections = [s for s in doc_sections if s.get("source_page") == selected_page]
        else:
            page_sections = doc_sections

        # Document-like container for source content
        source_content = None
        doc_id = None

        # Get document ID from sections
        if page_sections:
            doc_id = page_sections[0].get("source_document", "")
        elif doc_sections:
            doc_id = doc_sections[0].get("source_document", "")
        elif sections:
            doc_id = sections[0].get("source_document", "")

        if doc_id and source_collection:
            # Try loading by page if available
            if selected_page:
                source_content = _load_source_page_content(
                    collection_name=source_collection,
                    document_id=doc_id,
                    page_number=selected_page
                )

            # Fallback: load full document content if page-specific loading failed
            if not source_content:
                try:
                    # Try to get document content directly
                    doc_response = api_client.get(
                        f"{config.fastapi_url}/api/vectordb/documents",
                        params={"collection_name": source_collection},
                        timeout=30,
                        show_errors=False
                    )
                    if doc_response:
                        ids = doc_response.get("ids", [])
                        documents = doc_response.get("documents", [])
                        metadatas = doc_response.get("metadatas", [])

                        # Find chunks for this document
                        doc_chunks = []
                        for idx, chunk_id in enumerate(ids):
                            meta = metadatas[idx] if idx < len(metadatas) else {}
                            # Match by document_id or by document name in chunk_id
                            if (meta.get("document_id") == doc_id or
                                doc_id in chunk_id or
                                meta.get("document_name", "").lower() == doc_id.lower()):
                                page_num = meta.get("page_number", 0)
                                content = documents[idx] if idx < len(documents) else ""
                                doc_chunks.append((page_num, content, meta))

                        if doc_chunks:
                            # Sort by page number and combine
                            doc_chunks.sort(key=lambda x: x[0] if x[0] else 0)
                            content_parts = []
                            for page_num, content, meta in doc_chunks[:10]:  # Limit to first 10 chunks
                                heading = meta.get("heading_text") or meta.get("section_title", "")
                                if heading:
                                    content_parts.append(f'<div style="font-weight: 600; color: #333; margin-top: 12px; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px;">{heading}</div>')
                                if content:
                                    # Add with proper styling
                                    content_parts.append(f'<p style="font-size: 0.85em; line-height: 1.5; color: #333; margin: 6px 0;">{content[:500]}{"..." if len(content) > 500 else ""}</p>')
                            source_content = "".join(content_parts)
                except Exception:
                    pass

        if source_content:
            # Document-like container with paper styling (uses shared PANEL_HEIGHT)
            st.markdown(
                f'''<div class="source-document-panel">{source_content}</div>''',
                unsafe_allow_html=True
            )
        elif doc_id and not source_collection:
            st.info(f"Source collection not found for document: {doc_id[:30]}...\nThe source collection metadata may be missing from this test plan.")
        elif doc_id:
            st.info(f"Source content not available for document: {doc_id[:30]}...")
        else:
            st.info("No source document linked to this test plan")

    # =========================================================================
    # RIGHT COLUMN: Section Dropdown + Editable Test Plan
    # =========================================================================
    with right_col:
        # Section dropdown at top (matches page nav styling)
        if not page_sections:
            st.info("No sections on this page")
            return

        # Build section labels with hierarchy and review status
        section_options = []
        for idx, s in enumerate(page_sections):
            level = s.get("heading_level", 1)
            indent = "→ " * (level - 1) if level > 1 else ""
            title = s.get("section_title", f"Section {idx + 1}")
            reviewed_mark = "✓ " if s.get("reviewed", False) else "○ "
            section_options.append(f"{reviewed_mark}{indent}{title}")

        # Section selector
        selected_section_idx_in_page = st.selectbox(
            "Section",
            options=range(len(page_sections)),
            format_func=lambda i: section_options[i],
            key="section_dropdown",
            label_visibility="collapsed"
        )

        # Get selected section
        section = page_sections[selected_section_idx_in_page]
        selected_section_idx = sections.index(section)
        section_title = section.get("section_title", f"Section {selected_section_idx + 1}")
        is_section_reviewed = section.get("reviewed", False)

        # Compact metadata row
        level = section.get('heading_level', 'N/A')
        parent = section.get('parent_heading', '')
        parent_display = f" | Parent: {parent[:20]}..." if parent and len(parent) > 20 else (f" | Parent: {parent}" if parent else "")
        st.caption(f"Level {level}{parent_display}")

        # =====================================================================
        # DOCUMENT-LIKE EDITOR (WYSIWYG with Quill)
        # =====================================================================

        # Unique key for this section's editor state
        editor_key = f"editor_{plan_id}_{version_id}_{selected_section_idx}"

        if version_status != "draft":
            # Read-only display for non-draft versions (uses shared editor-panel class)
            rules_content = section.get("synthesized_rules", "")
            rendered_content = _markdown_to_document_html(rules_content)

            st.markdown(
                f'''<div class="editor-panel">
                    <h3 class="section-header">{section_title}</h3>
                    <div style="font-size: 0.92em; color: #333;">
                        {rendered_content}
                    </div>
                </div>''',
                unsafe_allow_html=True
            )

        else:
            # Section Title (editable)
            edited_title = st.text_input(
                "Section Title",
                value=section_title,
                key=f"title_{editor_key}",
                placeholder="Section Title"
            )

            # WYSIWYG Rich Text Editor for Requirements
            st.markdown('<div style="font-size: 0.85em; color: #666; margin-bottom: 4px;">Requirements & Rules</div>', unsafe_allow_html=True)

            # Convert markdown/plain text to HTML for the Quill editor
            current_rules = section.get("synthesized_rules", "")
            if current_rules and not current_rules.strip().startswith("<"):
                # Use the new converter for proper formatting
                html_content = _markdown_to_document_html(current_rules)
            else:
                html_content = current_rules

            # Quill WYSIWYG editor
            edited_rules_html = st_quill(
                value=html_content,
                html=True,
                toolbar=[
                    [{'header': [1, 2, 3, False]}],
                    ['bold', 'italic', 'underline', 'strike'],
                    [{'list': 'ordered'}, {'list': 'bullet'}],
                    [{'indent': '-1'}, {'indent': '+1'}],
                    ['link'],
                    ['clean']
                ],
                key=f"quill_{editor_key}",
                placeholder="Enter requirements and rules..."
            )

            # Test Procedures section
            test_procedures = section.get("test_procedures", [])
            edited_procedures = []

            if test_procedures:
                with st.expander(f"📋 Test Procedures ({len(test_procedures)})", expanded=False):
                    for proc_idx, proc in enumerate(test_procedures):
                        st.markdown(f"**Test {proc_idx + 1}:** {proc.get('title', 'Untitled')}")
                        proc_title = st.text_input(
                            "Title",
                            value=proc.get("title", ""),
                            key=f"proc_title_{editor_key}_{proc_idx}",
                            label_visibility="collapsed"
                        )
                        proc_objective = st_quill(
                            value=proc.get("objective", ""),
                            html=True,
                            toolbar=[
                                ['bold', 'italic'],
                                [{'list': 'ordered'}, {'list': 'bullet'}],
                            ],
                            key=f"proc_obj_{editor_key}_{proc_idx}",
                            placeholder="Test objective..."
                        )
                        edited_procedures.append({
                            "id": proc.get("id", f"proc_{proc_idx}"),
                            "title": proc_title,
                            "objective": proc_objective or proc.get("objective", ""),
                            "setup": proc.get("setup", ""),
                            "priority": proc.get("priority", "medium"),
                            "steps": proc.get("steps", [])
                        })
                        st.markdown("---")

            # Review status and Save button row
            st.markdown("")  # Spacing
            review_col, save_col = st.columns([1, 1])

            with review_col:
                # Mark as Reviewed checkbox
                mark_reviewed = st.checkbox(
                    "✅ Mark as Reviewed",
                    value=is_section_reviewed,
                    key=f"reviewed_{editor_key}",
                    help="Check this box to mark this section as reviewed. All sections must be reviewed before publishing."
                )

            with save_col:
                save_clicked = st.button("💾 Save Changes", key=f"save_{editor_key}", type="primary", use_container_width=True)

            if save_clicked:
                # Get the edited content
                edited_rules = edited_rules_html if edited_rules_html else current_rules

                section["section_title"] = edited_title
                section["synthesized_rules"] = edited_rules
                section["test_procedures"] = edited_procedures
                section["reviewed"] = mark_reviewed  # Save review status
                sections[selected_section_idx] = section
                test_plan_data["test_plan"]["sections"] = sections

                # Save to ChromaDB
                collection_name = selected_plan.get("collection_name", "test_plan_drafts")
                current_doc_id = selected_version["document_id"]

                try:
                    # Prepare documents for upsert (update if exists, add if not)
                    documents_to_upsert = []
                    ids_to_upsert = []
                    metadatas_to_upsert = []

                    # Add individual sections
                    for idx, sect in enumerate(sections):
                        section_doc_id = f"{current_doc_id}_section_{idx}"
                        section_content = json.dumps(sect, indent=2)

                        documents_to_upsert.append(section_content)
                        ids_to_upsert.append(section_doc_id)
                        metadatas_to_upsert.append({
                            "plan_id": str(plan_id),
                            "version_id": str(version_id),
                            "version_number": str(selected_version.get("version_number", 1)),
                            "section_id": sect.get("section_id", ""),
                            "section_title": sect.get("section_title", ""),
                            "section_index": str(idx),
                            "test_plan_title": selected_plan.get("title", ""),
                            "status": "draft",
                            "type": "test_plan_section",
                            "reviewed": str(sect.get("reviewed", False)).lower()
                        })

                    # Add full test plan document (includes all sections with reviewed status)
                    documents_to_upsert.append(json.dumps(test_plan_data, indent=2))
                    ids_to_upsert.append(current_doc_id)
                    metadatas_to_upsert.append({
                        "plan_id": str(plan_id),
                        "plan_key": selected_plan.get("plan_key", ""),
                        "version_id": str(version_id),
                        "version_number": str(selected_version.get("version_number", 1)),
                        "title": selected_plan.get("title", ""),
                        "status": "draft",
                        "type": "test_plan_full",
                        "updated_at": datetime.now().isoformat(),
                        "total_sections": str(len(sections)),
                        "reviewed_sections": str(sum(1 for s in sections if s.get("reviewed", False)))
                    })

                    # Upsert to ChromaDB (update if exists, add if not)
                    api_client.post(
                        f"{config.fastapi_url}/api/vectordb/documents/upsert",
                        data={
                            "collection_name": collection_name,
                            "documents": documents_to_upsert,
                            "ids": ids_to_upsert,
                            "metadatas": metadatas_to_upsert
                        }
                    )

                    st.success(f"✅ Section saved successfully! ({sum(1 for s in sections if s.get('reviewed', False))}/{len(sections)} sections reviewed)")
                    st.rerun()

                except Exception as e:
                    st.error(f"Failed to save: {e}")
                    import traceback
                    with st.expander("Show error details"):
                        st.code(traceback.format_exc())


if __name__ == "__main__":
    render_sidebyside_editor()
