"""
Integration tests for the complete AAS sync flow.
"""

from contextlib import suppress
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
import requests
from basyx.aas import model as aas_model
from basyx.aas.adapter import aasx

from aas_integration.models import AASSyncModes
from aas_integration.services.sync import SyncObject, SyncParams
from aas_integration.services.utils import encode_id_base64


@pytest.mark.django_db
def test_aasx_upload_endpoint_reachable(test_aas_connection, test_basyx_urls):
    """
    Test that /upload endpoint is reachable and accepts authenticated requests.
    """
    # Create minimal AAS and submodel
    aas_id = "urn:test:integration:upload-endpoint-test"
    aas = aas_model.AssetAdministrationShell(
        id_=aas_id,
        asset_information=aas_model.AssetInformation(
            asset_kind=aas_model.AssetKind.INSTANCE,
            global_asset_id="urn:test:asset:upload-test"
        )
    )

    submodel = aas_model.Submodel(
        id_="urn:test:submodel:technical-data",
        semantic_id=aas_model.ExternalReference(
            (aas_model.Key(
                type_=aas_model.KeyTypes.GLOBAL_REFERENCE,
                value="https://admin-shell.io/idta/TechnicalData/1/1"
            ),)
        )
    )

    # Create AASX package
    object_store = aas_model.DictIdentifiableStore()
    object_store.add(aas)
    object_store.add(submodel)
    file_store = aasx.DictSupplementaryFileContainer()

    aasx_buffer = BytesIO()
    with aasx.AASXWriter(aasx_buffer) as writer:
        writer.write_all_aas_objects("/aasx/data.xml", object_store, file_store)
    aasx_buffer.seek(0)

    # Upload using authenticated request
    auth_headers = test_aas_connection.get_auth_headers()
    files = {"file": ("test-upload.aasx", aasx_buffer, "application/octet-stream")}

    aas_env_url = test_basyx_urls['aas_env']
    response = requests.post(
        f"{aas_env_url}/upload",
        files=files,
        headers=auth_headers,
        timeout=30
    )

    # Success: 200/201 (uploaded) or 409 (already exists, but endpoint works)
    assert response.status_code in [200, 201, 409], \
        f"/upload endpoint failed: {response.status_code} - {response.text}"

    with suppress(requests.RequestException):
        requests.delete(
            f"{aas_env_url}/shells/{encode_id_base64(aas_id)}",
            headers=auth_headers,
            timeout=10
        )


@pytest.mark.django_db
def test_sync_merge_mode_with_mocked_entity(test_aas_connection, test_basyx_urls):
    """
    Test the MERGE mode sync flow with a mocked NetBox entity.
    """
    # Create a mock Device-like object with minimal required attributes
    mock_device = Mock()
    mock_device.id = 9999
    mock_device.pk = 9999
    mock_device.name = "integration-test-device"
    mock_device.cf = {}
    mock_device.custom_field_data = {}
    mock_device.__class__.__name__ = "Device"

    mock_manufacturer = Mock()
    mock_manufacturer.name = "Test Manufacturer"
    mock_manufacturer.id = 1

    mock_device_type = Mock()
    mock_device_type.manufacturer = mock_manufacturer
    mock_device_type.model = "Test Model"
    mock_device_type.id = 10

    mock_device.device_type = mock_device_type
    mock_device.serial = "TEST-SERIAL-123"

    test_aas_connection.aas_id_field = "aas_id"
    test_aas_connection.aas_link = "aas_link"
    test_aas_connection.aas_ui_url = "http://localhost:9085/aasviewer"

    sync_params = SyncParams(
        sync_mode=AASSyncModes.MERGE,
        urn_namespace="urn:test:integration",
        aasx_upload_timeout=30
    )

    sync_obj = SyncObject(
        obj=mock_device,
        connection=test_aas_connection,
        sync_params=sync_params
    )

    # Mock the AASShellBuilder to return a valid AAS and submodels
    with patch('aas_integration.builders.aas_shell_builder.AASShellBuilder') as MockBuilder:
        aas_id = f"urn:test:integration:device:{mock_device.id}"
        aas = aas_model.AssetAdministrationShell(
            id_=aas_id,
            asset_information=aas_model.AssetInformation(
                asset_kind=aas_model.AssetKind.INSTANCE,
                global_asset_id=f"urn:test:asset:device:{mock_device.id}"
            )
        )

        submodel = aas_model.Submodel(
            id_=f"urn:test:submodel:technical-data:{mock_device.id}",
            semantic_id=aas_model.ExternalReference(
                (aas_model.Key(
                    type_=aas_model.KeyTypes.GLOBAL_REFERENCE,
                    value="https://admin-shell.io/idta/TechnicalData/1/1"
                ),)
            )
        )

        aas.submodel.add(aas_model.ModelReference.from_referable(submodel))

        mock_builder_instance = MockBuilder.return_value
        mock_builder_instance.build_aas_for_entity.return_value = (aas, [submodel])

        # Mock the save method to avoid Django signal issues
        with patch.object(mock_device, 'save'):
            result = sync_obj.sync_entity_to_aas_repo()

    assert result.success, f"Sync failed: {result.error}"
    assert result.asset_name == "integration-test-device"

    auth_headers = test_aas_connection.get_auth_headers()

    response = requests.get(
        f"{test_basyx_urls['aas_env']}/shells/{encode_id_base64(aas_id)}",
        headers=auth_headers,
        timeout=10
    )

    assert response.status_code == 200, \
        f"AAS not found after sync: {response.status_code}"

    with suppress(requests.RequestException):
        requests.delete(
            f"{test_basyx_urls['aas_env']}/shells/{encode_id_base64(aas_id)}",
            headers=auth_headers,
            timeout=10
        )


@pytest.mark.django_db
def test_sync_overwrite_mode_with_mocked_entity(test_aas_connection, test_basyx_urls):
    """
    Test the OVERWRITE mode sync flow.
    """
    mock_device = Mock()
    mock_device.id = 8888
    mock_device.pk = 8888
    mock_device.name = "overwrite-test-device"
    mock_device.cf = {}
    mock_device.custom_field_data = {}
    mock_device.__class__.__name__ = "Device"

    mock_manufacturer = Mock()
    mock_manufacturer.name = "Test Manufacturer"
    mock_manufacturer.id = 1

    mock_device_type = Mock()
    mock_device_type.manufacturer = mock_manufacturer
    mock_device_type.model = "Overwrite Test Model"
    mock_device_type.id = 11

    mock_device.device_type = mock_device_type
    mock_device.serial = "OVERWRITE-123"

    test_aas_connection.aas_id_field = "aas_id"
    test_aas_connection.aas_link = "aas_link"
    test_aas_connection.aas_ui_url = "http://localhost:9085/aasviewer"

    aas_id = f"urn:test:integration:device:{mock_device.id}"
    existing_aas = aas_model.AssetAdministrationShell(
        id_=aas_id,
        asset_information=aas_model.AssetInformation(
            asset_kind=aas_model.AssetKind.INSTANCE,
            global_asset_id=f"urn:test:asset:device:{mock_device.id}"
        )
    )

    # Upload the existing AAS
    object_store = aas_model.DictIdentifiableStore()
    object_store.add(existing_aas)
    file_store = aasx.DictSupplementaryFileContainer()

    aasx_buffer = BytesIO()
    with aasx.AASXWriter(aasx_buffer) as writer:
        writer.write_all_aas_objects("/aasx/data.xml", object_store, file_store)
    aasx_buffer.seek(0)

    auth_headers = test_aas_connection.get_auth_headers()
    files = {"file": ("existing.aasx", aasx_buffer, "application/octet-stream")}

    upload_response = requests.post(
        f"{test_basyx_urls['aas_env']}/upload",
        files=files,
        headers=auth_headers,
        timeout=30
    )

    assert upload_response.status_code in [200, 201, 409], \
        f"Failed to create existing AAS: {upload_response.status_code}"

    sync_params = SyncParams(
        sync_mode=AASSyncModes.OVERWRITE,
        urn_namespace="urn:test:integration",
        aasx_upload_timeout=30
    )

    sync_obj = SyncObject(
        obj=mock_device,
        connection=test_aas_connection,
        sync_params=sync_params
    )

    with patch('aas_integration.builders.aas_shell_builder.AASShellBuilder') as MockBuilder:
        new_aas = aas_model.AssetAdministrationShell(
            id_=aas_id,
            asset_information=aas_model.AssetInformation(
                asset_kind=aas_model.AssetKind.INSTANCE,
                global_asset_id=f"urn:test:asset:device:{mock_device.id}"
            )
        )

        new_submodel = aas_model.Submodel(
            id_=f"urn:test:submodel:technical-data:{mock_device.id}",
            semantic_id=aas_model.ExternalReference(
                (aas_model.Key(
                    type_=aas_model.KeyTypes.GLOBAL_REFERENCE,
                    value="https://admin-shell.io/idta/TechnicalData/1/1"
                ),)
            )
        )

        mock_builder_instance = MockBuilder.return_value
        mock_builder_instance.build_aas_for_entity.return_value = (new_aas, [new_submodel])

        with patch.object(mock_device, 'save'):
            result = sync_obj.sync_entity_to_aas_repo()

    assert result.success, f"OVERWRITE sync failed: {result.error}"

    response = requests.get(
        f"{test_basyx_urls['aas_env']}/shells/{encode_id_base64(aas_id)}",
        headers=auth_headers,
        timeout=10
    )

    assert response.status_code == 200, \
        f"AAS not found after OVERWRITE: {response.status_code}"

    with suppress(requests.RequestException):
        requests.delete(
            f"{test_basyx_urls['aas_env']}/shells/{encode_id_base64(aas_id)}",
            headers=auth_headers,
            timeout=10
        )


@pytest.mark.django_db
def test_merge_mode_conflict_fallback(test_aas_connection, test_basyx_urls):
    """
    Test MERGE mode fallback when shell already exists (HTTP 409).
    """
    mock_device = Mock()
    mock_device.id = 7777
    mock_device.pk = 7777
    mock_device.name = "merge-conflict-test"
    mock_device.cf = {}
    mock_device.custom_field_data = {}
    mock_device.__class__.__name__ = "Device"

    mock_manufacturer = Mock()
    mock_manufacturer.name = "Test Manufacturer"
    mock_manufacturer.id = 1

    mock_device_type = Mock()
    mock_device_type.manufacturer = mock_manufacturer
    mock_device_type.model = "Merge Test Model"
    mock_device_type.id = 12

    mock_device.device_type = mock_device_type
    mock_device.serial = "MERGE-123"

    test_aas_connection.aas_id_field = "aas_id"
    test_aas_connection.aas_link = "aas_link"
    test_aas_connection.aas_ui_url = "http://localhost:9085/aasviewer"

    aas_id = f"urn:test:integration:device:{mock_device.id}"

    initial_aas = aas_model.AssetAdministrationShell(
        id_=aas_id,
        asset_information=aas_model.AssetInformation(
            asset_kind=aas_model.AssetKind.INSTANCE,
            global_asset_id=f"urn:test:asset:device:{mock_device.id}"
        )
    )

    initial_submodel = aas_model.Submodel(
        id_=f"urn:test:submodel:nameplate:{mock_device.id}",
        semantic_id=aas_model.ExternalReference(
            (aas_model.Key(
                type_=aas_model.KeyTypes.GLOBAL_REFERENCE,
                value="https://admin-shell.io/idta/Nameplate/1/0"
            ),)
        )
    )

    object_store = aas_model.DictIdentifiableStore()
    object_store.add(initial_aas)
    object_store.add(initial_submodel)
    file_store = aasx.DictSupplementaryFileContainer()

    aasx_buffer = BytesIO()
    with aasx.AASXWriter(aasx_buffer) as writer:
        writer.write_all_aas_objects("/aasx/data.xml", object_store, file_store)
    aasx_buffer.seek(0)

    auth_headers = test_aas_connection.get_auth_headers()
    files = {"file": ("initial.aasx", aasx_buffer, "application/octet-stream")}

    upload_response = requests.post(
        f"{test_basyx_urls['aas_env']}/upload",
        files=files,
        headers=auth_headers,
        timeout=30
    )

    assert upload_response.status_code in [200, 201, 409], \
        f"Failed to create initial AAS: {upload_response.status_code}"

    # Second sync: MERGE mode should handle conflict gracefully
    sync_params = SyncParams(
        sync_mode=AASSyncModes.MERGE,
        urn_namespace="urn:test:integration",
        aasx_upload_timeout=30
    )

    sync_obj = SyncObject(
        obj=mock_device,
        connection=test_aas_connection,
        sync_params=sync_params
    )

    with patch('aas_integration.builders.aas_shell_builder.AASShellBuilder') as MockBuilder:
        updated_aas = aas_model.AssetAdministrationShell(
            id_=aas_id,
            asset_information=aas_model.AssetInformation(
                asset_kind=aas_model.AssetKind.INSTANCE,
                global_asset_id=f"urn:test:asset:device:{mock_device.id}"
            )
        )

        # Different submodel than initial upload
        updated_submodel = aas_model.Submodel(
            id_=f"urn:test:submodel:technical-data:{mock_device.id}",
            semantic_id=aas_model.ExternalReference(
                (aas_model.Key(
                    type_=aas_model.KeyTypes.GLOBAL_REFERENCE,
                    value="https://admin-shell.io/idta/TechnicalData/1/1"
                ),)
            )
        )

        updated_aas.submodel.add(aas_model.ModelReference.from_referable(updated_submodel))

        mock_builder_instance = MockBuilder.return_value
        mock_builder_instance.build_aas_for_entity.return_value = (updated_aas, [updated_submodel])

        with patch.object(mock_device, 'save'):
            # Execute MERGE sync (should hit 409 and fall back to submodel upsert)
            result = sync_obj.sync_entity_to_aas_repo()

    # Validate that sync succeeded despite 409
    assert result.success, f"MERGE with conflict failed: {result.error}"

    # Verify the shell still exists
    shell_response = requests.get(
        f"{test_basyx_urls['aas_env']}/shells/{encode_id_base64(aas_id)}",
        headers=auth_headers,
        timeout=10
    )

    assert shell_response.status_code == 200, \
        f"Shell not found after MERGE with conflict: {shell_response.status_code}"

    # Verify submodel was created/updated
    submodel_id = f"urn:test:submodel:technical-data:{mock_device.id}"
    submodel_response = requests.get(
        f"{test_basyx_urls['aas_env']}/submodels/{encode_id_base64(submodel_id)}",
        headers=auth_headers,
        timeout=10
    )

    assert submodel_response.status_code == 200, \
        f"Submodel not found after MERGE fallback: {submodel_response.status_code}"

    with suppress(requests.RequestException):
        requests.delete(
            f"{test_basyx_urls['aas_env']}/shells/{encode_id_base64(aas_id)}",
            headers=auth_headers,
            timeout=10
        )
