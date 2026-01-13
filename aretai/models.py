"""
Data models for AretAI
Unified request/response structures across all LLM providers
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class Usage:
    """Token usage statistics - unified across all providers"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0  # For Anthropic/Groq auto-caching
    reasoning_tokens: int = 0  # For Grok reasoning models
    cache_details: Dict[str, Any] = None  # Provider-specific cache breakdown

    def __post_init__(self):
        if self.cache_details is None:
            self.cache_details = {}

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cached_tokens": self.cached_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }
        if self.cache_details:
            result["cache_details"] = self.cache_details
        return result


@dataclass
class Message:
    """Chat message - OpenAI compatible"""
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "role": self.role,
            "content": self.content
        }


@dataclass
class Choice:
    """Response choice - OpenAI compatible"""
    index: int
    message: Message
    finish_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "message": self.message.to_dict(),
            "finish_reason": self.finish_reason
        }


@dataclass
class CompletionResponse:
    """
    Unified completion response - OpenAI compatible structure
    Works across Groq, Grok, Anthropic, and OpenAI
    """
    id: str
    model: str
    choices: List[Choice]
    usage: Usage
    provider: str  # Which provider was used

    # Optional fields
    thinking: Optional[str] = None  # Extracted <think> tags
    raw_response: Optional[Dict[str, Any]] = None  # Original provider response
    execution_time_ms: Optional[float] = None  # LLM call execution time in milliseconds

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "model": self.model,
            "choices": [choice.to_dict() for choice in self.choices],
            "usage": self.usage.to_dict(),
            "provider": self.provider,
            "thinking": self.thinking,
        }
        if self.execution_time_ms is not None:
            result["execution_time_ms"] = self.execution_time_ms
        return result


@dataclass
class CompletionRequest:
    """
    Unified completion request - validates and structures user input
    Supports all features across Groq, Grok, Anthropic, OpenAI
    """
    messages: List[Dict[str, Any]]
    model: str

    # Standard parameters (OpenAI compatible)
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 1.0
    stop: Optional[List[str]] = None

    # Response control
    response_format: Optional[Dict[str, str]] = None  # {"type": "json_object"}
    extract_thinking: bool = False  # Extract <think> tags from response

    # Provider-specific features
    seed: Optional[int] = None  # Groq: deterministic output
    cache_ttl: Optional[str] = None  # Anthropic: cache TTL ("5m" or "1h")

    # Advanced settings
    timeout: float = 120.0
    max_retries: int = 3

    def validate(self) -> None:
        """Validate request parameters"""
        if not self.messages:
            raise ValueError("messages cannot be empty")

        if not self.model:
            raise ValueError("model must be specified")

        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")

        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        if not 0 <= self.top_p <= 1:
            raise ValueError("top_p must be between 0 and 1")

        # Validate cache_ttl if provided
        if self.cache_ttl and self.cache_ttl not in ["5m", "1h"]:
            raise ValueError("cache_ttl must be '5m' or '1h' if specified")

        # Validate messages structure
        for i, msg in enumerate(self.messages):
            if "role" not in msg:
                raise ValueError(f"Message {i} missing 'role' field")
            if "content" not in msg:
                raise ValueError(f"Message {i} missing 'content' field")
            if msg["role"] not in ["system", "user", "assistant"]:
                raise ValueError(f"Message {i} has invalid role: {msg['role']}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API calls"""
        data = {
            "messages": self.messages,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }

        if self.stop:
            data["stop"] = self.stop
        if self.response_format:
            data["response_format"] = self.response_format
        if self.seed is not None:
            data["seed"] = self.seed

        return data
