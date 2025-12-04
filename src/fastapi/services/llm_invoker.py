"""
LLMInvoker - Standardized LLM invocation utility.

This module provides a unified interface for invoking LLMs across all services,
with consistent error handling, response normalization, and token tracking.
"""

import logging
import time
from typing import Optional, Dict, Any, List, Union
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from services.llm_utils import get_llm
from services.error_handling import LLMServiceError

logger = logging.getLogger(__name__)


class LLMInvoker:
    """Standardized LLM invocation with response normalization and error handling"""

    @staticmethod
    def invoke(
        model_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        retry_count: int = 0,
        log_timing: bool = True
    ) -> str:
        """
        Invoke an LLM with a prompt and return the normalized response.

        This method:
        - Gets the appropriate LLM instance for the model
        - Constructs the message chain (system + user message)
        - Invokes the LLM
        - Normalizes the response (handles different response types)
        - Logs timing information
        - Handles errors consistently

        Args:
            model_name: Name of the model to use (e.g., "gpt-4", "claude-3-sonnet")
            prompt: User prompt/query text
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            timeout: Optional timeout in seconds
            retry_count: Number of retries on failure (default: 0)
            log_timing: Whether to log timing information

        Returns:
            Normalized string response from the LLM

        Raises:
            LLMServiceError: If LLM invocation fails

        Example:
            response = LLMInvoker.invoke(
                model_name="gpt-4",
                prompt="What is the capital of France?",
                system_prompt="You are a helpful geography assistant."
            )
        """
        start_time = time.time()
        attempts = 0
        last_error = None

        while attempts <= retry_count:
            try:
                # Get LLM instance with temperature and max_tokens if provided
                # get_llm will handle model-specific parameter support
                llm = get_llm(
                    model_name=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                # Apply timeout if provided
                if timeout is not None:
                    llm.request_timeout = timeout

                # Construct message chain
                messages = []
                if system_prompt:
                    messages.append(SystemMessage(content=system_prompt))
                messages.append(HumanMessage(content=prompt))

                # Invoke LLM
                response = llm.invoke(messages)

                # Normalize response
                normalized_response = LLMInvoker._normalize_response(response)

                # Log timing
                if log_timing:
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"LLM invocation completed in {elapsed_ms}ms (model: {model_name})")

                return normalized_response

            except Exception as e:
                attempts += 1
                last_error = e
                logger.error(f"LLM invocation failed (attempt {attempts}/{retry_count + 1}): {e}")

                if attempts > retry_count:
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    raise LLMServiceError(
                        f"LLM invocation failed after {attempts} attempts: {str(last_error)}",
                        error_code="LLM_INVOCATION_FAILED",
                        details={
                            "model_name": model_name,
                            "attempts": attempts,
                            "elapsed_ms": elapsed_ms
                        }
                    )

                # Wait before retry (exponential backoff)
                time.sleep(2 ** attempts)

    @staticmethod
    def invoke_with_template(
        model_name: str,
        system_prompt: str,
        user_prompt_template: str,
        template_data: Dict[str, Any],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        retry_count: int = 0
    ) -> str:
        """
        Invoke an LLM with a prompt template and data.

        Args:
            model_name: Name of the model to use
            system_prompt: System prompt to set context
            user_prompt_template: User prompt template with placeholders (e.g., "{data_sample}")
            template_data: Dictionary of template variables
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            retry_count: Number of retries on failure

        Returns:
            Normalized string response from the LLM

        Example:
            response = LLMInvoker.invoke_with_template(
                model_name="gpt-4",
                system_prompt="You are a helpful assistant.",
                user_prompt_template="Analyze this data: {data_sample}",
                template_data={"data_sample": "Sample data here"}
            )
        """
        # Format user prompt with template data
        user_prompt = user_prompt_template
        for key, value in template_data.items():
            placeholder = f"{{{key}}}"
            user_prompt = user_prompt.replace(placeholder, str(value))

        # Construct full prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        return LLMInvoker.invoke(
            model_name=model_name,
            prompt=full_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            retry_count=retry_count
        )

    @staticmethod
    def invoke_with_context(
        model_name: str,
        query: str,
        context_documents: List[str],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Invoke an LLM with query and context documents (RAG pattern).

        Args:
            model_name: Name of the model to use
            query: User query
            context_documents: List of context document strings
            system_prompt: Optional system prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override

        Returns:
            Normalized string response from the LLM

        Example:
            response = LLMInvoker.invoke_with_context(
                model_name="gpt-4",
                query="What is the capital?",
                context_documents=["France has Paris as capital.", "Spain has Madrid."],
                system_prompt="Answer based on the provided context."
            )
        """
        # Construct context section
        context_text = "\n\n".join([
            f"Document {i + 1}:\n{doc}"
            for i, doc in enumerate(context_documents)
        ])

        # Build full prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\nContext:\n{context_text}\n\nQuery: {query}"
        else:
            full_prompt = f"Context:\n{context_text}\n\nQuery: {query}"

        return LLMInvoker.invoke(
            model_name=model_name,
            prompt=full_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

    @staticmethod
    def _normalize_response(response: Any) -> str:
        """
        Normalize different LLM response types to a string.

        Handles:
        - LangChain AIMessage objects (response.content)
        - Direct string responses
        - Other response types (converted to string)

        Args:
            response: Raw LLM response

        Returns:
            Normalized string response
        """
        if hasattr(response, 'content'):
            return response.content
        elif isinstance(response, str):
            return response
        else:
            return str(response)

    @staticmethod
    def get_response_with_timing(
        model_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> tuple[str, int]:
        """
        Invoke LLM and return both response and timing.

        Args:
            model_name: Name of the model to use
            prompt: User prompt/query text
            system_prompt: Optional system prompt
            **kwargs: Additional arguments passed to invoke()

        Returns:
            Tuple of (response_text, response_time_ms)

        Example:
            response, time_ms = LLMInvoker.get_response_with_timing(
                model_name="gpt-4",
                prompt="Hello!"
            )
        """
        start_time = time.time()
        response = LLMInvoker.invoke(
            model_name=model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            log_timing=False,  # We'll handle timing ourselves
            **kwargs
        )
        response_time_ms = int((time.time() - start_time) * 1000)
        return response, response_time_ms


# Export for convenience
def invoke_llm(model_name: str, prompt: str, **kwargs) -> str:
    """Convenience function for simple LLM invocation"""
    return LLMInvoker.invoke(model_name=model_name, prompt=prompt, **kwargs)
