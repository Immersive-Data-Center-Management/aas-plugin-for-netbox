"""
Services for AAS integration.

This package contains client modules for interacting with external AAS services
and orchestration logic for sync operations.
"""
from .aas_client import (
    get_existing_submodels_for_entity,
    get_submodels_for_shell,
    get_all_synced_shells_by_type,
)

from .sync import (
    SyncObject,
    SyncParams,
    AASRequest,
)

from .utils import (
    create_aas_id,
    get_entity_type,
    get_entity_type_singular,
    get_object_name,
)

from .sync_results import (
    create_sync_results_template,
    create_type_results_template,
    finalize_sync_results,
)

__all__ = [
    # AAS client
    'get_existing_submodels_for_entity',
    'get_submodels_for_shell',
    'get_all_synced_shells_by_type',
    # AAS operations
    'create_aas_id',
    'get_entity_type',
    'get_entity_type_singular',
    'get_object_name',
    'SyncParams',
    'AASRequest',
    'SyncObject',
    # Sync result helpers
    'create_sync_results_template',
    'create_type_results_template',
    'finalize_sync_results',
]
