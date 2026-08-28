"""
Unit tests for AASShellBuilder.

Tests AAS shell building with dynamic submodels.
"""
import pytest
from unittest.mock import Mock, patch
from basyx.aas import model as aas_model

from aas_integration.builders.aas_shell_builder import AASShellBuilder


@pytest.fixture
def builder():
    """Fixture providing an AASShellBuilder instance"""
    return AASShellBuilder()


@pytest.fixture
def mock_device():
    """Fixture providing a standard mock device"""
    device = Mock()
    device.name = "switch01"
    device.pk = 42
    device.id = 42
    return device


@pytest.fixture
def mock_rack():
    """Fixture providing a standard mock rack"""
    rack = Mock()
    rack.name = "rack-01-A"
    rack.pk = 7
    rack.id = 7
    return rack


@pytest.fixture
def mock_connection():
    """Fixture providing a mock AAS connection"""
    return Mock()


class TestAASShellBuilderBasicFunctionality:
    """Test core AAS shell building functionality"""

    @patch('aas_integration.builders.aas_shell_builder.build_submodels_for_entity')
    def test_build_aas_for_device_single_submodel(self, mock_build_submodels, builder, mock_device, mock_connection):
        """Test building AAS shell for device with single submodel"""
        # Create real submodel for BaSyx reference creation
        nameplate = aas_model.Submodel(
            id_="urn:apeirora.eu:sm:switch01_42_Nameplate",
            id_short="Nameplate"
        )
        mock_build_submodels.return_value = [nameplate]

        aas, submodels = builder.build_aas_for_entity(
            obj=mock_device,
            entity_type='devices',
            connection=mock_connection,
            base_url='netbox.local',
            urn_namespace='apeirora.eu'
        )

        # Verify submodel builder was called with correct parameters
        mock_build_submodels.assert_called_once_with(
            obj=mock_device,
            entity_type='devices',
            connection=mock_connection,
            base_url='netbox.local',
            urn_namespace='apeirora.eu'
        )

        # Verify AAS shell structure
        assert aas is not None
        assert isinstance(aas, aas_model.AssetAdministrationShell)
        assert aas.id == "urn:apeirora.eu:aas:devices:switch01_42"
        assert aas.id_short == "switch01_42"

        # Verify asset information
        assert aas.asset_information is not None
        assert aas.asset_information.asset_kind == aas_model.AssetKind.INSTANCE
        assert aas.asset_information.global_asset_id == "urn:apeirora.eu:aas:devices:switch01_42"

        # Verify submodel references
        assert isinstance(aas.submodel, set)
        assert len(aas.submodel) == 1

        # Verify returned submodels list
        assert len(submodels) == 1
        assert submodels[0] == nameplate

    @patch('aas_integration.builders.aas_shell_builder.build_submodels_for_entity')
    def test_build_aas_for_rack_multiple_submodels(self, mock_build_submodels, builder, mock_rack, mock_connection):
        """Test building AAS shell for rack with multiple submodels"""
        # Create real submodels
        nameplate = aas_model.Submodel(
            id_="urn:apeirora.eu:sm:rack_01_A_7_Nameplate",
            id_short="Nameplate"
        )
        rack_usage = aas_model.Submodel(
            id_="urn:apeirora.eu:sm:rack_01_A_7_RackUsage",
            id_short="RackUsage"
        )
        mock_build_submodels.return_value = [nameplate, rack_usage]

        aas, submodels = builder.build_aas_for_entity(
            obj=mock_rack,
            entity_type='racks',
            connection=mock_connection,
            base_url='netbox.local',
            urn_namespace='apeirora.eu'
        )

        # Verify AAS ID follows rack naming convention
        assert aas.id == "urn:apeirora.eu:aas:racks:rack_01_A_7"
        assert aas.id_short == "rack_01_A_7"

        # Verify multiple submodel references
        assert len(aas.submodel) == 2
        assert len(submodels) == 2

        # Verify all references are ModelReference objects
        for ref in aas.submodel:
            assert isinstance(ref, aas_model.ModelReference)

    @patch('aas_integration.builders.aas_shell_builder.build_submodels_for_entity')
    def test_build_aas_with_no_submodels(self, mock_build_submodels, builder, mock_device, mock_connection):
        """Test building AAS shell when no submodels are configured (empty shell is valid)"""
        mock_build_submodels.return_value = []

        aas, submodels = builder.build_aas_for_entity(
            obj=mock_device,
            entity_type='devices',
            connection=mock_connection,
            base_url='netbox.local',
            urn_namespace='apeirora.eu'
        )

        # Empty shell should still be created
        assert aas is not None
        assert aas.id == "urn:apeirora.eu:aas:devices:switch01_42"
        assert len(aas.submodel) == 0
        assert len(submodels) == 0


class TestAASShellBuilderURLHandling:
    """Test URL protocol stripping and handling"""

    @pytest.mark.parametrize("input_url,expected_url", [
        ("https://netbox.local", "netbox.local"),
        ("http://netbox.local", "netbox.local"),
        ("netbox.local", "netbox.local"),  # Already stripped
        ("https://192.168.1.1", "192.168.1.1"),
        ("http://netbox.local:8080", "netbox.local:8080"),
    ])
    @patch('aas_integration.builders.aas_shell_builder.build_submodels_for_entity')
    def test_build_aas_strips_url_protocol(self, mock_build_submodels, builder, mock_device, mock_connection, input_url, expected_url):
        """Test that base_url protocol is correctly stripped"""
        mock_build_submodels.return_value = []

        builder.build_aas_for_entity(
            obj=mock_device,
            entity_type='devices',
            connection=mock_connection,
            base_url=input_url,
            urn_namespace='apeirora.eu'
        )

        # Verify build_submodels_for_entity received stripped URL
        call_kwargs = mock_build_submodels.call_args[1]
        assert call_kwargs['base_url'] == expected_url


class TestAASShellBuilderNameGeneration:
    """Test unique name generation for different entity types"""

    @pytest.mark.parametrize("name,pk,expected", [
        ("switch01", 42, "switch01_42"),
        ("Device Name-01", 123, "Device_Name_01_123"),
        ("rack_A-1", 7, "rack_A_1_7"),
        ("Test!@#$%Name", 5, "Test_Name_5"),
    ])
    def test_generate_unique_name(self, builder, name, pk, expected):
        """Test unique name generation with various device names"""
        mock_obj = Mock()
        mock_obj.name = name
        mock_obj.pk = pk

        result = builder._generate_unique_name(mock_obj, 'devices')

        assert result == expected

    def test_generate_unique_name_empty_string(self, builder):
        """Test name generation when object name is empty"""
        from unittest.mock import MagicMock
        mock_obj = MagicMock()
        mock_obj.name = ""
        mock_obj.pk = 99
        mock_obj.__str__.return_value = "devices_99_str"  # str(obj) fallback

        result = builder._generate_unique_name(mock_obj, 'devices')

        # Empty string triggers str(obj) fallback in implementation
        assert result == "devices_99_str_99"

    def test_generate_unique_name_none(self, builder):
        """Test name generation when object name is None"""
        from unittest.mock import MagicMock
        mock_obj = MagicMock()
        mock_obj.name = None
        mock_obj.pk = 42
        mock_obj.__str__.return_value = "racks_42_str"  # str(obj) fallback

        result = builder._generate_unique_name(mock_obj, 'racks')

        # None triggers str(obj) fallback
        assert result == "racks_42_str_42"

    def test_generate_unique_name_special_chars_only(self, builder):
        """Test name generation when name contains only special characters"""
        mock_obj = Mock()
        mock_obj.name = "!@#$%^&*()"
        mock_obj.pk = 123

        result = builder._generate_unique_name(mock_obj, 'devices')

        # sanitize_name_for_urn with all special chars triggers fallback
        # Returns "devices_123", then _generate_unique_name appends _pk
        assert result == "devices_123_123"


class TestAASShellBuilderNamespaceHandling:
    """Test custom URN namespace handling"""

    @pytest.mark.parametrize("namespace", [
        "custom.example.com",
        "company.internal",
        "test.domain.org",
    ])
    @patch('aas_integration.builders.aas_shell_builder.build_submodels_for_entity')
    def test_build_aas_custom_namespace(self, mock_build_submodels, builder, mock_device, mock_connection, namespace):
        """Test building AAS with custom URN namespaces"""
        mock_build_submodels.return_value = []

        aas, _ = builder.build_aas_for_entity(
            obj=mock_device,
            entity_type='devices',
            connection=mock_connection,
            base_url='netbox.local',
            urn_namespace=namespace
        )

        # Verify custom namespace in AAS IDs
        assert aas.id == f"urn:{namespace}:aas:devices:switch01_42"
        assert aas.asset_information.global_asset_id == f"urn:{namespace}:aas:devices:switch01_42"

        # Verify namespace passed to submodel builder
        call_kwargs = mock_build_submodels.call_args[1]
        assert call_kwargs['urn_namespace'] == namespace


class TestAASShellBuilderEntityTypes:
    """Test support for different entity types"""

    @pytest.mark.parametrize("entity_type,name,pk,expected_id_pattern", [
        ("devices", "switch01", 1, "urn:apeirora.eu:aas:devices:switch01_1"),
        ("racks", "rack01", 2, "urn:apeirora.eu:aas:racks:rack01_2"),
        ("cables", "cable-01", 3, "urn:apeirora.eu:aas:cables:cable_01_3"),
        ("sites", "site-A", 4, "urn:apeirora.eu:aas:sites:site_A_4"),
    ])
    @patch('aas_integration.builders.aas_shell_builder.build_submodels_for_entity')
    def test_build_aas_for_different_entity_types(self, mock_build_submodels, builder, mock_connection, entity_type, name, pk, expected_id_pattern):
        """Test AAS building for various entity types (devices, racks, cables, etc.)"""
        mock_build_submodels.return_value = []

        mock_obj = Mock()
        mock_obj.name = name
        mock_obj.pk = pk
        mock_obj.id = pk

        aas, _ = builder.build_aas_for_entity(
            obj=mock_obj,
            entity_type=entity_type,
            connection=mock_connection,
            base_url='netbox.local',
            urn_namespace='apeirora.eu'
        )

        assert aas.id == expected_id_pattern
        assert entity_type in aas.id


class TestAASShellBuilderSubmodelReferences:
    """Test submodel reference creation and structure"""

    @patch('aas_integration.builders.aas_shell_builder.build_submodels_for_entity')
    def test_submodel_references_are_unique_set(self, mock_build_submodels, builder, mock_device, mock_connection):
        """Test that submodel references are stored in a set (no duplicates possible)"""
        submodel = aas_model.Submodel(
            id_="urn:apeirora.eu:sm:switch01_42_Nameplate",
            id_short="Nameplate"
        )
        mock_build_submodels.return_value = [submodel]

        aas, _ = builder.build_aas_for_entity(
            obj=mock_device,
            entity_type='devices',
            connection=mock_connection,
            base_url='netbox.local',
            urn_namespace='apeirora.eu'
        )

        # Verify submodel references are in a set (not list)
        assert isinstance(aas.submodel, set)
        assert len(aas.submodel) == 1

        # Verify reference is ModelReference type
        ref = list(aas.submodel)[0]
        assert isinstance(ref, aas_model.ModelReference)

    @patch('aas_integration.builders.aas_shell_builder.build_submodels_for_entity')
    def test_multiple_submodels_all_referenced(self, mock_build_submodels, builder, mock_device, mock_connection):
        """Test that all returned submodels are added as references"""
        submodels_list = [
            aas_model.Submodel(id_=f"urn:test:sm:sub{i}", id_short=f"Sub{i}")
            for i in range(5)
        ]
        mock_build_submodels.return_value = submodels_list

        aas, returned_submodels = builder.build_aas_for_entity(
            obj=mock_device,
            entity_type='devices',
            connection=mock_connection,
            base_url='netbox.local',
            urn_namespace='test'
        )

        # Verify count matches
        assert len(aas.submodel) == 5
        assert len(returned_submodels) == 5

        # Verify all are references
        assert all(isinstance(ref, aas_model.ModelReference) for ref in aas.submodel)
