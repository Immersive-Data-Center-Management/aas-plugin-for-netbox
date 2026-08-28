"""
Logging utility functions.
"""
import re


def sanitize_for_log(value, max_length: int = 200) -> str:
    """
    Sanitize a string for safe logging by removing control characters.

    Args:
        value: The string to sanitize
        max_length: Maximum length to truncate to (default 200)

    Returns:
        Sanitized string safe for logging

    Example:
        >>> sanitize_for_log("normal text")
        'normal text'
        >>> sanitize_for_log("text\\nwith\\nnewlines")
        'text with newlines'
        >>> sanitize_for_log("x" * 300)
        'xxx...xxx (truncated)'
    """
    if not isinstance(value, str):
        value = str(value)

    # Remove control characters (including newlines, carriage returns, tabs)
    # Keep only printable ASCII and common Unicode characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', value)

    if len(sanitized) > max_length:
        truncated_length = max_length - 15
        sanitized = f"{sanitized[:truncated_length]}... (truncated)"

    return sanitized