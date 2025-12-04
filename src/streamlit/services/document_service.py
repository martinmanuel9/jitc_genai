from typing import Dict, Any, Optional
from app_lib.api.client import api_client
from config.settings import config
import tempfile
import base64


class DocumentService:
    def __init__(self):
        self.client = api_client
        self.endpoints = config.endpoints

    def export_to_word(
        self,
        document_data: Dict[str, Any],
        filename: Optional[str] = None
    ) -> bytes:
        response = self.client.post(
            f"{self.endpoints.doc_gen}/export-reconstructed-word",
            data=document_data,
            timeout=60
        )

        # Decode base64 content
        content_b64 = response.get('content_b64')
        if content_b64:
            return base64.b64decode(content_b64)
        else:
            raise ValueError("No content returned from export service")

    def export_simulation_to_word(
        self,
        simulation_data: Dict[str, Any]
    ) -> bytes:
        response = self.client.post(
            f"{self.endpoints.doc_gen}/export-simulation-word",
            data=simulation_data,
            timeout=30
        )

        content_b64 = response.get('content_b64')
        if content_b64:
            return base64.b64decode(content_b64)
        else:
            raise ValueError("No content returned from export service")

    def generate_document(
        self,
        template: str,
        context: Dict[str, Any],
        format: str = "docx"
    ) -> bytes:
        payload = {
            'template': template,
            'context': context,
            'format': format
        }

        response = self.client.post(
            f"{self.endpoints.doc_gen}/generate",
            data=payload,
            timeout=60
        )

        content_b64 = response.get('content_b64')
        if content_b64:
            return base64.b64decode(content_b64)
        else:
            raise ValueError("No content returned from generation service")


# Export singleton
document_service = DocumentService()
