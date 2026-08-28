"""
AAS Repository Client.

Handles all interactions with the AAS repository API for querying and managing
AAS shells and submodels.
"""
import logging
import base64
import requests
from aas_integration.logging_utils import sanitize_for_log
from ..defaults import TIMEOUT_LONG, TIMEOUT_SHORT

logger = logging.getLogger(__name__)


def fetch_shells(connection):
    try:
        auth_headers = connection.get_auth_headers()
        shells_url = f"{connection.aas_api_url}/shells"
        response = requests.get(
            shells_url,
            headers=auth_headers,
            timeout=TIMEOUT_LONG
        )
        if response.status_code != 200:
            logger.warning("Failed to fetch shells: HTTP %s", response.status_code)
            return []
        data = response.json()
        return data.get("result", [])
    except requests.exceptions.RequestException:
        logger.warning("Error querying AAS repository")
        return []
    except Exception:
        logger.exception("Unexpected error fetching shells from AAS repository")
        return []


def get_entity_type_from_shell_id(shell_id: str) -> str | None:
    """
    Extract entity type from AAS shell ID.
    
    Expected format: urn:namespace:aas:entity_type:name_id
    Example: urn:apeirora.eu:aas:device:server_1 or urn:apeirora.eu:aas:rack:R101_14
    
    Args:
        shell_id: AAS shell identifier (URN format)
    
    Returns:
        'device', 'rack', or None if unknown
    """
    if not shell_id:
        return None
    
    shell_lower = shell_id.lower()
    urn_parts = shell_lower.split(':')
    
    if len(urn_parts) != 5:
        logger.warning(f"Invalid URN format for shell ID: {sanitize_for_log(shell_id)} (expected 5 parts, got {len(urn_parts)})")
        return None
    
    schema, _, aas_type, entity_type, _ = urn_parts
    
    if schema != 'urn' or aas_type != 'aas':
        logger.warning(f"Unexpected URN format: {sanitize_for_log(shell_id)}")
        return None

    if entity_type not in ['device', 'rack']:
        logger.warning(f"Unknown entity type '{entity_type}' in URN: {sanitize_for_log(shell_id)}")
        return None

    return entity_type

def filter_shells_by_entity_type(shells, entity_type):
    """
    Filter shells by entity type.
    
    Args:
        shells: List of shell dictionaries from AAS repository
        entity_type: 'devices' or 'racks' (plural form)
    
    Returns:
        List of shells matching the entity type
    """
    entity_type_singular = entity_type.rstrip('s') if entity_type else None
    
    filtered = []
    for shell in shells:
        shell_id = shell.get("id", "")
        if not shell_id:
            continue
        
        shell_entity_type = get_entity_type_from_shell_id(shell_id)
        if shell_entity_type == entity_type_singular:
            filtered.append(shell)
    
    return filtered


def derive_submodel_types(submodel_refs):
    """Map submodel references to their type names."""
    submodel_types = []
    for ref in submodel_refs or []:
        keys = ref.get("keys", [])
        if not keys:
            continue
        submodel_id = keys[0].get("value", "")
        if "_Nameplate" in submodel_id:
            submodel_types.append("Nameplate")
        elif "_TechnicalData" in submodel_id:
            submodel_types.append("TechnicalData")
        elif "_RackUsage" in submodel_id:
            submodel_types.append("RackUsage")
        elif "_ContactInformation" in submodel_id:
            submodel_types.append("ContactInformation")
        elif "_CarbonFootprint" in submodel_id:
            submodel_types.append("CarbonFootprint")
    return submodel_types


def get_existing_submodels_for_entity(entity_type, connection):
    """
    Query the AAS repository to find which submodel types exist for each entity.
    
    Args:
        entity_type: 'devices' or 'racks'
        connection: AASConnection object
    
    Returns:
        dict: {submodel_type: count} e.g., {'Nameplate': 15, 'TechnicalData': 10}
    """
    submodel_counts = {}
    
    try:
        shells = fetch_shells(connection)
        filtered_shells = filter_shells_by_entity_type(shells, entity_type)
        
        for shell in filtered_shells:
            for submodel_type in derive_submodel_types(shell.get("submodels", [])):
                if entity_type == "devices" and submodel_type == "RackUsage":
                    continue
                submodel_counts[submodel_type] = submodel_counts.get(submodel_type, 0) + 1

        return submodel_counts
    except Exception:
        logger.exception("Unexpected error querying AAS repository")
        return submodel_counts


def get_submodels_for_shell(aas_id, connection):
    """
    Get the list of submodel types for a specific AAS shell.
    
    Args:
        aas_id: The AAS identifier (URN format)
        connection: AASConnection object
    
    Returns:
        list: List of submodel type names (e.g., ['Nameplate', 'TechnicalData'])
    """
    submodel_types = []
    
    try:
        auth_headers = connection.get_auth_headers()
        encoded_aas_id = base64.b64encode(aas_id.encode('utf-8')).decode('utf-8')
        shell_url = f"{connection.aas_api_url}/shells/{encoded_aas_id}"
        response = requests.get(
            shell_url,
            headers=auth_headers,
            timeout=TIMEOUT_SHORT
        )
        
        if response.status_code != 200:
            return submodel_types
        
        shell_data = response.json()
        submodel_refs = shell_data.get('submodels', [])
        
        for ref in submodel_refs:
            keys = ref.get('keys', [])
            if keys:
                submodel_id = keys[0].get('value', '')
                
                # Extract submodel type from URN
                if '_Nameplate' in submodel_id:
                    submodel_types.append('Nameplate')
                elif '_TechnicalData' in submodel_id:
                    submodel_types.append('TechnicalData')
                elif '_RackUsage' in submodel_id:
                    submodel_types.append('RackUsage')
                elif '_ContactInformation' in submodel_id:
                    submodel_types.append('ContactInformation')
                elif '_CarbonFootprint' in submodel_id:
                    submodel_types.append('CarbonFootprint')
        
        return submodel_types

    except Exception:
        logger.warning(f"Error getting submodels for shell {sanitize_for_log(aas_id)}")
        return submodel_types

def get_all_synced_shells_by_type(entity_type, connection):
    """
    Get all AAS shells for a specific entity type with their submodel info.
    
    Args:
        entity_type: 'devices' or 'racks'
        connection: AASConnection object
    
    Returns:
        dict: {
            'total_shells': int,
            'submodel_counts': {'Nameplate': count, ...},
            'shells': [{'id': str, 'submodels': [str, ...]}]
        }
    """
    result = {
        'total_shells': 0,
        'submodel_counts': {},
        'shells': []
    }
    
    try:
        shells = fetch_shells(connection)
        filtered_shells = filter_shells_by_entity_type(shells, entity_type)
        
        for shell in filtered_shells:
            submodel_types = derive_submodel_types(shell.get("submodels", []))
            
            for submodel_type in submodel_types:
                result['submodel_counts'][submodel_type] = result['submodel_counts'].get(submodel_type, 0) + 1

            result['shells'].append({
                'id': shell.get("id", ""),
                'submodels': submodel_types,
            })
            result['total_shells'] += 1
        
        return result
        
    except Exception:
        logger.exception(f"Error getting synced shells for {entity_type}")
        return result
