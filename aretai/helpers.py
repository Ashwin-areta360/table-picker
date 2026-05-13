"""
Helper functions for AretAI
Quick access functions for common use cases
"""
from typing import Optional
from .client import AretAI


def quick_complete(
    prompt: str,
    provider: str = "groq",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    system_prompt: Optional[str] = None,
    response_format: Optional[dict] = None,
    extract_thinking: bool = False,
    **kwargs
) -> str:
    """
    Quick one-off LLM completion without creating a client instance

    This is a drop-in replacement for quick_llm_call() from the old llm_client.
    For multiple calls, use AretAI client directly for better performance.

    Args:
        prompt: User prompt/question
        provider: LLM provider ("groq", "anthropic", "grok", "openai")
        model: Model name (uses provider default if not specified)
        api_key: API key (reads from environment if not provided)
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        system_prompt: Optional system prompt
        response_format: Response format (e.g., {"type": "json_object"})
        extract_thinking: Extract <think> tags from response
        **kwargs: Additional parameters (seed, cache_ttl, etc.)

    Returns:
        Response content as string

    Example:
        >>> from aretai import quick_complete
        >>>
        >>> # Simple completion
        >>> answer = quick_complete(
        ...     prompt="What is the capital of France?",
        ...     provider="groq",
        ...     temperature=0.3
        ... )
        >>> print(answer)  # "Paris"
        >>>
        >>> # With system prompt and JSON mode
        >>> result = quick_complete(
        ...     prompt="Give me user data",
        ...     provider="anthropic",
        ...     system_prompt="You are a helpful assistant",
        ...     response_format={"type": "json_object"}
        ... )
        >>>
        >>> # Migration from old code:
        >>> # OLD: quick_llm_call(prompt, temperature=0.3)
        >>> # NEW: quick_complete(prompt, provider="groq", temperature=0.3)
    """
    # Build messages
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})

    # Create temporary client
    client = AretAI(provider=provider, model=model, api_key=api_key)

    # Make call
    response = client.chat.completions.create(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
        extract_thinking=extract_thinking,
        **kwargs
    )

    # Return content only (just like old quick_llm_call)
    return response.choices[0].message.content
