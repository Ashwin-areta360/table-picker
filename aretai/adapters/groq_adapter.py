"""
Groq adapter for AretAI
Uses the official Groq SDK with auto-caching support
"""
from typing import Any, Dict
import time
from groq import Groq
from groq.types.chat import ChatCompletion

from ..base import BaseAdapter
from ..models import CompletionRequest, CompletionResponse, Choice, Message, Usage
from ..utils import extract_thinking, retry_with_exponential_backoff, parse_usage
from ..exceptions import ProviderError, AuthenticationError, RateLimitError, ServerError


class GroqAdapter(BaseAdapter):
    """
    Groq API adapter

    Features:
    - OpenAI-compatible API
    - Automatic prompt caching (no configuration needed)
    - Deterministic output with seed parameter
    - Fast inference
    """

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self._validate_api_key()
        self.client = Groq(api_key=api_key)

    def _get_provider_name(self) -> str:
        return "groq"

    def create_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Create a chat completion using Groq API"""
        request.validate()

        # Transform messages (cache flags are ignored, Groq auto-caches)
        messages = self._transform_messages(request.messages, request.cache_ttl)

        # Build Groq API request
        groq_request = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_completion_tokens": request.max_tokens,  # Note: Groq uses max_completion_tokens
            "top_p": request.top_p,
            "stream": False,
        }

        # Add optional parameters
        if request.stop:
            groq_request["stop"] = request.stop

        if request.seed is not None:
            groq_request["seed"] = request.seed

        if request.response_format:
            groq_request["response_format"] = request.response_format

        # Make API call with retry logic
        try:
            def _call_api():
                return self.client.chat.completions.create(**groq_request)

            # Measure execution time
            start_time = time.time()
            raw_response = retry_with_exponential_backoff(
                func=_call_api,
                max_retries=request.max_retries,
                initial_delay=1.0
            )
            end_time = time.time()
            execution_time_ms = (end_time - start_time) * 1000

            return self._transform_response(raw_response, request.extract_thinking, execution_time_ms)

        except Exception as e:
            self._handle_error(e)

    def _transform_messages(self, messages: list, cache_ttl: str = None) -> list:
        """
        Transform unified messages to Groq format

        Groq uses standard OpenAI format. Cache flags are stripped since
        Groq automatically caches prompts.

        Args:
            messages: Unified message list
            cache_ttl: Ignored (Groq auto-caches)

        Returns:
            Groq-compatible message list
        """
        groq_messages = []

        for msg in messages:
            # Strip cache-related flags (not needed for Groq)
            groq_msg = {
                "role": msg["role"],
                "content": msg["content"]
            }
            groq_messages.append(groq_msg)

        return groq_messages

    def _transform_response(self, raw_response: ChatCompletion, extract_thinking: bool, execution_time_ms: float = None) -> CompletionResponse:
        """Transform Groq response to unified format"""

        # Extract content
        raw_content = raw_response.choices[0].message.content

        # Extract thinking if requested
        thinking = None
        if extract_thinking:
            from ..utils import extract_thinking as extract_think_fn
            raw_content, thinking = extract_think_fn(raw_content)

        # Parse usage statistics
        usage_data = {}
        if raw_response.usage:
            usage_data = raw_response.usage.model_dump() or {}
        usage_dict = parse_usage(usage_data, provider="groq")

        # Build unified response
        return CompletionResponse(
            id=raw_response.id,
            model=raw_response.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=raw_content
                    ),
                    finish_reason=raw_response.choices[0].finish_reason
                )
            ],
            usage=Usage(**usage_dict),
            provider=self.provider_name,
            thinking=thinking,
            raw_response=raw_response.model_dump(),
            execution_time_ms=execution_time_ms
        )

    def _handle_error(self, error: Exception) -> None:
        """Handle Groq API errors and convert to unified exceptions"""
        error_str = str(error).lower()

        # Check for status code in error
        status_code = None
        if hasattr(error, 'status_code'):
            status_code = error.status_code
        else:
            # Try to extract from error string
            import re
            status_match = re.search(r'status[:\s]+(\d{3})|error\s+(\d{3})|(\d{3})\s+error', error_str)
            if status_match:
                status_code = int(status_match.group(1) or status_match.group(2) or status_match.group(3))

        # Handle specific errors (order matters - check 5xx before timeout!)
        if "api key" in error_str or "unauthorized" in error_str or "401" in error_str or status_code == 401:
            raise AuthenticationError(f"Invalid Groq API key: {error}")
        elif "rate limit" in error_str or "429" in error_str or status_code == 429:
            raise RateLimitError(f"Groq rate limit exceeded: {error}")
        elif "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str or (status_code and 500 <= status_code < 600):
            # Server error (5xx) - stop execution immediately
            # Check this BEFORE timeout check (504 Gateway Timeout is a server error)
            raise ServerError(
                provider="groq",
                message=f"Internal server error. Please try again later. Error: {error}",
                status_code=status_code or 500
            )
        elif "timeout" in error_str:
            from ..exceptions import TimeoutError
            raise TimeoutError(f"Groq API timeout: {error}")
        else:
            raise ProviderError("groq", str(error))
