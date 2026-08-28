"""
Unit tests for SubmodelBuilder.

Tests submodel building from database configuration.
"""
import pytest
from unittest.mock import Mock
from basyx.aas import model as aas_model

from aas_integration.builders.submodel_builder import SubmodelBuilder


@pytest.fixture
def builder():
    """Fixture providing a SubmodelBuilder instance"""
    return SubmodelBuilder()


@pytest.fixture
def mock_device():
    """Fixture providing a mock device object"""
    device = Mock()
    device._meta.model_name = "device"
    device.name = "switch01"
    device.pk = 42
    device.serial = "SN123456"
    device.device_type.manufacturer.name = "Cisco"
    device.device_type.model = "Catalyst 2960"
    device.device_type.part_number = "WS-C2960-24TC-L"
    return device


class TestSubmodelBuilderDataTypeMapping:
    """Test XSD to AAS datatype mapping"""

    @pytest.mark.parametrize("xs_type,expected_type", [
        ("xs:string", aas_model.datatypes.String),
        ("xs:int", aas_model.datatypes.Int),
        ("xs:integer", aas_model.datatypes.Integer),
        ("xs:long", aas_model.datatypes.Long),
        ("xs:double", aas_model.datatypes.Double),
        ("xs:float", aas_model.datatypes.Float),
        ("xs:boolean", aas_model.datatypes.Boolean),
        ("xs:dateTime", aas_model.datatypes.DateTime),
        ("xs:date", aas_model.datatypes.Date),
        ("xs:time", aas_model.datatypes.Time),
        ("xs:anyURI", aas_model.datatypes.AnyURI),
        ("xs:unknown", aas_model.datatypes.String),  # default fallback
        ("", aas_model.datatypes.String),  # empty string
        (None, aas_model.datatypes.String),  # None
    ])
    def test_get_aas_datatype(self, builder, xs_type, expected_type):
        """Test converting XSD types to AAS datatypes"""
        result = builder._get_aas_datatype(xs_type)
        assert result == expected_type


class TestSubmodelBuilderLangStringCreation:
    """Test multilanguage string creation"""

    def test_create_langstring_text_type(self, builder):
        """Test creating MultiLanguageTextType (unlimited length)"""
        description = {"en": "English text", "de": "Deutscher Text", "fr": "Texte français"}

        result = builder._create_langstring_set(description, use_text_type=True)

        assert isinstance(result, aas_model.MultiLanguageTextType)
        assert result["en"] == "English text"
        assert result["de"] == "Deutscher Text"
        assert result["fr"] == "Texte français"

    def test_create_langstring_name_type(self, builder):
        """Test creating MultiLanguageNameType (max 64 chars)"""
        description = {"en": "Short Name", "de": "Kurzer Name"}

        result = builder._create_langstring_set(description, use_text_type=False)

        assert isinstance(result, aas_model.MultiLanguageNameType)
        assert result["en"] == "Short Name"
        assert result["de"] == "Kurzer Name"

    @pytest.mark.parametrize("invalid_input", [
        {},           # empty dict
        None,         # None
        [],           # wrong type
        "",           # empty string
    ])
    def test_create_langstring_invalid_input(self, builder, invalid_input):
        """Test langstring creation with invalid input returns None"""
        result = builder._create_langstring_set(invalid_input, use_text_type=True)
        assert result is None


class TestSubmodelBuilderSemanticReference:
    """Test semantic reference creation"""

    @pytest.mark.parametrize("semantic_id", [
        "0173-1#02-AAO677#002",
        "https://example.com/semantic/id",
        "urn:example:semantic:123",
        "simple-id",
    ])
    def test_create_semantic_reference(self, builder, semantic_id):
        """Test creating ExternalReference from semantic ID"""
        ref = builder._create_semantic_reference(semantic_id)

        assert isinstance(ref, aas_model.ExternalReference)
        assert len(ref.key) == 1
        assert ref.key[0].type == aas_model.KeyTypes.GLOBAL_REFERENCE
        assert ref.key[0].value == semantic_id

    def test_create_semantic_reference_empty_string(self, builder):
        """Test semantic reference with empty string raises ValueError"""
        # BaSyx enforces minimum length of 1 for identifiers
        with pytest.raises(ValueError, match="minimum length of 1"):
            builder._create_semantic_reference("")


class TestSubmodelBuilderNameGeneration:
    """Test unique name generation"""

    @pytest.mark.parametrize("name,pk,expected", [
        ("switch01", 42, "switch01_42"),
        ("Device-Name", 123, "Device_Name_123"),
        ("Device Name-01", 99, "Device_Name_01_99"),
        ("rack_A-1", 7, "rack_A_1_7"),
        ("___test___", 1, "test_1"),  # Multiple underscores collapsed
        ("Test!@#$%Name", 5, "Test_Name_5"),  # Special chars
    ])
    def test_generate_unique_name(self, builder, name, pk, expected):
        """Test unique name generation with various inputs"""
        mock_obj = Mock()
        mock_obj._meta.model_name = "device"
        mock_obj.name = name
        mock_obj.pk = pk

        result = builder._generate_unique_name(mock_obj)

        assert result == expected

    def test_generate_unique_name_empty_string(self, builder):
        """Test unique name generation when name is empty string"""
        from unittest.mock import MagicMock
        mock_obj = MagicMock()
        mock_obj._meta.model_name = "device"
        mock_obj.name = ""
        mock_obj.pk = 42
        mock_obj.__str__.return_value = "device_42_str"  # str(obj) fallback

        result = builder._generate_unique_name(mock_obj)

        # Empty string triggers str(obj) fallback, then sanitize
        # sanitize_name_for_urn("device_42_str", "device", 42) returns "device_42_str"
        # then we append _42 → "device_42_str_42"
        assert result == "device_42_str_42"

    def test_generate_unique_name_none(self, builder):
        """Test unique name generation when name is None"""
        from unittest.mock import MagicMock
        mock_obj = MagicMock()
        mock_obj._meta.model_name = "rack"
        mock_obj.name = None
        mock_obj.pk = 99
        mock_obj.__str__.return_value = "rack_99_str"  # str(obj) fallback

        result = builder._generate_unique_name(mock_obj)

        # None triggers str(obj) fallback, then sanitize and append pk
        assert result == "rack_99_str_99"

    def test_generate_unique_name_pk_zero(self, builder):
        """Test unique name generation with pk=0 (edge case)"""
        mock_obj = Mock()
        mock_obj._meta.model_name = "device"
        mock_obj.name = "test"
        mock_obj.pk = 0

        result = builder._generate_unique_name(mock_obj)

        assert result == "test_0"

    def test_generate_unique_name_very_large_pk(self, builder):
        """Test unique name generation with very large primary key"""
        mock_obj = Mock()
        mock_obj._meta.model_name = "device"
        mock_obj.name = "switch"
        mock_obj.pk = 2**63 - 1  # Max 64-bit int

        result = builder._generate_unique_name(mock_obj)

        assert result == f"switch_{2**63 - 1}"

    def test_generate_unique_name_only_special_chars(self, builder):
        """Test unique name when name contains only special characters"""
        mock_obj = Mock()
        mock_obj._meta.model_name = "device"
        mock_obj.name = "!@#$%^&*()"
        mock_obj.pk = 42

        result = builder._generate_unique_name(mock_obj)

        # sanitize_name_for_urn("!@#$%^&*()", "device", 42):
        # - Replace special chars with _ → "__________"
        # - Collapse multiple underscores → "_"
        # - Strip leading/trailing underscores → ""
        # - Empty result triggers fallback → "device_42"
        # Then _generate_unique_name appends _pk → "device_42_42"
        assert result == "device_42_42"

    def test_generate_unique_name_unicode_chars(self, builder):
        """Test unique name with unicode characters"""
        mock_obj = Mock()
        mock_obj._meta.model_name = "device"
        mock_obj.name = "Device-Ñame-01"
        mock_obj.pk = 123

        result = builder._generate_unique_name(mock_obj)

        # Non-ASCII chars should be replaced with underscores
        assert "123" in result
        assert "_" in result


class TestSubmodelBuilderFieldMapping:
    """Test field mapping resolution (integration with MappingResolver)"""

    def test_get_mapping_found(self, builder):
        """Test retrieving existing field mapping"""
        mock_config = Mock()
        mock_element = Mock()
        mock_mapping = Mock()

        mock_config.field_mappings.get.return_value = mock_mapping

        result = builder._get_mapping(mock_config, mock_element)

        assert result == mock_mapping
        mock_config.field_mappings.get.assert_called_once_with(submodel_element=mock_element)

    def test_get_mapping_not_found(self, builder):
        """Test retrieving non-existent field mapping returns None"""
        from aas_integration.models import FieldMapping

        mock_config = Mock()
        mock_element = Mock()

        mock_config.field_mappings.get.side_effect = FieldMapping.DoesNotExist()

        result = builder._get_mapping(mock_config, mock_element)

        assert result is None

    def test_get_mapping_multiple_found(self, builder):
        """Test multiple mappings returns first one (with warning)"""
        from aas_integration.models import FieldMapping

        mock_config = Mock()
        mock_element = Mock()
        mock_first_mapping = Mock()

        mock_config.field_mappings.get.side_effect = FieldMapping.MultipleObjectsReturned()
        mock_config.field_mappings.filter.return_value.first.return_value = mock_first_mapping

        result = builder._get_mapping(mock_config, mock_element)

        assert result == mock_first_mapping
        mock_config.field_mappings.filter.assert_called_once_with(submodel_element=mock_element)
