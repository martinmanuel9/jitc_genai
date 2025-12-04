import requests
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
import streamlit as st
from config.settings import config


@dataclass
class RequestConfig:
    """Request configuration options"""
    timeout: int = 30
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    show_errors: bool = True  # Whether to show errors in Streamlit UI


class APIClient:
    def __init__(self):
        self.config = config
        self.session = requests.Session()
        self.base_url = config.endpoints.base
        self._interceptors: List[Callable] = []
        self._setup_defaults()

    def _setup_defaults(self):
        """Setup default headers and session configuration"""
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        # Add API keys if available
        if self.config.openai_api_key:
            self.session.headers['X-OpenAI-API-Key'] = self.config.openai_api_key

        if self.config.anthropic_api_key:
            self.session.headers['X-Anthropic-API-Key'] = self.config.anthropic_api_key

    def add_interceptor(self, interceptor: Callable):
        self._interceptors.append(interceptor)

    def _apply_interceptors(self, request_config: Dict[str, Any]) -> Dict[str, Any]:
        for interceptor in self._interceptors:
            request_config = interceptor(request_config)
        return request_config

    def _handle_error(self, error: Exception, url: str, show_ui_error: bool = True):
        error_message = ""
        response_text = ""

        if isinstance(error, requests.exceptions.HTTPError) and getattr(error, "response", None) is not None:
            try:
                response_text = error.response.text
            except Exception:
                response_text = ""

        if isinstance(error, requests.exceptions.Timeout):
            error_message = f"Request timeout: {url}"
        elif isinstance(error, requests.exceptions.ConnectionError):
            error_message = f"Connection error: Could not connect to {url}"
        elif isinstance(error, requests.exceptions.HTTPError):
            status_code = error.response.status_code if hasattr(error, 'response') else 'Unknown'
            error_message = f"HTTP {status_code} error: {url}"
            if response_text:
                error_message = f"{error_message}\nDetails: {response_text}"
        else:
            error_message = f"Request failed: {str(error)}"

        # Show in UI if enabled
        if show_ui_error:
            st.error(error_message)

        # Re-raise to allow caller to handle if needed
        raise error

    def _build_url(self, endpoint: str) -> str:
        if endpoint.startswith('http'):
            return endpoint
        if endpoint.startswith('/'):
            return f"{self.base_url}{endpoint}"
        return f"{self.base_url}/{endpoint}"

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        show_errors: bool = True
    ) -> Dict[str, Any]:
        url = self._build_url(endpoint)
        try:
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._handle_error(e, url, show_errors)

    def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[List] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        show_errors: bool = True
    ) -> Dict[str, Any]:
        url = self._build_url(endpoint)
        try:
            if files:
                # For file uploads, don't send as JSON
                upload_headers = self.session.headers.copy()
                upload_headers.pop('Content-Type', None)  # allow requests to set multipart boundary

                # Don't pass data parameter for file uploads (keep it simple)
                response = self.session.post(
                    url,
                    files=files,
                    params=params,
                    timeout=timeout,
                    headers=upload_headers
                )
            else:
                # Regular JSON POST
                response = self.session.post(
                    url,
                    json=data,
                    params=params,
                    timeout=timeout
                )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._handle_error(e, url, show_errors)

    def put(
        self,
        endpoint: str,
        data: Dict[str, Any],
        timeout: int = 30,
        show_errors: bool = True
    ) -> Dict[str, Any]:
        url = self._build_url(endpoint)
        try:
            response = self.session.put(url, json=data, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._handle_error(e, url, show_errors)

    def delete(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        show_errors: bool = True
    ) -> Dict[str, Any]:
        url = self._build_url(endpoint)
        try:
            response = self.session.delete(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._handle_error(e, url, show_errors)

    def upload(
        self,
        endpoint: str,
        files: List,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 300,
        show_errors: bool = True
    ) -> Dict[str, Any]:
        return self.post(
            endpoint=endpoint,
            files=files,
            data=data,
            params=params,
            timeout=timeout,
            show_errors=show_errors
        )


# Export singleton instance - use this throughout the app
api_client = APIClient()


# Convenience functions for common operations
def get_json(endpoint: str, **kwargs) -> Dict[str, Any]:
    """Shorthand for GET request"""
    return api_client.get(endpoint, **kwargs)


def post_json(endpoint: str, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Shorthand for POST request"""
    return api_client.post(endpoint, data=data, **kwargs)


def upload_files(endpoint: str, files: List, **kwargs) -> Dict[str, Any]:
    """Shorthand for file upload"""
    return api_client.upload(endpoint, files=files, **kwargs)
