"""
Colored error formatting for AretAI
Provides user-friendly error messages with color coding
"""
from typing import Optional
from .exceptions import (
    AretAIError,
    ProviderError,
    AuthenticationError,
    RateLimitError,
    TimeoutError,
    ModelNotFoundError,
    InvalidRequestError
)


class Colors:
    """ANSI color codes for terminal output"""
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def format_error(error: Exception, show_traceback: bool = False) -> str:
    """
    Format an error with appropriate colors based on error type

    Args:
        error: The exception to format
        show_traceback: Whether to include full traceback

    Returns:
        Formatted error string with color codes
    """
    # Determine error type and color
    if isinstance(error, AuthenticationError):
        color = Colors.RED
        error_type = "AUTHENTICATION ERROR"
    elif isinstance(error, RateLimitError):
        color = Colors.YELLOW
        error_type = "RATE LIMIT ERROR"
    elif isinstance(error, TimeoutError):
        color = Colors.YELLOW
        error_type = "TIMEOUT ERROR"
    elif isinstance(error, ModelNotFoundError):
        color = Colors.MAGENTA
        error_type = "MODEL NOT FOUND"
    elif isinstance(error, InvalidRequestError):
        color = Colors.CYAN
        error_type = "INVALID REQUEST"
    elif isinstance(error, ProviderError):
        color = Colors.RED
        error_type = "PROVIDER ERROR"
    elif isinstance(error, AretAIError):
        color = Colors.RED
        error_type = "ARETAI ERROR"
    else:
        color = Colors.RED
        error_type = "UNEXPECTED ERROR"

    # Build formatted message
    formatted = f"{color}{Colors.BOLD}[{error_type}]{Colors.RESET}\n"
    formatted += f"{color}{str(error)}{Colors.RESET}"

    # Add provider info if available
    if isinstance(error, ProviderError) and hasattr(error, 'provider'):
        formatted += f"\n{Colors.BLUE}Provider: {error.provider}{Colors.RESET}"

    # Add status code if available
    if hasattr(error, 'status_code') and error.status_code:
        formatted += f"\n{Colors.BLUE}Status Code: {error.status_code}{Colors.RESET}"

    # Add traceback if requested
    if show_traceback:
        import traceback
        tb = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        formatted += f"\n\n{Colors.YELLOW}Traceback:{Colors.RESET}\n{tb}"

    return formatted


def print_error(error: Exception, show_traceback: bool = False):
    """
    Print a formatted error to console

    Args:
        error: The exception to print
        show_traceback: Whether to include full traceback
    """
    print(format_error(error, show_traceback))


def get_error_suggestions(error: Exception) -> Optional[str]:
    """
    Get helpful suggestions based on error type

    Args:
        error: The exception to analyze

    Returns:
        Suggestion string or None
    """
    suggestions = {
        AuthenticationError: (
            f"{Colors.GREEN}Suggestions:{Colors.RESET}\n"
            f"  - Check your API key is correct\n"
            f"  - Verify the API key is set in environment variables\n"
            f"  - Ensure the API key hasn't expired"
        ),
        RateLimitError: (
            f"{Colors.GREEN}Suggestions:{Colors.RESET}\n"
            f"  - Wait a moment before retrying\n"
            f"  - Consider upgrading your API plan\n"
            f"  - Implement request throttling"
        ),
        TimeoutError: (
            f"{Colors.GREEN}Suggestions:{Colors.RESET}\n"
            f"  - Increase the timeout parameter\n"
            f"  - Check your network connection\n"
            f"  - Try a simpler query"
        ),
        ModelNotFoundError: (
            f"{Colors.GREEN}Suggestions:{Colors.RESET}\n"
            f"  - Check model name spelling\n"
            f"  - Verify model is available for your provider\n"
            f"  - See documentation for available models"
        ),
        InvalidRequestError: (
            f"{Colors.GREEN}Suggestions:{Colors.RESET}\n"
            f"  - Check your request parameters\n"
            f"  - Verify message format is correct\n"
            f"  - Review provider-specific requirements"
        ),
    }

    for error_type, suggestion in suggestions.items():
        if isinstance(error, error_type):
            return suggestion

    return None


def format_error_with_suggestions(error: Exception, show_traceback: bool = False) -> str:
    """
    Format error with helpful suggestions

    Args:
        error: The exception to format
        show_traceback: Whether to include full traceback

    Returns:
        Formatted error string with suggestions
    """
    formatted = format_error(error, show_traceback)

    suggestions = get_error_suggestions(error)
    if suggestions:
        formatted += f"\n\n{suggestions}"

    return formatted


def print_error_with_suggestions(error: Exception, show_traceback: bool = False):
    """
    Print formatted error with helpful suggestions

    Args:
        error: The exception to print
        show_traceback: Whether to include full traceback
    """
    print(format_error_with_suggestions(error, show_traceback))
