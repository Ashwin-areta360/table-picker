"""
Utility functions for AretAI
Includes retry logic, thinking extraction, and helper functions
"""
import time
from typing import Tuple, Callable, Any, Optional
from .exceptions import ProviderError, RateLimitError, TimeoutError


def extract_thinking(raw_response: str) -> Tuple[str, str]:
    """
    Extract thinking content from response if present

    Looks for <think>...</think> tags in the response and extracts them.
    Also cleans up markdown code blocks if present (for JSON responses).

    Args:
        raw_response: Raw API response text

    Returns:
        Tuple of (cleaned_response, thinking_content)

    Example:
        >>> text = "Let me think <think>2+2 is 4</think> The answer is 4"
        >>> cleaned, thinking = extract_thinking(text)
        >>> print(cleaned)  # "Let me think  The answer is 4"
        >>> print(thinking)  # "2+2 is 4"
    """
    thinking_content = ""
    cleaned_response = raw_response

    # Extract <think> tags
    if "<think>" in raw_response and "</think>" in raw_response:
        start_idx = raw_response.find("<think>")
        end_idx = raw_response.find("</think>")
        if start_idx != -1 and end_idx != -1:
            thinking_content = raw_response[start_idx + 7:end_idx].strip()
            # Remove thinking tags from the response
            cleaned_response = raw_response[:start_idx] + raw_response[end_idx + 8:]

    # Clean up markdown code blocks if present (for JSON responses)
    cleaned_response = cleaned_response.strip()
    if cleaned_response.startswith("```json") and cleaned_response.endswith("```"):
        cleaned_response = cleaned_response[7:-3].strip()
    elif cleaned_response.startswith("```") and cleaned_response.endswith("```"):
        cleaned_response = cleaned_response[3:-3].strip()

    return cleaned_response.strip(), thinking_content


def retry_with_exponential_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,)
) -> Any:
    """
    Retry a function with exponential backoff

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exception types that should trigger retry

    Returns:
        Result of the function call

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except retryable_exceptions as e:
            last_exception = e

            # Don't retry on certain errors (client errors)
            if hasattr(e, 'status_code'):
                if e.status_code in [400, 401, 403, 404]:
                    raise

            # Calculate delay with exponential backoff
            if attempt < max_retries - 1:
                delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                print(f"[RETRY] Attempt {attempt + 1}/{max_retries} failed. Retrying in {delay:.1f}s...")
                time.sleep(delay)

    # All retries failed
    raise last_exception


def build_cache_control(cache_ttl: Optional[str] = None) -> dict:
    """
    Build Anthropic cache_control object

    Args:
        cache_ttl: Optional TTL ("5m" or "1h")

    Returns:
        cache_control dict for Anthropic API

    Example:
        >>> build_cache_control()
        {"type": "ephemeral"}
        >>> build_cache_control("5m")
        {"type": "ephemeral", "ttl": "5m"}
    """
    cache_control = {"type": "ephemeral"}

    if cache_ttl:
        if cache_ttl not in ["5m", "1h"]:
            raise ValueError(f"Invalid cache_ttl: {cache_ttl}. Must be '5m' or '1h'")
        cache_control["ttl"] = cache_ttl

    return cache_control


def normalize_messages(messages: list) -> list:
    """
    Normalize message format across providers

    Handles cache flags embedded in messages:
    - Extracts {"role": "...", "content": "...", "cache": True, "cache_ttl": "5m"}
    - Returns normalized messages for processing

    Args:
        messages: List of message dicts

    Returns:
        Normalized messages (cache flags preserved as metadata)
    """
    normalized = []

    for msg in messages:
        # Ensure all messages have required fields
        if "role" not in msg or "content" not in msg:
            raise ValueError(f"Invalid message format: {msg}")

        # Keep the message as-is (cache flag will be handled by adapters)
        normalized.append(msg.copy())

    return normalized


def format_json_instructions(instructions: str = None) -> str:
    """
    Generate JSON formatting instructions for providers that need it

    Args:
        instructions: Optional custom instructions

    Returns:
        JSON formatting instruction string
    """
    if instructions:
        return instructions

    return (
        "You must respond with valid JSON only. "
        "Do not include any text before or after the JSON object. "
        "Ensure the JSON is properly formatted and can be parsed."
    )


def parse_usage(provider_usage: dict, provider: str) -> dict:
    """
    Parse usage statistics from provider-specific format to unified format

    Handles detailed Anthropic cache statistics including TTL breakdowns.

    Args:
        provider_usage: Raw usage dict from provider
        provider: Provider name (groq, anthropic, grok, openai)

    Returns:
        Unified usage dict with standard fields and provider-specific details

    Anthropic Usage Structure:
        {
            "input_tokens": 100,
            "cache_read_input_tokens": 50,
            "cache_creation_input_tokens": 20,
            "output_tokens": 30,
            "cache_creation": {
                "ephemeral_5m_input_tokens": 10,
                "ephemeral_1h_input_tokens": 10
            }
        }
    """
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
        "cache_details": {}  # Provider-specific cache breakdown
    }

    # Ensure provider_usage is a dict and not None
    if not provider_usage or not isinstance(provider_usage, dict):
        return usage

    if provider == "anthropic":
        # Map Anthropic fields to standard fields
        input_tokens = provider_usage.get("input_tokens", 0)
        output_tokens = provider_usage.get("output_tokens", 0)

        usage["prompt_tokens"] = input_tokens
        usage["completion_tokens"] = output_tokens
        usage["total_tokens"] = input_tokens + output_tokens

        # Cache statistics (detailed)
        cache_read = provider_usage.get("cache_read_input_tokens", 0)
        cache_creation = provider_usage.get("cache_creation_input_tokens", 0)
        usage["cached_tokens"] = cache_read + cache_creation

        # Detailed cache breakdown (TTL-specific)
        cache_creation_details = provider_usage.get("cache_creation") or {}
        if cache_creation_details and isinstance(cache_creation_details, dict):
            usage["cache_details"] = {
                "cache_read_tokens": cache_read,
                "cache_creation_tokens": cache_creation,
                "ephemeral_5m_tokens": cache_creation_details.get("ephemeral_5m_input_tokens", 0),
                "ephemeral_1h_tokens": cache_creation_details.get("ephemeral_1h_input_tokens", 0),
            }

    elif provider == "grok":
        # Standard OpenAI-compatible fields
        usage["prompt_tokens"] = provider_usage.get("prompt_tokens", 0)
        usage["completion_tokens"] = provider_usage.get("completion_tokens", 0)
        usage["total_tokens"] = provider_usage.get("total_tokens", 0)

        # Grok cached tokens (from prompt_tokens_details)
        prompt_details = provider_usage.get("prompt_tokens_details") or {}
        if not isinstance(prompt_details, dict):
            prompt_details = {}
        cached = prompt_details.get("cached_tokens", 0)
        usage["cached_tokens"] = cached

        # Grok reasoning tokens (from completion_tokens_details)
        completion_details = provider_usage.get("completion_tokens_details") or {}
        if not isinstance(completion_details, dict):
            completion_details = {}
        reasoning = completion_details.get("reasoning_tokens", 0)
        usage["reasoning_tokens"] = reasoning

        # Build detailed cache breakdown
        if cached > 0 or reasoning > 0:
            usage["cache_details"] = {}
            if cached > 0:
                usage["cache_details"]["cached_tokens"] = cached
            if reasoning > 0:
                usage["cache_details"]["reasoning_tokens"] = reasoning

    elif provider in ["groq", "openai"]:
        # Standard OpenAI-compatible fields
        usage["prompt_tokens"] = provider_usage.get("prompt_tokens", 0)
        usage["completion_tokens"] = provider_usage.get("completion_tokens", 0)
        usage["total_tokens"] = provider_usage.get("total_tokens", 0)

        # Groq auto-caching (if available)
        if provider == "groq":
            prompt_details = provider_usage.get("prompt_tokens_details") or {}
            if not isinstance(prompt_details, dict):
                prompt_details = {}
            cached = prompt_details.get("cached_tokens", 0)
            if cached > 0:
                usage["cached_tokens"] = cached
                usage["cache_details"] = {"auto_cached_tokens": cached}

    return usage
