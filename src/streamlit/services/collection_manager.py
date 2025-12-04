"""
CollectionManager - Centralized collection management for Streamlit components.

This service provides a unified interface for loading and managing collections
across the application, with built-in caching, error handling, and session state management.
"""

import streamlit as st
from services.chromadb_service import chromadb_service
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class CollectionManager:
    """Centralized collection management for Streamlit components"""

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=300)  # 5-minute cache
    def get_collections_cached() -> List[str]:
        """
        Get collections with caching.

        Returns:
            List of collection names
        """
        return chromadb_service.get_collections()

    @staticmethod
    def ensure_collections_loaded(use_cache: bool = True) -> List[str]:
        """
        Ensure collections are loaded into session state.

        This method checks if collections are already loaded in session state,
        and if not, fetches them from the API with optional caching.

        Args:
            use_cache: Whether to use cached collections (default: True)

        Returns:
            List of collection names
        """
        if "collections" not in st.session_state:
            try:
                if use_cache:
                    st.session_state.collections = CollectionManager.get_collections_cached()
                else:
                    st.session_state.collections = chromadb_service.get_collections()
            except Exception as e:
                logger.error(f"Failed to load collections: {e}")
                st.session_state.collections = []

        return st.session_state.collections

    @staticmethod
    def refresh_collections() -> bool:
        """
        Force refresh of collections (bypasses cache).

        Returns:
            True if refresh was successful, False otherwise
        """
        try:
            # Clear cache
            CollectionManager.get_collections_cached.clear()
            # Reload
            st.session_state.collections = chromadb_service.get_collections()
            return True
        except Exception as e:
            logger.error(f"Failed to refresh collections: {e}")
            return False

    @staticmethod
    def get_collections(use_session_state: bool = True, use_cache: bool = True) -> List[str]:
        """
        Get collections with flexible loading strategy.

        Args:
            use_session_state: Check session state first (default: True)
            use_cache: Use cached data (default: True)

        Returns:
            List of collection names
        """
        if use_session_state and "collections" in st.session_state:
            return st.session_state.collections

        try:
            if use_cache:
                return CollectionManager.get_collections_cached()
            else:
                return chromadb_service.get_collections()
        except Exception as e:
            logger.error(f"Failed to get collections: {e}")
            return []

    @staticmethod
    def refresh_button(
        button_text: str = "Refresh Collections",
        key: str = "refresh_collections",
        show_count: bool = True,
        use_container_width: bool = False
    ) -> bool:
        """
        Render a refresh collections button with standardized UI.

        Args:
            button_text: Button label
            key: Streamlit key for button
            show_count: Show collection count in success message
            use_container_width: Use full container width

        Returns:
            True if refresh was successful
        """
        if st.button(button_text, key=key, use_container_width=use_container_width):
            with st.spinner("Loading collections..."):
                success = CollectionManager.refresh_collections()

                if success:
                    collections = st.session_state.collections
                    if show_count:
                        st.success(f"Loaded {len(collections)} collection(s)")
                    else:
                        st.success("Collections refreshed successfully")
                    return True
                else:
                    st.error("Failed to refresh collections")
                    return False

        return False


# Export singleton instance for convenience
collection_manager = CollectionManager()
