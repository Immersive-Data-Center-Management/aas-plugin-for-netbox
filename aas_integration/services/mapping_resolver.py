"""
Service for resolving field mappings from NetBox objects to AAS element values.
Uses JSONPath expressions for secure field extraction.
"""
from typing import Any, Dict, Optional
from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.exceptions import JsonPathParserError
from django.db import models

from ..converters import netbox_obj_to_dict


class MappingResolver:
    """
    Resolves FieldMapping records to actual values from NetBox objects.

    Supports multiple mapping types:
    - JSONPATH: Extract field using JSONPath expression (e.g., "$.device_type.manufacturer.name")
    - STATIC: Return a static value

    Includes transformation support (uppercase, lowercase, sanitize_urn, etc.)
    """

    def __init__(self):
        self._transform_functions = {
            'uppercase': self._transform_uppercase,
            'lowercase': self._transform_lowercase,
            'strip_protocol': self._transform_strip_protocol,
            'sanitize_urn': self._transform_sanitize_urn,
            'format_uri': self._transform_format_uri,
        }

    def resolve(
        self,
        obj: models.Model,
        mapping: 'FieldMapping',  # Type hint for FieldMapping model
        obj_dict: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Resolve a FieldMapping to an actual value from a NetBox object.

        Args:
            obj: NetBox model instance (Device, Rack, etc.)
            mapping: FieldMapping instance with expression and configuration
            obj_dict: Pre-converted dict representation (optional, for performance)

        Returns:
            Resolved value (may be str, int, float, dict for multilanguage, or None)

        Raises:
            ValueError: If mapping configuration is invalid
        """
        # Convert object to dict if not provided (cached for multiple mappings)
        if obj_dict is None:
            obj_dict = netbox_obj_to_dict(obj)

        # Try JSONPath expression first, fall back to default value
        value = None
        if mapping.jsonpath_expression:
            value = self._resolve_jsonpath(obj_dict, mapping.jsonpath_expression)

        # Apply default value if result is None/empty
        if value is None or (isinstance(value, str) and not value.strip()):
            value = mapping.default_value if mapping.default_value else None

        # Apply transformation function if configured
        if value is not None and mapping.transform_function:
            value = self._apply_transform(value, mapping.transform_function)

        # Handle multilanguage conversion
        if mapping.is_multilanguage and value is not None:
            # If value is already a dict, assume it's multilanguage
            if isinstance(value, dict):
                return value
            # Otherwise wrap in language code
            return {mapping.language_code: str(value)}

        return value

    def _resolve_jsonpath(self, obj_dict: Dict[str, Any], expression: str) -> Optional[Any]:
        """
        Resolve a JSONPath expression against object dictionary.

        Args:
            obj_dict: Dictionary representation of object
            expression: JSONPath expression (e.g., "$.device_type.manufacturer.name")

        Returns:
            First matching value or None
        """
        if not expression or not expression.strip():
            return None

        try:
            # Parse and evaluate JSONPath expression
            jsonpath_expr = jsonpath_parse(expression)
            matches = jsonpath_expr.find(obj_dict)

            if matches:
                # Return first match value
                return matches[0].value
            return None

        except JsonPathParserError as e:
            raise ValueError(f"Invalid JSONPath expression '{expression}': {e}")
        except Exception as e:
            raise ValueError(f"Error evaluating JSONPath '{expression}': {e}")

    def _apply_transform(self, value: Any, transform_function: str) -> Any:
        """
        Apply a transformation function to a value.

        Args:
            value: Input value to transform
            transform_function: Name of built-in transformation

        Returns:
            Transformed value
        """
        # Apply built-in transformation
        transform_fn = self._transform_functions.get(transform_function)
        if transform_fn:
            return transform_fn(value)

        return value  # No transformation

    # Built-in transformation functions

    def _transform_uppercase(self, value: Any) -> str:
        """Convert value to uppercase string."""
        return str(value).upper() if value is not None else ''

    def _transform_lowercase(self, value: Any) -> str:
        """Convert value to lowercase string."""
        return str(value).lower() if value is not None else ''

    def _transform_strip_protocol(self, value: Any) -> str:
        """Strip http:// or https:// from URL."""
        s = str(value) if value is not None else ''
        if s.startswith('https://'):
            return s[8:]
        if s.startswith('http://'):
            return s[7:]
        return s

    def _transform_sanitize_urn(self, value: Any) -> str:
        """
        Sanitize value for use in URN format.
        Replaces spaces with underscores, removes special characters.
        """
        s = str(value) if value is not None else ''
        # Replace spaces with underscores
        s = s.replace(' ', '_')
        # Remove or replace characters not allowed in URNs
        allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.')
        s = ''.join(c if c in allowed else '_' for c in s)
        return s

    def _transform_format_uri(self, value: Any) -> str:
        """
        Format value as URI (add http:// if not present).
        """
        s = str(value) if value is not None else ''
        if s and not s.startswith(('http://', 'https://', 'ftp://', 'urn:')):
            return f'http://{s}'
        return s


class MappingValidationError(Exception):
    """Raised when a required mapping cannot be resolved."""
    pass


def validate_mapping(mapping: 'FieldMapping') -> None:
    """
    Validate a FieldMapping configuration.

    Args:
        mapping: FieldMapping instance to validate

    Raises:
        ValueError: If mapping configuration is invalid
    """
    # Ensure mapping has appropriate expression for its type
    # Validate that at least one source is provided
    if not mapping.jsonpath_expression and not mapping.default_value:
        raise ValueError("At least one of jsonpath_expression or default_value must be provided")

    # Validate JSONPath syntax
    if mapping.jsonpath_expression:
        try:
            jsonpath_parse(mapping.jsonpath_expression)
        except JsonPathParserError as e:
            raise ValueError(f"Invalid JSONPath syntax in '{mapping.jsonpath_expression}': {e}")
