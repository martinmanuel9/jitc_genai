"""
WordExport - Unified Word document export component.

This component provides a standardized interface for exporting data to Word documents
across the application, with built-in caching, error handling, and consistent UI.
"""

import streamlit as st
import base64
from config.settings import config
from app_lib.api.client import api_client
import logging
import traceback
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class WordExport:
    """Unified Word export component with caching and error handling"""

    @staticmethod
    def export_button(
        endpoint: str,
        data_payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        button_label: str = "Export to Word Document",
        download_label: str = "Download {filename}",
        cache_in_session: bool = False,
        cache_key: Optional[str] = None,
        cache_identifier: Optional[str] = None,
        show_traceback: bool = False,
        button_key: str = "export_word",
        download_key: str = "download_word",
        timeout: int = 60,
        use_full_width: bool = True,
        auto_generate: bool = False
    ) -> bool:
        """
        Unified Word export button with download.

        Args:
            endpoint: API endpoint for export (relative to base URL)
            data_payload: Data to POST (json body)
            params: Query parameters
            button_label: Export button label
            download_label: Download button label (can include {filename})
            cache_in_session: Cache generated document in session state
            cache_key: Session state key for caching
            cache_identifier: Unique identifier for cache validation (e.g., document_id)
            show_traceback: Show detailed error traceback
            button_key: Streamlit key for export button
            download_key: Streamlit key for download button
            timeout: Request timeout in seconds
            use_full_width: Use full container width for buttons
            auto_generate: Auto-generate on first display

        Returns:
            True if export was successful

        Example:
            # Simple usage
            WordExport.export_button(
                endpoint="/doc_gen/export-legal-research-word",
                data_payload=research_result,
                button_key="export_research"
            )

            # With caching
            WordExport.export_button(
                endpoint="/doc_gen/export-reconstructed-word",
                data_payload=document_data,
                cache_in_session=True,
                cache_key="export_doc_cache",
                cache_identifier=document_data.get("document_id"),
                auto_generate=True
            )
        """
        # Initialize cache if requested
        if cache_in_session and cache_key:
            if cache_key not in st.session_state:
                st.session_state[cache_key] = None

            # Check if cache is valid
            cached_data = st.session_state[cache_key]
            cache_valid = (
                cached_data is not None and
                (cache_identifier is None or
                 cached_data.get("cache_identifier") == cache_identifier)
            )

            # Auto-generate if requested and cache is invalid
            if auto_generate and not cache_valid:
                success = WordExport._generate_export(
                    endpoint=endpoint,
                    data_payload=data_payload,
                    params=params,
                    timeout=timeout,
                    cache_key=cache_key,
                    cache_identifier=cache_identifier,
                    show_traceback=show_traceback
                )
                if not success:
                    return False
                cached_data = st.session_state[cache_key]

            # Show download button if cache exists
            if cached_data:
                return WordExport._render_download_button(
                    cached_data=cached_data,
                    download_label=download_label,
                    download_key=download_key,
                    use_full_width=use_full_width
                )

        # Export button (only if not using auto-generate with valid cache)
        if st.button(button_label, type="primary", key=button_key, use_container_width=use_full_width):
            return WordExport._generate_export(
                endpoint=endpoint,
                data_payload=data_payload,
                params=params,
                timeout=timeout,
                cache_key=cache_key if cache_in_session else None,
                cache_identifier=cache_identifier,
                show_traceback=show_traceback,
                download_key=download_key,
                download_label=download_label,
                use_full_width=use_full_width
            )

        return False

    @staticmethod
    def _generate_export(
        endpoint: str,
        data_payload: Optional[Dict[str, Any]],
        params: Optional[Dict[str, Any]],
        timeout: int,
        cache_key: Optional[str],
        cache_identifier: Optional[str],
        show_traceback: bool,
        download_key: Optional[str] = None,
        download_label: Optional[str] = None,
        use_full_width: bool = True
    ) -> bool:
        """Internal method to generate Word export"""
        try:
            with st.spinner("Generating Word document..."):
                # Build full endpoint URL
                if not endpoint.startswith("http"):
                    full_endpoint = f"{config.endpoints.base}{endpoint}"
                else:
                    full_endpoint = endpoint

                # Make API request
                if data_payload is not None:
                    response_data = api_client.post(
                        full_endpoint,
                        data=data_payload,
                        params=params,
                        timeout=timeout
                    )
                else:
                    response_data = api_client.get(
                        full_endpoint,
                        params=params,
                        timeout=timeout
                    )

                if not response_data:
                    st.error("Export failed - no response from server")
                    return False

                # Extract content
                b64_content = response_data.get("content_b64")
                filename = response_data.get("filename", "export.docx")
                mime_type = response_data.get(
                    "content_type",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

                if not b64_content:
                    st.error("No file content received from server")
                    return False

                # Decode base64
                doc_bytes = base64.b64decode(b64_content)

                # Cache if requested
                if cache_key:
                    st.session_state[cache_key] = {
                        "data": doc_bytes,
                        "filename": filename,
                        "mime_type": mime_type,
                        "cache_identifier": cache_identifier
                    }

                # Show download button immediately if not caching
                if not cache_key and download_key:
                    label = download_label.format(filename=filename) if download_label else f"Download {filename}"
                    st.download_button(
                        label=label,
                        data=doc_bytes,
                        file_name=filename,
                        mime=mime_type,
                        key=download_key,
                        type="primary",
                        use_container_width=use_full_width
                    )

                st.success(f"Word document generated: {filename}")
                return True

        except Exception as e:
            logger.error(f"Word export failed: {e}")
            st.error(f"Failed to export to Word: {str(e)}")

            if show_traceback:
                with st.expander("Error Details"):
                    st.code(traceback.format_exc())

            # Clear cache on error
            if cache_key:
                st.session_state[cache_key] = None

            return False

    @staticmethod
    def _render_download_button(
        cached_data: Dict[str, Any],
        download_label: str,
        download_key: str,
        use_full_width: bool
    ) -> bool:
        """Render download button from cached data"""
        filename = cached_data.get("filename", "export.docx")
        label = download_label.format(filename=filename)

        st.download_button(
            label=label,
            data=cached_data["data"],
            file_name=filename,
            mime=cached_data.get(
                "mime_type",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            key=download_key,
            type="primary",
            use_container_width=use_full_width
        )
        return True

    @staticmethod
    def clear_cache(cache_key: str):
        """
        Clear cached export data.

        Args:
            cache_key: Session state key to clear
        """
        if cache_key in st.session_state:
            st.session_state[cache_key] = None


# Export singleton instance for convenience
word_export = WordExport()
