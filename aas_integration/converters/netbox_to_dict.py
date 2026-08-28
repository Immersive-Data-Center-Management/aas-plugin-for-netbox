"""
Utility for converting NetBox model instances to dictionary representations.
Used for JSONPath-based field mapping in the dynamic submodel builder.
"""
from typing import Any, Dict, Set
from django.db import models
from django.db.models.fields.related import ForeignKey, OneToOneField, ManyToManyField


def netbox_obj_to_dict(obj: models.Model, max_depth: int = 3, _visited: Set[int] = None) -> Dict[str, Any]:
    """
    Convert a NetBox Django model instance to a nested dictionary for JSONPath evaluation.

    Handles:
    - Simple fields (CharField, IntegerField, etc.)
    - Foreign key relationships (e.g., device.device_type.manufacturer.name)
    - One-to-one relationships
    - Many-to-many relationships (converted to list)
    - Choice fields (returns the actual value, not display name)
    - JSON fields (returns the parsed dict/list)
    - Circular reference detection

    Args:
        obj: Django model instance to convert
        max_depth: Maximum depth for related field traversal (default 3)
        _visited: Internal set for tracking visited objects (prevents infinite loops)

    Returns:
        Dictionary representation suitable for JSONPath queries

    Example:
        device = Device.objects.get(name='switch-01')
        data = netbox_obj_to_dict(device)
        # Can now use JSONPath: $.device_type.manufacturer.name
    """
    if obj is None:
        return None

    if _visited is None:
        _visited = set()

    # Prevent infinite loops on circular references
    obj_id = id(obj)
    if obj_id in _visited:
        return {'__ref__': str(obj)}

    if max_depth <= 0:
        return {'__truncated__': str(obj)}

    _visited.add(obj_id)
    result = {}

    # Get all fields for this model
    for field in obj._meta.get_fields():
        field_name = field.name

        try:
            # Skip reverse relations (these would be query-heavy)
            if field.auto_created and not field.concrete:
                continue

            # Handle ForeignKey and OneToOneField
            if isinstance(field, (ForeignKey, OneToOneField)):
                related_obj = getattr(obj, field_name, None)
                if related_obj is not None:
                    # Recursively convert related object
                    result[field_name] = netbox_obj_to_dict(
                        related_obj,
                        max_depth=max_depth - 1,
                        _visited=_visited.copy()
                    )
                else:
                    result[field_name] = None

            # Handle ManyToManyField
            elif isinstance(field, ManyToManyField):
                related_objs = getattr(obj, field_name).all()
                result[field_name] = [
                    netbox_obj_to_dict(
                        related_obj,
                        max_depth=max_depth - 1,
                        _visited=_visited.copy()
                    )
                    for related_obj in related_objs[:20]  # Limit to first 20 to avoid huge datasets
                ]

            # Handle regular fields
            elif field.concrete:
                value = getattr(obj, field_name, None)

                # Convert UUID to string for JSONPath compatibility
                if hasattr(value, 'hex'):  # UUID objects
                    result[field_name] = str(value)
                # Keep primitives as-is (str, int, float, bool, dict, list)
                elif isinstance(value, (str, int, float, bool, type(None))):
                    result[field_name] = value
                elif isinstance(value, (dict, list)):
                    result[field_name] = value
                # Convert other objects to string representation
                else:
                    result[field_name] = str(value)

        except Exception:
            # If field access fails (lazy loading issues, etc.), skip it
            result[field_name] = '__error__'

    # Add string representation for reference
    result['__str__'] = str(obj)
    result['__model__'] = obj._meta.model_name

    return result


def get_field_value(obj: models.Model, field_path: str, default: Any = None) -> Any:
    """
    Get a field value from a NetBox object using dot notation.

    This is a simpler alternative to full JSONPath for basic field access.

    Args:
        obj: Django model instance
        field_path: Dot-notation path (e.g., "device_type.manufacturer.name")
        default: Default value if path cannot be resolved

    Returns:
        Field value or default if not found

    Example:
        value = get_field_value(device, "device_type.manufacturer.name", default="Unknown")
    """
    if not field_path:
        return default

    current = obj
    parts = field_path.split('.')

    for part in parts:
        try:
            if current is None:
                return default

            # Handle dict-like access (for JSON fields)
            if isinstance(current, dict):
                current = current.get(part)
            # Handle Django model field access
            else:
                current = getattr(current, part, None)
        except (AttributeError, KeyError, TypeError):
            return default

    return current if current is not None else default
