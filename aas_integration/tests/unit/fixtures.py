"""
Test fixtures and mock object factories for AAS integration tests.

Provides reusable mock NetBox objects (Device, Rack, Manufacturer, etc.)
to facilitate isolated unit testing without database dependencies.
"""
from unittest.mock import Mock, MagicMock
from io import BytesIO


def create_mock_manufacturer(name="TestManufacturer", slug=None):
    """
    Create a mock Manufacturer object.
    
    Args:
        name: Manufacturer name
        slug: URL slug (auto-generated if not provided)
    
    Returns:
        Mock Manufacturer object
    """
    manufacturer = Mock()
    manufacturer.name = name
    manufacturer.slug = slug or name.lower().replace(' ', '-')
    manufacturer.id = 1
    return manufacturer


def create_mock_device_type(
    manufacturer,
    model="TestModel",
    part_number=None,
    u_height=1,
    front_image=None,
    rear_image=None,
    slug=None
):
    """
    Create a mock DeviceType object.
    
    Args:
        manufacturer: Mock Manufacturer object
        model: Device model name
        part_number: Optional part number
        u_height: Height in rack units (default: 1)
        front_image: Optional mock ImageField for front image
        rear_image: Optional mock ImageField for rear image
        slug: URL slug (auto-generated if not provided)
    
    Returns:
        Mock DeviceType object
    """
    device_type = Mock()
    device_type.manufacturer = manufacturer
    device_type.model = model
    device_type.part_number = part_number
    device_type.u_height = u_height
    device_type.front_image = front_image
    device_type.rear_image = rear_image
    device_type.slug = slug or model.lower().replace(' ', '-')
    device_type.id = 10
    return device_type


def create_mock_image_field(filename="test.jpg", content=b"fake_image_data"):
    """
    Create a mock Django ImageField.
    
    Args:
        filename: Image filename (used for URL and content-type detection)
        content: Binary image data
    
    Returns:
        Mock ImageField object
    """
    image_field = MagicMock()
    image_field.url = f"/media/device-types/{filename}"
    image_field.name = filename
    
    # Mock the open() context manager to return binary data
    image_file = BytesIO(content)
    image_field.open.return_value.__enter__.return_value = image_file
    image_field.open.return_value.__exit__.return_value = None
    
    return image_field


def create_mock_device(
    device_type,
    name="test-device-01",
    serial=None,
    device_id=100,
    rack=None,
    position=None
):
    """
    Create a mock Device object.
    
    Args:
        device_type: Mock DeviceType object
        name: Device name
        serial: Optional serial number
        device_id: Device primary key
        rack: Optional mock Rack object
        position: Optional position in rack (U number)
    
    Returns:
        Mock Device object
    """
    device = Mock()
    device.name = name
    device.serial = serial
    device.id = device_id
    device.pk = device_id
    device.device_type = device_type
    device.rack = rack
    device.position = position
    return device


def create_mock_site(name="Test Site", physical_address=None):
    """
    Create a mock Site object.
    
    Args:
        name: Site name
        physical_address: Optional physical address
    
    Returns:
        Mock Site object
    """
    site = Mock()
    site.name = name
    site.physical_address = physical_address
    site.id = 50
    return site


def create_mock_rack_type(
    manufacturer,
    model="TestRack",
    slug=None
):
    """
    Create a mock RackType object.
    
    Args:
        manufacturer: Mock Manufacturer object
        model: Rack model name
        slug: URL slug (auto-generated if not provided)
    
    Returns:
        Mock RackType object
    """
    rack_type = Mock()
    rack_type.manufacturer = manufacturer
    rack_type.model = model
    rack_type.slug = slug or model.lower().replace(' ', '-')
    rack_type.id = 20
    return rack_type


def create_mock_rack(
    rack_type,
    name="test-rack-01",
    serial=None,
    rack_id=200,
    u_height=42,
    facility_id=None,
    site=None
):
    """
    Create a mock Rack object.
    
    Args:
        rack_type: Mock RackType object
        name: Rack name
        serial: Optional serial number
        rack_id: Rack primary key
        u_height: Rack height in units (default: 42)
        facility_id: Optional facility identifier
        site: Optional mock Site object
    
    Returns:
        Mock Rack object
    """
    rack = Mock()
    rack.name = name
    rack.serial = serial
    rack.id = rack_id
    rack.pk = rack_id
    rack.rack_type = rack_type
    rack.u_height = u_height
    rack.facility_id = facility_id
    rack.site = site
    return rack


def create_mock_submodel_configuration(entity_type, enabled_submodels):
    """
    Create a mock SubmodelConfiguration object.
    
    Args:
        entity_type: Entity type ('devices' or 'racks')
        enabled_submodels: List of enabled submodel IDs
    
    Returns:
        Mock SubmodelConfiguration object
    """
    config = Mock()
    config.entity_type = entity_type
    config.enabled_submodels = enabled_submodels
    config.id = 1
    return config


# Preset configurations for common test scenarios

def create_complete_device():
    """
    Create a fully populated mock Device with all optional fields.
    
    Returns:
        Mock Device with manufacturer, device_type, serial, images, etc.
    """
    manufacturer = create_mock_manufacturer("Cisco")
    
    front_image = create_mock_image_field("cisco-front.jpg", b"\xff\xd8\xff\xe0...JPEG")
    rear_image = create_mock_image_field("cisco-rear.png", b"\x89PNG...")
    
    device_type = create_mock_device_type(
        manufacturer=manufacturer,
        model="Catalyst 9300",
        part_number="C9300-48P",
        u_height=1,
        front_image=front_image,
        rear_image=rear_image
    )
    
    device = create_mock_device(
        device_type=device_type,
        name="sw-core-01",
        serial="FCW2315G0MA",
        device_id=101
    )
    
    return device


def create_minimal_device():
    """
    Create a minimally populated mock Device with only mandatory fields.
    
    Returns:
        Mock Device with just manufacturer and model
    """
    manufacturer = create_mock_manufacturer("Dell")
    device_type = create_mock_device_type(
        manufacturer=manufacturer,
        model="PowerEdge R640",
        part_number=None,
        front_image=None,
        rear_image=None
    )
    
    device = create_mock_device(
        device_type=device_type,
        name="server-01",
        serial=None,
        device_id=102
    )
    
    return device


def create_complete_rack():
    """
    Create a fully populated mock Rack with all optional fields.
    
    Returns:
        Mock Rack with manufacturer, rack_type, site, facility_id, etc.
    """
    manufacturer = create_mock_manufacturer("APC")
    rack_type = create_mock_rack_type(manufacturer=manufacturer, model="NetShelter SX")
    site = create_mock_site("Main DC", physical_address="123 Data Center Ave, City, Country")
    
    rack = create_mock_rack(
        rack_type=rack_type,
        name="rack-a01",
        serial="SX42U-001",
        rack_id=201,
        u_height=42,
        facility_id="DC1-A01",
        site=site
    )
    
    return rack


def create_minimal_rack():
    """
    Create a minimally populated mock Rack with only mandatory fields.
    
    Returns:
        Mock Rack with just manufacturer and model
    """
    manufacturer = create_mock_manufacturer("Generic")
    rack_type = create_mock_rack_type(manufacturer=manufacturer, model="Standard Rack")
    
    rack = create_mock_rack(
        rack_type=rack_type,
        name="rack-b01",
        serial=None,
        rack_id=202,
        u_height=42,
        facility_id=None,
        site=None
    )
    
    return rack
