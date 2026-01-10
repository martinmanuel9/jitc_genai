"""
Test Card Viewer Component - Simplified
Generate and execute test cards from test plans.
"""

import streamlit as st
import pandas as pd
import json
import uuid
from typing import Dict, List, Optional, Tuple
from config.settings import config
from app_lib.api.client import api_client
from datetime import datetime, timezone
from components.job_status_monitor import JobStatusMonitor


def TestCardViewer():
    """
    Simplified component for managing test cards.
    Two workflows: Generate test cards, Execute test cards.
    """
    st.header("Test Cards")

    # Two simple tabs
    tab1, tab2 = st.tabs([
        "Generate Test Cards",
        "Execute Test Cards"
    ])

    with tab1:
        render_test_card_generator()

    with tab2:
        render_test_card_executor()


def _list_test_plans() -> Tuple[List[str], List[dict], Dict[str, dict]]:
    response = api_client.get(
        f"{config.fastapi_url}/api/vectordb/documents?collection_name=generated_test_plan",
        timeout=30
    )
    doc_ids = response.get("ids", [])
    metadatas = response.get("metadatas", [])
    metadata_map = {
        doc_id: (metadatas[idx] if idx < len(metadatas) else {})
        for idx, doc_id in enumerate(doc_ids)
    }
    return doc_ids, metadatas, metadata_map


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
                timeout=30
            )
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

        plan_options = {
            f"{m.get('title', 'Untitled')} ({doc_id[:8]}...)": doc_id
            for doc_id, m in zip(doc_ids, metadatas)
        }

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

        plan_record = _find_plan_record(plan_key, _fetch_plan_records())
        plan_versions = _list_plan_versions(plan_record["id"]) if plan_record else []
        selected_plan_version = None

        if plan_versions:
            version_options = {
                f"v{v['version_number']} ({v['document_id'][:8]}...)": v
                for v in plan_versions
            }
            selected_version_label = st.selectbox(
                "Plan Version",
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

        # Step 2: Generate Test Cards
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
            if st.button("Generate Test Cards", type="primary", use_container_width=True):
                if existing_count and not confirm_regen:
                    st.error("Please confirm regeneration to continue.")
                    return
                with st.spinner("Submitting generation request..."):
                    try:
                        response = api_client.post(
                            f"{config.endpoints.doc_gen}/generate-test-cards-from-plan-async",
                            data={
                                "test_plan_id": plan_doc_id_for_generation,
                                "collection_name": "generated_test_plan",
                                "format": "markdown_table"
                            },
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
                            "plan_doc_id": plan_doc_id_for_generation
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
                    st.warning(f"Test card versioning failed: {e}")

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


def render_test_card_executor():
    """Execute and track test cards"""
    st.subheader("Execute Test Cards")

    try:
        # Fetch available test plans
        doc_ids, metadatas, metadata_map = _list_test_plans()

        if not doc_ids:
            st.info("No test plans found.")
            return

        # Select test plan
        plan_options = {
            f"{m.get('title', 'Untitled')} ({doc_id[:20]}...)": doc_id
            for doc_id, m in zip(doc_ids, metadatas)
        }

        selected_plan = st.selectbox(
            "Select test plan to view test cards:",
            list(plan_options.keys()),
            key="executor_test_plan"
        )

        if not selected_plan:
            return

        selected_doc_id = plan_options[selected_plan]
        selected_metadata = metadata_map.get(selected_doc_id, {})
        plan_key = selected_metadata.get("plan_key") or selected_doc_id
        plan_title = selected_metadata.get("title", "Untitled Plan")
        plan_record = _find_plan_record(plan_key, _fetch_plan_records())

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
            total_count = len(test_cards)

        if not test_cards:
            st.info("No test cards found for this test plan. Generate test cards first.")
            return

        st.success(f"Found {total_count} test cards")

        # Display test cards in editable table format
        cards_data = []
        card_id_map = {}  # Map row index to card document_id for updates
        cards_by_id = {card.get("document_id"): card for card in test_cards}

        for idx, card in enumerate(test_cards):
            card_id_map[idx] = card.get("document_id", "")
            cards_data.append({
                "Test ID": card.get("test_id", "N/A"),
                "Test Title": card.get("document_name", "N/A"),
                "Requirement ID": card.get("requirement_id", "N/A"),
                "Requirement": card.get("requirement_text", "N/A") or "N/A",
                "Status": card.get("execution_status", "not_executed"),
                "Pass": str(card.get("passed", "false")).lower() == "true",
                "Fail": str(card.get("failed", "false")).lower() == "true",
                "Notes": card.get("notes", "")
            })

        df = pd.DataFrame(cards_data)

        # Configure editable columns
        column_config = {
            "Test ID": st.column_config.TextColumn("Test ID", disabled=True),
            "Test Title": st.column_config.TextColumn("Test Title", disabled=False),
            "Requirement ID": st.column_config.TextColumn("Requirement ID", disabled=True),
            "Requirement": st.column_config.TextColumn("Requirement", disabled=False, width="large"),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["not_executed", "in_progress", "completed", "failed"],
                required=True
            ),
            "Pass": st.column_config.CheckboxColumn("Pass"),
            "Fail": st.column_config.CheckboxColumn("Fail"),
            "Notes": st.column_config.TextColumn("Notes", disabled=False)
        }

        # Display editable dataframe
        edited_df = st.data_editor(
            df,
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            key="test_cards_editor"
        )

        # Save changes button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Save Changes", type="primary", use_container_width=True):
                updated_count = 0
                errors = []
                for idx in range(len(df)):
                    if idx < len(edited_df):
                        # Check if any values changed
                        original = df.iloc[idx]
                        edited = edited_df.iloc[idx]

                        if not original.equals(edited):
                            document_id = card_id_map.get(idx)
                            if document_id:
                                card = cards_by_id.get(document_id, {})
                                updates = {
                                    "document_name": str(edited["Test Title"]),
                                    "requirement_text": str(edited["Requirement"]),
                                    "execution_status": str(edited["Status"]),
                                    "passed": str(edited["Pass"]).lower(),
                                    "failed": str(edited["Fail"]).lower(),
                                    "notes": str(edited["Notes"])
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
                    st.success(f"Successfully updated {updated_count} test cards")
                    st.rerun()
                elif errors:
                    st.error("Some updates failed: " + "; ".join(errors))
                    if updated_count:
                        st.warning(f"{updated_count} test card updates succeeded before errors")
                else:
                    st.info("No changes detected")

        with col2:
            st.text("")  # Spacer

        # Export option
        st.markdown("---")
        st.markdown("### Export Test Cards")

        export_col1, export_col2 = st.columns(2)

        with export_col1:
            if st.button("Export to DOCX", use_container_width=True, type="primary"):
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
                            key="download_docx_execute_tab"
                        )
                    else:
                        st.error(f"Export failed: {export_response.text}")

                except Exception as e:
                    st.error(f"Export failed: {str(e)}")

        with export_col2:
            if st.button("Export to Markdown", use_container_width=True, type="secondary"):
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
                            key="download_md_execute_tab"
                        )
                    else:
                        st.error(f"Export failed: {export_response.text}")

                except Exception as e:
                    st.error(f"Export failed: {str(e)}")

        # Edit individual test card
        st.markdown("---")
        st.markdown("### Edit Individual Test Card")

        card_options = {
            f"{card.get('test_id', 'N/A')} - {card.get('document_name', 'N/A')}": card
            for card in test_cards
        }

        selected_card_key = st.selectbox(
            "Select a test card to edit:",
            list(card_options.keys()),
            key="selected_card"
        )

        if selected_card_key:
            selected_card = card_options[selected_card_key]

            # Store original values to detect changes
            original_values = {
                "test_title": selected_card.get("document_name", ""),
                "requirement_text": selected_card.get("requirement_text", ""),
                "procedures": selected_card.get("content", selected_card.get("content_preview", "")),  # Use full content
                "execution_status": selected_card.get("execution_status", "not_executed"),
                "passed": str(selected_card.get("passed", "false")).lower() == "true",
                "failed": str(selected_card.get("failed", "false")).lower() == "true",
                "notes": selected_card.get("notes", "")
            }

            st.markdown(f"**Test ID:** {selected_card.get('test_id', 'N/A')}")
            st.markdown(f"**Requirement ID:** {selected_card.get('requirement_id', 'N/A')}")

            # Editable fields
            edited_title = st.text_input(
                "Test Title:",
                value=original_values["test_title"],
                key="edit_test_title"
            )

            edited_requirement = st.text_area(
                "Requirement:",
                value=original_values["requirement_text"],
                height=100,
                key="edit_requirement"
            )

            # Parse markdown table to extract structured fields
            def parse_test_card_table(markdown_table):
                """Parse markdown table to extract test procedure fields"""
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
                        # Parse data row (skip header and separator)
                        data_row = lines[2] if len(lines) > 2 else ""
                        cells = [cell.strip() for cell in data_row.split('|')]

                        # Table format: | Test ID | Test Title | Procedures | Expected Results | Acceptance Criteria | Dependencies | Executed | Pass | Fail | Notes |
                        if len(cells) >= 7:
                            fields["procedures"] = cells[3] if len(cells) > 3 else ""
                            fields["expected_results"] = cells[4] if len(cells) > 4 else ""
                            fields["acceptance_criteria"] = cells[5] if len(cells) > 5 else ""
                            fields["dependencies"] = cells[6] if len(cells) > 6 else ""
                except Exception as e:
                    st.warning(f"Could not parse test card table: {e}")

                return fields

            # Parse current procedures
            parsed_fields = parse_test_card_table(original_values["procedures"])

            # Editable procedure fields
            st.markdown("### Test Procedure Details")

            edited_procedures_text = st.text_area(
                "Procedures/Steps:",
                value=parsed_fields["procedures"],
                height=100,
                key="edit_procedures_text",
                help="Enter test procedures/steps (use <br> for line breaks)"
            )

            edited_expected_results = st.text_area(
                "Expected Results:",
                value=parsed_fields["expected_results"],
                height=80,
                key="edit_expected_results",
                help="What should happen when the test is executed"
            )

            col1, col2 = st.columns(2)
            with col1:
                edited_acceptance_criteria = st.text_area(
                    "Acceptance Criteria:",
                    value=parsed_fields["acceptance_criteria"],
                    height=80,
                    key="edit_acceptance_criteria",
                    help="Criteria to determine if test passes"
                )

            with col2:
                edited_dependencies = st.text_area(
                    "Dependencies:",
                    value=parsed_fields["dependencies"],
                    height=80,
                    key="edit_dependencies",
                    help="Prerequisites or dependencies for this test"
                )

            # Execution tracking
            col1, col2 = st.columns(2)
            with col1:
                edited_status = st.selectbox(
                    "Execution Status:",
                    options=["not_executed", "in_progress", "completed", "failed"],
                    index=["not_executed", "in_progress", "completed", "failed"].index(original_values["execution_status"]),
                    key="edit_status"
                )

            with col2:
                st.markdown("**Test Result:**")
                result_col1, result_col2 = st.columns(2)
                with result_col1:
                    edited_passed = st.checkbox("Pass", value=original_values["passed"], key="edit_passed")
                with result_col2:
                    edited_failed = st.checkbox("Fail", value=original_values["failed"], key="edit_failed")

            edited_notes = st.text_area(
                "Notes:",
                value=original_values["notes"],
                height=100,
                key="edit_notes"
            )

            # Save button
            if st.button("Save Changes", type="primary", use_container_width=True, key="save_individual_card"):
                # Check if procedure fields changed
                procedures_changed = (
                    edited_procedures_text != parsed_fields["procedures"] or
                    edited_expected_results != parsed_fields["expected_results"] or
                    edited_acceptance_criteria != parsed_fields["acceptance_criteria"] or
                    edited_dependencies != parsed_fields["dependencies"]
                )

                # Check if anything changed
                changes_detected = (
                    edited_title != original_values["test_title"] or
                    edited_requirement != original_values["requirement_text"] or
                    procedures_changed or
                    edited_status != original_values["execution_status"] or
                    edited_passed != original_values["passed"] or
                    edited_failed != original_values["failed"] or
                    edited_notes != original_values["notes"]
                )

                if changes_detected:
                    try:
                        # Build update payload
                        update_payload = {
                            "document_name": edited_title,
                            "requirement_text": edited_requirement,
                            "execution_status": edited_status,
                            "passed": str(edited_passed).lower(),
                            "failed": str(edited_failed).lower(),
                            "notes": edited_notes
                        }
                        updated_content = selected_card.get("content") or selected_card.get("content_preview", "")

                        # Reconstruct markdown table if procedures were edited
                        if procedures_changed:
                            test_id = selected_card.get("test_id", "")

                            # Reconstruct the markdown table with updated fields
                            reconstructed_table = f"""| Test ID | Test Title | Procedures | Expected Results | Acceptance Criteria | Dependencies | Executed | Pass | Fail | Notes |
|---------|------------|------------|------------------|---------------------|--------------|----------|------|------|-------|
| {test_id} | {edited_title} | {edited_procedures_text} | {edited_expected_results} | {edited_acceptance_criteria} | {edited_dependencies} | () | () | () | |"""

                            updated_content = reconstructed_table

                        _create_test_card_version(
                            card=selected_card,
                            updates=update_payload,
                            updated_content=updated_content,
                            plan_key=plan_key,
                            plan_title=plan_title,
                            plan_doc_id=selected_doc_id
                        )

                        st.success("Test card updated successfully!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Failed to save changes: {str(e)}")
                else:
                    st.info("No changes detected")

    except Exception as e:
        st.error(f"Failed to load test cards: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
