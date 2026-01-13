"""
OpenAI adapter for AretAI
Uses the official OpenAI SDK
"""
from typing import Any, Dict
import time
from openai import OpenAI as OpenAIClient
from openai.types.chat import ChatCompletion

from ..base import BaseAdapter
from ..models import CompletionRequest, CompletionResponse, Choice, Message, Usage
from ..utils import extract_thinking, retry_with_exponential_backoff, parse_usage
from ..exceptions import ProviderError, AuthenticationError, RateLimitError, ServerError


class OpenAIAdapter(BaseAdapter):
    """
    OpenAI API adapter

    Features:
    - Standard OpenAI chat completions
    - JSON mode support
    - Function calling support (future)
    """

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self._validate_api_key()
        self.client = OpenAIClient(api_key=api_key)

    def _get_provider_name(self) -> str:
        return "openai"

    def create_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Create a chat completion using OpenAI API"""
        request.validate()

        # Transform messages (cache flags ignored for OpenAI)
        messages = self._transform_messages(request.messages, request.cache_ttl)

        # Build OpenAI API request
        openai_request = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
        }

        # Add optional parameters
        if request.stop:
            openai_request["stop"] = request.stop

        if request.response_format:
            openai_request["response_format"] = request.response_format

        # Seed is not supported by OpenAI (ignored)

        # Make API call with retry logic
        try:
            def _call_api():
                return self.client.chat.completions.create(**openai_request)

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
        Transform unified messages to OpenAI format

        OpenAI uses standard format. Cache flags are stripped (not supported).

        Args:
            messages: Unified message list
            cache_ttl: Ignored (OpenAI doesn't support caching)

        Returns:
            OpenAI-compatible message list
        """
        openai_messages = []

        for msg in messages:
            # Strip cache-related flags (not supported by OpenAI)
            openai_msg = {
                "role": msg["role"],
                "content": msg["content"]
            }
            openai_messages.append(openai_msg)

        return openai_messages

    def _transform_response(self, raw_response: ChatCompletion, extract_thinking: bool, execution_time_ms: float = None) -> CompletionResponse:
        """Transform OpenAI response to unified format"""

        # Extract content
        raw_content = raw_response.choices[0].message.content

        # Extract thinking if requested
        thinking = None
        if extract_thinking:
            from ..utils import extract_thinking as extract_think_fn
            raw_content, thinking = extract_think_fn(raw_content)

        # Parse usage statistics
        usage_dict = parse_usage(
            raw_response.usage.model_dump() if raw_response.usage else {},
            provider="openai"
        )

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
        """Handle OpenAI API errors and convert to unified exceptions"""
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
            raise AuthenticationError(f"Invalid OpenAI API key: {error}")
        elif "rate limit" in error_str or "429" in error_str or status_code == 429:
            raise RateLimitError(f"OpenAI rate limit exceeded: {error}")
        elif "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str or (status_code and 500 <= status_code < 600):
            # Server error (5xx) - stop execution immediately
            # Check this BEFORE timeout check (504 Gateway Timeout is a server error)
            raise ServerError(
                provider="openai",
                message=f"Internal server error. Please try again later. Error: {error}",
                status_code=status_code or 500
            )
        elif "timeout" in error_str:
            from ..exceptions import TimeoutError
            raise TimeoutError(f"OpenAI API timeout: {error}")
        else:
            raise ProviderError("openai", str(error))
