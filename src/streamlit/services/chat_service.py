from typing import Dict, Any, Optional, List
from app_lib.api.client import api_client
from config.settings import config
from models.models import ChatRequest, ChatResponse, ChatMessage


class ChatService:
    def __init__(self):
        self.client = api_client
        self.endpoints = config.endpoints

    def send_message(
        self,
        query: str,
        model: str,  # Keep parameter name for backward compatibility
        use_rag: bool = False,
        collection_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_k: int = 5
    ) -> ChatResponse:
        # Create request object using Streamlit's ChatRequest model
        request = ChatRequest(
            query=query,
            model=model,  # Use 'model' field name for Streamlit schema
            use_rag=use_rag,
            collection_name=collection_name,
            temperature=temperature,
            max_tokens=max_tokens,
            top_k=top_k
        )

        # Convert to dict and remap to FastAPI's expected field names
        request_data = request.model_dump() if hasattr(request, 'model_dump') else request.dict()
        # Map Streamlit field names to FastAPI field names
        request_data['model_name'] = request_data.pop('model')  # Rename 'model' to 'model_name'
        # Map use_rag to query_type
        if request_data.get('use_rag'):
            request_data['query_type'] = 'rag'
        else:
            request_data['query_type'] = 'direct'
        request_data.pop('use_rag', None)  # Remove use_rag as API doesn't use it
        request_data.pop('top_k', None)  # Remove top_k as it's not in API schema

        # Send request
        response_data = self.client.post(
            self.endpoints.chat,
            data=request_data,
            timeout=300
        )

        # Parse response
        return ChatResponse(**response_data)

    def get_chat_history(
        self,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> List[ChatMessage]:
        params = {'limit': limit}
        if session_id:
            params['session_id'] = session_id

        response = self.client.get(
            self.endpoints.history,
            params=params,
            timeout=30
        )

        messages = [
            ChatMessage(**msg_data)
            for msg_data in response.get('messages', [])
        ]

        return messages

    def evaluate_document(
        self,
        document_id: str,
        collection_name: str,
        prompt: str,
        model_name: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        payload = {
            'document_id': document_id,
            'collection_name': collection_name,
            'prompt': prompt,
            'model_name': model_name,
            'top_k': top_k
        }

        response = self.client.post(
            f"{self.endpoints.doc_gen}/evaluate_doc",
            data=payload,
            timeout=300
        )

        return response


# Export singleton
chat_service = ChatService()
