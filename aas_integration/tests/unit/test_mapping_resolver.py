"""
Unit tests for MappingResolver.

Tests JSONPath field mapping resolution from NetBox objects to AAS element values.
"""
import pytest
from unittest.mock import Mock, patch
from jsonpath_ng.exceptions import JsonPathParserError

from aas_integration.services.mapping_resolver import (
    MappingResolver,
    MappingValidationError,
)


@pytest.fixture
def resolver():
    """Fixture providing a MappingResolver instance"""
    return MappingResolver()


@pytest.fixture
def mock_obj():
    """Fixture providing a basic mock NetBox object"""
    return Mock()


def create_mock_mapping(**kwargs):
    """Helper to create complete mock FieldMapping with all required attributes"""
    mock = Mock()
    mock.jsonpath_expression = kwargs.get('jsonpath_expression', None)
    mock.default_value = kwargs.get('default_value', None)
    mock.transform_function = kwargs.get('transform_function', None)
    mock.is_multilanguage = kwargs.get('is_multilanguage', False)
    mock.language_code = kwargs.get('language_code', 'en')
    return mock


class TestMappingResolverJSONPathBasics:
    """Test basic JSONPath resolution"""

    @pytest.mark.parametrize("jsonpath,data,expected", [
        ('$.serial', {'serial': 'ABC123'}, 'ABC123'),
        ('$.name', {'name': 'Device-01'}, 'Device-01'),
        ('$.id', {'id': 42}, 42),
        ('$.is_active', {'is_active': True}, True),
    ])
    def test_resolve_jsonpath_simple_fields(self, resolver, mock_obj, jsonpath, data, expected):
        """Test resolving various simple top-level fields with JSONPath"""
        mapping = create_mock_mapping(jsonpath_expression=jsonpath)

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = data

            result = resolver.resolve(mock_obj, mapping)

            assert result == expected
            mock_to_dict.assert_called_once_with(mock_obj)

    @pytest.mark.parametrize("jsonpath,data,expected", [
        ('$.device_type.manufacturer.name',
         {'device_type': {'manufacturer': {'name': 'Cisco'}}},
         'Cisco'),
        ('$.site.region.name',
         {'site': {'region': {'name': 'North America'}}},
         'North America'),
        ('$.rack.location.facility.name',
         {'rack': {'location': {'facility': {'name': 'DC-01'}}}},
         'DC-01'),
    ])
    def test_resolve_jsonpath_nested_fields(self, resolver, mock_obj, jsonpath, data, expected):
        """Test resolving nested object paths"""
        mapping = create_mock_mapping(jsonpath_expression=jsonpath)

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = data

            result = resolver.resolve(mock_obj, mapping)

            assert result == expected

    @pytest.mark.parametrize("jsonpath,data", [
        ('$.nonexistent', {'serial': 'ABC123'}),
        ('$.device_type.missing.field', {'device_type': {'name': 'Switch'}}),
        ('$.completely.wrong.path', {}),
    ])
    def test_resolve_jsonpath_missing_field_returns_none(self, resolver, mock_obj, jsonpath, data):
        """Test JSONPath that doesn't match any data returns None"""
        mapping = create_mock_mapping(
            jsonpath_expression=jsonpath,
            default_value=None
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = data

            result = resolver.resolve(mock_obj, mapping)

            assert result is None


class TestMappingResolverDefaultValues:
    """Test default value handling"""

    @pytest.mark.parametrize("default_value,expected", [
        ('UNKNOWN', 'UNKNOWN'),
        ('N/A', 'N/A'),
        ('Not Specified', 'Not Specified'),
        ('', None),  # Empty string is falsy, becomes None
        (0, None),   # Zero is falsy, becomes None
    ])
    def test_resolve_with_default_value(self, resolver, mock_obj, default_value, expected):
        """Test that default values are used when field is missing"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.nonexistent.field',
            default_value=default_value
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {'serial': 'ABC123'}

            result = resolver.resolve(mock_obj, mapping)

            assert result == expected

    def test_resolve_empty_string_uses_default(self, resolver, mock_obj):
        """Test that empty string triggers default value"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.serial',
            default_value='UNKNOWN'
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {'serial': ''}

            result = resolver.resolve(mock_obj, mapping)

            # Empty string should trigger default
            assert result == 'UNKNOWN'

    def test_resolve_whitespace_string_uses_default(self, resolver, mock_obj):
        """Test that whitespace-only string triggers default value"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.serial',
            default_value='N/A'
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {'serial': '   '}

            result = resolver.resolve(mock_obj, mapping)

            assert result == 'N/A'


class TestMappingResolverStaticValues:
    """Test static value mapping"""

    @pytest.mark.parametrize("default_value", [
        'CONSTANT_VALUE',
        'EN 61406:2005',
        'https://example.com/spec',
        42,
        True,
    ])
    def test_resolve_default_values(self, resolver, mock_obj, default_value):
        """Test resolving default values when JSONPath is not provided"""
        mapping = create_mock_mapping(
            default_value=default_value
        )

        result = resolver.resolve(mock_obj, mapping, obj_dict={})

        assert result == default_value


class TestMappingResolverMultilanguage:
    """Test multilanguage property mapping"""

    @pytest.mark.parametrize("language_code", ['en', 'de', 'fr', 'es', 'zh'])
    def test_resolve_multilanguage_property(self, resolver, mock_obj, language_code):
        """Test resolving value as multilanguage property with different languages"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.device_type.manufacturer.name',
            is_multilanguage=True,
            language_code=language_code
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {
                'device_type': {'manufacturer': {'name': 'Cisco'}}
            }

            result = resolver.resolve(mock_obj, mapping)

            # Should wrap in language dict with correct language code
            assert result == {language_code: 'Cisco'}

    def test_resolve_multilanguage_already_dict(self, resolver, mock_obj):
        """Test multilanguage when value is already a dict (passthrough)"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.multilang_field',
            is_multilanguage=True,
            language_code='en'
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {
                'multilang_field': {'en': 'English', 'de': 'German'}
            }

            result = resolver.resolve(mock_obj, mapping)

            # Should return dict as-is
            assert result == {'en': 'English', 'de': 'German'}


class TestMappingResolverTransformations:
    """Test value transformation functions"""

    @pytest.mark.parametrize("input_value,expected", [
        ('abc123', 'ABC123'),
        ('lowercase', 'LOWERCASE'),
        ('MiXeD CaSe', 'MIXED CASE'),
    ])
    def test_transform_uppercase(self, resolver, mock_obj, input_value, expected):
        """Test uppercase transformation"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.value',
            transform_function='uppercase'
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {'value': input_value}

            result = resolver.resolve(mock_obj, mapping)

            assert result == expected

    @pytest.mark.parametrize("input_value,expected", [
        ('ABC123', 'abc123'),
        ('UPPERCASE', 'uppercase'),
        ('MiXeD CaSe', 'mixed case'),
    ])
    def test_transform_lowercase(self, resolver, mock_obj, input_value, expected):
        """Test lowercase transformation"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.value',
            transform_function='lowercase'
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {'value': input_value}

            result = resolver.resolve(mock_obj, mapping)

            assert result == expected

    @pytest.mark.parametrize("input_url,expected", [
        ('https://example.com', 'example.com'),
        ('http://example.com', 'example.com'),
        ('https://192.168.1.1', '192.168.1.1'),
        ('http://netbox.local:8080', 'netbox.local:8080'),
        ('example.com', 'example.com'),  # Already stripped
    ])
    def test_transform_strip_protocol(self, resolver, mock_obj, input_url, expected):
        """Test strip_protocol transformation"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.url',
            transform_function='strip_protocol'
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {'url': input_url}

            result = resolver.resolve(mock_obj, mapping)

            assert result == expected

    @pytest.mark.parametrize("input_name,expected", [
        ('Device Name-01', 'Device_Name-01'),  # Space → _, dash allowed
        ('Test!@#$%Name', 'Test_____Name'),     # Special chars → _
        ('___test___', '___test___'),           # Underscores preserved
    ])
    def test_transform_sanitize_urn(self, resolver, mock_obj, input_name, expected):
        """Test sanitize_urn transformation"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.name',
            transform_function='sanitize_urn'
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {'name': input_name}

            result = resolver.resolve(mock_obj, mapping)

            assert result == expected

    def test_transform_unknown_function_silently_ignored(self, resolver, mock_obj):
        """Test that unknown transformation function is silently ignored (fail-safe)"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.serial',
            transform_function='unknown_function'
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {'serial': 'ABC123'}

            result = resolver.resolve(mock_obj, mapping)

            # Value should be unchanged
            assert result == 'ABC123'


class TestMappingResolverErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.parametrize("invalid_expression", [
        '$.[invalid',
        '$.{broken',
        '$.unclosed[',
        '$$invalid',
    ])
    def test_resolve_invalid_jsonpath_raises_error(self, resolver, mock_obj, invalid_expression):
        """Test that invalid JSONPath syntax raises ValueError"""
        mapping = create_mock_mapping(jsonpath_expression=invalid_expression)

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {'serial': 'ABC123'}

            # Error message includes "Invalid JSONPath expression" or "Error evaluating JSONPath"
            with pytest.raises(ValueError, match="(Invalid|Error evaluating) JSONPath"):
                resolver.resolve(mock_obj, mapping)

    def test_resolve_none_value_from_jsonpath(self, resolver, mock_obj):
        """Test handling of None values from JSONPath"""
        mapping = create_mock_mapping(
            jsonpath_expression='$.nullable_field',
            default_value='DEFAULT'
        )

        with patch('aas_integration.services.mapping_resolver.netbox_obj_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {'nullable_field': None}

            result = resolver.resolve(mock_obj, mapping)

            # None should trigger default
            assert result == 'DEFAULT'
