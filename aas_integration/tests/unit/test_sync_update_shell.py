"""
Unit tests for SyncObject._update_shell exception handling.

Covers both except branches (requests.RequestException and the generic
catch-all Exception), validating the returned AASRequest and that the
exception info is logged via logger.exception.
"""
import logging

import pytest
import requests
from unittest.mock import Mock, patch
from basyx.aas import model as aas_model

from aas_integration.services.sync import SyncObject, SyncParams, AASRequest


@pytest.fixture
def shell():
    """A minimal, JSON-serializable AAS shell."""
    return aas_model.AssetAdministrationShell(
        id_="urn:test:shell:1",
        asset_information=aas_model.AssetInformation(
            asset_kind=aas_model.AssetKind.INSTANCE,
            global_asset_id="urn:test:asset:1",
        ),
    )


@pytest.fixture
def sync_object():
    """
    A SyncObject with only the attributes _update_shell needs.

    __init__ is bypassed to avoid pulling in NetBox model dependencies.
    """
    obj = SyncObject.__new__(SyncObject)
    obj.connection = Mock()
    obj.connection.aas_api_url = "http://basyx.example/api/v3.0"
    obj.connection.get_auth_headers.return_value = {}
    obj.sync_params = SyncParams(sync_mode="MERGE")
    obj.aas_id_log = "urn:test:shell:1"
    return obj


class TestUpdateShellExceptionHandling:
    """Both exception paths of _update_shell return a failing AASRequest and log with traceback."""

    def test_request_exception_returns_failure_and_logs(self, sync_object, shell, caplog):
        with patch(
            "aas_integration.services.sync.requests.put",
            side_effect=requests.RequestException("boom"),
        ):
            with caplog.at_level(logging.ERROR):
                result = sync_object._update_shell(shell)

        assert isinstance(result, AASRequest)
        assert result.success is False
        assert result.response is None
        assert result.message == "Error while updating shell: urn:test:shell:1"

        # logger.exception attaches traceback info to the record
        records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert any(r.exc_info is not None for r in records)
        assert "Error while updating shell: urn:test:shell:1" in caplog.text

    def test_unexpected_exception_returns_failure_and_logs(self, sync_object, shell, caplog):
        with patch(
            "aas_integration.services.sync.requests.put",
            side_effect=ValueError("unexpected"),
        ):
            with caplog.at_level(logging.ERROR):
                result = sync_object._update_shell(shell)

        assert isinstance(result, AASRequest)
        assert result.success is False
        assert result.response is None
        assert result.message == "Unexpected error while updating shell"

        records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert any(r.exc_info is not None for r in records)
        assert "Unexpected error while updating shell" in caplog.text
