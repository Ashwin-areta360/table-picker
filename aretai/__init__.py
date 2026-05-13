"""
AretAI - Unified LLM Client for Areta360

A single, consistent API for multiple LLM providers:
- Groq: Fast inference with auto-caching
- Anthropic (Claude): Advanced reasoning with prompt caching
- Grok (xAI): Reasoning models with thinking tokens
- OpenAI: Standard GPT models

Example:
    >>> from aretai import AretAI
    >>>
    >>> client = AretAI(provider="anthropic", model="claude-sonnet-4-5")
    >>> response = client.chat.completions.create(
    ...     messages=[{"role": "user", "content": "Hello!"}],
    ...     temperature=0.7
    ... )
    >>> print(response.choices[0].message.content)
"""

__version__ = "1.0.0"

# Main client
from .client import AretAI

# Helper functions
from .helpers import quick_complete

# Error formatting
from .error_formatter import (
    format_error,
    print_error,
    format_error_with_suggestions,
    print_error_with_suggestions,
)

# Exceptions
from .exceptions import (
    AretAIError,
    ProviderError,
    AuthenticationError,
    RateLimitError,
    InvalidRequestError,
    TimeoutError,
    UnsupportedProviderError,
    ModelNotFoundError,
    ServerError,
)

# Models (for type hints)
from .models import (
    CompletionResponse,
    CompletionRequest,
    Usage,
    Message,
    Choice,
)

__all__ = [
    # Main API
    "AretAI",
    "quick_complete",

    # Error formatting
    "format_error",
    "print_error",
    "format_error_with_suggestions",
    "print_error_with_suggestions",

    # Exceptions
    "AretAIError",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "InvalidRequestError",
    "TimeoutError",
    "UnsupportedProviderError",
    "ModelNotFoundError",
    "ServerError",

    # Models
    "CompletionResponse",
    "CompletionRequest",
    "Usage",
    "Message",
    "Choice",
]
