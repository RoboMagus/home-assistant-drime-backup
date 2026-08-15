"""Test the Drime Backup backup agent."""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, call

import pytest
from homeassistant.components.backup import BackupAgentError, BackupNotFound
from homeassistant.util import dt as dt_util

from custom_components.drime.backup import (
    DATA_BACKUP_AGENT_LISTENERS,
    DrimeBackupAgent,
    ProgressScope,
    async_register_backup_agents_listener,
    suggested_filenames,
)
from custom_components.drime.data import ActiveBackupData, DrimeFileInfo, DrimeRuntimeData

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


class MockResponse:
    """Mock Response."""

    class ContentWrapper:
        """Async Content wrapper."""

        def __init__(self, data: str) -> None:
            """Initialize."""
            self.data = data

        async def read(self) -> str:
            """Async read."""
            return self.data

        def iter_chunked(self, size: int) -> str:
            """Chunked reader for download_file."""
            return self.data

    def __init__(self, data: dict[str, Any], status: int = 200) -> None:
        """Mock Response init."""
        self.status = status
        self.content = self.ContentWrapper(json.dumps(data))

    def raise_for_status(self) -> None:
        """ClientResponse compat."""
        return


def test_suggested_filenames(mock_agent_backup) -> None:
    """Test suggested_filenames."""
    tar, meta = suggested_filenames(mock_agent_backup)
    assert tar.removesuffix(".tar") == meta.removesuffix(".metadata.json")


def test_progres_scope(
    hass: HomeAssistant, mock_coordinator, mock_agent_backup, freezer: FrozenDateTimeFactory
) -> None:
    """Test progress scope wrapper."""
    on_upload_progress = Mock()
    mock_coordinator.update_active_backup = Mock()
    upload_start_time = dt_util.now()
    with ProgressScope(mock_coordinator, on_upload_progress, mock_agent_backup) as scoped_upload_progress:
        scoped_upload_progress(bytes_uploaded=42)
        on_upload_progress.assert_called_once_with(bytes_uploaded=42)
        mock_coordinator.update_active_backup.assert_called_once_with(
            ActiveBackupData(
                total_size=mock_agent_backup.size,
                uploaded=42,
                name=mock_agent_backup.name,
                upload_start_time=upload_start_time,
            )
        )
        # Clear mock before scope exit:
        mock_coordinator.update_active_backup.reset_mock()
    mock_coordinator.update_active_backup.assert_called_once_with(None)


async def test_backup_init(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
    mock_coordinator,
    mock_call_later,
) -> None:
    """Test agent list backups."""
    mock_coordinator.async_request_refresh = AsyncMock()
    mock_config_entry.runtime_data = DrimeRuntimeData(
        client=mock_api,
        coordinator=mock_coordinator,
        backup_folder=DrimeFileInfo(name="/foobar", hash="foobar_hash", id=0),
    )
    dba = DrimeBackupAgent(mock_config_entry, hass)

    mock_api.get_file_entries = AsyncMock(
        return_value={
            "data": [
                {
                    "id": 485529677,
                    "name": "My Documents",
                    "type": "folder",
                    "hash": "NDg1NTI5Njc3fA",
                    "file_size": 0,
                    "parent_id": None,
                    "workspace_id": 0,
                    "created_at": "2024-01-15T10:30:00.000000Z",
                    "updated_at": "2024-01-15T10:30:00.000000Z",
                },
                {
                    "id": 485529678,
                    "name": "backup_1.tar",
                    "hash": "NDg1NTI5Njc4fA",
                    "file_size": 2048576,
                    "parent_id": None,
                    "workspace_id": 0,
                    "created_at": "2024-01-14T08:20:00.000000Z",
                    "updated_at": "2024-01-14T08:20:00.000000Z",
                },
                {
                    "id": 485529679,
                    "name": "backup_1.metadata.json",
                    "hash": "NDg1NTI5Njc4fB",
                    "file_size": 64,
                    "parent_id": None,
                    "workspace_id": 0,
                    "created_at": "2024-01-14T08:20:00.000000Z",
                    "updated_at": "2024-01-14T08:20:00.000000Z",
                },
            ],
        }
    )

    mock_api.download_file = AsyncMock(
        return_value=MockResponse(
            data={
                "addons": [],
                "backup_id": "backup_1",
                "date": "2024-01-14T08:20:00.000000Z",
                "database_included": True,
                "extra_metadata": {},
                "folders": [],
                "homeassistant_included": True,
                "homeassistant_version": "2026.7.3",
                "name": "backup_1",
                "size": 123456,
                "protected": False,
            }
        )
    )

    backups = await dba.async_list_backups()
    mock_api.get_file_entries.assert_awaited_once_with("foobar_hash")
    mock_api.download_file.assert_awaited_once_with("NDg1NTI5Njc4fB", timeout=30)

    assert len(backups) == 1
    assert backups[0].name == "backup_1"
    # Validate extra attributes for DrimeAgentBackup:
    assert backups[0].tar_id == 485529678
    assert backups[0].meta_id == 485529679
    assert backups[0].tar_hash == "NDg1NTI5Njc4fA"
    assert backups[0].meta_hash == "NDg1NTI5Njc4fB"

    mock_api.get_file_entries.reset_mock()
    query_result = await dba.async_get_backup("backup_1")

    # Query within cache time: API not called
    mock_api.get_file_entries.assert_not_called()
    assert query_result == backups[0]

    # Download existing backup:
    mock_api.download_file.reset_mock()
    await dba.async_download_backup("backup_1")
    mock_api.download_file.assert_awaited_once_with("NDg1NTI5Njc4fA", timeout=600)

    # Download nonexisting backup:
    with pytest.raises(BackupNotFound, match="Backup does_not_exist not found"):
        await dba.async_download_backup("does_not_exist")

    # Delete nonexisting backup:
    with pytest.raises(BackupNotFound, match="Backup does_not_exist not found"):
        await dba.async_delete_backup("does_not_exist")

    # Delete existing backup Error:
    mock_api.delete_entries = AsyncMock(side_effect=Exception("Unknown"))
    with pytest.raises(BackupAgentError, match=r"Failed to delete backup: .*"):
        await dba.async_delete_backup("backup_1")

    # Delete existing backup:
    mock_api.delete_entries = AsyncMock()
    await dba.async_delete_backup("backup_1")
    await asyncio.sleep(0.1)  # allow call_later to run
    mock_api.delete_entries.assert_awaited_once_with([485529679, 485529678], permanent=True)
    mock_call_later.assert_called_once_with(hass, 15, dba._delayed_refresh_coordinator)
    mock_coordinator.async_request_refresh.assert_awaited_once()


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [listener]  # make sure it's the last listener
    remove_listener()

    assert hass.data.get(DATA_BACKUP_AGENT_LISTENERS) is None


async def test_backup_upload_small(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_agent_backup,
    mock_api,
    mock_coordinator,
    mock_call_later,
) -> None:
    mock_coordinator.async_request_refresh = AsyncMock()
    mock_config_entry.runtime_data = DrimeRuntimeData(
        client=mock_api,
        coordinator=mock_coordinator,
        backup_folder=DrimeFileInfo(name="/foobar", hash="foobar_hash", id=0),
    )
    dba = DrimeBackupAgent(mock_config_entry, hass)

    open_stream = AsyncMock()
    on_progress = Mock()
    await dba.async_upload_backup(open_stream=open_stream, backup=mock_agent_backup, on_progress=on_progress)
    open_stream.assert_awaited_once()
    on_progress.assert_not_called()
    mock_api.upload_file_simple.assert_has_calls(
        [
            # Tar file:
            call("/foobar", ANY, ANY, "application/x-tar", mock_agent_backup.size),
            # Metadata:
            call("/foobar", ANY, ANY, "application/json", 0),
        ]
    )
    await asyncio.sleep(0.1)  # allow call_later to run
    mock_call_later.assert_called_once_with(hass, 15, dba._delayed_refresh_coordinator)
    mock_coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.parametrize("backup_size", [2**32], ids=["big"])
async def test_backup_upload_big(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator,
    mock_agent_backup,
    mock_api,
    mock_call_later,
) -> None:
    mock_coordinator.update_active_backup = Mock()
    mock_config_entry.runtime_data = DrimeRuntimeData(
        client=mock_api,
        coordinator=mock_coordinator,
        backup_folder=DrimeFileInfo(name="/foobar", hash="foobar_hash", id=0),
    )
    dba = DrimeBackupAgent(mock_config_entry, hass)

    open_stream = AsyncMock()
    on_progress = Mock()
    await dba.async_upload_backup(open_stream=open_stream, backup=mock_agent_backup, on_progress=on_progress)
    open_stream.assert_not_called()  # Passed into multipart upload instead
    mock_api.upload_file_multipart.assert_awaited_once_with(
        "/foobar", ANY, open_stream, ANY, "application/x-tar", mock_agent_backup.size
    )
    mock_api.upload_file_simple.assert_awaited_once_with("/foobar", ANY, ANY, "application/json", 0)

    await asyncio.sleep(0.1)  # allow call_later to run
    mock_call_later.assert_called_once_with(hass, 15, dba._delayed_refresh_coordinator)
    mock_coordinator.async_request_refresh.assert_awaited_once()
