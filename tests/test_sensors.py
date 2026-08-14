"""Test Drime Backup sensors."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from homeassistant.helpers import entity_registry as er

from custom_components.drime.data import DrimeFileInfo

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_basic_sensor_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: AsyncMock,
) -> None:
    """Basic sensor test."""
    backup_folder_info = DrimeFileInfo(name="/HomeAssistant-Tests/backups", hash="hash", id=12345)
    with patch("custom_components.drime.DrimeClient.get_folder_id", return_value=backup_folder_info) as gfi:
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        gfi.assert_awaited_once_with("/HomeAssistant-Tests/backups", "54321")

    entities = er.async_get(hass).entities.get_entries_for_config_entry_id(mock_config_entry.entry_id)
    assert len(entities) == 5


async def test_extra_sensors_creation(
    hass: HomeAssistant,
    mock_config_entry_extra_paths: MockConfigEntry,
    mock_coordinator: AsyncMock,
) -> None:
    """Extra path sensors test."""
    backup_folder_info = DrimeFileInfo(name="/HomeAssistant-Tests/backups", hash="hash", id=12345)
    with patch("custom_components.drime.DrimeClient.get_folder_id", return_value=backup_folder_info) as gfi:
        mock_config_entry_extra_paths.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_extra_paths.entry_id)
        await hass.async_block_till_done()
        gfi.assert_awaited_once_with("/HomeAssistant-Tests/backups", "54321")

    entities = er.async_get(hass).entities.get_entries_for_config_entry_id(mock_config_entry_extra_paths.entry_id)
    entity_names = [e.original_name for e in entities]
    assert len(entity_names) == 7
    assert "Total size of folder_1" in entity_names
    assert "Total size of folder_2" in entity_names
