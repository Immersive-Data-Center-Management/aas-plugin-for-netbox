"""
Utility functions for AAS synchronization.

This module serves as a compatibility layer, re-exporting functions
from the refactored services package.

DEPRECATED: Import directly from .services instead.
"""

# Re-export from services for backward compatibility
from .services import (
    get_existing_submodels_for_entity,
    register_in_discovery_service,
)

__all__ = [
    'get_existing_submodels_for_entity',
    'register_in_discovery_service',
]

