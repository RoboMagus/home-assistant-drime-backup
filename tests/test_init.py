"""Tests Drime Backup integration init."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PATH
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from custom_components.drime.const import CONF_EXTRA_PATHS, CONF_PROXY_URL, DOMAIN
from custom_components.drime.data import DrimeFileInfo

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_option_change_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: AsyncMock,
) -> None:
    """Test options change will reload entity."""
    with (
        patch(
            "custom_components.drime.async_create_clientsession",
            wraps=async_create_clientsession,
        ) as create_clientsession,
        patch(
            "custom_components.drime.DrimeClient.get_folder_id",
            return_value=DrimeFileInfo(name="/HomeAssistant-Tests/backups", hash="hash", id=12345),
        ) as get_folder_info,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        create_clientsession.assert_called_once_with(hass)
        get_folder_info.assert_awaited_once_with("/HomeAssistant-Tests/backups", "54321")
        assert mock_config_entry.options == {}
        entities = er.async_get(hass).entities.get_entries_for_config_entry_id(mock_config_entry.entry_id)
        assert len(entities) == 5

        # Test reload with Proxy + ExtraPaths:
        create_clientsession.reset_mock()
        get_folder_info.reset_mock()
        hass.config_entries.async_update_entry(
            mock_config_entry,
            data=mock_config_entry.data | {CONF_PROXY_URL: "http://username:pass@proxyhost:8080"},
            options={CONF_EXTRA_PATHS: {"/path/a": "hash_a", "/path/b": "hash_b"}},
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        create_clientsession.assert_called_once_with(hass, proxy="http://username:pass@proxyhost:8080")
        get_folder_info.assert_awaited_once_with("/HomeAssistant-Tests/backups", "54321")
        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert mock_config_entry.options == {CONF_EXTRA_PATHS: {"/path/a": "hash_a", "/path/b": "hash_b"}}

        entities = er.async_get(hass).entities.get_entries_for_config_entry_id(mock_config_entry.entry_id)
        entity_names = [e.original_name for e in entities]
        assert len(entity_names) == 7
        assert "Total size of /path/a" in entity_names
        assert "Total size of /path/b" in entity_names


async def test_backup_path_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: AsyncMock,
) -> None:
    """Test options change will reload entity."""
    with (
        patch(
            "custom_components.drime.DrimeClient.get_folder_id",
            return_value=DrimeFileInfo(name="/path/dont/match", hash="hash", id=12345),
        ) as get_folder_info,
        patch(
            "custom_components.drime.async_create_issue",
        ) as create_issue,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        get_folder_info.assert_awaited_once_with("/HomeAssistant-Tests/backups", "54321")
        create_issue.assert_called_once()
        assert create_issue.call_args_list[0].args[1] == DOMAIN
        assert create_issue.call_args_list[0].kwargs["translation_key"] == "drime_backup_folder_not_found"
        assert create_issue.call_args_list[0].kwargs["translation_placeholders"] == {
            "path": mock_config_entry.data[CONF_PATH]
        }
