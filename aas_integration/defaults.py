"""
Package-wide defaults and constants for aas_integration.
Single source of truth for all configurable defaults and shared constants.
"""

URN_NAMESPACE_DEFAULT: str = "apeirora.eu"
URN_PREFIX: str = f"urn:{URN_NAMESPACE_DEFAULT}:aas:"

BASE_URL_DEFAULT: str = "netbox.local"

TIMEOUT_SHORT: int = 10   # test connection, submodel ref checks, shell existence
TIMEOUT_LONG: int = 30    # AASX upload, general requests

# --- MIME types ---
MIME_JSON: str = "application/json"
MIME_OCTET_STREAM: str = "application/octet-stream"
MIME_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# --- Fallback values ---
FALLBACK_UNKNOWN: str = "Unknown"
FALLBACK_ARTICLE_NUMBER: str = "N/A"

# --- Image limits ---
MAX_IMAGE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
