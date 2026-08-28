"""
Background tasks for AAS synchronization.

These tasks are executed by NetBox's RQ workers and handle the actual
communication with the BaSyx AAS Environment.
"""
import logging
from dcim.models import Device
from .models import AASConnection
from .services import SyncObject
from .logging_utils import sanitize_for_log

logger = logging.getLogger(__name__)


def sync_single_device_task(device, connection_id, created=False):
    """
    Background task to sync a single device to AAS.
    
    This task is queued by Django signals when a device is created or updated.
    It runs in the background to avoid blocking the web request.
    
    Args:
        device: device to sync
        connection_id: ID of the AASConnection to use
        created: Whether this is a new device (True) or update (False)
    """
    try:
        device = Device.objects.select_related(
            'device_type',
            'device_type__manufacturer',
            'site'
        ).get(id=device.id)
        sync_obj = SyncObject(obj=device,connection=AASConnection.objects.get(id=connection_id))
        sync_result = sync_obj.sync_entity_to_aas_repo()

        if sync_result.success:
            action = "created" if created else "updated"
            logger.info(f"Successfully {action} AAS for device {sanitize_for_log(device.name)}: {sync_result.message}")
        else:
            logger.warning(f"Failed to sync device {sanitize_for_log(device.name)} to AAS: {sync_result.message}")
            
    except Device.DoesNotExist:
        logger.error(f"Device {device.id} not found - may have been deleted")
    except AASConnection.DoesNotExist:
        logger.error(f"AAS Connection {connection_id} not found")
    except Exception:
        logger.exception(f"Unexpected error syncing device {device.id} to AAS.")


def delete_device_aas_task(device, connection_id):
    """
    Background task to delete AAS shell when device is deleted.
    
    This task is queued by Django signals when a device is deleted from NetBox.
    
    Args:
        device: deleted device
        device_name: Name of the deleted device (for logging)
        connection_id: ID of the AASConnection to use
    """
    try:
        sync_obj = SyncObject(obj=device, connection=AASConnection.objects.get(id=connection_id))
        delete_request = sync_obj.delete_shell_from_aas_repo()
        if delete_request.success:
            logger.info(f"Successfully deleted AAS for device {sanitize_for_log(device.name)}: {delete_request.message}")
        else:
            logger.warning(f"Failed to delete AAS for device {sanitize_for_log(device.name)}: {delete_request.message}")
            
    except AASConnection.DoesNotExist:
        logger.error(f"AAS Connection {connection_id} not found")
    except Exception:
        logger.exception(f"Unexpected error deleting AAS for device {sanitize_for_log(device.name)}")
