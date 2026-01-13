"""
Test Plan Version Manager Component

Provides version status management and comparison features for test plans.
"""

import streamlit as st
import pandas as pd
import json
import re
import html
from typing import List, Dict, Any, Optional
from datetime import datetime
from config.settings import config
from app_lib.api.client import api_client


def _clean_content_for_display(content: str) -> str:
    """Clean HTML/markdown content for human-readable display."""
    if not content:
        return "(empty)"

    # Unescape HTML entities
    text = html.unescape(content)

    # Remove HTML tags but preserve line breaks
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)

    # Clean up markdown formatting for readability
    # Convert headers to plain text with emphasis
    text = re.sub(r'^#{1,6}\s*(.+)$', r'=== \1 ===', text, flags=re.MULTILINE)

    # Convert bold/italic markers to plain text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
    text = re.sub(r'__([^_]+)__', r'\1', text)      # Bold
    text = re.sub(r'_([^_]+)_', r'\1', text)        # Italic

    # Clean up extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


def render_version_manager():
    """
    Render the version manager interface.

    Features:
    - View test plan versions
    - Create new drafts from existing versions
    - Compare versions side-by-side
    - Manage version status (Draft, Reviewed, Published)
    """
    st.header("Test Plan Version Manager")
    st.caption("Create drafts, compare versions, and manage the review workflow.")

    try:
        # Fetch all test plans from versioning API
        plans_response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-plans",
            timeout=30
        )
        plans = plans_response.get("plans", []) if plans_response else []

        if not plans:
            st.info("No test plans found. Generate a test plan first using the Document Generator.")
            return

        # Plan selection
        plan_options = {
            f"{p.get('title', 'Untitled')} (ID: {p.get('id')})": p
            for p in plans
        }

        selected_plan_label = st.selectbox(
            "Select Test Plan:",
            list(plan_options.keys()),
            key="version_manager_plan"
        )

        if not selected_plan_label:
            return

        selected_plan = plan_options[selected_plan_label]
        plan_id = selected_plan.get("id")
        plan_title = selected_plan.get("title", "Untitled")
        plan_key = selected_plan.get("plan_key", "")

        st.markdown("---")

        # Fetch versions for this plan
        versions_response = api_client.get(
            f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions",
            timeout=30
        )
        versions = versions_response.get("versions", []) if versions_response else []

        # Tabs for different operations
        tab1, tab2, tab3 = st.tabs(["📋 Versions", "➕ Create Draft", "🔍 Compare"])

        with tab1:
            render_versions_list(plan_id, plan_title, versions)

        with tab2:
            render_create_draft(plan_id, plan_key, plan_title, versions)

        with tab3:
            render_compare_versions(plan_id, versions)

    except Exception as e:
        st.error(f"Failed to load version manager: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


def render_versions_list(plan_id: int, plan_title: str, versions: List[dict]):
    """Display list of versions with status management."""
    st.subheader(f"Versions of: {plan_title}")

    if not versions:
        st.warning("No versions found for this test plan.")
        return

    st.success(f"Found {len(versions)} version(s)")

    # Display versions in a table
    version_data = []
    for v in versions:
        status = v.get("status", "draft")
        status_badge = {
            "draft": "📝 Draft",
            "final": "✅ Final",
            "published": "🚀 Published"
        }.get(status, status)

        version_data.append({
            "Version": f"v{v.get('version_number', '?')}",
            "Document ID": v.get("document_id", "")[:25] + "..." if v.get("document_id", "") else "N/A",
            "Status": status_badge,
            "Created": v.get("created_at", "")[:19] if v.get("created_at") else "N/A",
            "Based On": f"v{v.get('based_on_version_id', '-')}" if v.get('based_on_version_id') else "-",
            "_id": v.get("id"),
            "_status_raw": status
        })

    df = pd.DataFrame(version_data)
    display_df = df.drop(columns=["_id", "_status_raw"])
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Status management
    st.markdown("### Update Version Status")
    st.caption("Change the status of a version: Draft → Final → Published")

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        version_options = {
            f"v{v.get('version_number')} ({v.get('status', 'draft')})": v
            for v in versions
        }
        selected_version_label = st.selectbox(
            "Select version:",
            list(version_options.keys()),
            key="status_version_select"
        )

    with col2:
        new_status = st.selectbox(
            "New status:",
            ["draft", "final", "published"],
            key="new_status_select"
        )

    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Update Status", type="primary", use_container_width=True):
            if selected_version_label:
                selected_version = version_options[selected_version_label]
                version_id = selected_version.get("id")

                try:
                    response = api_client.patch(
                        f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions/{version_id}/status",
                        data={"status": new_status},
                        timeout=30
                    )
                    if response:
                        st.success(f"Version updated to {new_status}!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Failed to update status: {e}")


def render_create_draft(plan_id: int, plan_key: str, plan_title: str, versions: List[dict]):
    """Create a new draft version from an existing version."""
    st.subheader("Create New Draft")
    st.caption("Create a new draft version based on an existing version for editing.")

    if not versions:
        st.warning("No versions available to create a draft from.")
        return

    # Select base version
    version_options = {
        f"v{v.get('version_number')} - {v.get('status', 'draft')} ({v.get('document_id', '')[:20]}...)": v
        for v in versions
    }

    selected_base_label = st.selectbox(
        "Base version (copy from):",
        list(version_options.keys()),
        key="create_draft_base_version"
    )

    if not selected_base_label:
        return

    base_version = version_options[selected_base_label]
    base_version_id = base_version.get("id")
    base_document_id = base_version.get("document_id")

    st.info(f"New draft will be based on **v{base_version.get('version_number')}** (Document: {base_document_id[:30]}...)")

    # Show what will happen
    with st.expander("How it works", expanded=False):
        st.markdown("""
        **Creating a new draft:**
        1. Copies the content from the selected base version
        2. Creates a new version number (v{next})
        3. Links to the base version for tracking
        4. New draft starts with status "Draft"

        **Use cases:**
        - Make changes without affecting the published version
        - Create alternative versions for comparison
        - Track change history across versions
        """.format(next=len(versions) + 1))

    # Create button
    if st.button("Create New Draft", type="primary", use_container_width=True):
        with st.spinner("Creating new draft version..."):
            try:
                # Fetch the content from the base version's document
                # Try test_plan_drafts first, then generated_test_plan
                content = None
                for collection in ["test_plan_drafts", "generated_test_plan"]:
                    try:
                        docs_response = api_client.get(
                            f"{config.fastapi_url}/api/vectordb/documents",
                            params={"collection_name": collection},
                            timeout=30,
                            show_errors=False
                        )
                        if docs_response:
                            doc_ids = docs_response.get("ids", [])
                            documents = docs_response.get("documents", [])
                            for idx, doc_id in enumerate(doc_ids):
                                if doc_id == base_document_id:
                                    content = documents[idx] if idx < len(documents) else None
                                    break
                        if content:
                            break
                    except Exception:
                        continue

                if not content:
                    st.error("Could not find source document content. Please try a different version.")
                    return

                # Generate new document ID
                import uuid
                new_doc_id = f"draft_{plan_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

                # Save to test_plan_drafts collection
                api_client.post(
                    f"{config.fastapi_url}/api/vectordb/documents/add",
                    data={
                        "collection_name": "test_plan_drafts",
                        "documents": [content],
                        "ids": [new_doc_id],
                        "metadatas": [{
                            "title": plan_title,
                            "plan_key": plan_key,
                            "type": "test_plan_full",
                            "status": "DRAFT",
                            "based_on_version": base_version_id,
                            "created_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat()
                        }]
                    },
                    timeout=30
                )

                # Create version record in PostgreSQL
                version_response = api_client.post(
                    f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions",
                    data={
                        "document_id": new_doc_id,
                        "based_on_version_id": base_version_id
                    },
                    timeout=30
                )

                if version_response:
                    new_version_num = version_response.get("version_number", "?")
                    st.success(f"Created new draft version v{new_version_num}!")
                    st.info(f"Document ID: `{new_doc_id}`")
                    st.balloons()
                    st.rerun()

            except Exception as e:
                st.error(f"Failed to create draft: {e}")
                import traceback
                st.code(traceback.format_exc())


def render_compare_versions(plan_id: int, versions: List[dict]):
    """Compare two versions side-by-side."""
    st.subheader("Compare Versions")
    st.caption("Compare two versions to see what changed (Was/Is comparison).")

    if len(versions) < 2:
        st.warning("Need at least 2 versions to compare.")
        return

    col1, col2 = st.columns(2)

    version_options = {
        f"v{v.get('version_number')} - {v.get('status', 'draft')}": v
        for v in versions
    }

    with col1:
        st.markdown("**Was (Previous)**")
        was_label = st.selectbox(
            "Previous version:",
            list(version_options.keys()),
            key="compare_was_version",
            index=min(1, len(versions) - 1)  # Default to second version if available
        )

    with col2:
        st.markdown("**Is (Current)**")
        is_label = st.selectbox(
            "Current version:",
            list(version_options.keys()),
            key="compare_is_version",
            index=0  # Default to first (latest) version
        )

    if was_label and is_label:
        was_version = version_options[was_label]
        is_version = version_options[is_label]

        if was_version.get("id") == is_version.get("id"):
            st.warning("Please select two different versions to compare.")
            return

        # Compare button
        compare_col1, compare_col2 = st.columns([1, 1])

        with compare_col1:
            if st.button("Compare Versions", type="primary", use_container_width=True):
                with st.spinner("Comparing versions..."):
                    try:
                        compare_response = api_client.post(
                            f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/versions/compare",
                            data={
                                "version_id_was": was_version.get("id"),
                                "version_id_is": is_version.get("id")
                            },
                            timeout=60
                        )

                        if compare_response:
                            st.session_state["comparison_result"] = compare_response
                            st.rerun()

                    except Exception as e:
                        st.error(f"Comparison failed: {e}")

        with compare_col2:
            if st.button("Export Comparison (DOCX)", use_container_width=True):
                try:
                    import requests
                    export_url = (
                        f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/"
                        f"versions/{was_version.get('id')}/export-comparison/{is_version.get('id')}"
                    )
                    response = requests.get(export_url, timeout=60)

                    if response.status_code == 200:
                        st.download_button(
                            label="Download DOCX",
                            data=response.content,
                            file_name=f"comparison_v{was_version.get('version_number')}_to_v{is_version.get('version_number')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    else:
                        st.error(f"Export failed: {response.text}")
                except Exception as e:
                    st.error(f"Export failed: {e}")

        # Display comparison results
        if "comparison_result" in st.session_state:
            result = st.session_state["comparison_result"]

            st.markdown("---")
            st.markdown("### Comparison Results")

            # Summary metrics
            total_changes = result.get("total_changes", 0)
            differences = result.get("differences", [])

            # Count by change type
            added_count = sum(1 for d in differences if d.get("change_type") == "added")
            deleted_count = sum(1 for d in differences if d.get("change_type") == "deleted")
            modified_count = sum(1 for d in differences if d.get("change_type") == "modified")

            metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)

            with metrics_col1:
                st.metric("Total Changes", total_changes)
            with metrics_col2:
                st.metric("Added", added_count)
            with metrics_col3:
                st.metric("Removed", deleted_count)
            with metrics_col4:
                st.metric("Modified", modified_count)

            # Differences
            if differences:
                st.markdown("### Changes")

                for diff_idx, diff in enumerate(differences):
                    # Service returns "change_type" not "type"
                    change_type = diff.get("change_type", "modified")
                    section_title = diff.get("section_title", f"Section {diff_idx + 1}")
                    field_name = diff.get("field", "content")

                    if change_type == "added":
                        icon = "🟢"
                        label = "Added"
                    elif change_type == "deleted":
                        icon = "🔴"
                        label = "Removed"
                    else:
                        icon = "🟡"
                        label = "Modified"

                    with st.expander(f"{icon} {label}: {section_title} ({field_name})", expanded=True):
                        if change_type == "modified":
                            # Service returns "old_value" and "new_value" not "was" and "is"
                            was_content = _clean_content_for_display(diff.get("old_value", "") or "")
                            is_content = _clean_content_for_display(diff.get("new_value", "") or "")

                            diff_col1, diff_col2 = st.columns(2)
                            with diff_col1:
                                st.markdown("**Was (Previous)**")
                                st.text_area(
                                    "Previous",
                                    value=was_content[:3000],
                                    height=250,
                                    key=f"was_diff_{diff_idx}",
                                    label_visibility="collapsed"
                                )
                            with diff_col2:
                                st.markdown("**Is (Current)**")
                                st.text_area(
                                    "Current",
                                    value=is_content[:3000],
                                    height=250,
                                    key=f"is_diff_{diff_idx}",
                                    label_visibility="collapsed"
                                )
                        elif change_type == "added":
                            st.markdown("**New content:**")
                            new_val = _clean_content_for_display(diff.get("new_value", "") or "")
                            st.text_area(
                                "Added",
                                value=new_val[:3000],
                                height=200,
                                key=f"added_diff_{diff_idx}",
                                label_visibility="collapsed"
                            )
                        elif change_type == "deleted":
                            st.markdown("**Removed content:**")
                            old_val = _clean_content_for_display(diff.get("old_value", "") or "")
                            st.text_area(
                                "Removed",
                                value=old_val[:3000],
                                height=200,
                                key=f"removed_diff_{diff_idx}",
                                label_visibility="collapsed"
                            )
            else:
                st.info("No differences found between the selected versions.")

            # Export options
            st.markdown("---")
            st.markdown("### Export Comparison")

            export_col1, export_col2, export_col3 = st.columns([1, 1, 1])

            # Generate text export content
            was_ver = result.get("was_version", {})
            is_ver = result.get("is_version", {})

            text_export = f"""VERSION COMPARISON REPORT
========================

Previous Version: v{was_ver.get('version_number', '?')} ({was_ver.get('status', 'unknown')})
Current Version: v{is_ver.get('version_number', '?')} ({is_ver.get('status', 'unknown')})
Total Changes: {total_changes}
- Added: {added_count}
- Removed: {deleted_count}
- Modified: {modified_count}

"""
            for diff_idx, diff in enumerate(differences):
                change_type = diff.get("change_type", "modified")
                section_title = diff.get("section_title", f"Section {diff_idx + 1}")
                field_name = diff.get("field", "content")

                text_export += f"\n{'='*60}\n"
                text_export += f"[{change_type.upper()}] {section_title} ({field_name})\n"
                text_export += f"{'='*60}\n\n"

                if change_type == "modified":
                    was_val = _clean_content_for_display(diff.get("old_value", "") or "")
                    is_val = _clean_content_for_display(diff.get("new_value", "") or "")
                    text_export += f"--- WAS (Previous) ---\n{was_val}\n\n"
                    text_export += f"--- IS (Current) ---\n{is_val}\n\n"
                elif change_type == "added":
                    new_val = _clean_content_for_display(diff.get("new_value", "") or "")
                    text_export += f"--- ADDED ---\n{new_val}\n\n"
                elif change_type == "deleted":
                    old_val = _clean_content_for_display(diff.get("old_value", "") or "")
                    text_export += f"--- REMOVED ---\n{old_val}\n\n"

            with export_col1:
                st.download_button(
                    label="Download as Text",
                    data=text_export,
                    file_name=f"comparison_v{was_ver.get('version_number', '?')}_to_v{is_ver.get('version_number', '?')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )

            with export_col2:
                try:
                    import requests
                    was_version = version_options.get(was_label, {})
                    is_version = version_options.get(is_label, {})
                    export_url = (
                        f"{config.fastapi_url}/api/versioning/test-plans/{plan_id}/"
                        f"versions/{was_version.get('id')}/export-comparison/{is_version.get('id')}"
                    )
                    if st.button("Download as DOCX", use_container_width=True):
                        response = requests.get(export_url, timeout=60)
                        if response.status_code == 200:
                            st.download_button(
                                label="Save DOCX File",
                                data=response.content,
                                file_name=f"comparison_v{was_ver.get('version_number', '?')}_to_v{is_ver.get('version_number', '?')}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key="docx_download"
                            )
                        else:
                            st.error(f"DOCX export failed: {response.text[:200]}")
                except Exception as e:
                    st.error(f"DOCX export error: {e}")

            with export_col3:
                if st.button("Clear Comparison", use_container_width=True):
                    del st.session_state["comparison_result"]
                    st.rerun()

            # Show raw comparison data for debugging
            # with st.expander("Debug: Raw Comparison Data", expanded=False):
            #     st.json(result)


if __name__ == "__main__":
    render_version_manager()
