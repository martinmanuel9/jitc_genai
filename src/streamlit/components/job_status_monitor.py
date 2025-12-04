"""
Reusable Job Status Monitor Component
Monitors async job status with progress updates and result handling.
Used for test plan generation, test card generation, document uploads, etc.
"""
import streamlit as st
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from config.settings import config
from app_lib.api.client import api_client


class JobStatusMonitor:
    """
    Reusable component for monitoring async job status.

    Example usage:
        monitor = JobStatusMonitor(
            job_id="job_123",
            session_key="my_job",
            status_endpoint="{config.endpoints.doc_gen}/status/{job_id}",
            result_endpoint="{config.endpoints.doc_gen}/result/{job_id}",
            job_name="Test Plan Generation"
        )
        monitor.render()
    """

    def __init__(
        self,
        job_id: str,
        session_key: str,
        status_endpoint: str,
        result_endpoint: Optional[str] = None,
        job_name: str = "Job",
        show_metrics: bool = True,
        show_elapsed_time: bool = True,
        allow_cancel: bool = False,
        cancel_endpoint: Optional[str] = None,
        on_completed: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_clear: Optional[Callable[[], None]] = None,
        auto_refresh_interval: Optional[int] = None,  # seconds
        auto_clear_on_complete: bool = False,  # Auto-clear when completed/failed
        custom_progress_renderer: Optional[Callable[[Dict[str, Any]], None]] = None,  # Custom progress display
    ):
        """
        Initialize the job status monitor.

        Args:
            job_id: Unique identifier for the job
            session_key: Key prefix for storing job state in session_state
            status_endpoint: API endpoint for checking job status (use {job_id} placeholder)
            result_endpoint: API endpoint for fetching results when completed
            job_name: Display name for the job type
            show_metrics: Whether to show progress metrics
            show_elapsed_time: Whether to show elapsed time
            allow_cancel: Whether to allow job cancellation
            cancel_endpoint: API endpoint for cancelling the job
            on_completed: Callback function when job completes (receives result data)
            on_clear: Callback function when user clears the job
            auto_refresh_interval: Auto-refresh interval in seconds (None = manual refresh only)
            auto_clear_on_complete: Automatically clear job when completed/failed
            custom_progress_renderer: Custom function to render progress UI (receives status_response)
        """
        self.job_id = job_id
        self.session_key = session_key
        self.status_endpoint = status_endpoint.format(job_id=job_id)
        self.result_endpoint = result_endpoint.format(job_id=job_id) if result_endpoint else None
        self.job_name = job_name
        self.show_metrics = show_metrics
        self.show_elapsed_time = show_elapsed_time
        self.allow_cancel = allow_cancel
        self.cancel_endpoint = cancel_endpoint.format(job_id=job_id) if cancel_endpoint else None
        self.on_completed = on_completed
        self.on_clear = on_clear
        self.auto_refresh_interval = auto_refresh_interval
        self.auto_clear_on_complete = auto_clear_on_complete
        self.custom_progress_renderer = custom_progress_renderer

    def render(self) -> Optional[str]:
        """
        Render the status monitor UI.
        Returns the current status string.
        """
        try:
            # Fetch job status
            status_response = api_client.get(self.status_endpoint, timeout=10)

            status = status_response.get("status", "unknown")
            progress_message = status_response.get("progress_message", "")

            # Store status in session state
            st.session_state[f"{self.session_key}_status"] = status

            # Normalize status to lowercase
            status_lower = status.lower()

            # Render based on status
            if status_lower in ["completed", "success"]:  # Handle both "completed" and "success"
                self._render_completed(status_response)
            elif status_lower == "failed":
                self._render_failed(status_response)
            elif status_lower == "cancelling":
                self._render_cancelling(status_response)
            elif status_lower in ["queued", "processing", "initializing", "running"]:  # Added "running"
                self._render_in_progress(status_response)
            else:
                self._render_unknown(status_response)

            # Auto-refresh if configured and job is in progress
            if self.auto_refresh_interval and status_lower in ["queued", "processing", "initializing", "running"]:
                import time
                last_refresh_key = f"{self.session_key}_last_refresh"
                current_time = time.time()

                # Initialize last refresh time if not exists
                if last_refresh_key not in st.session_state:
                    st.session_state[last_refresh_key] = current_time

                # Check if it's time to refresh
                time_since_refresh = current_time - st.session_state[last_refresh_key]
                if time_since_refresh >= self.auto_refresh_interval:
                    st.session_state[last_refresh_key] = current_time
                    st.rerun()
                else:
                    # Show countdown to next refresh
                    remaining = int(self.auto_refresh_interval - time_since_refresh)
                    st.caption(f"Auto-refreshing in {remaining}s...")
                    time.sleep(1)
                    st.rerun()

            return status

        except Exception as e:
            st.error(f"Failed to check {self.job_name} status: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            if st.button("Clear Status", key=f"{self.session_key}_clear_error"):
                self._clear_job()
            return "error"

    def _render_completed(self, status_response: Dict[str, Any]):
        """Render completed status UI"""
        import time

        # Show success message prominently
        st.success(f"{self.job_name} completed successfully!")

        # Show final document stats if available
        documents = status_response.get("documents", [])
        if documents:
            # Show final stats
            completed_count = len([d for d in documents if d.get("status") == "completed"])
            failed_count = len([d for d in documents if d.get("status") == "failed"])
            st.info(f"Processed {completed_count} files successfully" + (f", {failed_count} failed" if failed_count > 0 else ""))

        # Fetch and display results if result endpoint provided
        if self.result_endpoint:
            import time as time_module
            retry_key = f"{self.session_key}_result_retry_count"

            # Initialize retry count if not exists
            if retry_key not in st.session_state:
                st.session_state[retry_key] = 0

            try:
                result_response = api_client.get(self.result_endpoint, timeout=30)

                # Reset retry count on success
                if retry_key in st.session_state:
                    del st.session_state[retry_key]

                # Call custom completion handler if provided
                if self.on_completed:
                    self.on_completed(result_response)
                else:
                    # Default display
                    st.json(result_response)

            except Exception as e:
                error_str = str(e)

                # Handle 404 errors with retry (race condition between status update and result save)
                if "404" in error_str and st.session_state[retry_key] < 3:
                    st.session_state[retry_key] += 1
                    st.warning(f"Result not yet available, retrying... (attempt {st.session_state[retry_key]}/3)")
                    time_module.sleep(2)  # Wait 2 seconds before retry
                    st.rerun()
                else:
                    # Final error after retries or non-404 error
                    st.error(f"Failed to fetch results: {error_str}")
                    if retry_key in st.session_state:
                        del st.session_state[retry_key]

        # Auto-clear if configured (with visible delay)
        if self.auto_clear_on_complete:
            completion_time_key = f"{self.session_key}_completion_time"

            # Record completion time on first render
            if completion_time_key not in st.session_state:
                st.session_state[completion_time_key] = time.time()

            # Check if enough time has passed to auto-clear
            elapsed_since_completion = time.time() - st.session_state[completion_time_key]
            clear_delay = 3  # Show success for 3 seconds

            if elapsed_since_completion >= clear_delay:
                # Clean up and clear
                del st.session_state[completion_time_key]
                self._clear_job()
                st.rerun()
            else:
                # Show countdown and auto-refresh
                remaining = int(clear_delay - elapsed_since_completion)
                st.caption(f"Auto-clearing in {remaining}s...")
                time.sleep(1)
                st.rerun()
        else:
            # Manual clear button
            if st.button("Clear Status", key=f"{self.session_key}_clear_completed", type="secondary"):
                self._clear_job()
                st.rerun()

    def _render_failed(self, status_response: Dict[str, Any]):
        """Render failed status UI"""
        import time

        st.error(f"✗ {self.job_name} failed")
        error = status_response.get("error", "Unknown error")
        st.error(f"Error: {error}")

        # Show any partial results if available
        if "partial_result" in status_response:
            with st.expander("Partial Results"):
                st.json(status_response["partial_result"])

        # Auto-clear if configured (with visible delay)
        if self.auto_clear_on_complete:
            failure_time_key = f"{self.session_key}_failure_time"

            # Record failure time on first render
            if failure_time_key not in st.session_state:
                st.session_state[failure_time_key] = time.time()

            # Check if enough time has passed to auto-clear
            elapsed_since_failure = time.time() - st.session_state[failure_time_key]
            clear_delay = 5  # Show error for 5 seconds (longer to read error message)

            if elapsed_since_failure >= clear_delay:
                # Clean up and clear
                del st.session_state[failure_time_key]
                self._clear_job()
                st.rerun()
            else:
                # Show countdown and auto-refresh
                remaining = int(clear_delay - elapsed_since_failure)
                st.caption(f"Auto-clearing in {remaining}s...")
                time.sleep(1)
                st.rerun()
        else:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Clear Status", key=f"{self.session_key}_clear_failed", use_container_width=True):
                    self._clear_job()
                    st.rerun()
            with col2:
                if st.button("Retry", key=f"{self.session_key}_retry", use_container_width=True):
                    st.info("Please start a new job")

    def _render_cancelling(self, status_response: Dict[str, Any]):
        """Render cancelling status UI"""
        st.warning(f"{self.job_name} is being cancelled...")
        progress_msg = status_response.get("progress_message", "")
        if progress_msg:
            st.write(f"**Message:** {progress_msg}")
        st.info("The job will stop at the next checkpoint and may return partial results.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Refresh Status", key=f"{self.session_key}_refresh_cancelling", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("Clear Status", key=f"{self.session_key}_clear_cancelling", use_container_width=True):
                self._clear_job()
                st.rerun()

    def _render_in_progress(self, status_response: Dict[str, Any]):
        """Render in-progress status UI"""
        status = status_response.get("status", "unknown")
        progress_message = status_response.get("progress_message", "")

        st.info(f"{self.job_name} in progress...")

        # Use custom progress renderer if provided
        if self.custom_progress_renderer:
            self.custom_progress_renderer(status_response)
        else:
            # Check for multi-item progress (documents, files, sections, etc.)
            documents = status_response.get("documents", [])

            # Default progress rendering
            if self.show_metrics:
                cols = []

                # Status metric
                cols.append(st.columns(3 if self.show_elapsed_time else 2)[0])
                cols[0].metric("Status", status.upper())

                # Progress metrics (customizable based on response data)
                metrics_col_idx = 1
                if "sections_processed" in status_response or "total_sections" in status_response:
                    if len(cols) == 1:
                        cols = st.columns(3 if self.show_elapsed_time else 2)
                    sections_done = status_response.get("sections_processed", "0")
                    total_sections = status_response.get("total_sections", "?")
                    cols[metrics_col_idx].metric("Sections", f"{sections_done}/{total_sections}")
                    metrics_col_idx += 1

                elif "test_cards_generated" in status_response:
                    if len(cols) == 1:
                        cols = st.columns(3 if self.show_elapsed_time else 2)
                    count = status_response.get("test_cards_generated", "0")
                    cols[metrics_col_idx].metric("Test Cards", count)
                    metrics_col_idx += 1

                elif "processed_chunks" in status_response or "total_chunks" in status_response:
                    if len(cols) == 1:
                        cols = st.columns(3 if self.show_elapsed_time else 2)
                    done = status_response.get("processed_chunks", "0")
                    total = status_response.get("total_chunks", "?")
                    cols[metrics_col_idx].metric("Chunks", f"{done}/{total}")
                    metrics_col_idx += 1

                # Elapsed time metric
                if self.show_elapsed_time:
                    if len(cols) == 1:
                        cols = st.columns(3)
                    created_at = status_response.get("created_at", "")
                    if created_at:
                        try:
                            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            elapsed = datetime.now() - created.replace(tzinfo=None)
                            minutes = int(elapsed.total_seconds() / 60)
                            cols[-1].metric("Elapsed", f"{minutes}m")
                        except:
                            cols[-1].metric("Elapsed", "N/A")

            # Show progress message
            if progress_message:
                st.write(f"**Progress:** {progress_message}")

            # Render progress bars
            if documents:
                # Multi-file progress
                st.markdown("---")
                self._render_per_item_progress(documents, status_response)
            elif "sections_processed" in status_response and "total_sections" in status_response:
                # Section-based progress bar (e.g., for test plan generation)
                try:
                    sections_done = int(status_response.get("sections_processed", 0))
                    total_sections = int(status_response.get("total_sections", 1))
                    if total_sections > 0:
                        progress_pct = sections_done / total_sections
                        st.progress(progress_pct, text=f"Processing sections: {sections_done}/{total_sections}")
                except (ValueError, ZeroDivisionError):
                    pass  # Skip if values are invalid
            elif "processed_chunks" in status_response and "total_chunks" in status_response:
                # Chunk-based progress bar
                try:
                    chunks_done = int(status_response.get("processed_chunks", 0))
                    total_chunks = int(status_response.get("total_chunks", 1))
                    if total_chunks > 0:
                        progress_pct = chunks_done / total_chunks
                        st.progress(progress_pct, text=f"Processing chunks: {chunks_done}/{total_chunks}")
                except (ValueError, ZeroDivisionError):
                    pass  # Skip if values are invalid

        # Control buttons
        button_cols = st.columns([1, 1] if self.allow_cancel else [1])
        with button_cols[0]:
            if st.button("Refresh Status", key=f"{self.session_key}_refresh", type="secondary", use_container_width=True):
                st.rerun()

        if self.allow_cancel and len(button_cols) > 1:
            with button_cols[1]:
                if st.button("Cancel Job", key=f"{self.session_key}_cancel", type="primary", use_container_width=True):
                    self._cancel_job()

    def _render_unknown(self, status_response: Dict[str, Any]):
        """Render unknown status UI"""
        status = status_response.get("status", "unknown")
        st.info(f"Status: {status}")
        # st.json(status_response)


        if st.button("Refresh Status", key=f"{self.session_key}_refresh_unknown"):
            st.rerun()

    def _render_per_item_progress(self, documents: List[Dict[str, Any]], status_response: Dict[str, Any]):
        """Render progress bars for individual items (files/documents)"""
        total_docs = status_response.get("total_documents", len(documents))
        done_docs = status_response.get("processed_documents", 0)

        # Overall document progress
        if total_docs > 0:
            overall_doc_pct = done_docs / total_docs
            st.progress(overall_doc_pct, text=f"Documents: {done_docs}/{total_docs}")

        # Status summary
        status_counts = {
            "pending": len([d for d in documents if d.get("status") == "pending"]),
            "processing": len([d for d in documents if d.get("status") == "processing"]),
            "completed": len([d for d in documents if d.get("status") == "completed"]),
            "failed": len([d for d in documents if d.get("status") == "failed"])
        }

        # Display status summary
        status_parts = []
        if status_counts["pending"] > 0:
            status_parts.append(f"{status_counts['pending']} pending")
        if status_counts["processing"] > 0:
            status_parts.append(f"{status_counts['processing']} processing")
        if status_counts["completed"] > 0:
            status_parts.append(f"{status_counts['completed']} completed")
        if status_counts["failed"] > 0:
            status_parts.append(f"{status_counts['failed']} failed")

        if status_parts:
            st.caption(" | ".join(status_parts))

        # Individual file/document progress bars
        st.markdown("#### File Progress")

        for doc in documents:
            filename = doc.get("filename", doc.get("name", "Unknown"))
            doc_status = doc.get("status", "unknown")
            chunks_done = doc.get("chunks_processed", 0)
            chunks_total = doc.get("chunks_total", 0)

            # Determine status icon and color
            status_icon = {
                "pending": "⏳",
                "processing": "🔄",
                "completed": "✅",
                "failed": "❌"
            }.get(doc_status, "❓")

            # Create columns for filename and progress
            col1, col2 = st.columns([3, 1])

            with col1:
                st.text(f"{status_icon} {filename}")

            with col2:
                if chunks_total > 0:
                    st.caption(f"{chunks_done}/{chunks_total} chunks")

            # Progress bar
            if chunks_total > 0:
                progress_pct = chunks_done / chunks_total
                st.progress(progress_pct)
            elif doc_status == "completed":
                st.progress(1.0)
            elif doc_status == "processing":
                st.progress(0.5)  # Indeterminate progress
            else:
                st.progress(0.0)

            # Error message if failed
            if doc_status == "failed":
                error_msg = doc.get("error_message", "Unknown error")
                st.error(f"Error: {error_msg}", icon="❌")

            st.markdown("")  # Spacer

    def _clear_job(self):
        """Clear job from session state"""
        # Clear all session state keys related to this job
        keys_to_delete = [
            f"{self.session_key}_job_id",
            f"{self.session_key}_status",
            f"{self.session_key}_completion_time",
            f"{self.session_key}_failure_time",
            f"{self.session_key}_last_refresh",
        ]
        for key in keys_to_delete:
            if key in st.session_state:
                del st.session_state[key]

        # Call custom clear handler if provided
        if self.on_clear:
            self.on_clear()

    def _cancel_job(self):
        """Cancel the job"""
        if not self.cancel_endpoint:
            st.error("Cancel endpoint not configured")
            return

        try:
            response = api_client.post(self.cancel_endpoint, data={}, timeout=10)
            st.success("Cancellation requested")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to cancel job: {str(e)}")


def render_job_status(
    job_id: str,
    session_key: str,
    status_endpoint: str,
    result_endpoint: Optional[str] = None,
    job_name: str = "Job",
    **kwargs
) -> Optional[str]:
    """
    Convenience function to render a job status monitor.

    Returns the current job status string.
    """
    monitor = JobStatusMonitor(
        job_id=job_id,
        session_key=session_key,
        status_endpoint=status_endpoint,
        result_endpoint=result_endpoint,
        job_name=job_name,
        **kwargs
    )
    return monitor.render()
