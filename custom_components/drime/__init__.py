"""Custom integration implements Drime backups for Home Assistant."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import CONF_API_KEY, CONF_PATH, Platform
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue, async_delete_issue

from .api import DrimeClient
from .backup import DATA_BACKUP_AGENT_LISTENERS
from .const import CONF_USER_ID, DEFAULT_BACKUP_PATH, DOMAIN, LOGGER
from .coordinator import DrimeUpdateCoordinator
from .data import DrimeRuntimeData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import DrimeConfigEntry

PLATFORMS: list[Platform] = [Platform.SENSOR]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: DrimeConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = DrimeUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(hours=1),
    )

    client = DrimeClient(
        api_key=entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    drime_folder_path, _, folder_hash = await client.get_folder_id(
        conf_folder_path := entry.data.get(CONF_PATH, DEFAULT_BACKUP_PATH), entry.data.get(CONF_USER_ID)
    )
    if drime_folder_path.strip(" /") != conf_folder_path.strip(" /"):
        async_create_issue(
            hass,
            DOMAIN,
            f"drime_backup_folder_not_found_{entry.unique_id}",
            is_fixable=False,
            is_persistent=False,
            severity=IssueSeverity.ERROR,
            translation_key="drime_backup_folder_not_found",
            translation_placeholders={"path": conf_folder_path},
        )
        raise ConfigEntryError(f"Backup folder '{conf_folder_path}' not found!")
    else:  # noqa: RET506
        async_delete_issue(hass, DOMAIN, f"drime_backup_folder_not_found_{entry.unique_id}")

    entry.runtime_data = DrimeRuntimeData(client=client, coordinator=coordinator, backup_folder_hash=folder_hash)

    def async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(async_notify_backup_listeners))

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: DrimeConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: DrimeConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
