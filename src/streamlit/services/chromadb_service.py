from typing import List, Dict, Any, Optional
from app_lib.api.client import api_client
from config.settings import config
from models.models import Collection, Document


class ChromaDBService:
    def __init__(self):
        self.client = api_client
        self.endpoints = config.endpoints

    def get_collections(self) -> List[str]:
        response = self.client.get(
            f"{self.endpoints.vectordb}/collections",
            timeout=10
        )
        return response.get('collections', [])

    def create_collection(self, name: str) -> Dict[str, Any]:
        # Validate collection name
        if len(name) < 3 or len(name) > 63:
            raise ValueError("Collection name must be 3-63 characters")

        response = self.client.post(
            f"{self.endpoints.vectordb}/collection/create",
            params={'collection_name': name},
            timeout=30
        )
        return response

    def delete_collection(self, name: str) -> Dict[str, Any]:
        response = self.client.delete(
            f"{self.endpoints.vectordb}/collection",
            params={'collection_name': name},
            timeout=30
        )
        return response

    def get_documents(self, collection_name: str) -> List[Document]:
        response = self.client.get(
            f"{self.endpoints.vectordb}/documents",
            params={'collection_name': collection_name},
            timeout=60
        )

        # Group chunks by document_id to get unique documents
        documents_dict: Dict[str, Dict[str, Any]] = {}

        for i, doc_id in enumerate(response.get('ids', [])):
            metadata = response.get('metadatas', [])[i] if i < len(response.get('metadatas', [])) else {}
            document_id = metadata.get('document_id')

            if document_id and document_id not in documents_dict:
                documents_dict[document_id] = {
                    'document_id': document_id,
                    'document_name': metadata.get('document_name', 'Unknown'),
                    'file_type': metadata.get('file_type', ''),
                    'total_chunks': metadata.get('total_chunks', 0),
                    'has_images': metadata.get('has_images', False),
                    'image_count': metadata.get('image_count', 0),
                    'metadata': metadata
                }

        # Convert to Document objects
        documents = [
            Document(**doc_data)
            for doc_data in documents_dict.values()
        ]

        return documents

    def query_documents(
        self,
        collection_name: str,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        n_results: int = 5
    ) -> Dict[str, Any]:
        if query_embedding is None:
            raise ValueError("query_embedding must be provided for document queries")

        # Support both single-vector and batched embeddings
        if query_embedding and isinstance(query_embedding[0], list):
            embeddings_payload = query_embedding
        else:
            embeddings_payload = [query_embedding]

        payload = {
            'collection_name': collection_name,
            'query_embeddings': embeddings_payload,
            'n_results': n_results,
            'include': ['documents', 'metadatas', 'distances']
        }

        response = self.client.post(
            f"{self.endpoints.vectordb}/documents/query",
            data=payload,
            timeout=60
        )

        return response

    def upload_documents(
        self,
        files: List,
        collection_name: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        vision_models: Optional[List[str]] = None,
        store_images: bool = True
    ) -> Dict[str, Any]:
        # Prepare files for upload
        files_data = [
            ('files', (f.name, f.getvalue(), getattr(f, 'type', None) or 'application/octet-stream'))
            for f in files
        ]

        params = {
            'collection_name': collection_name,
            'chunk_size': str(chunk_size),
            'chunk_overlap': str(chunk_overlap),
            'store_images': 'true' if store_images else 'false',
            'model_name': 'enhanced',
            'vision_models': ','.join(vision_models or [])
        }

        response = self.client.upload(
            f"{self.endpoints.vectordb}/documents/upload-and-process",
            files=files_data,
            params=params,
            timeout=300
        )

        return response

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        response = self.client.get(
            f"{self.endpoints.vectordb}/jobs/{job_id}",
            timeout=10
        )
        return response

    def reconstruct_document(
        self,
        document_id: str,
        collection_name: str
    ) -> Dict[str, Any]:
        response = self.client.get(
            f"{self.endpoints.vectordb}/documents/reconstruct/{document_id}",
            params={'collection_name': collection_name},
            timeout=300
        )
        return response

    def ingest_url(self, url: str, collection_name: str) -> Dict[str, Any]:
        payload = {
            'url': url,
            'collection_name': collection_name
        }

        response = self.client.post(
            f"{self.endpoints.vectordb}/ingest-url",
            data=payload,
            timeout=120
        )
        return response


# Export singleton instance
chromadb_service = ChromaDBService()
