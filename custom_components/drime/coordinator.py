"""DataUpdateCoordinator for Drime."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_PATH
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DrimeApiClientAuthenticationError
from .const import CONF_EXTRA_PATHS, DEFAULT_BACKUP_PATH, CONF_USER_ID, LOGGER
from .data import DrimeConfigEntry, DrimeData


class DrimeUpdateCoordinator(DataUpdateCoordinator[DrimeData]):
    """Class to manage fetching data from the API."""

    config_entry: DrimeConfigEntry

    async def _async_update_data(self) -> DrimeData:
        """Update data via library."""
        try:
            space_usage = await self.config_entry.runtime_data.client.get_space_usage()

            folders = (
                await self.config_entry.runtime_data.client.get_folders(self.config_entry.data.get(CONF_USER_ID))
            ).get("folders", [])
            folder_hashes = [
                self.config_entry.runtime_data.backup_folder.hash,
                *self.config_entry.options.get(CONF_EXTRA_PATHS, {}).values(),
            ]
            folder_sizes = {
                f["hash"]: f["file_size"] for f in folders if f["type"] == "folder" and f["hash"] in folder_hashes
            }
            LOGGER.debug("Folder sizes: %r", folder_sizes)

            return DrimeData(
                100 * space_usage["used"] / space_usage["available"],
                space_usage["used"],
                space_usage["available"],
                folder_sizes[self.config_entry.runtime_data.backup_folder.hash],
                folder_sizes,
            )
        except DrimeApiClientAuthenticationError as exception:
            LOGGER.error("Drime authentication error. Please check API key permissions.")
            raise ConfigEntryAuthFailed from exception
        except Exception as exception:
            raise UpdateFailed from exception
