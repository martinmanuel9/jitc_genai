"""
Test Card Viewer Component - Simplified
Generate and execute test cards from test plans.
"""

import streamlit as st
import pandas as pd
import json
from config.settings import config
from app_lib.api.client import api_client
from datetime import datetime
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


def render_test_card_generator():
    """Generate test cards from a test plan - simplified workflow"""
    st.subheader("Generate Test Cards")

    try:
        # Fetch available test plans
        response = api_client.get(
            f"{config.fastapi_url}/api/vectordb/documents?collection_name=generated_test_plan",
            timeout=30
        )

        doc_ids = response.get("ids", [])
        metadatas = response.get("metadatas", [])

        if not doc_ids:
            st.info("No test plans found. Generate a test plan first using the Document Generator.")
            return

        # Create simple dropdown options - just show document name for consistency
        plan_options = {
            m.get('title', 'Untitled'): doc_id
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
        selected_metadata = next(m for doc_id, m in zip(doc_ids, metadatas) if doc_id == selected_doc_id)

        # Show plan details
        with st.expander("Test Plan Details"):
            st.text(f"Document ID: {selected_doc_id}")
            st.text(f"Generated: {selected_metadata.get('generated_at', 'N/A')}")
            st.text(f"Sections: {selected_metadata.get('total_sections', 0)}")
            st.text(f"Requirements: {selected_metadata.get('total_requirements', 0)}")

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

        with col1:
            if st.button("Generate Test Cards", type="primary", use_container_width=True):
                with st.spinner("Submitting generation request..."):
                    try:
                        response = api_client.post(
                            f"{config.endpoints.doc_gen}/generate-test-cards-from-plan-async",
                            data={
                                "test_plan_id": selected_doc_id,
                                "collection_name": "generated_test_plan",
                                "format": "markdown_table"
                            },
                            timeout=30
                        )

                        job_id = response.get("job_id")
                        st.session_state.testcard_job_id = job_id
                        st.session_state.testcard_job_status = "queued"
                        st.session_state.selected_test_plan_id = selected_doc_id
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
        response = api_client.get(
            f"{config.fastapi_url}/api/vectordb/documents?collection_name=generated_test_plan",
            timeout=30
        )

        doc_ids = response.get("ids", [])
        metadatas = response.get("metadatas", [])

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

        if not test_cards:
            st.info("No test cards found for this test plan. Generate test cards first.")
            return

        st.success(f"Found {total_count} test cards")

        # Display test cards in editable table format
        cards_data = []
        card_id_map = {}  # Map row index to card document_id for updates

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
                # Detect changes and prepare updates
                updates = []
                for idx in range(len(df)):
                    if idx < len(edited_df):
                        # Check if any values changed
                        original = df.iloc[idx]
                        edited = edited_df.iloc[idx]

                        if not original.equals(edited):
                            document_id = card_id_map.get(idx)
                            if document_id:
                                updates.append({
                                    "document_id": document_id,
                                    "updates": {
                                        "document_name": str(edited["Test Title"]),
                                        "requirement_text": str(edited["Requirement"]),
                                        "execution_status": str(edited["Status"]),
                                        "passed": str(edited["Pass"]).lower(),
                                        "failed": str(edited["Fail"]).lower(),
                                        "notes": str(edited["Notes"])
                                    }
                                })

                if updates:
                    try:
                        # Call API to update test cards
                        import requests
                        update_response = requests.post(
                            f"{config.fastapi_url}/api/doc_gen/test-cards/bulk-update",
                            json={
                                "collection_name": "test_cards",
                                "updates": updates
                            },
                            timeout=30
                        )

                        if update_response.status_code == 200:
                            result = update_response.json()
                            st.success(f"Successfully updated {result.get('updated_count', 0)} test cards")
                            st.rerun()
                        else:
                            st.error(f"Update failed: {update_response.text}")

                    except Exception as e:
                        st.error(f"Failed to save changes: {str(e)}")
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
                        import requests

                        # Build update payload
                        update_payload = {
                            "document_name": edited_title,
                            "requirement_text": edited_requirement,
                            "execution_status": edited_status,
                            "passed": str(edited_passed).lower(),
                            "failed": str(edited_failed).lower(),
                            "notes": edited_notes
                        }

                        # Reconstruct markdown table if procedures were edited
                        if procedures_changed:
                            test_id = selected_card.get("test_id", "")

                            # Reconstruct the markdown table with updated fields
                            reconstructed_table = f"""| Test ID | Test Title | Procedures | Expected Results | Acceptance Criteria | Dependencies | Executed | Pass | Fail | Notes |
|---------|------------|------------|------------------|---------------------|--------------|----------|------|------|-------|
| {test_id} | {edited_title} | {edited_procedures_text} | {edited_expected_results} | {edited_acceptance_criteria} | {edited_dependencies} | () | () | () | |"""

                            update_payload["content"] = reconstructed_table

                        update_response = requests.post(
                            f"{config.fastapi_url}/api/doc_gen/test-cards/bulk-update",
                            json={
                                "collection_name": "test_cards",
                                "updates": [{
                                    "document_id": selected_card.get("document_id"),
                                    "updates": update_payload
                                }]
                            },
                            timeout=30
                        )

                        if update_response.status_code == 200:
                            st.success("Test card updated successfully!")
                            st.rerun()
                        else:
                            st.error(f"Update failed: {update_response.text}")

                    except Exception as e:
                        st.error(f"Failed to save changes: {str(e)}")
                else:
                    st.info("No changes detected")

    except Exception as e:
        st.error(f"Failed to load test cards: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
