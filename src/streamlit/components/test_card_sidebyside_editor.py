"""
Test Card Side-by-Side Editor

Displays the original test plan section on the left and the editable test card(s) on the right.
This makes it easier for users to compare and align test card edits with the source test plan.

Features:
- WYSIWYG rich text editing (like Google Docs/Word)
- Source test plan section display
- Test card versioning and drafting
- Document-like styling

Note: JSON is used internally for LLM processing. Users see and edit clean, formatted documents.
"""

from __future__ import annotations

import json
import uuid
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import streamlit as st
from streamlit_quill import st_quill

from app_lib.api.client import api_client
from config.settings import config
from components.review_workflow import render_status_badge
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


def _parse_markdown_table(content: str) -> Dict[str, str]:
    """Parse markdown table to extract structured fields from test card content."""
    fields = {
        "test_id": "",
        "test_title": "",
        "procedures": "",
        "expected_results": "",
        "acceptance_criteria": "",
        "dependencies": ""
    }

    if not content or not content.strip():
        return fields

    try:
        lines = content.strip().split('\n')
        if len(lines) >= 3:
            # Parse data row (skip header and separator)
            data_row = lines[2] if len(lines) > 2 else ""
            cells = [cell.strip() for cell in data_row.split('|')]

            # Table format: | Test ID | Test Title | Procedures | Expected Results | Acceptance Criteria | Dependencies | ...
            if len(cells) >= 7:
                fields["test_id"] = cells[1] if len(cells) > 1 else ""
                fields["test_title"] = cells[2] if len(cells) > 2 else ""
                fields["procedures"] = cells[3] if len(cells) > 3 else ""
                fields["expected_results"] = cells[4] if len(cells) > 4 else ""
                fields["acceptance_criteria"] = cells[5] if len(cells) > 5 else ""
                fields["dependencies"] = cells[6] if len(cells) > 6 else ""
    except Exception:
        pass

    return fields


def _load_test_plan_sections(plan_id: int, version_id: int) -> List[Dict[str, Any]]:
    """Load test plan sections from a specific version"""
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
            st.warning(f"Version {version_id} not found for plan {plan_id}")
            return []

        document_id = version["document_id"]

        # Get test plan to find primary collection
        plan_response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}"
        )
        primary_collection = plan_response.get("collection_name", "test_plan_drafts")

        # Try multiple collections - document might be in drafts, generated, or json_test_plans
        collections_to_try = [primary_collection]
        if primary_collection != "test_plan_drafts":
            collections_to_try.append("test_plan_drafts")
        if primary_collection != "generated_test_plan":
            collections_to_try.append("generated_test_plan")
        if primary_collection != "json_test_plans":
            collections_to_try.append("json_test_plans")

        # Search for the document in each collection
        for try_collection in collections_to_try:
            try:
                doc_response = api_client.get(
                    f"{config.fastapi_url}/api/vectordb/documents",
                    params={"collection_name": try_collection},
                    show_errors=False
                )

                if not doc_response:
                    continue

                ids = doc_response.get("ids", [])
                documents = doc_response.get("documents", [])

                for idx, doc_id in enumerate(ids):
                    if doc_id == document_id:
                        content = documents[idx] if idx < len(documents) else "{}"
                        if isinstance(content, str):
                            try:
                                test_plan_data = json.loads(content) if content.strip() else {}
                            except json.JSONDecodeError:
                                # Not JSON - might be markdown or plain text
                                continue
                        else:
                            test_plan_data = content if content else {}

                        sections = test_plan_data.get("test_plan", {}).get("sections", [])
                        if sections:
                            return sections

            except Exception:
                continue

        # Debug: Show what we were looking for
        with st.expander("🔍 Debug: Test Plan Section Loading", expanded=False):
            st.markdown(f"**Looking for document ID:** `{document_id}`")
            st.markdown(f"**Tried collections:** {collections_to_try}")
            st.markdown("**Checking what's in each collection...**")

            for try_collection in collections_to_try:
                try:
                    doc_response = api_client.get(
                        f"{config.fastapi_url}/api/vectordb/documents",
                        params={"collection_name": try_collection},
                        show_errors=False
                    )
                    if doc_response:
                        ids = doc_response.get("ids", [])
                        st.markdown(f"- **{try_collection}**: {len(ids)} documents")
                        # Show if document_id is close to any in collection
                        for doc_id in ids[:5]:
                            match = "✅" if doc_id == document_id else ("⚠️ partial" if document_id in doc_id or doc_id in document_id else "")
                            st.markdown(f"  - `{doc_id[:40]}...` {match}")
                except Exception:
                    st.markdown(f"- **{try_collection}**: ❌ Error accessing")

        return []

    except Exception as e:
        st.error(f"Failed to load test plan sections: {e}")
        import traceback
        st.code(traceback.format_exc())
        return []


def _load_test_cards_for_plan(plan_id: int, plan_doc_id: str = None, plan_title: str = None) -> List[Dict[str, Any]]:
    """
    Load all test cards associated with a test plan.

    Uses the /query-test-cards API which has robust fallback matching built-in.
    Then tries PostgreSQL versioning records for additional cards.
    Deduplicates by document_id, card_key, and title.
    """
    card_details = []
    seen_doc_ids = set()
    seen_card_keys = set()
    seen_titles = set()

    # Method 1: Use the query-test-cards API (has built-in fallback matching)
    # This is the most reliable method as the API handles ID mismatches
    if plan_doc_id:
        try:
            query_response = api_client.post(
                f"{config.fastapi_url}/api/doc_gen/query-test-cards",
                data={
                    "test_plan_id": plan_doc_id,
                    "collection_name": "test_cards"
                },
                timeout=30,
                show_errors=False
            )

            if query_response:
                api_cards = query_response.get("test_cards", [])
                for card in api_cards:
                    doc_id = card.get("document_id", "")
                    card_title = (card.get("test_title") or card.get("document_name", "Untitled")).strip().lower()

                    if doc_id in seen_doc_ids:
                        continue
                    if card_title and card_title in seen_titles:
                        continue

                    seen_doc_ids.add(doc_id)
                    if card_title:
                        seen_titles.add(card_title)

                    card_details.append({
                        "card_id": None,
                        "card_key": "",
                        "version_id": None,
                        "version_number": 1,
                        "document_id": doc_id,
                        "title": card.get("test_title") or card.get("document_name", "Untitled"),
                        "requirement_id": card.get("requirement_id", ""),
                        "content": card.get("content", card.get("content_preview", "")),
                        "metadata": {k: v for k, v in card.items() if k not in ["content", "content_preview"]},
                        "versions": [],
                        "status": card.get("execution_status", "draft"),
                        "_source": "query_api"
                    })

        except Exception as e:
            # Continue to other methods
            pass

    # Method 2: Try PostgreSQL versioning records (for version tracking)
    try:
        cards_response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-cards",
            params={"plan_id": plan_id},
            timeout=30,
            show_errors=False
        )

        cards = cards_response.get("cards", []) if cards_response else []

        for card in cards:
            # Get versions for this card
            versions_response = api_client.get(
                f"{config.fastapi_url}/api/versioning/test-cards/{card['id']}/versions",
                timeout=30,
                show_errors=False
            )
            versions = versions_response.get("versions", []) if versions_response else []

            if versions:
                latest_version = versions[0]  # Versions are ordered by creation date desc
                doc_id = latest_version["document_id"]

                # Skip if already loaded
                if doc_id in seen_doc_ids:
                    continue

                card_key = card.get("card_key", "")
                card_title = card.get("title", "Untitled").strip().lower()

                # Skip if duplicate by key or title
                if card_key and card_key in seen_card_keys:
                    continue
                if card_title and card_title in seen_titles:
                    continue

                # Fetch card content from ChromaDB
                try:
                    doc_response = api_client.get(
                        f"{config.fastapi_url}/api/vectordb/documents",
                        params={"collection_name": "test_cards"},
                        show_errors=False
                    )

                    ids = doc_response.get("ids", []) if doc_response else []
                    documents = doc_response.get("documents", []) if doc_response else []
                    metadatas = doc_response.get("metadatas", []) if doc_response else []

                    for idx, chromadb_id in enumerate(ids):
                        if chromadb_id == doc_id:
                            # Track seen values
                            seen_doc_ids.add(doc_id)
                            if card_key:
                                seen_card_keys.add(card_key)
                            if card_title:
                                seen_titles.add(card_title)

                            card_details.append({
                                "card_id": card["id"],
                                "card_key": card_key,
                                "version_id": latest_version["id"],
                                "version_number": latest_version.get("version_number", 1),
                                "document_id": doc_id,
                                "title": card.get("title", "Untitled"),
                                "requirement_id": card.get("requirement_id", ""),
                                "content": documents[idx] if idx < len(documents) else "",
                                "metadata": metadatas[idx] if idx < len(metadatas) else {},
                                "versions": versions,
                                "status": latest_version.get("status", "draft"),
                                "_source": "versioning"
                            })
                            break
                except Exception:
                    pass

    except Exception as e:
        # Continue to fallback method
        pass

    # Method 3: Direct ChromaDB fallback with flexible matching
    # (For cases where neither API nor versioning found cards)
    if not card_details:
        # Extract plan title prefix for flexible matching
        plan_doc_prefix = None
        if plan_doc_id and "_" in plan_doc_id:
            parts = plan_doc_id.split("_")
            if len(parts) >= 2:
                plan_doc_prefix = f"{parts[0]}_{parts[1]}"

        try:
            doc_response = api_client.get(
                f"{config.fastapi_url}/api/vectordb/documents",
                params={"collection_name": "test_cards"},
                show_errors=False
            )

            ids = doc_response.get("ids", []) if doc_response else []
            documents = doc_response.get("documents", []) if doc_response else []
            metadatas = doc_response.get("metadatas", []) if doc_response else []

            for idx, doc_id in enumerate(ids):
                if doc_id in seen_doc_ids:
                    continue

                meta = metadatas[idx] if idx < len(metadatas) else {}
                stored_plan_id = meta.get("test_plan_id", "")

                # Flexible matching
                matches_plan = False
                if plan_doc_id and stored_plan_id:
                    # Exact match
                    if stored_plan_id == plan_doc_id:
                        matches_plan = True
                    # Partial match (one contains the other)
                    elif plan_doc_id in stored_plan_id or stored_plan_id in plan_doc_id:
                        matches_plan = True
                    # Case-insensitive match
                    elif stored_plan_id.lower() == plan_doc_id.lower():
                        matches_plan = True
                    # Prefix match
                    elif plan_doc_prefix and stored_plan_id.startswith(plan_doc_prefix):
                        matches_plan = True

                # Check by plan_id metadata (numeric ID)
                if not matches_plan and plan_id:
                    stored_numeric_id = meta.get("plan_id")
                    if stored_numeric_id and str(stored_numeric_id) == str(plan_id):
                        matches_plan = True

                # Check by test_plan_title
                if not matches_plan and plan_title:
                    stored_plan_title = meta.get("test_plan_title", "")
                    if stored_plan_title and stored_plan_title.lower() == plan_title.lower():
                        matches_plan = True

                if matches_plan:
                    card_title = (meta.get("test_title") or meta.get("document_name", "Untitled")).strip().lower()

                    if card_title and card_title in seen_titles:
                        continue

                    seen_doc_ids.add(doc_id)
                    if card_title:
                        seen_titles.add(card_title)

                    card_details.append({
                        "card_id": None,
                        "card_key": "",
                        "version_id": None,
                        "version_number": 1,
                        "document_id": doc_id,
                        "title": meta.get("test_title") or meta.get("document_name", "Untitled"),
                        "requirement_id": meta.get("requirement_id", ""),
                        "content": documents[idx] if idx < len(documents) else "",
                        "metadata": meta,
                        "versions": [],
                        "status": "draft",
                        "_source": "chromadb_fallback"
                    })

        except Exception as e:
            pass

    return card_details


def _sanitize_metadata_for_chromadb(metadata: Dict) -> Dict:
    """
    Sanitize metadata to ensure all values are ChromaDB-compatible primitives.
    ChromaDB only accepts str, int, float, bool values - no dicts, lists, or None.
    """
    import json as json_lib
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = ""  # Convert None to empty string
        elif isinstance(value, dict):
            # Convert dicts to JSON strings
            sanitized[key] = json_lib.dumps(value)
        elif isinstance(value, list):
            # Convert lists to JSON strings
            sanitized[key] = json_lib.dumps(value)
        elif isinstance(value, bool):
            # Keep bools as strings for consistency
            sanitized[key] = str(value).lower()
        elif isinstance(value, (str, int, float)):
            sanitized[key] = value
        else:
            # Convert anything else to string
            sanitized[key] = str(value)
    return sanitized


def _save_test_card(card_id: int, plan_id: int, updated_content: str, updated_metadata: Dict, document_id: str = None) -> bool:
    """
    Save updated test card.

    Handles two cases:
    1. Versioning system cards (card_id is valid int) - creates new version via API
    2. ChromaDB-only cards (card_id is None) - updates directly in ChromaDB via upsert

    Args:
        card_id: Versioning system card ID (can be None for ChromaDB-only cards)
        plan_id: Test plan ID
        updated_content: Updated test card content
        updated_metadata: Updated metadata dict
        document_id: ChromaDB document ID (required for ChromaDB-only cards)
    """
    try:
        updated_metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Sanitize metadata to ensure all values are ChromaDB-compatible primitives
        updated_metadata = _sanitize_metadata_for_chromadb(updated_metadata)

        # Case 1: ChromaDB-only card (no versioning card_id)
        if card_id is None:
            if not document_id:
                st.error("Cannot save: No card_id or document_id provided")
                return False

            # Try to delete existing document first, then add new one
            # This is more reliable than upsert for ChromaDB
            try:
                # Delete existing document (ignore errors if it doesn't exist)
                api_client.post(
                    f"{config.fastapi_url}/api/vectordb/documents/remove",
                    data={
                        "collection_name": "test_cards",
                        "ids": [document_id]
                    },
                    timeout=30,
                    show_errors=False
                )
            except Exception:
                pass  # Ignore delete errors - document might not exist

            # Add updated document
            add_response = api_client.post(
                f"{config.fastapi_url}/api/vectordb/documents/add",
                data={
                    "collection_name": "test_cards",
                    "documents": [updated_content],
                    "ids": [document_id],
                    "metadatas": [updated_metadata]
                },
                timeout=30,
                show_errors=True
            )

            if add_response is None:
                st.error("Failed to add document to ChromaDB")
                return False

            return True

        # Case 2: Versioning system card (has valid card_id)
        # Get latest version
        versions_response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-cards/{card_id}/versions",
            timeout=30
        )
        versions = versions_response.get("versions", []) if versions_response else []
        base_version_id = versions[0]["id"] if versions else None

        # Create new document in ChromaDB
        new_doc_id = f"testcard_{uuid.uuid4().hex[:12]}"

        api_client.post(
            f"{config.fastapi_url}/api/vectordb/documents/add",
            data={
                "collection_name": "test_cards",
                "documents": [updated_content],
                "ids": [new_doc_id],
                "metadatas": [updated_metadata]
            },
            timeout=30
        )

        # Get test plan version for linking
        if plan_id:
            plan_versions_response = api_client.get(
                f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions"
            )
            plan_versions = plan_versions_response.get("versions", []) if plan_versions_response else []
            plan_version_id = plan_versions[0]["id"] if plan_versions else None
        else:
            plan_version_id = None

        # Create version record
        api_client.post(
            f"{config.fastapi_url}/api/versioning/test-cards/{card_id}/versions",
            data={
                "document_id": new_doc_id,
                "based_on_version_id": base_version_id,
                "plan_version_id": plan_version_id
            },
            timeout=30
        )

        return True

    except Exception as e:
        st.error(f"Failed to save test card: {e}")
        return False


def render_test_card_sidebyside_editor():
    """Render side-by-side test card editor with test plan and test cards - WYSIWYG Style"""

    # =========================================================================
    # IMMEDIATE DEBUG: Show test cards collection status at the very top
    # =========================================================================

    # Always show this debug info at the top to help diagnose issues
    # with st.expander("🔧 Test Cards Collection Status (Debug)", expanded=False):
    #     st.markdown("**Checking test_cards collection...**")
    #     try:
    #         debug_response = api_client.get(
    #             f"{config.fastapi_url}/api/vectordb/documents",
    #             params={"collection_name": "test_cards"},
    #             timeout=30,
    #             show_errors=True
    #         )

    #         if debug_response:
    #             debug_ids = debug_response.get("ids", [])
    #             debug_metas = debug_response.get("metadatas", [])

    #             st.success(f"✅ Collection accessible - Found {len(debug_ids)} test card(s)")

    #             if debug_ids:
    #                 st.markdown("**First 10 test cards:**")
    #                 for i, doc_id in enumerate(debug_ids[:10]):
    #                     meta = debug_metas[i] if i < len(debug_metas) else {}
    #                     test_plan_id = meta.get("test_plan_id", "N/A")
    #                     test_title = meta.get("test_title", meta.get("document_name", "Untitled"))
    #                     st.markdown(f"{i+1}. `{doc_id}` → Plan ID: `{test_plan_id}` | Title: {test_title}")
    #             else:
    #                 st.warning("⚠️ Collection exists but is empty. Generate test cards first.")
    #         else:
    #             st.error("❌ API returned empty response")
    #     except Exception as e:
    #         st.error(f"❌ Error accessing test_cards collection: {e}")
    #         import traceback
    #         st.code(traceback.format_exc())

    # =========================================================================
    # HEADER: Test Plan → Version → Test Card selector (similar to test plan editor)
    # =========================================================================

    st.markdown("##### Select Test Plan and Test Card")

    # Load test plans with deduplication
    try:
        plans_response = api_client.get(f"{config.fastapi_url}/api/versioning/test-plans", show_errors=False)
        raw_plans = plans_response.get("plans", []) if plans_response else []
    except Exception as e:
        st.error(f"Failed to load test plans: {e}")
        raw_plans = []

    # Deduplicate by plan_key, id, and title
    seen_plan_keys = set()
    seen_plan_ids = set()
    seen_titles = set()
    plans = []

    for plan in raw_plans:
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

        plans.append(plan)

    if not plans:
        st.info("No test plans available. Generate a test plan first.")

        # Show test cards collection status even when no plans
        with st.expander("🔍 Debug: Test Cards Collection Status"):
            try:
                tc_response = api_client.get(
                    f"{config.fastapi_url}/api/vectordb/documents",
                    params={"collection_name": "test_cards"},
                    show_errors=False
                )
                if tc_response:
                    tc_ids = tc_response.get("ids", [])
                    st.markdown(f"**Test cards in ChromaDB:** {len(tc_ids)}")
                    if tc_ids:
                        st.markdown("**First 5 test card IDs:**")
                        for tc_id in tc_ids[:5]:
                            st.code(tc_id)
                else:
                    st.warning("test_cards collection not found or empty")
            except Exception as e:
                st.error(f"Error querying test_cards: {e}")
        return

    # Header row with selectors
    header_cols = st.columns([2, 1, 2])

    with header_cols[0]:
        selected_plan = st.selectbox(
            "Test Plan",
            options=plans,
            format_func=lambda p: f"{p.get('title', 'Untitled')}",
            key="testcard_sidebyside_plan_selector"
        )

    if not selected_plan:
        return

    plan_id = selected_plan["id"]

    # Load plan versions
    try:
        versions_response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions",
            show_errors=False
        )
        versions = versions_response.get("versions", []) if versions_response else []
    except Exception as e:
        st.error(f"Failed to load plan versions: {e}")
        versions = []

    if not versions:
        st.info("No versions available for this test plan")
        return

    with header_cols[1]:
        if len(versions) == 1:
            selected_version = versions[0]
            st.caption(f"v{selected_version['version_number']}")
        else:
            selected_version = st.selectbox(
                "Plan Version",
                options=versions,
                format_func=lambda v: f"v{v['version_number']}",
                key="testcard_sidebyside_version_selector",
                label_visibility="collapsed"
            )

    if not selected_version:
        return

    version_id = selected_version["id"]

    # Load test plan sections
    sections = _load_test_plan_sections(plan_id, version_id)

    if not sections:
        st.warning("No sections found in this test plan version")
        return

    # Load test cards for this plan (pass document_id and title to enable ChromaDB fallback)
    plan_doc_id = selected_version.get("document_id", "")
    plan_title = selected_plan.get("title", "")
    test_cards = _load_test_cards_for_plan(plan_id, plan_doc_id, plan_title)

    if not test_cards:
        st.info("No test cards found matching this test plan. Generate test cards first from the 'Generate Test Cards' tab.")

        # Debug expander to help diagnose why test cards aren't found
        with st.expander("🔍 Debug: Test Card Loading Info", expanded=True):
            st.markdown(f"**Looking for test cards with:**")
            st.markdown(f"- Plan ID (numeric): `{plan_id}`")
            st.markdown(f"- Plan Document ID: `{plan_doc_id}`")
            st.markdown(f"- Plan Title: `{plan_title}`")

            # Step 1: Try the query-test-cards API
            st.markdown("---")
            st.markdown("**Step 1: Query API Result**")
            try:
                api_query_response = api_client.post(
                    f"{config.fastapi_url}/api/doc_gen/query-test-cards",
                    data={
                        "test_plan_id": plan_doc_id,
                        "collection_name": "test_cards"
                    },
                    timeout=30,
                    show_errors=True
                )
                if api_query_response:
                    api_card_count = len(api_query_response.get("test_cards", []))
                    st.markdown(f"✅ API returned **{api_card_count}** test cards")
                    if api_card_count > 0:
                        st.markdown("Sample cards from API:")
                        for card in api_query_response.get("test_cards", [])[:3]:
                            st.code(f"ID: {card.get('document_id', 'N/A')[:30]} | Title: {card.get('test_title', card.get('document_name', 'N/A'))}")
                else:
                    st.warning("API returned empty response")
            except Exception as e:
                st.error(f"API query failed: {e}")

            # Step 2: Check what's in the test_cards collection directly
            st.markdown("---")
            st.markdown("**Step 2: Direct ChromaDB Check**")
            all_cards_data = None
            try:
                debug_response = api_client.get(
                    f"{config.fastapi_url}/api/vectordb/documents",
                    params={"collection_name": "test_cards"},
                    show_errors=False
                )
                if debug_response:
                    debug_ids = debug_response.get("ids", [])
                    debug_docs = debug_response.get("documents", [])
                    debug_metas = debug_response.get("metadatas", [])
                    st.markdown(f"✅ ChromaDB has **{len(debug_ids)}** test card(s)")

                    if debug_ids:
                        all_cards_data = (debug_ids, debug_docs, debug_metas)
                        st.markdown("**Test plan IDs stored in these cards:**")
                        unique_plan_ids = set()
                        for meta in debug_metas[:20]:
                            stored_id = meta.get("test_plan_id", "")
                            if stored_id:
                                unique_plan_ids.add(stored_id)
                        for uid in list(unique_plan_ids)[:5]:
                            match_indicator = "✅ MATCH" if (plan_doc_id and (plan_doc_id in uid or uid in plan_doc_id)) else "❌ NO MATCH"
                            st.code(f"{uid} {match_indicator}")

                        # Show comparison
                        st.markdown("---")
                        st.markdown("**ID Comparison:**")
                        st.markdown(f"- Looking for: `{plan_doc_id}`")
                        if unique_plan_ids:
                            first_stored = list(unique_plan_ids)[0]
                            st.markdown(f"- First stored: `{first_stored}`")
                            if plan_doc_id and first_stored:
                                st.markdown(f"- Exact match: `{plan_doc_id == first_stored}`")
                                st.markdown(f"- Contains: `{plan_doc_id in first_stored or first_stored in plan_doc_id}`")

                        # Offer to show all test cards
                        st.markdown("---")
                        st.markdown("**Want to see all test cards anyway?**")
                        if st.button("📋 Show All Test Cards", key="show_all_test_cards"):
                            st.session_state["show_all_test_cards"] = True
                            st.rerun()
                    else:
                        st.warning("⚠️ No test cards found in test_cards collection - Generate test cards first!")
                else:
                    st.warning("Could not query test_cards collection")
            except Exception as e:
                # Handle 404 (collection doesn't exist) gracefully
                if "404" in str(e):
                    st.info("ℹ️ The test_cards collection doesn't exist yet. Generate test cards first in Tab 4 (Generate Test Cards).")
                else:
                    st.error(f"Debug query error: {e}")

        # Check if user wants to see all test cards
        if st.session_state.get("show_all_test_cards"):
            try:
                all_response = api_client.get(
                    f"{config.fastapi_url}/api/vectordb/documents",
                    params={"collection_name": "test_cards"},
                    show_errors=False
                )
                if all_response:
                    all_ids = all_response.get("ids", [])
                    all_docs = all_response.get("documents", [])
                    all_metas = all_response.get("metadatas", [])

                    if all_ids:
                        # Build test_cards list from all available cards
                        test_cards = []
                        for idx, doc_id in enumerate(all_ids):
                            meta = all_metas[idx] if idx < len(all_metas) else {}
                            test_cards.append({
                                "card_id": None,
                                "card_key": "",
                                "version_id": None,
                                "version_number": 1,
                                "document_id": doc_id,
                                "title": meta.get("test_title") or meta.get("document_name", "Untitled"),
                                "requirement_id": meta.get("requirement_id", ""),
                                "content": all_docs[idx] if idx < len(all_docs) else "",
                                "metadata": meta,
                                "versions": [],
                                "status": "draft",
                                "_source": "chromadb_all"
                            })
                        st.success(f"Showing all {len(test_cards)} test cards (unfiltered)")
            except Exception as e:
                # Handle 404 (collection doesn't exist) gracefully
                if "404" in str(e):
                    st.info("ℹ️ No test cards exist yet. Generate test cards first in Tab 4 (Generate Test Cards).")
                else:
                    st.error(f"Error loading all test cards: {e}")

        if not test_cards:
            return

    with header_cols[2]:
        # Test card selector - deduplicate by document_id to avoid actual duplicates
        # But keep cards with same title if they have different test IDs (they're different cards)
        seen_doc_ids = set()
        deduplicated_cards = []
        for card in test_cards:
            doc_id = card.get("document_id", "")
            if doc_id and doc_id in seen_doc_ids:
                continue  # Skip actual duplicate document
            if doc_id:
                seen_doc_ids.add(doc_id)
            deduplicated_cards.append(card)

        # Use deduplicated cards for the dropdown
        card_options = {card["document_id"]: card for card in deduplicated_cards}

        # Build labels that include test_id to differentiate cards with same title
        card_labels = {}
        for card in deduplicated_cards:
            doc_id = card["document_id"]
            title = card.get("title", "Untitled")
            test_id = card.get("metadata", {}).get("test_id", "") or card.get("requirement_id", "")
            version = card.get("version_number", 1)

            # Include test_id in label if available to differentiate cards with same title
            if test_id:
                card_labels[doc_id] = f"{test_id}: {title}"
            else:
                card_labels[doc_id] = f"{title} (v{version})"

        selected_card_doc_id = st.selectbox(
            "Test Card",
            options=list(card_options.keys()),
            format_func=lambda doc_id: card_labels.get(doc_id, "Unknown"),
            key="selected_test_card_sidebyside"
        )

    selected_card = card_options.get(selected_card_doc_id)
    if not selected_card:
        return

    # Info bar (use deduplicated count)
    st.caption(f"Plan: {len(sections)} sections | Test Cards: {len(deduplicated_cards)} cards")

    # Get selected card metadata for status section
    card_status = selected_card.get("status", "draft")
    card_metadata = selected_card.get("metadata", {})
    review_status = card_metadata.get("review_status", "DRAFT")
    editor_key = f"testcard_editor_{selected_card['card_id']}_{selected_card['version_id']}"

    # =========================================================================
    # REVIEW PROGRESS & STATUS (Above side-by-side layout)
    # =========================================================================

    # Count test cards by review status
    total_cards = len(deduplicated_cards)
    draft_count = sum(1 for c in deduplicated_cards if c.get("metadata", {}).get("review_status", "DRAFT") == "DRAFT")
    reviewed_count = sum(1 for c in deduplicated_cards if c.get("metadata", {}).get("review_status", "DRAFT") == "REVIEWED")
    published_count = sum(1 for c in deduplicated_cards if c.get("metadata", {}).get("review_status", "DRAFT") == "PUBLISHED")

    # Calculate progress (reviewed + published = complete)
    completed = reviewed_count + published_count
    progress = completed / total_cards if total_cards > 0 else 0

    # Progress metrics row
    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric("Draft", draft_count, help="Test cards pending review")
    with metric_cols[1]:
        st.metric("Reviewed", reviewed_count, help="Test cards marked as reviewed")
    with metric_cols[2]:
        st.metric("Published", published_count, help="Test cards ready for execution")
    with metric_cols[3]:
        pct = int(progress * 100)
        st.metric("Progress", f"{pct}%", help="Review completion")

    # Progress bar
    if total_cards > 0:
        if progress == 0:
            progress_text = "No test cards reviewed yet"
        elif progress < 1.0:
            progress_text = f"{completed}/{total_cards} test cards reviewed/published"
        else:
            progress_text = "All test cards complete!"
        st.progress(progress, text=progress_text)

    # Status badge and action buttons row
    st.markdown("**Selected Test Card Status:**")

    status_row = st.columns([1, 1, 1, 1])

    with status_row[0]:
        render_status_badge(review_status, size="normal")

    # Collection name for test cards
    collection_name = "test_cards"

    # Define status change handler
    def handle_status_change(new_status: str) -> bool:
        """Update the review status of the current test card."""
        try:
            updated_metadata = dict(card_metadata)
            updated_metadata["review_status"] = new_status
            updated_metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

            # Sanitize metadata
            sanitized = {}
            for k, v in updated_metadata.items():
                if v is None:
                    sanitized[k] = ""
                elif isinstance(v, (dict, list)):
                    import json
                    sanitized[k] = json.dumps(v)
                elif isinstance(v, bool):
                    sanitized[k] = str(v).lower()
                else:
                    sanitized[k] = v

            # Update via API - use document_id as the unique identifier
            doc_id = selected_card.get("document_id") or selected_card.get("card_id")
            if not doc_id:
                st.error("Cannot update: No document ID found for this card")
                return False

            # ChromaDB requires delete+add for updates (add with existing ID is ignored)
            # Step 1: Delete existing document
            try:
                api_client.post(
                    f"{config.fastapi_url}/api/vectordb/documents/remove",
                    data={
                        "collection_name": collection_name,
                        "ids": [doc_id]
                    },
                    timeout=30,
                    show_errors=False
                )
            except Exception:
                pass  # Ignore delete errors - document might not exist

            # Step 2: Add document with updated metadata
            update_response = api_client.post(
                f"{config.fastapi_url}/api/vectordb/documents/add",
                data={
                    "collection_name": collection_name,
                    "documents": [selected_card.get("content", "")],
                    "ids": [doc_id],
                    "metadatas": [sanitized]
                },
                timeout=30
            )
            return update_response is not None
        except Exception as e:
            st.error(f"Failed to update status: {e}")
            return False

    with status_row[1]:
        can_review = review_status == "DRAFT"
        if st.button(
            "Reviewed",
            key=f"review_card_{editor_key}",
            disabled=not can_review,
            use_container_width=True,
            help="Mark as reviewed after approval"
        ):
            if handle_status_change("REVIEWED"):
                st.success("Marked as Reviewed!")
                st.rerun()

    with status_row[2]:
        can_publish = review_status != "PUBLISHED"
        if st.button(
            "Publish",
            key=f"publish_card_{editor_key}",
            disabled=not can_publish,
            use_container_width=True,
            help="Publish for execution"
        ):
            if handle_status_change("PUBLISHED"):
                st.success("Published!")
                st.rerun()

    with status_row[3]:
        # Can only reset REVIEWED to DRAFT (not PUBLISHED - that's final)
        can_reset = review_status == "REVIEWED"
        if st.button(
            "Draft",
            key=f"reset_card_{editor_key}",
            disabled=not can_reset,
            use_container_width=True,
            help="Reset reviewed card to draft (published cards are final)"
        ):
            if handle_status_change("DRAFT"):
                st.success("Reset to Draft!")
                st.rerun()

    st.markdown("---")

    # =========================================================================
    # MAIN LAYOUT: Left (Test Plan Section) | Right (Test Card Editor)
    # =========================================================================

    # Apply shared CSS for consistent side-by-side layout
    st.markdown(get_sidebyside_css(), unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1])

    # =========================================================================
    # LEFT COLUMN: Source Test Plan Section Display
    # =========================================================================
    with left_col:
        st.markdown("##### Source Test Plan Section")

        # Find matching section based on requirement ID
        matching_section = None
        requirement_id = selected_card.get("requirement_id", "")

        for section in sections:
            for proc in section.get("test_procedures", []):
                if proc.get("id") == requirement_id or proc.get("requirement_id") == requirement_id:
                    matching_section = section
                    break
            if matching_section:
                break

        # Section selector if no auto-match
        if matching_section:
            st.success(f"Matched: {matching_section.get('section_title', 'Untitled')[:40]}...")
        else:
            section_titles = [s.get("section_title", f"Section {i+1}") for i, s in enumerate(sections)]
            selected_section_title = st.selectbox(
                "Select Section",
                options=["(Auto-match)"] + section_titles,
                key="manual_section_select_sidebyside"
            )

            if selected_section_title != "(Auto-match)":
                section_idx = section_titles.index(selected_section_title)
                matching_section = sections[section_idx]

        # Display section content in document-like container
        if matching_section:
            section_title = matching_section.get("section_title", "Untitled")
            section_rules = matching_section.get("synthesized_rules", "")
            section_procedures = matching_section.get("test_procedures", [])

            # Document-like container
            content_html = f'''
            <div style="font-size: 1.1em; font-weight: 600; color: #222; margin-bottom: 12px; border-bottom: 2px solid #333; padding-bottom: 6px;">
                {section_title}
            </div>
            '''

            # Requirements
            if section_rules:
                content_html += '<div style="font-size: 0.85em; font-weight: 600; color: #444; margin: 12px 0 6px 0;">Requirements:</div>'
                content_html += _markdown_to_document_html(section_rules)

            # Test procedures summary
            if section_procedures:
                content_html += f'<div style="font-size: 0.85em; font-weight: 600; color: #444; margin: 16px 0 8px 0;">Test Procedures ({len(section_procedures)}):</div>'
                for idx, proc in enumerate(section_procedures, 1):
                    proc_title = proc.get("title", f"Test {idx}")
                    proc_objective = proc.get("objective", "")[:100]
                    content_html += f'''
                    <div style="background: #f8f9fa; padding: 8px 12px; margin: 6px 0; border-radius: 4px; border-left: 3px solid #0066cc;">
                        <strong style="font-size: 0.9em;">{proc_title}</strong>
                        <p style="font-size: 0.8em; color: #666; margin: 4px 0 0 0;">{proc_objective}{"..." if len(proc.get("objective", "")) > 100 else ""}</p>
                    </div>
                    '''

            # Render in document-like container (uses shared source-document-panel class)
            st.markdown(
                f'''<div class="source-document-panel">{content_html}</div>''',
                unsafe_allow_html=True
            )
        else:
            st.info("Select a test plan section to display")

    # =========================================================================
    # RIGHT COLUMN: Test Card Editor (WYSIWYG)
    # =========================================================================
    with right_col:
        version_num = selected_card.get("version_number", 1)
        st.markdown(f"##### Test Card v{version_num}")

        # Version selector (if multiple versions exist)
        card_versions = selected_card.get("versions", [])
        if len(card_versions) > 1:
            with st.expander("Version History", expanded=False):
                for v in card_versions[:5]:
                    st.caption(f"v{v.get('version_number', '?')} - {v.get('created_at', 'Unknown')[:10]}")

        # Parse test card content
        card_content = selected_card.get("content", "")
        parsed_fields = _parse_markdown_table(card_content)

        # Test Card Title
        edited_title = st.text_input(
            "Test Title",
            value=card_metadata.get("test_title", selected_card.get("title", "")),
            key=f"title_{editor_key}",
            placeholder="Test Card Title"
        )

        # Test Objective (WYSIWYG)
        st.markdown('<div style="font-size: 0.85em; color: #666; margin: 8px 0 4px 0;">Test Objective</div>', unsafe_allow_html=True)

        objective_text = card_metadata.get("objective", "")
        if objective_text and not objective_text.strip().startswith("<"):
            objective_html = _markdown_to_document_html(objective_text)
        else:
            objective_html = objective_text

        edited_objective_html = st_quill(
            value=objective_html,
            html=True,
            toolbar=[
                ['bold', 'italic', 'underline'],
                [{'list': 'ordered'}, {'list': 'bullet'}],
                ['clean']
            ],
            key=f"quill_objective_{editor_key}",
            placeholder="What is this test verifying?"
        )

        # Test Setup (WYSIWYG)
        st.markdown('<div style="font-size: 0.85em; color: #666; margin: 8px 0 4px 0;">Test Setup</div>', unsafe_allow_html=True)

        setup_text = card_metadata.get("setup", "")
        if setup_text and not setup_text.strip().startswith("<"):
            setup_html = _markdown_to_document_html(setup_text)
        else:
            setup_html = setup_text

        edited_setup_html = st_quill(
            value=setup_html,
            html=True,
            toolbar=[
                ['bold', 'italic', 'underline'],
                [{'list': 'ordered'}, {'list': 'bullet'}],
                ['clean']
            ],
            key=f"quill_setup_{editor_key}",
            placeholder="Prerequisites, equipment, and setup steps..."
        )

        # Requirement (WYSIWYG)
        st.markdown('<div style="font-size: 0.85em; color: #666; margin-bottom: 4px;">Requirement Being Tested</div>', unsafe_allow_html=True)

        requirement_text = card_metadata.get("requirement_text", "")
        if requirement_text and not requirement_text.strip().startswith("<"):
            requirement_html = _markdown_to_document_html(requirement_text)
        else:
            requirement_html = requirement_text

        edited_requirement_html = st_quill(
            value=requirement_html,
            html=True,
            toolbar=[
                ['bold', 'italic', 'underline'],
                [{'list': 'ordered'}, {'list': 'bullet'}],
                ['clean']
            ],
            key=f"quill_req_{editor_key}",
            placeholder="Enter the requirement being tested..."
        )

        # Test Procedures (WYSIWYG)
        st.markdown('<div style="font-size: 0.85em; color: #666; margin: 12px 0 4px 0;">Test Procedures & Steps</div>', unsafe_allow_html=True)

        procedures_text = parsed_fields.get("procedures", "")
        if procedures_text and not procedures_text.strip().startswith("<"):
            procedures_html = _markdown_to_document_html(procedures_text)
        else:
            procedures_html = procedures_text

        edited_procedures_html = st_quill(
            value=procedures_html,
            html=True,
            toolbar=[
                [{'header': [1, 2, 3, False]}],
                ['bold', 'italic', 'underline'],
                [{'list': 'ordered'}, {'list': 'bullet'}],
                [{'indent': '-1'}, {'indent': '+1'}],
                ['clean']
            ],
            key=f"quill_proc_{editor_key}",
            placeholder="Enter test procedures and steps..."
        )

        # Expected Results (WYSIWYG)
        st.markdown('<div style="font-size: 0.85em; color: #666; margin: 12px 0 4px 0;">Expected Results</div>', unsafe_allow_html=True)

        expected_text = parsed_fields.get("expected_results", "")
        if expected_text and not expected_text.strip().startswith("<"):
            expected_html = _markdown_to_document_html(expected_text)
        else:
            expected_html = expected_text

        edited_expected_html = st_quill(
            value=expected_html,
            html=True,
            toolbar=[
                ['bold', 'italic'],
                [{'list': 'ordered'}, {'list': 'bullet'}],
                ['clean']
            ],
            key=f"quill_expected_{editor_key}",
            placeholder="Enter expected results..."
        )

        # Pass/Fail Criteria (uses shared TEXT_AREA_STANDARD height)
        criteria_cols = st.columns(2)
        with criteria_cols[0]:
            st.markdown('<div class="field-label-success">Pass Criteria</div>', unsafe_allow_html=True)
            edited_pass_criteria = st.text_area(
                "Pass Criteria",
                value=card_metadata.get("pass_criteria", ""),
                height=TEXT_AREA_STANDARD,
                key=f"pass_criteria_{editor_key}",
                placeholder="When does this test pass?",
                label_visibility="collapsed"
            )
        with criteria_cols[1]:
            st.markdown('<div class="field-label-danger">Fail Criteria</div>', unsafe_allow_html=True)
            edited_fail_criteria = st.text_area(
                "Fail Criteria",
                value=card_metadata.get("fail_criteria", ""),
                height=TEXT_AREA_STANDARD,
                key=f"fail_criteria_{editor_key}",
                placeholder="When does this test fail?",
                label_visibility="collapsed"
            )

        # Execution Status Section (Inline)
        st.markdown('<div style="font-size: 0.85em; color: #666; margin: 12px 0 4px 0;">Execution Status</div>', unsafe_allow_html=True)

        exec_cols = st.columns([2, 1, 1])

        with exec_cols[0]:
            execution_status = st.selectbox(
                "Status",
                options=["not_executed", "in_progress", "completed", "failed"],
                format_func=lambda x: {
                    "not_executed": "Not Executed",
                    "in_progress": "In Progress",
                    "completed": "Completed",
                    "failed": "Failed"
                }.get(x, x),
                index=["not_executed", "in_progress", "completed", "failed"].index(
                    card_metadata.get("execution_status", "not_executed")
                ),
                key=f"status_{editor_key}",
                label_visibility="collapsed"
            )

        with exec_cols[1]:
            passed = st.checkbox(
                "✅ Pass",
                value=str(card_metadata.get("passed", "false")).lower() == "true",
                key=f"passed_{editor_key}"
            )

        with exec_cols[2]:
            failed = st.checkbox(
                "❌ Fail",
                value=str(card_metadata.get("failed", "false")).lower() == "true",
                key=f"failed_{editor_key}"
            )

        # Execution Notes (uses shared TEXT_AREA_STANDARD height)
        st.markdown('<div class="field-label">Execution Notes</div>', unsafe_allow_html=True)
        notes = st.text_area(
            "Execution Notes",
            value=card_metadata.get("notes", ""),
            height=TEXT_AREA_STANDARD,
            key=f"notes_{editor_key}",
            placeholder="Add any observations or comments...",
            label_visibility="collapsed"
        )

        # Review checkbox and Save button row
        st.markdown("---")
        review_save_cols = st.columns([1, 1])

        with review_save_cols[0]:
            is_reviewed = review_status in ["REVIEWED", "PUBLISHED"]

            # Define callback for checkbox change (only fires on actual change)
            def on_review_checkbox_change():
                """Handle review checkbox change via callback to prevent infinite loops."""
                checkbox_key = f"mark_reviewed_{editor_key}"
                checkbox_value = st.session_state.get(checkbox_key, False)
                current_status = review_status  # Capture current status

                if checkbox_value and current_status == "DRAFT":
                    # User checked the box - update to REVIEWED
                    if handle_status_change("REVIEWED"):
                        st.session_state[f"status_updated_{editor_key}"] = True
                elif not checkbox_value and current_status == "REVIEWED":
                    # User unchecked the box - reset to DRAFT
                    if handle_status_change("DRAFT"):
                        st.session_state[f"status_updated_{editor_key}"] = True

            mark_reviewed = st.checkbox(
                "✅ Mark as Reviewed",
                value=is_reviewed,
                key=f"mark_reviewed_{editor_key}",
                help="Check to mark this test card as reviewed",
                on_change=on_review_checkbox_change,
                disabled=review_status == "PUBLISHED"  # Can't uncheck published cards
            )

            # Check if status was updated by callback and rerun to refresh data
            if st.session_state.pop(f"status_updated_{editor_key}", False):
                st.success("Status updated!")
                st.rerun()

        # Get current checkbox state for save (may have changed since page load)
        current_mark_reviewed = st.session_state.get(f"mark_reviewed_{editor_key}", is_reviewed)
        if current_mark_reviewed and review_status == "DRAFT":
            final_review_status = "REVIEWED"
        elif not current_mark_reviewed and review_status == "REVIEWED":
            final_review_status = "DRAFT"
        else:
            final_review_status = review_status

        with review_save_cols[1]:
            save_clicked = st.button("💾 Save Changes", key=f"save_{editor_key}", type="primary", use_container_width=True)

        if save_clicked:
            # Build updated metadata with all new fields
            updated_metadata = dict(card_metadata)
            updated_metadata.update({
                "test_title": edited_title,
                "objective": edited_objective_html or objective_text,
                "setup": edited_setup_html or setup_text,
                "requirement_text": edited_requirement_html or requirement_text,
                "pass_criteria": edited_pass_criteria,
                "fail_criteria": edited_fail_criteria,
                "review_status": final_review_status,
                "execution_status": execution_status,
                "passed": str(passed).lower(),
                "failed": str(failed).lower(),
                "notes": notes,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })

            # Reconstruct content with edited fields (enhanced format)
            test_id = selected_card.get("requirement_id") or parsed_fields.get("test_id", "")

            # Build updated content with all fields
            procedures_clean = edited_procedures_html or procedures_text
            expected_clean = edited_expected_html or expected_text
            objective_clean = edited_objective_html or objective_text
            setup_clean = edited_setup_html or setup_text
            acceptance = parsed_fields.get("acceptance_criteria", "")
            dependencies = parsed_fields.get("dependencies", "")

            # Enhanced content format with all fields
            content_parts = []
            content_parts.append(f"## {test_id}: {edited_title}\n")
            if objective_clean:
                content_parts.append(f"**Objective:** {objective_clean}\n")
            if setup_clean:
                content_parts.append(f"**Setup:** {setup_clean}\n")
            content_parts.append(f"**Procedures:**\n{procedures_clean}\n")
            content_parts.append(f"**Expected Results:** {expected_clean}\n")
            if edited_pass_criteria:
                content_parts.append(f"**Pass Criteria:** {edited_pass_criteria}\n")
            if edited_fail_criteria:
                content_parts.append(f"**Fail Criteria:** {edited_fail_criteria}\n")
            if acceptance:
                content_parts.append(f"**Acceptance Criteria:** {acceptance}\n")
            if dependencies:
                content_parts.append(f"**Dependencies:** {dependencies}\n")
            content_parts.append(f"\n| Executed | Pass | Fail | Notes |\n")
            content_parts.append(f"|----------|------|------|-------|\n")
            content_parts.append(f"| ({execution_status}) | ({passed}) | ({failed}) | {notes} |\n")

            updated_content = "".join(content_parts)

            # Save as new version (pass document_id for ChromaDB-only cards)
            success = _save_test_card(
                card_id=selected_card.get("card_id"),
                plan_id=plan_id,
                updated_content=updated_content,
                updated_metadata=updated_metadata,
                document_id=selected_card.get("document_id")
            )

            if success:
                st.success("Test card saved successfully!")
                st.rerun()


if __name__ == "__main__":
    render_test_card_sidebyside_editor()
