"""
Main AretAI client
Unified interface for all LLM providers
"""
import os
from typing import Optional, Dict
from .models import CompletionRequest, CompletionResponse
from .adapters import GroqAdapter, AnthropicAdapter, GrokAdapter, OpenAIAdapter
from .exceptions import UnsupportedProviderError

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, will use system environment variables only
    pass


class ChatCompletions:
    """
    Chat completions interface - OpenAI compatible

    This class provides the familiar .create() method for chat completions.
    """

    def __init__(self, adapter):
        self._adapter = adapter

    def create(
        self,
        messages: list,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        top_p: float = 1.0,
        stop: Optional[list] = None,
        response_format: Optional[Dict[str, str]] = None,
        extract_thinking: bool = False,
        seed: Optional[int] = None,
        cache_ttl: Optional[str] = None,
        timeout: float = 120.0,
        max_retries: int = 3,
        **kwargs
    ) -> CompletionResponse:
        """
        Create a chat completion - OpenAI compatible

        Args:
            messages: List of message dicts [{"role": "user", "content": "..."}]
            model: Model name (if not set during client initialization)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            stop: List of stop sequences
            response_format: Response format (e.g., {"type": "json_object"})
            extract_thinking: Extract <think> tags from response
            seed: Seed for deterministic output (Groq only)
            cache_ttl: Cache TTL for Anthropic ("5m" or "1h")
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            **kwargs: Additional provider-specific parameters

        Returns:
            CompletionResponse with unified structure

        Example:
            >>> client = AretAI(provider="anthropic", model="claude-sonnet-4-5")
            >>> response = client.chat.completions.create(
            ...     messages=[{"role": "user", "content": "Hello!"}],
            ...     temperature=0.7
            ... )
            >>> print(response.choices[0].message.content)
        """
        # Use default model if not specified
        if model is None:
            model = self._adapter._default_model

        # Build request
        request = CompletionRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stop=stop,
            response_format=response_format,
            extract_thinking=extract_thinking,
            seed=seed,
            cache_ttl=cache_ttl,
            timeout=timeout,
            max_retries=max_retries
        )

        # Execute via adapter
        return self._adapter.create_completion(request)


class Chat:
    """Chat interface - provides .completions attribute"""

    def __init__(self, adapter):
        self.completions = ChatCompletions(adapter)


class AretAI:
    """
    AretAI - Unified LLM client for Areta360

    Supports multiple providers with a single, consistent API:
    - Groq: Fast inference with auto-caching
    - Anthropic (Claude): Advanced reasoning with prompt caching
    - Grok (xAI): Reasoning models with thinking tokens
    - OpenAI: Standard GPT models

    Usage:
        >>> from aretai import AretAI
        >>>
        >>> # Initialize with provider
        >>> client = AretAI(provider="anthropic", model="claude-sonnet-4-5")
        >>>
        >>> # Make a request - OpenAI style
        >>> response = client.chat.completions.create(
        ...     messages=[
        ...         {"role": "system", "content": "You are helpful"},
        ...         {"role": "user", "content": "What is 2+2?"}
        ...     ],
        ...     temperature=0.7
        ... )
        >>>
        >>> # Access response
        >>> print(response.choices[0].message.content)
        >>> print(f"Tokens used: {response.usage.total_tokens}")
    """

    # Provider to adapter mapping
    ADAPTERS = {
        "groq": GroqAdapter,
        "anthropic": AnthropicAdapter,
        "grok": GrokAdapter,
        "openai": OpenAIAdapter,
    }

    # Environment variable mappings for API keys
    ENV_KEYS = {
        "groq": "GROQ_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "grok": "XAI_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    # Default models for each provider
    DEFAULT_MODELS = {
        "groq": "moonshotai/kimi-k2-instruct-0905",
        "anthropic": "claude-sonnet-4-5",
        "grok": "grok-code-fast-1",
        "openai": "gpt-5-2025-08-07",
    }

    def __init__(
        self,
        provider: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize AretAI client

        Args:
            provider: Provider name ("groq", "anthropic", "grok", "openai")
            api_key: API key (reads from environment if not provided)
            model: Default model to use
            **kwargs: Additional provider-specific configuration

        Raises:
            UnsupportedProviderError: If provider is not supported
            AuthenticationError: If API key is missing or invalid

        Example:
            >>> # With explicit API key
            >>> client = AretAI(provider="groq", api_key="your-key")
            >>>
            >>> # Auto-read from environment
            >>> client = AretAI(provider="anthropic")  # Reads ANTHROPIC_API_KEY
        """
        # Validate provider
        provider = provider.lower()
        if provider not in self.ADAPTERS:
            raise UnsupportedProviderError(
                f"Provider '{provider}' not supported. "
                f"Available providers: {', '.join(self.ADAPTERS.keys())}"
            )

        # Get API key from env if not provided
        if api_key is None:
            env_key = self.ENV_KEYS.get(provider)
            api_key = os.getenv(env_key)

            if not api_key:
                from .exceptions import AuthenticationError
                raise AuthenticationError(
                    f"API key not provided and {env_key} environment variable not set"
                )

        # Set default model
        if model is None:
            model = self.DEFAULT_MODELS.get(provider)

        # Initialize adapter
        adapter_class = self.ADAPTERS[provider]
        self._adapter = adapter_class(api_key=api_key, **kwargs)
        self._adapter._default_model = model
        self.provider = provider
        self.model = model

        # Create OpenAI-compatible interface
        self.chat = Chat(self._adapter)

    def __repr__(self) -> str:
        return f"AretAI(provider='{self.provider}', model='{self.model}')"
