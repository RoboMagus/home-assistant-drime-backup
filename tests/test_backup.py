"""Test the Drime Backup backup agent."""

import json
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

from custom_components.drime.backup import (
    DATA_BACKUP_AGENT_LISTENERS,
    DrimeBackupAgent,
    async_register_backup_agents_listener,
)
from custom_components.drime.data import DrimeFileInfo, DrimeRuntimeData

if TYPE_CHECKING:
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

    def __init__(self, data: dict[str, Any], status: int = 200) -> None:
        """Mock Response init."""
        self.status = status
        self.content = self.ContentWrapper(json.dumps(data))

    def raise_for_status(self) -> None:
        """ClientResponse Dummy."""
        return


async def test_backup_init(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
) -> None:
    """Test agent list backups."""
    mock_config_entry.runtime_data = DrimeRuntimeData(
        client=mock_api, coordinator=None, backup_folder=DrimeFileInfo(name="/foobar", hash="foobar_hash", id=0)
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


async def test_listeners_get_cleaned_up(hass: HomeAssistant) -> None:
    """Test listener gets cleaned up."""
    listener = MagicMock()
    remove_listener = async_register_backup_agents_listener(hass, listener=listener)

    hass.data[DATA_BACKUP_AGENT_LISTENERS] = [listener]  # make sure it's the last listener
    remove_listener()

    assert hass.data.get(DATA_BACKUP_AGENT_LISTENERS) is None
