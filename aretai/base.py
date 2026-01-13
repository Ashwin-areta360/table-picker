"""
Base adapter interface for AretAI
All provider adapters must implement this interface
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from .models import CompletionRequest, CompletionResponse


class BaseAdapter(ABC):
    """
    Abstract base class for all LLM provider adapters

    Each provider (Groq, Anthropic, Grok, OpenAI) implements this interface
    to provide a unified API regardless of the underlying provider's format.
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize the adapter

        Args:
            api_key: API key for the provider
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.provider_name = self._get_provider_name()

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return the provider name (groq, anthropic, grok, openai)"""
        pass

    @abstractmethod
    def create_completion(self, request: CompletionRequest) -> CompletionResponse:
        """
        Create a chat completion

        This is the main method that must be implemented by all adapters.
        It takes a unified CompletionRequest and returns a unified CompletionResponse.

        Args:
            request: Unified completion request

        Returns:
            Unified completion response

        Raises:
            ProviderError: If the API call fails
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit is exceeded
        """
        pass

    @abstractmethod
    def _transform_messages(self, messages: list, cache_ttl: str = None) -> Any:
        """
        Transform unified messages format to provider-specific format

        Handles:
        - Cache flags embedded in messages ({"cache": True, "cache_ttl": "5m"})
        - Provider-specific message structures
        - System prompts (separate or in messages)

        Args:
            messages: Unified message list
            cache_ttl: Optional cache TTL for Anthropic

        Returns:
            Provider-specific message format
        """
        pass

    @abstractmethod
    def _transform_response(self, raw_response: Any, extract_thinking: bool) -> CompletionResponse:
        """
        Transform provider-specific response to unified format

        Args:
            raw_response: Raw response from provider API
            extract_thinking: Whether to extract <think> tags

        Returns:
            Unified CompletionResponse
        """
        pass

    def _validate_api_key(self) -> None:
        """Validate that API key is set"""
        if not self.api_key:
            from .exceptions import AuthenticationError
            raise AuthenticationError(f"API key not provided for {self.provider_name}")

    def _handle_json_mode(self, messages: list, response_format: Dict[str, str] = None) -> list:
        """
        Handle JSON response format for providers that need explicit instructions

        Some providers (like Anthropic) need JSON instructions in the system prompt
        instead of a response_format parameter.

        Args:
            messages: Message list
            response_format: Response format dict (e.g., {"type": "json_object"})

        Returns:
            Modified messages with JSON instructions if needed
        """
        if not response_format or response_format.get("type") != "json_object":
            return messages

        # Default: return messages as-is (provider supports response_format natively)
        return messages
