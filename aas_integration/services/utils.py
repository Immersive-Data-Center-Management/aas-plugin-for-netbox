import base64
from django.db import models as django_models
from ..defaults import URN_NAMESPACE_DEFAULT
import re

class AASOperationsException(Exception):
    pass

def strip_url_protocol(base_url: str) -> str:
    """
    Remove protocol prefix from a URL.

    Args:
        base_url: URL that may contain http:// or https:// prefix

    Returns:
        URL without protocol prefix
    """
    return base_url.replace('https://', '').replace('http://', '')

def sanitize_name_for_urn(name: str, fallback_prefix: str, pk: int) -> str:
    """
    Sanitize a name for use in URN identifiers.

    Args:
        name: The name to sanitize (e.g., device.name or rack.name)
        fallback_prefix: Prefix to use if name is empty (e.g., 'device' or 'rack')
        pk: Primary key to use in fallback

    Returns:
        Sanitized name suitable for URN (only letters, digits, underscores)
    """

    if not name:
        return f"{fallback_prefix}_{pk}"

    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name) # Ensure only letters, digits, underscores
    sanitized = re.sub(r'_+', '_', sanitized).strip('_') # Collapse multiple underscores and trim

    if not sanitized:
        return f"{fallback_prefix}_{pk}"

    return sanitized

def encode_id_base64(identifier: str) -> str:
    """
    Encode an identifier to base64 URL-safe format.
    Args:
        identifier: Identifier to encode
    Returns:
        Base64 encoded identifier
    """
    try:
        return base64.urlsafe_b64encode(identifier.encode("utf-8")).decode("utf-8").rstrip("=")
    except Exception as e:
        raise AASOperationsException(f"Failed to encode {identifier}") from e

def create_aas_id(obj: django_models.Model, urn_namespace: str = URN_NAMESPACE_DEFAULT) -> str:
    """Construct a deterministic URN-based AAS ID for *obj* from its model name, sanitized name, and primary key."""
    try:
        entity_type = get_entity_type(obj)
        obj_name = getattr(obj, 'name', None) or str(obj)
        obj_id = obj.pk
        sanitized_name = sanitize_name_for_urn(obj_name, entity_type, obj_id)
        unique_name = f"{sanitized_name}_{obj_id}"
        return f"urn:{urn_namespace}:aas:{entity_type}:{unique_name}"
    except Exception as e:
        raise AASOperationsException("Error when creating AAS ID") from e

def get_entity_type(obj: django_models.Model) -> str:
    """Return the normalised entity-type string (e.g. ``'devices'``, ``'racks'``) for *obj*."""
    try:
        return obj._meta.verbose_name_plural.lower().replace(' ', '_')
    except Exception as e:
        raise AASOperationsException("Error while getting Entity Type") from e

def get_entity_type_singular(obj: django_models.Model) -> str:
    """Return the normalised singular entity-type string (e.g. ``'device'``, ``'rack'``) for *obj*."""
    try:
        return obj._meta.verbose_name.lower().replace(' ', '_')
    except Exception as e:
        raise AASOperationsException("Error while getting Entity Type") from e

def get_object_name(obj: django_models.Model) -> str:
    """Get user friendly object name"""
    try:
        return getattr(obj, 'name', None) or str(obj)
    except Exception as e:
        raise AASOperationsException("Error when getting object name") from e
