"""Test the Drime Backup coordinator."""

import logging
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

from custom_components.drime.coordinator import DrimeUpdateCoordinator
from custom_components.drime.data import DrimeFileInfo, DrimeRuntimeData

if TYPE_CHECKING:
    import pytest
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


_LOGGER = logging.getLogger(__name__)


async def test_coordinator_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Basic coordinator test."""
    caplog.set_level(logging.DEBUG)
    mock_logger = MagicMock()
    mock_config_entry.runtime_data = DrimeRuntimeData(
        client=mock_api, coordinator=None, backup_folder=DrimeFileInfo(name="/foobar", hash="foobar", id=0)
    )
    coordinator = DrimeUpdateCoordinator(hass, _LOGGER, name="Dummy", config_entry=mock_config_entry)

    listener = Mock()
    coordinator.async_add_listener(listener)

    mock_api.get_space_usage = AsyncMock(
        return_value={"used": 120042057597, "available": 6597069766656, "status": "success"}
    )
    mock_api.get_folders = AsyncMock(
        return_value={
            "folders": [
                {
                    "id": 111222,
                    "name": "Foobar",
                    "parent_id": None,
                    "path": "111222",
                    "type": "folder",
                    "file_size": 123456,
                    "workspace_id": 0,
                    "permissions": {
                        "files.update": True,
                        "files.create": True,
                        "files.download": True,
                        "files.delete": True,
                    },
                    "hash": "foobar",
                },
                {
                    "id": 111344,
                    "name": "Documents",
                    "parent_id": None,
                    "path": "111344",
                    "type": "folder",
                    "file_size": 1234,
                    "workspace_id": 0,
                    "permissions": {
                        "files.update": True,
                        "files.create": True,
                        "files.download": True,
                        "files.delete": True,
                    },
                    "hash": "MTExMzQ0fHBhZA",
                },
                {
                    "id": 111345,
                    "name": "Photos",
                    "parent_id": None,
                    "path": "111345",
                    "type": "folder",
                    "workspace_id": 0,
                },
            ],
            "rootFolder": {"type": "folder", "id": 0, "hash": "0", "path": "", "name": "All Files", "workspace_id": 0},
            "status": "success",
        }
    )

    await coordinator.async_refresh()
    mock_api.get_space_usage.assert_awaited_once()
    mock_api.get_folders.assert_awaited_once_with("54321")
    mock_logger.assert_not_called()

    assert listener.mock_calls == [call()]
    assert coordinator.last_update_success
    assert coordinator.data.percentage_used == 100 * 120042057597 / 6597069766656
    assert coordinator.data.storage_used == 120042057597
    assert coordinator.data.storage_available == 6597069766656
    assert coordinator.data.total_backup_size == 123456
    assert coordinator.data.folder_sizes == {"foobar": 123456}

    for record in caplog.records:
        assert record.levelname <= "INFO"
