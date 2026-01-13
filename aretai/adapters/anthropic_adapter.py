"""
Anthropic (Claude) adapter for AretAI
Supports prompt caching with TTL control
"""
from typing import Any, Dict, List
import time
import anthropic
from anthropic.types import Message as AnthropicMessage

from ..base import BaseAdapter
from ..models import CompletionRequest, CompletionResponse, Choice, Message, Usage
from ..utils import extract_thinking, retry_with_exponential_backoff, parse_usage, build_cache_control
from ..exceptions import ProviderError, AuthenticationError, RateLimitError, ServerError


class AnthropicAdapter(BaseAdapter):
    """
    Anthropic Claude API adapter

    Features:
    - Explicit prompt caching with cache_control
    - TTL support ("5m" or "1h")
    - Separate system parameter
    - High-quality reasoning
    """

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self._validate_api_key()
        self.client = anthropic.Anthropic(api_key=api_key)

    def _get_provider_name(self) -> str:
        return "anthropic"

    def create_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Create a chat completion using Anthropic API"""
        request.validate()

        # Transform messages (extract system messages and apply cache_control)
        system_blocks, user_messages = self._transform_messages(request.messages, request.cache_ttl)

        # Build Anthropic API request
        # Note: Anthropic doesn't allow both temperature and top_p
        anthropic_request = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": user_messages,
        }

        # Only include one: top_p if specified (not default), otherwise temperature
        if request.top_p != 1.0:
            anthropic_request["top_p"] = request.top_p
        else:
            anthropic_request["temperature"] = request.temperature

        # Add system blocks if present
        if system_blocks:
            anthropic_request["system"] = system_blocks

        # Add stop sequences if provided
        if request.stop:
            anthropic_request["stop_sequences"] = request.stop

        # Handle JSON mode (Anthropic needs explicit instructions)
        if request.response_format and request.response_format.get("type") == "json_object":
            # Inject JSON instructions into system prompt
            json_instruction = {
                "type": "text",
                "text": "You must respond with valid JSON only. Do not include any text before or after the JSON object."
            }
            if system_blocks:
                anthropic_request["system"].append(json_instruction)
            else:
                anthropic_request["system"] = [json_instruction]

        # Make API call with retry logic
        try:
            def _call_api():
                return self.client.messages.create(**anthropic_request)

            # Measure execution time
            start_time = time.time()
            raw_response = retry_with_exponential_backoff(
                func=_call_api,
                max_retries=request.max_retries,
                initial_delay=1.0
            )
            end_time = time.time()
            execution_time_ms = (end_time - start_time) * 1000

            # Check if JSON mode is enabled
            is_json_mode = request.response_format and request.response_format.get("type") == "json_object"

            return self._transform_response(raw_response, request.extract_thinking, is_json_mode, execution_time_ms)

        except Exception as e:
            self._handle_error(e)

    def _transform_messages(self, messages: list, cache_ttl: str = None) -> tuple:
        """
        Transform unified messages to Anthropic format

        Anthropic requires:
        - System messages in separate 'system' parameter
        - User/assistant messages in 'messages' parameter
        - Cache control applied to system blocks and user messages

        Args:
            messages: Unified message list
            cache_ttl: Optional cache TTL ("5m" or "1h")

        Returns:
            Tuple of (system_blocks, user_messages)
        """
        system_blocks = []
        user_messages = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            should_cache = msg.get("cache", False)
            msg_cache_ttl = msg.get("cache_ttl", cache_ttl)

            if role == "system":
                # System message goes in system blocks
                system_block = {
                    "type": "text",
                    "text": content
                }

                # Add cache_control if caching is enabled
                if should_cache:
                    system_block["cache_control"] = build_cache_control(msg_cache_ttl)

                system_blocks.append(system_block)

            else:
                # User/assistant messages
                message_obj = {
                    "role": role,
                    "content": content
                }

                # For user messages with cache flag, use content blocks format
                if role == "user" and should_cache:
                    message_obj["content"] = [
                        {
                            "type": "text",
                            "text": content,
                            "cache_control": build_cache_control(msg_cache_ttl)
                        }
                    ]

                user_messages.append(message_obj)

        return system_blocks, user_messages

    def _transform_response(self, raw_response: AnthropicMessage, extract_thinking: bool, is_json_mode: bool = False, execution_time_ms: float = None) -> CompletionResponse:
        """
        Transform Anthropic response to unified format

        Args:
            raw_response: Raw Anthropic API response
            extract_thinking: Whether to extract <think> tags
            is_json_mode: Whether JSON mode is enabled (cleans markdown if True)
            execution_time_ms: LLM call execution time in milliseconds
        """

        # Extract content (Anthropic returns list of content blocks)
        raw_content = ""
        if raw_response.content:
            # Join all text blocks
            raw_content = "".join(
                block.text for block in raw_response.content
                if hasattr(block, 'text')
            )

        # Clean markdown code blocks ONLY if JSON mode is requested
        # This preserves legitimate markdown in normal responses
        if is_json_mode:
            raw_content_stripped = raw_content.strip()
            if raw_content_stripped.startswith("```json") and raw_content_stripped.endswith("```"):
                raw_content = raw_content_stripped[7:-3].strip()
            elif raw_content_stripped.startswith("```") and raw_content_stripped.endswith("```"):
                raw_content = raw_content_stripped[3:-3].strip()

        # Extract thinking if requested
        thinking = None
        if extract_thinking:
            from ..utils import extract_thinking as extract_think_fn
            raw_content, thinking = extract_think_fn(raw_content)

        # Parse usage statistics (Anthropic has detailed cache stats)
        usage_dict = parse_usage(
            raw_response.usage.model_dump() if raw_response.usage else {},
            provider="anthropic"
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
                    finish_reason=raw_response.stop_reason
                )
            ],
            usage=Usage(**usage_dict),
            provider=self.provider_name,
            thinking=thinking,
            raw_response=raw_response.model_dump(),
            execution_time_ms=execution_time_ms
        )

    def _handle_error(self, error: Exception) -> None:
        """Handle Anthropic API errors and convert to unified exceptions"""
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
            raise AuthenticationError(f"Invalid Anthropic API key: {error}")
        elif "rate limit" in error_str or "429" in error_str or status_code == 429:
            raise RateLimitError(f"Anthropic rate limit exceeded: {error}")
        elif "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str or (status_code and 500 <= status_code < 600):
            # Server error (5xx) - stop execution immediately
            # Check this BEFORE timeout check (504 Gateway Timeout is a server error)
            raise ServerError(
                provider="anthropic",
                message=f"Internal server error. Please try again later. Error: {error}",
                status_code=status_code or 500
            )
        elif "overloaded" in error_str or "529" in error_str:
            raise ServerError("anthropic", "Service temporarily overloaded", status_code=529)
        elif "timeout" in error_str:
            from ..exceptions import TimeoutError
            raise TimeoutError(f"Anthropic API timeout: {error}")
        else:
            raise ProviderError("anthropic", str(error))
