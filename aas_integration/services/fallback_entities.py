"""
Fallback entity creation and management for AAS sync operations.

Creates standardized fallback entities (DeviceType, RackType, Manufacturer) 
when objects are missing required data for AAS sync.
"""

# Lazy imports of Django models - imported only when needed to support testing
# from dcim.models import DeviceType, RackType, Manufacturer  
# from django.db import transaction


# Standardized names for fallback entities
FALLBACK_MANUFACTURER_NAME = "AAS Plugin Fallback Manufacturer"
FALLBACK_DEVICE_TYPE_MODEL = "AAS Plugin Fallback Device"
FALLBACK_RACK_TYPE_MODEL = "AAS Plugin Fallback Rack"


def get_or_create_fallback_manufacturer():
    """
    Get or create the fallback manufacturer.
    
    Returns:
        Tuple of (manufacturer, created)
    """
    # Lazy import to support testing without Django
    from dcim.models import Manufacturer
    from django.db import transaction
    from netbox.context import current_request
    
    # Temporarily clear request context to prevent change logging
    request = current_request.get()
    try:
        current_request.set(None)
        with transaction.atomic():
            manufacturer, created = Manufacturer.objects.get_or_create(
                name=FALLBACK_MANUFACTURER_NAME,
                defaults={
                    'slug': 'aas-plugin-fallback-manufacturer',
                    'description': 'Fallback manufacturer created by AAS Integration Plugin for objects without manufacturer data'
                }
            )
    finally:
        current_request.set(request)
    return manufacturer, created


def get_or_create_fallback_device_type():
    """
    Get or create the fallback device type with fallback manufacturer.
    
    Returns:
        Tuple of (device_type, created)
    """
    # Lazy import to support testing without Django
    from dcim.models import DeviceType
    from django.db import transaction
    from netbox.context import current_request
    
    # Temporarily clear request context to prevent change logging
    request = current_request.get()
    try:
        current_request.set(None)
        with transaction.atomic():
            # Ensure fallback manufacturer exists
            fallback_manufacturer, _ = get_or_create_fallback_manufacturer()
            
            # Create or get fallback device type
            device_type, created = DeviceType.objects.get_or_create(
                model=FALLBACK_DEVICE_TYPE_MODEL,
                manufacturer=fallback_manufacturer,
                defaults={
                    'slug': 'aas-plugin-fallback-device',
                    'part_number': 'AAS-FALLBACK-DEV',
                    'u_height': 1,
                    'is_full_depth': True,
                    'comments': 'Fallback device type created by AAS Integration Plugin for devices without device type data'
                }
            )
    finally:
        current_request.set(request)
    
    return device_type, created


def get_or_create_fallback_rack_type():
    """
    Get or create the fallback rack type with fallback manufacturer.
    
    Returns:
        Tuple of (rack_type, created)
    """
    # Lazy import to support testing without Django
    from dcim.models import RackType
    from django.db import transaction
    from netbox.context import current_request
    
    # Temporarily clear request context to prevent change logging
    request = current_request.get()
    try:
        current_request.set(None)
        with transaction.atomic():
            # Ensure fallback manufacturer exists
            fallback_manufacturer, _ = get_or_create_fallback_manufacturer()
            
            # Create or get fallback rack type
            # Note: RackType doesn't have part_number field like DeviceType does
            rack_type, created = RackType.objects.get_or_create(
                model=FALLBACK_RACK_TYPE_MODEL,
                manufacturer=fallback_manufacturer,
                defaults={
                    'slug': 'aas-plugin-fallback-rack',
                    'u_height': 42,  # Standard rack height
                    'comments': 'Fallback rack type created by AAS Integration Plugin for racks without rack type data'
                }
            )
    finally:
        current_request.set(request)
    
    return rack_type, created


def cleanup_unused_fallback_entities():
    """
    Clean up fallback entities that are no longer in use.
    
    This is a utility function that can be called periodically to clean up
    fallback entities that are no longer assigned to any objects.
    """
    # Lazy import to support testing without Django
    from dcim.models import Manufacturer, DeviceType, RackType
    from django.db import transaction
    
    with transaction.atomic():
        # Find fallback entities
        try:
            fallback_manufacturer = Manufacturer.objects.get(name=FALLBACK_MANUFACTURER_NAME)
        except Manufacturer.DoesNotExist:
            return  # No fallback entities exist
        
        # Check if fallback device type is in use
        try:
            fallback_device_type = DeviceType.objects.get(
                model=FALLBACK_DEVICE_TYPE_MODEL,
                manufacturer=fallback_manufacturer
            )
            if not fallback_device_type.instances.exists():
                fallback_device_type.delete()
        except DeviceType.DoesNotExist:
            pass
        
        # Check if fallback rack type is in use
        try:
            fallback_rack_type = RackType.objects.get(
                model=FALLBACK_RACK_TYPE_MODEL,
                manufacturer=fallback_manufacturer
            )
            if not fallback_rack_type.instances.exists():
                fallback_rack_type.delete()
        except RackType.DoesNotExist:
            pass
        
        # Check if fallback manufacturer is still in use
        if not (fallback_manufacturer.device_types.exists() or 
                fallback_manufacturer.rack_types.exists()):
            fallback_manufacturer.delete()


def get_fallback_entity_info() -> dict:
    """
    Get information about existing fallback entities.
    
    Returns:
        Dict with information about fallback entities and their usage
    """
    # Lazy import to support testing without Django
    from dcim.models import Manufacturer, DeviceType, RackType
    
    info = {
        'manufacturer': None,
        'device_type': None,
        'rack_type': None
    }
    
    # Check fallback manufacturer
    try:
        manufacturer = Manufacturer.objects.get(name=FALLBACK_MANUFACTURER_NAME)
        info['manufacturer'] = {
            'exists': True,
            'id': manufacturer.id,
            'name': manufacturer.name,
            'device_types_count': manufacturer.device_types.count(),
            'rack_types_count': manufacturer.rack_types.count()
        }
        
        # Check fallback device type
        try:
            device_type = DeviceType.objects.get(
                model=FALLBACK_DEVICE_TYPE_MODEL,
                manufacturer=manufacturer
            )
            info['device_type'] = {
                'exists': True,
                'id': device_type.id,
                'model': device_type.model,
                'devices_count': device_type.instances.count()
            }
        except DeviceType.DoesNotExist:
            info['device_type'] = {'exists': False}
        
        # Check fallback rack type
        try:
            rack_type = RackType.objects.get(
                model=FALLBACK_RACK_TYPE_MODEL,
                manufacturer=manufacturer
            )
            info['rack_type'] = {
                'exists': True,
                'id': rack_type.id,
                'model': rack_type.model,
                'racks_count': rack_type.instances.count()
            }
        except RackType.DoesNotExist:
            info['rack_type'] = {'exists': False}
            
    except Manufacturer.DoesNotExist:
        info['manufacturer'] = {'exists': False}
        info['device_type'] = {'exists': False}
        info['rack_type'] = {'exists': False}
    
    return info


def is_fallback_entity(obj) -> bool:
    """
    Check if an object is a fallback entity created by this plugin.
    
    Args:
        obj: NetBox object (Manufacturer, DeviceType, or RackType)
        
    Returns:
        True if the object is a fallback entity
    """
    # Lazy import to support testing without Django
    from dcim.models import Manufacturer, DeviceType, RackType
    
    if isinstance(obj, Manufacturer):
        return obj.name == FALLBACK_MANUFACTURER_NAME
    elif isinstance(obj, DeviceType):
        return (obj.model == FALLBACK_DEVICE_TYPE_MODEL and 
                obj.manufacturer and obj.manufacturer.name == FALLBACK_MANUFACTURER_NAME)
    elif isinstance(obj, RackType):
        return (obj.model == FALLBACK_RACK_TYPE_MODEL and 
                obj.manufacturer and obj.manufacturer.name == FALLBACK_MANUFACTURER_NAME)
    else:
        return False