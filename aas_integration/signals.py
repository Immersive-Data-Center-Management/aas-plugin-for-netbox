"""
Django signals for automatic Device-to-AAS synchronization.

Automatically syncs NetBox devices to BaSyx AAS when they are created, updated, or deleted.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from dcim.models import Device, Rack
import logging


from .logging_utils import sanitize_for_log

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Rack)
@receiver(post_save, sender=Device)
def on_entity_saved(sender, instance, created, **kwargs):
    """
    Automatically sync entity to AAS after save.
    Triggered on both CREATE and UPDATE operations.
    Also syncs the rack if the entity is a device is installed in one.

    Args:
        sender: The model class
        instance: The actual entity instance being saved
        created: Boolean indicating if this is a new entity
        **kwargs: Additional signal arguments
    """
    # Avoid circular imports
    from .models import AASConnection
    from .services import SyncObject, get_entity_type_singular, get_object_name

    # Check if auto-sync is enabled for any connection
    default_connection = AASConnection.objects.filter(
        is_active=True,
        auto_sync_enabled=True,
        is_default=True
    ).first()

    if not default_connection:
        logger.info(
            f"Auto-sync disabled or no default connection found for "
            f"{get_entity_type_singular(instance)} {sanitize_for_log(get_object_name(instance))}"
        )
        return

    sync_obj = SyncObject(
        obj=instance,
        connection=default_connection,
    )

    action = "creation" if created else "update"
    logger.debug(
        f"SIGNAL FIRED: {sync_obj.entity_type_singular.capitalize()} "
        f"{sanitize_for_log(sync_obj.obj_name)} ({action}) - ID: {instance.id}"
    )

    logger.info(
        f"Using connection: {sanitize_for_log(default_connection.name)} "
        f"(auto_sync={default_connection.auto_sync_enabled})"
    )

    # Perform sync synchronously (NetBox 4.x doesn't require background tasks for this)
    try:
        logger.info(
            f"Starting AAS sync for {sync_obj.entity_type_singular} "
            f"{sanitize_for_log(sync_obj.obj_name)} to {default_connection.aas_api_url}"
        )
        sync_result = sync_obj.sync_entity_to_aas_repo()
        if sync_result.success:
            logger.warning(
                f"Auto-sync successful for {sync_obj.entity_type_singular} "
                f"{sanitize_for_log(sync_obj.obj_name)} ({action}): {sync_result.message}"
            )
        else:
            logger.error(
                f"Auto-sync failed for {sync_obj.entity_type_singular} "
                f"{sanitize_for_log(sync_obj.obj_name)} ({action}): {sync_result.message}"
            )

        # If device is installed in a rack, also update the rack's RackUsage submodel
        if hasattr(instance, 'rack') and instance.rack is not None:
            logger.info(
                f"{sync_obj.entity_type_singular.capitalize()} is in rack "
                f"{sanitize_for_log(instance.rack.name)}, syncing rack to update RackUsage submodel"
            )
            rack_sync_obj = SyncObject(
                obj=instance.rack,
                connection=default_connection,
            )
            sync_result_rack = rack_sync_obj.sync_entity_to_aas_repo()
            if sync_result_rack.success:
                logger.warning(
                    f"Rack {sanitize_for_log(rack_sync_obj.obj_name)} synced successfully: "
                    f"{sync_result_rack.message}"
                )
            else:
                logger.error(
                    f"Rack {sanitize_for_log(rack_sync_obj.obj_name)} sync failed: "
                    f"{sync_result_rack.message}"
                )
    except Exception:
        logger.exception(
            f"Exception during auto-sync for {sync_obj.entity_type_singular} "
            f"{sanitize_for_log(sync_obj.obj_name)}"
        )


@receiver(post_delete, sender=Device)
@receiver(post_delete, sender=Rack) #TODO: test rack, at the moment failing for my local instance (error 500)
def on_entity_deleted(sender, instance, **kwargs):
    """
    Delete AAS shell when an entity is deleted from NetBox.

    Args:
        sender: The model class (e.g. Device)
        instance: The actual entity instance being deleted
        **kwargs: Additional signal arguments
    """
    # Avoid circular imports
    from .models import AASConnection
    from .services import SyncObject, get_entity_type_singular, get_object_name

    # Check if auto-delete is enabled
    default_connection = AASConnection.objects.filter(
        is_active=True,
        auto_sync_enabled=True,
        auto_delete_enabled=True,
        is_default=True
    ).first()

    if not default_connection:
        logger.debug(
            f"Auto-delete disabled or no default connection found for "
            f"{get_entity_type_singular(instance)} {sanitize_for_log(get_object_name(instance))}"
        )
        return

    sync_obj = SyncObject(
        obj=instance,
        connection=default_connection,
    )

    # Perform deletion synchronously
    try:
        delete_request = sync_obj.delete_shell_from_aas_repo()
        if delete_request.success:
            logger.info(
                f"Auto-delete successful for {sync_obj.entity_type_singular} "
                f"{sanitize_for_log(sync_obj.obj_name)}: {delete_request.message}"
            )
        else:
            logger.warning(
                f"Auto-delete failed for {sync_obj.entity_type_singular} "
                f"{sanitize_for_log(sync_obj.obj_name)}: {delete_request.message}"
            )
    except Exception:
        logger.exception(
            f"Failed to auto-delete AAS for {sync_obj.entity_type_singular} "
            f"{sanitize_for_log(sync_obj.obj_name)}"
        )