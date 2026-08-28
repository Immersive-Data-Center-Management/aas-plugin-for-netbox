"""Utilities for AASX and AAS operations."""

import logging
from io import BytesIO
import requests
from basyx.aas import model as aas_model
from basyx.aas.adapter import aasx
import json
from basyx.aas.adapter.json.json_serialization import AASToJsonEncoder
from aas_integration.models import AASConnection, AASSyncModes
from aas_integration.logging_utils import sanitize_for_log
from dataclasses import dataclass
from django.db import models as django_models
from ..defaults import URN_NAMESPACE_DEFAULT, BASE_URL_DEFAULT, MIME_JSON, MIME_OCTET_STREAM
from .validation import validate_asset_data
from .serializers import serialize_validation_issues
from .utils import (
    AASOperationsException,
    encode_id_base64,
    create_aas_id,
    get_entity_type,
    get_entity_type_singular,
    get_object_name,
)

logger = logging.getLogger(__name__)

@dataclass
class AASRequest:
    success: bool
    response: requests.Response
    message: str

@dataclass
class AssetSyncResult:
    success: bool
    asset_name: str
    message: str = ""
    error: str = ""

@dataclass
class SyncParams:
    sync_mode: str
    base_url: str = BASE_URL_DEFAULT
    urn_namespace: str = URN_NAMESPACE_DEFAULT
    aasx_upload_timeout: int = 30
    submodel_reference_timeout: int = 10
    test_connection_timeout: int = 10

_DEFAULT_SYNC_PARAMS = SyncParams(sync_mode=AASSyncModes.MERGE)

class SyncObject:
    """
    Wraps a NetBox object together with its AAS connection and sync configuration,
    and exposes the operations needed to sync the object to/from the AAS repository.
    """

    def __init__(
        self,
        obj: django_models.Model,
        connection: AASConnection,
        sync_params: SyncParams = _DEFAULT_SYNC_PARAMS,
    ):
        """
        Initialize a SyncObject for a single NetBox entity.

        Args:
            obj: NetBox model instance (Device, Rack, etc.) to sync.
            connection: AASConnection providing API URL, credentials, and custom-field config.
            sync_params: SyncParams with sync mode, URN namespace, base URL, and timeouts.
        """
        self.obj = obj
        self.connection = connection
        self.sync_params = sync_params
        self.obj_name = get_object_name(obj)
        self.aas_id = create_aas_id(obj=obj, urn_namespace=sync_params.urn_namespace)
        self.entity_type = get_entity_type(obj)
        self.entity_type_singular = get_entity_type_singular(obj)
        # Pre-sanitized versions, safe to embed directly in log messages
        self.obj_name_log = sanitize_for_log(self.obj_name)
        self.aas_id_log = sanitize_for_log(self.aas_id)
        self.entity_type_log = sanitize_for_log(self.entity_type)
        self.entity_type_sing_log = sanitize_for_log(self.entity_type_singular)

    @staticmethod
    def handle_pre_sync_validation() -> tuple[bool, dict | None]:
        """
        Run pre-sync data validation across all NetBox assets.

        Returns:
            (True, None) if no validation issues were found.
            (False, issues_dict) describing the issues otherwise.
        """
        try:
            validation_result = validate_asset_data()
            if not validation_result.has_issues():
                return True, None
            return False, SyncObject._validation_error(
                'Validation issues found - please fix them in NetBox and try again',
                serialize_validation_issues(validation_result.issues)
            )
        except Exception as e:
            raise AASOperationsException("Failed to perform pre-sync validation") from e

    @staticmethod
    def _validation_error(message, issues=None):
        error = {
            'success': False,
            'message': message
        }
        if issues:
            error['validation_required'] = True
            error['issues'] = issues
        return error

    def sync_entity_to_aas_repo(self) -> AssetSyncResult:
        """
        Sync this entity to the AAS repository.

        Builds the AAS shell and its submodels from the NetBox object, packages
        them into an AASX, and uploads them according to the configured sync
        mode (MERGE or OVERWRITE).

        Returns:
            AssetSyncResult describing the outcome of the sync.
        """
        from aas_integration.builders.aas_shell_builder import AASShellBuilder
        try:
            builder = AASShellBuilder()
            aas, submodels = builder.build_aas_for_entity(
                obj=self.obj,
                entity_type=self.entity_type,
                connection=self.connection,
                base_url=self.sync_params.base_url,
                urn_namespace=self.sync_params.urn_namespace
            )
            if not aas:
                return AssetSyncResult(success=False, asset_name=self.obj_name, error="Missing required data")
            if not submodels:
                return AssetSyncResult(
                    success=False,
                    asset_name=self.obj_name,
                    error=f"No submodels configured for {self.entity_type}"
                )
            aasx_buffer = self._create_aasx_package(aas, submodels)
            aasx_buffer.seek(0)
            match self.sync_params.sync_mode:
                case AASSyncModes.MERGE:
                    return self._merge_single_asset(aas=aas, aasx_buffer=aasx_buffer, submodels=submodels)
                case AASSyncModes.OVERWRITE:
                    return self._overwrite_single_asset(aas=aas, aasx_buffer=aasx_buffer)
                case _:
                    logger.error(f"Sync Mode not implemented: {sanitize_for_log(self.sync_params.sync_mode)}")
                    return AssetSyncResult(success=False, asset_name=self.obj_name, error="Sync failed")
        except Exception as e:
            logger.error(
                f'Error syncing {self.entity_type_sing_log} {self.obj_name_log} '
                f'to AAS: {str(e)}'
            )
            return AssetSyncResult(success=False, asset_name=self.obj_name, error="Sync failed")

    def delete_shell_from_aas_repo(self) -> AASRequest:
        """
        Delete this entity's AAS shell and all of its submodels from the AAS repository.

        Submodels are deleted first, then the shell itself. A missing shell
        (HTTP 404) is treated as success.

        Returns:
            AASRequest indicating whether the deletion was successful.
        """
        try:
            submodels_result = self._delete_shell_submodels()
            if not submodels_result.success:
                return submodels_result
            response = requests.delete(
                f"{self.connection.aas_api_url}/shells/{encode_id_base64(self.aas_id)}",
                headers=self.connection.get_auth_headers(),
                timeout=self.sync_params.test_connection_timeout
            )
            match response.status_code:
                case 204:
                    deleted_ok = True
                    result_message = "Shell deletion successful"
                case 404:
                    deleted_ok = True
                    result_message = "Shell not found. No deletion performed"
                    logger.warning(
                        f"{self.entity_type_sing_log.capitalize()}_{self.obj.id}: {result_message}"
                    )
                case _:
                    deleted_ok = False
                    result_message = f"Shell deletion failed: HTTP {response.status_code}"
            return AASRequest(success=deleted_ok, response=response, message=result_message)
        except requests.RequestException:
            result_message = f"Error deleting the AAS shell {self.aas_id_log}"
        except Exception:
            result_message = f"Unexpected error deleting AAS shell {self.aas_id_log}"
        logger.error(result_message)
        return AASRequest(success=False, response=None, message=result_message)

    def _create_aasx_package(
        self,
        aas_object: aas_model.AssetAdministrationShell,
        submodels: list
    ) -> BytesIO:
        try:
            object_store = aas_model.DictIdentifiableStore()
            object_store.add(aas_object)
            if submodels:
                for sm in submodels:
                    if sm:
                        object_store.add(sm)
            file_store = aasx.DictSupplementaryFileContainer()
            aasx_buffer = BytesIO()
            with aasx.AASXWriter(aasx_buffer) as writer:
                writer.write_all_aas_objects("/aasx/data.xml", object_store, file_store)
            aasx_buffer.seek(0)
            return aasx_buffer
        except Exception as e:
            raise AASOperationsException("Failed to create AASX package") from e

    def _upload_aasx_to_repository(self, aasx_buffer: BytesIO) -> AASRequest:
        try:
            auth_headers = self.connection.get_auth_headers()
            files = {"file": (f"{self.entity_type}_{self.obj.id}.aasx", aasx_buffer, MIME_OCTET_STREAM)}
            response = requests.post(
                f"{self.connection.aas_api_url}/upload",
                files=files,
                headers=auth_headers,
                timeout=self.sync_params.aasx_upload_timeout
            )
            match response.status_code:
                case 200 | 201:
                    success = True
                    response_message = "Upload successful"
                case 409:
                    success = False
                    response_message = "Shell already exists"
                    logger.warning(
                        f"{self.entity_type_log}_{self.obj.id}: {response_message} (HTTP {response.status_code})"
                    )
                case _:
                    success = False
                    response_message = f"AASX upload failed (HTTP {response.status_code})"
                    logger.error(response_message)
            return AASRequest(success=success, response=response, message=response_message)
        except requests.RequestException:
            error_message = "AASX upload error"
        except Exception:
            error_message = "Unexpected error uploading AASX"
        logger.error(error_message)
        return AASRequest(success=False, response=None, message=error_message)

    def _fill_aas_id(self) -> bool:
        try:
            id_field = self.connection.aas_id_field
            if not id_field:
                logger.warning('Custom field to store AAS ID not found')
                return False
            current_value = self.obj.cf.get(id_field)
            if self.aas_id == current_value:
                logger.info(f'AAS ID not changed: {self.aas_id_log}')
                return False
            self.obj.custom_field_data[id_field] = self.aas_id
            return True
        except Exception as e:
            logger.exception(f"Failed to fill AAS ID custom field: {str(e)}")
            return False

    def _fill_aas_url(self) -> tuple[bool, str]:
        try:
            link_field = self.connection.aas_link
            if not link_field:
                logger.warning('Custom field to store AAS link not found')
                return False, 'None'
            ui_url_base = self.connection.aas_ui_url
            if not ui_url_base:
                logger.warning('AAS UI URL not defined')
                return False, 'None'
            aas_api_url = self.connection.aas_api_url
            if not aas_api_url:
                logger.warning('AAS API URL not defined')
                return False, 'None'
            viewer_url = ui_url_base + '/aasviewer?aas='
            encoded_id = encode_id_base64(self.aas_id)
            aas_url = viewer_url + aas_api_url + '/shells/' + encoded_id
            current_value = self.obj.cf.get(link_field)
            if aas_url == current_value:
                logger.info(f'AAS link not changed: {sanitize_for_log(current_value)}')
                return False, 'None'
            self.obj.custom_field_data[link_field] = aas_url
            return True, aas_url
        except Exception as e:
            raise AASOperationsException("Failed to fill AAS URL custom field") from e

    def _save_skipping_post_save_signal(self):
        """Save the NetBox object without triggering the AAS auto-sync post_save signal."""
        from aas_integration.signals import on_entity_saved
        django_models.signals.post_save.disconnect(on_entity_saved, sender=self.obj.__class__)
        try:
            self.obj.save()
        finally:
            django_models.signals.post_save.connect(on_entity_saved, sender=self.obj.__class__)

    def _fill_aas_custom_fields(self) -> None:
        """Fill the AAS ID and AAS viewer URL custom fields on the NetBox object and persist them."""
        try:
            aas_id_saved = self._fill_aas_id()
            aas_url_saved, aas_url = self._fill_aas_url()
            self._save_skipping_post_save_signal()
            if aas_id_saved:
                logger.info(f'AAS ID saved: {self.aas_id_log}')
            if aas_url_saved:
                logger.info(f'AAS link saved: {sanitize_for_log(aas_url)}')
        except Exception as e:
            logger.error(f"Error saving AAS custom fields: {str(e)}")

    def _upsert_submodel(self, submodel: aas_model.Submodel) -> AASRequest:
        """Try to update the submodel; if it doesn't exist (HTTP 404), create it instead."""
        update_request = self._update_submodel(submodel)
        if update_request.response is None or update_request.success:
            return update_request
        if update_request.response.status_code == 404:
            return self._create_submodel(submodel)
        return update_request

    def _update_or_create_submodels(
        self,
        aas: aas_model.AssetAdministrationShell,
        submodels: list[aas_model.Submodel],
    ) -> tuple[bool, list]:
        """Upsert every submodel for this entity, returning (all_succeeded, list_of_errors)."""
        if not submodels:
            return True, []
        errors = []
        for submodel in submodels:
            result = self._upsert_submodel(submodel)
            if result.success:
                logger.info(result.message)
                continue
            logger.error(
                f"Failed to upsert submodel {sanitize_for_log(submodel.id)} "
                f"for {self.obj_name_log} in shell {sanitize_for_log(aas.id)}: "
                f"{sanitize_for_log(result.message)}"
            )
            errors.append({"submodel": submodel, "request": result})
        return (not errors), errors

    def _handle_upload_response(
        self,
        aas_request: AASRequest,
        aas: aas_model.AssetAdministrationShell,
        submodels: list[aas_model.Submodel],
    ) -> AssetSyncResult:
        """Translate the AASX upload result into a final AssetSyncResult, applying MERGE fallback on HTTP 409."""
        try:
            msg_sync_success = f"Successfully synced {self.obj_name}"
            msg_sync_fail = f"Sync failed for {self.obj_name}"

            if aas_request.success:
                logger.info(f"Uploaded AASX for {self.entity_type_sing_log} {self.obj_name_log}")
                self._fill_aas_custom_fields()
                return AssetSyncResult(success=True, asset_name=self.obj_name, message=msg_sync_success)

            if self.sync_params.sync_mode != AASSyncModes.MERGE:
                logger.error(
                    f"AASX upload failed for {self.entity_type_sing_log} {self.obj_name_log}: "
                    f"{sanitize_for_log(aas_request.message)}"
                )
                return AssetSyncResult(success=False, asset_name=self.obj_name, message=msg_sync_fail)

            if aas_request.response is None or aas_request.response.status_code != 409:
                logger.error(
                    f"AASX upload failed for {self.entity_type_sing_log} {self.obj_name_log}: "
                    f"{sanitize_for_log(aas_request.message)}"
                )
                return AssetSyncResult(success=False, asset_name=self.obj_name, message=msg_sync_fail)

            upload_success, _ = self._update_or_create_submodels(aas, submodels)
            if not upload_success:
                return AssetSyncResult(success=False, asset_name=self.obj_name, message=msg_sync_fail)

            result_message = msg_sync_success
            reconcile_success = self._reconcile_submodel_references(aas=aas)
            if not reconcile_success:
                result_message = msg_sync_fail
            self._fill_aas_custom_fields()

            return AssetSyncResult(success=reconcile_success, asset_name=self.obj_name, message=result_message)
        except AASOperationsException:
            raise
        except Exception as e:
            raise AASOperationsException("Error handling upload response") from e

    def _overwrite_single_asset(
        self,
        aas: aas_model.AssetAdministrationShell,
        aasx_buffer: BytesIO,
    ) -> AssetSyncResult:
        """Delete any existing shell/submodels first, then upload the new AASX."""
        try:
            delete_request = self.delete_shell_from_aas_repo()
            if not delete_request.success:
                logger.error(
                    f"Shell deletion failed. Stopped syncing {self.entity_type_sing_log} "
                    f"{self.obj_name_log}: {sanitize_for_log(delete_request.message)}"
                )
                return AssetSyncResult(success=False, asset_name=self.obj_name, error=delete_request.message)
            return self._merge_single_asset(aas=aas, aasx_buffer=aasx_buffer, submodels=[])
        except AASOperationsException:
            raise
        except Exception as e:
            raise AASOperationsException("Overwrite of asset in the AAS repository failed") from e

    def _merge_single_asset(
        self,
        aas: aas_model.AssetAdministrationShell,
        aasx_buffer: BytesIO,
        submodels: list[aas_model.Submodel],
    ) -> AssetSyncResult:
        """Upload AASX for new shells; for existing shells, update shell and upsert submodels directly."""
        try:
            msg_sync_success = f"Successfully synced {self.obj_name}"
            msg_sync_fail = f"Sync failed for {self.obj_name}"

            if self._shell_exists():
                logger.info(
                    f"Shell {self.aas_id_log} already exists, merging {self.entity_type_sing_log} "
                    f"{self.obj_name_log}"
                )
                shell_update = self._update_shell(aas)
                if not shell_update.success:
                    return AssetSyncResult(success=False, asset_name=self.obj_name, message=msg_sync_fail)

                upload_success, _ = self._update_or_create_submodels(aas, submodels)
                if not upload_success:
                    return AssetSyncResult(success=False, asset_name=self.obj_name, message=msg_sync_fail)

                result_message = msg_sync_success
                reconcile_success = self._reconcile_submodel_references(aas=aas)
                if not reconcile_success:
                    result_message = msg_sync_fail
                self._fill_aas_custom_fields()
                return AssetSyncResult(success=reconcile_success, asset_name=self.obj_name, message=result_message)

            aasx_buffer.seek(0)
            upload_request = self._upload_aasx_to_repository(aasx_buffer=aasx_buffer)
            return self._handle_upload_response(aas_request=upload_request, aas=aas, submodels=submodels)
        except AASOperationsException:
            raise
        except Exception as e:
            raise AASOperationsException("Merging of asset in the AAS repository failed") from e

    def _get_shell_submodel_refs(self) -> AASRequest:
        """Retrieve the list of submodel references currently attached to this entity's shell."""
        try:
            response = requests.get(
                f"{self.connection.aas_api_url}/shells/{encode_id_base64(self.aas_id)}/submodel-refs",
                headers=self.connection.get_auth_headers(),
                timeout=self.sync_params.test_connection_timeout
            )
            match response.status_code:
                case 200:
                    request_success = True
                    request_message = f"Submodel references retrieved for shell {self.aas_id_log}"
                case 404:
                    request_success = False
                    request_message = f"Shell {self.aas_id_log} not found (HTTP {response.status_code})"
                    logger.warning(request_message)
                case _:
                    request_success = False
                    request_message = (
                        f"Failed to retrieve submodels for shell {self.aas_id_log} "
                        f"(HTTP {response.status_code})"
                    )
                    logger.error(request_message)
            return AASRequest(success=request_success, response=response, message=request_message)
        except requests.RequestException:
            request_message = f"Error while retrieving submodel references for shell {self.aas_id_log}"
        except Exception:
            request_message = "Unexpected Error"
        logger.error(request_message)
        return AASRequest(success=False, response=None, message=request_message)

    def _delete_shell_submodels(self) -> AASRequest:
        try:
            submodels_request = self._get_shell_submodel_refs()
            if submodels_request.response is None:
                return AASRequest(success=False, response=None, message=submodels_request.message)
            if submodels_request.response.status_code == 404:
                return AASRequest(
                    success=True,
                    response=submodels_request.response,
                    message=f"Shell {self.aas_id_log} not found, no submodels to delete"
                )
            if submodels_request.response.status_code != 200:
                return AASRequest(
                    success=False,
                    response=submodels_request.response,
                    message=submodels_request.message
                )
            refs = submodels_request.response.json().get("result", [])
            submodel_ids = [ref["keys"][0]["value"] for ref in refs]
            for submodel_id in submodel_ids:
                delete_response = requests.delete(
                    f"{self.connection.aas_api_url}/submodels/{encode_id_base64(submodel_id)}",
                    headers=self.connection.get_auth_headers(),
                    timeout=self.sync_params.test_connection_timeout
                )
                if delete_response.status_code != 204:
                    error_message = f"Unexpected response while deleting submodel {sanitize_for_log(submodel_id)}"
                    logger.error(error_message)
                    return AASRequest(success=False, response=delete_response, message=error_message)
            return AASRequest(
                success=True,
                response=None,
                message=f"All submodels of shell {self.aas_id_log} deleted successfully"
            )
        except requests.RequestException:
            error_message = f"Request error while deleting the submodels for shell {self.aas_id_log}"
        except Exception:
            error_message = f"Unexpected error while deleting submodels of shell {self.aas_id_log}"
        logger.error(error_message)
        return AASRequest(success=False, response=None, message=error_message)

    def _get_aas_shell(self) -> AASRequest:
        try:
            encoded_aas_id = encode_id_base64(self.aas_id)
            response = requests.get(
                f"{self.connection.aas_api_url}/shells/{encoded_aas_id}",
                headers=self.connection.get_auth_headers(),
                timeout=self.sync_params.test_connection_timeout
            )
            match response.status_code:
                case 200:
                    return AASRequest(
                        success=True,
                        response=response,
                        message=f"Shell {self.aas_id_log} retrieved successfully"
                    )
                case 404:
                    return AASRequest(success=False, response=response, message=f"Shell {self.aas_id_log} not found")
                case _:
                    error_message = f"Failed to retrieve AAS shell: HTTP {response.status_code}"
                    logger.error(error_message)
                    return AASRequest(success=False, response=response, message=error_message)
        except requests.RequestException:
            error_message = "Error retrieving AAS shell"
        except Exception:
            error_message = "Unexpected error retrieving AAS shell"
        logger.error(error_message)
        return AASRequest(success=False, response=None, message=error_message)

    def _shell_exists(self) -> bool:
        """Return True if this entity's shell already exists in the AAS repository."""
        return self._get_aas_shell().success

    def _add_submodel_reference(self, ref_id: str, ref_type: str) -> AASRequest:
        """Attach a submodel reference (by id and key type) to this entity's shell."""
        try:
            encoded_aas_id = encode_id_base64(self.aas_id)
            ref_payload = {
                "type": "ModelReference",
                "keys": [{
                    "type": ref_type,
                    "value": ref_id
                }]
            }
            headers = {'Content-Type': MIME_JSON}
            headers.update(self.connection.get_auth_headers())
            response = requests.post(
                f"{self.connection.aas_api_url}/shells/{encoded_aas_id}/submodel-refs",
                json=ref_payload,
                headers=headers,
                timeout=self.sync_params.submodel_reference_timeout
            )
            match response.status_code:
                case 200 | 201 | 204:
                    return AASRequest(
                        success=True,
                        response=response,
                        message=f"Submodel reference {sanitize_for_log(ref_id)} added successfully"
                    )
                case 409:
                    error_message = (
                        f"Submodel reference {sanitize_for_log(ref_id)} already exists (409), treating as success"
                    )
                    logger.debug(error_message)
                    return AASRequest(success=True, response=response, message=error_message)
                case _:
                    error_message = f"Failed to add submodel ref {sanitize_for_log(ref_id)}: HTTP {response.status_code}"
                    return AASRequest(success=False, response=response, message=error_message)
        except requests.RequestException:
            error_message = "Error adding submodel reference"
        except Exception:
            error_message = "Unexpected error adding submodel reference"
        logger.error(error_message)
        return AASRequest(success=False, response=None, message=error_message)

    def _update_submodel(self, submodel: aas_model.Submodel) -> AASRequest:
        try:
            headers = {'Content-Type': MIME_JSON}
            headers.update(self.connection.get_auth_headers())
            submodel_dict = json.loads(json.dumps(submodel, cls=AASToJsonEncoder))
            encoded_id = encode_id_base64(submodel.id)
            response = requests.put(
                f"{self.connection.aas_api_url}/submodels/{encoded_id}",
                json=submodel_dict,
                headers=headers,
                timeout=self.sync_params.test_connection_timeout
            )
            match response.status_code:
                case 200 | 201 | 204:
                    request_success = True
                    request_message = f"Submodel {sanitize_for_log(submodel.id)} updated successfully"
                case _:
                    request_success = False
                    request_message = (
                        f"Submodel {sanitize_for_log(submodel.id)} update failed (HTTP {response.status_code})"
                    )
                    logger.error(request_message)
            return AASRequest(success=request_success, response=response, message=request_message)
        except requests.RequestException:
            request_message = f"Error while updating submodel: {sanitize_for_log(submodel.id)}"
        except Exception:
            request_message = "Unexpected error while updating submodel"
        logger.error(request_message)
        return AASRequest(success=False, response=None, message=request_message)

    def _update_shell(self, aas: aas_model.AssetAdministrationShell) -> AASRequest:
        try:
            headers = {'Content-Type': MIME_JSON}
            headers.update(self.connection.get_auth_headers())
            aas_dict = json.loads(json.dumps(aas, cls=AASToJsonEncoder))
            encoded_id = encode_id_base64(aas.id)
            response = requests.put(
                f"{self.connection.aas_api_url}/shells/{encoded_id}",
                json=aas_dict,
                headers=headers,
                timeout=self.sync_params.test_connection_timeout
            )
            match response.status_code:
                case 200 | 201 | 204:
                    request_success = True
                    request_message = f"Shell {self.aas_id_log} updated successfully"
                case _:
                    request_success = False
                    request_message = (
                        f"Shell {self.aas_id_log} update failed (HTTP {response.status_code})"
                    )
                    logger.error(request_message)
            return AASRequest(success=request_success, response=response, message=request_message)
        except requests.RequestException:
            request_message = f"Error while updating shell: {self.aas_id_log}"
            logger.exception(request_message)
            return AASRequest(success=False, response=None, message=request_message)
        except Exception:
            request_message = "Unexpected error while updating shell"
            logger.exception(request_message)
            return AASRequest(success=False, response=None, message=request_message)

    def _create_submodel(self, submodel: aas_model.Submodel) -> AASRequest:
        try:
            headers = {'Content-Type': MIME_JSON}
            headers.update(self.connection.get_auth_headers())
            submodel_dict = json.loads(json.dumps(submodel, cls=AASToJsonEncoder))
            response = requests.post(
                f"{self.connection.aas_api_url}/submodels",
                json=submodel_dict,
                headers=headers,
                timeout=self.sync_params.test_connection_timeout
            )
            match response.status_code:
                case 201:
                    request_success = True
                    request_message = f"Submodel {sanitize_for_log(submodel.id)} created successfully"
                case _:
                    request_success = False
                    request_message = (
                        f"Submodel {sanitize_for_log(submodel.id)} upload failed (HTTP {response.status_code})"
                    )
                    logger.error(request_message)
            return AASRequest(success=request_success, response=response, message=request_message)
        except requests.RequestException:
            request_message = f"Error while uploading submodel: {sanitize_for_log(submodel.id)}"
        except Exception:
            request_message = "Unexpected error while uploading submodel"
        logger.error(request_message)
        return AASRequest(success=False, response=None, message=request_message)

    def _reconcile_submodel_references(
        self,
        aas: aas_model.AssetAdministrationShell,
    ) -> bool:
        """Add any submodel references expected by the built AAS that are missing on the remote shell."""
        try:
            shell_request = self._get_aas_shell()
            if not shell_request.success or shell_request.response is None:
                logger.error(
                    f"Could not retrieve AAS shell for {self.obj_name_log}: {shell_request.message}"
                )
                return False
            shell_data = shell_request.response.json()
            existing_refs = shell_data.get('submodels', [])
            existing_ref_ids = {ref['keys'][0]['value'] for ref in existing_refs}

            expected_ref_ids = {ref.key[0].value for ref in aas.submodel}

            missing_ref_ids = expected_ref_ids - existing_ref_ids
            if missing_ref_ids:
                logger.info(
                    f"{self.entity_type_sing_log} {self.obj_name_log}: "
                    f"Adding {len(missing_ref_ids)} missing submodel references"
                )
                for ref in aas.submodel:
                    ref_id = ref.key[0].value
                    if ref_id in missing_ref_ids:
                        ref_type = ref.key[0].type.name
                        add_request = self._add_submodel_reference(ref_id=ref_id, ref_type=ref_type)
                        if not add_request.success:
                            logger.error(add_request.message)
                            return False
            else:
                logger.debug(
                    f"{self.entity_type_sing_log} {self.obj_name_log}: "
                    f"All submodel references present"
                )
            return True
        except Exception:
            logger.error(
                f"Error reconciling submodel references for {self.obj_name_log}",
                exc_info=True
            )
            return False
