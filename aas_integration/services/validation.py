"""
Validation service for AAS sync operations.

Handles pre-sync validation and provides resolution options for missing data.
"""
from typing import Dict, List, Tuple, Any, Optional
from contextlib import contextmanager
from dcim.models import Device, Rack

class ValidationIssue:
    """Represents a validation issue with resolution options."""
    
    def __init__(self, issue_type: str, object_type: str, objects: List[Any], 
                 description: str, resolution_options: List[Dict[str, Any]]):
        self.issue_type = issue_type  # e.g., "missing_device_type", "missing_manufacturer"
        self.object_type = object_type  # "device" or "rack"
        self.objects = objects  # List of affected NetBox objects
        self.description = description
        self.resolution_options = resolution_options


class ValidationResult:
    """Result of validation with any issues found."""
    
    def __init__(self, is_valid: bool, issues: List[ValidationIssue] = None):
        self.is_valid = is_valid
        self.issues = issues or []
    
    def has_issues(self) -> bool:
        return len(self.issues) > 0
    
    def get_issue_summary(self) -> Dict[str, int]:
        """Get summary of issues by object type."""
        summary = {}
        for issue in self.issues:
            key = f"{issue.object_type}_{issue.issue_type}"
            summary[key] = len(issue.objects)
        return summary


def validate_asset_data() -> ValidationResult:
    """
    Validate all syncable objects for required data.
    
    Args:
        connection: AASConnection instance
        
    Returns:
        ValidationResult with any issues found
    """
    issues = []

    issues.extend(_validate_devices())
    issues.extend(_validate_racks())
    
    is_valid = len(issues) == 0
    return ValidationResult(is_valid, issues)


def _build_resolution_option(option_id: str, label: str, description: str, 
                            action: str, creates_entities: bool) -> Dict[str, Any]:
    return {
        "id": option_id,
        "label": label,
        "description": description,
        "action": action,
        "creates_entities": creates_entities
    }


def _fallback_strings_option(description: str) -> Dict[str, Any]:
    """Build the common 'fallback_strings' resolution option."""
    return _build_resolution_option(
        "fallback_strings",
        "Use default values only",
        description,
        "use_fallback_strings",
        False
    )


def _create_entity_option(option_id: str, entity_label: str, scope: str, action: str) -> Dict[str, Any]:
    """Build a resolution option that creates and assigns fallback entities."""
    return _build_resolution_option(
        option_id,
        f"Create & assign fallback {entity_label}",
        f"Create and assign fallback {entity_label} to affected {scope}",
        action,
        True
    )


@contextmanager
def _silent_save_context():
    """Temporarily suppress NetBox change logging."""
    from netbox.context import current_request
    
    request = current_request.get()
    try:
        current_request.set(None)
        yield
    finally:
        current_request.set(request)


@contextmanager
def _disable_aas_signals():
    """
    Temporarily disable AAS integration signals to prevent auto-sync during manual operations.
    This prevents signal-based sync from interfering with manual sync workflows.
    """
    from django.db.models.signals import post_save, post_delete
    from dcim.models import Device, Rack
    from aas_integration import signals
    
    signal_handlers = [
        (post_save, signals.on_entity_saved, Device),
        (post_delete, signals.on_entity_deleted, Device),
        (post_save, signals.on_entity_saved, Rack),
        (post_delete, signals.on_entity_deleted, Rack),
    ]
    
    for signal, handler, sender in signal_handlers:
        signal.disconnect(handler, sender=sender)
    
    try:
        yield
    finally:
        for signal, handler, sender in signal_handlers:
            signal.connect(handler, sender=sender)


def _validate_devices() -> List[ValidationIssue]:
    """Validate devices for sync requirements."""
    issues = []
    
    devices = Device.objects.filter(status='active').select_related('device_type__manufacturer')
    
    devices_without_type = [d for d in devices if d.device_type is None]
    if devices_without_type:
        issue = ValidationIssue(
            issue_type="missing_device_type",
            object_type="device",
            objects=devices_without_type,
            description=f"{len(devices_without_type)} devices have no device type assigned",
            resolution_options=_get_device_type_resolution_options()
        )
        issues.append(issue)
    
    devices_without_manufacturer = [
        d for d in devices 
        if d.device_type is not None and d.device_type.manufacturer is None
    ]
    if devices_without_manufacturer:
        issue = ValidationIssue(
            issue_type="missing_manufacturer",
            object_type="device",
            objects=devices_without_manufacturer,
            description=f"{len(devices_without_manufacturer)} devices have device types without manufacturers",
            resolution_options=_get_manufacturer_resolution_options("device")
        )
        issues.append(issue)
    
    return issues


def _validate_racks() -> List[ValidationIssue]:
    """Validate racks for sync requirements."""
    issues = []
    
    racks = Rack.objects.filter(status='active').select_related('rack_type__manufacturer')
    
    racks_without_type = [r for r in racks if r.rack_type is None]
    if racks_without_type:
        issue = ValidationIssue(
            issue_type="missing_rack_type",
            object_type="rack",
            objects=racks_without_type,
            description=f"{len(racks_without_type)} racks have no rack type assigned",
            resolution_options=_get_rack_type_resolution_options()
        )
        issues.append(issue)
    
    racks_without_manufacturer = [
        r for r in racks 
        if r.rack_type is not None and r.rack_type.manufacturer is None
    ]
    if racks_without_manufacturer:
        issue = ValidationIssue(
            issue_type="missing_manufacturer",
            object_type="rack",
            objects=racks_without_manufacturer,
            description=f"{len(racks_without_manufacturer)} racks have rack types without manufacturers",
            resolution_options=_get_manufacturer_resolution_options("rack")
        )
        issues.append(issue)
    
    return issues


def _get_device_type_resolution_options() -> List[Dict[str, Any]]:
    """Get resolution options for missing device types."""
    return [
        _fallback_strings_option(
            "Use 'Unknown Manufacturer' and '[Device Name] - Generic Device' in AAS nameplate only"
        ),
        _create_entity_option(
            "create_fallback_type",
            "device type",
            "devices",
            "create_fallback_device_type"
        )
    ]


def _get_rack_type_resolution_options() -> List[Dict[str, Any]]:
    """Get resolution options for missing rack types."""
    return [
        _fallback_strings_option(
            "Use 'Unknown Manufacturer' and '[Rack Name] - Generic Rack' in AAS nameplate only"
        ),
        _create_entity_option(
            "create_fallback_type",
            "rack type",
            "racks",
            "create_fallback_rack_type"
        )
    ]


def _get_manufacturer_resolution_options(object_type: str) -> List[Dict[str, Any]]:
    """Get resolution options for missing manufacturers."""
    return [
        _fallback_strings_option("Use 'Unknown Manufacturer' in AAS nameplate only"),
        _create_entity_option(
            "create_fallback_manufacturer",
            "manufacturer",
            f"{object_type} types",
            "create_fallback_manufacturer"
        )
    ]


def apply_resolution(issue: ValidationIssue, resolution_choice_id: str) -> Tuple[bool, str]:
    """
    Apply the chosen resolution for a validation issue.
    
    Args:
        issue: ValidationIssue to resolve
        resolution_choice_id: ID of the chosen resolution option (e.g., "fallback_strings", "create_fallback_type")
        user: Optional User instance for audit logging context (pass request.user from views)
        
    Returns:
        Tuple of (success, message)
    """
    resolution_option = None
    for opt in issue.resolution_options:
        if opt["id"] == resolution_choice_id:
            resolution_option = opt
            break
    
    if not resolution_option:
        return False, f"Invalid resolution choice: {resolution_choice_id}"
    
    action = resolution_option.get("action")
    
    try:
        if action == "use_fallback_strings":
            return True, f"Will use fallback strings for {len(issue.objects)} {issue.object_type}s"
            
        elif action == "create_fallback_device_type":
            return _create_and_assign_fallback_device_type(issue.objects)
            
        elif action == "create_fallback_rack_type":
            return _create_and_assign_fallback_rack_type(issue.objects)
            
        elif action == "create_fallback_manufacturer":
            return _create_and_assign_fallback_manufacturer(issue)
            
        else:
            return False, f"Unknown resolution action: {action}"

    except Exception:
        return False, "Error applying resolution"


def _create_and_assign_fallback_device_type(devices: List[Device]) -> Tuple[bool, str]:
    """Create fallback device type and assign to devices."""
    from .fallback_entities import get_or_create_fallback_device_type
    
    fallback_type, created = get_or_create_fallback_device_type()
    
    with _silent_save_context(), _disable_aas_signals():
        for device in devices:
            if device.device_type is None:
                device.device_type = fallback_type
                device.save()
    
    return True, f"Fallback device type {'created and ' if created else ''} assigned to {len(devices)} devices"


def _create_and_assign_fallback_rack_type(racks: List[Rack]) -> Tuple[bool, str]:
    """Create fallback rack type and assign to racks."""
    from .fallback_entities import get_or_create_fallback_rack_type
    
    fallback_type, created = get_or_create_fallback_rack_type()
    
    with _silent_save_context(), _disable_aas_signals():
        for rack in racks:
            if rack.rack_type is None:
                rack.rack_type = fallback_type
                rack.save()
    
    return True, f"Fallback rack type {'created and ' if created else ''} assigned to {len(racks)} racks"


def _create_and_assign_fallback_manufacturer(issue: ValidationIssue) -> Tuple[bool, str]:
    """Create fallback manufacturer and assign to device/rack types."""
    from .fallback_entities import get_or_create_fallback_manufacturer
    
    fallback_manufacturer, created = get_or_create_fallback_manufacturer()
    
    count = 0
    with _silent_save_context(), _disable_aas_signals():
        for obj in issue.objects:
            if issue.object_type == "device" and obj.device_type:
                if obj.device_type.manufacturer is None:
                    obj.device_type.manufacturer = fallback_manufacturer
                    obj.device_type.save()
                    count += 1
            elif issue.object_type == "rack" and obj.rack_type:
                if obj.rack_type.manufacturer is None:
                    obj.rack_type.manufacturer = fallback_manufacturer
                    obj.rack_type.save()
                    count += 1
    
    return True, f"Fallback manufacturer {'created and ' if created else ''} assigned to {count} {issue.object_type} types"