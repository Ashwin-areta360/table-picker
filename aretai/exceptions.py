"""
Custom exceptions for AretAI module
"""


class AretAIError(Exception):
    """Base exception for all AretAI errors"""
    pass


class ProviderError(AretAIError):
    """Error from LLM provider API"""
    def __init__(self, provider: str, message: str, status_code: int = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}" + (f" (status: {status_code})" if status_code else ""))


class AuthenticationError(AretAIError):
    """Authentication failed - invalid API key"""
    pass


class RateLimitError(AretAIError):
    """Rate limit exceeded"""
    pass


class InvalidRequestError(AretAIError):
    """Invalid request parameters"""
    pass


class TimeoutError(AretAIError):
    """Request timed out"""
    pass


class UnsupportedProviderError(AretAIError):
    """Unsupported provider specified"""
    pass


class ModelNotFoundError(AretAIError):
    """Model not found or not available"""
    pass


class ServerError(AretAIError):
    """Server error (5xx) from LLM provider"""
    def __init__(self, provider: str, message: str, status_code: int = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] Server error {status_code if status_code else '5xx'}: {message}")
