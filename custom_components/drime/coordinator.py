"""DataUpdateCoordinator for Drime."""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DrimeApiClientAuthenticationError
from .const import LOGGER
from .data import DrimeConfigEntry, DrimeData


class DrimeUpdateCoordinator(DataUpdateCoordinator[DrimeData]):
    """Class to manage fetching data from the API."""

    config_entry: DrimeConfigEntry

    async def _async_update_data(self) -> DrimeData:
        """Update data via library."""
        try:
            space_usage = await self.config_entry.runtime_data.client.get_space_usage()
            return DrimeData(space_usage["used"], space_usage["available"])
        except DrimeApiClientAuthenticationError as exception:
            LOGGER.error("Drime authentication error. Please check API key permissions.")
            raise ConfigEntryAuthFailed from exception
        except Exception as exception:
            raise UpdateFailed from exception

    async def async_initialize(self) -> None:
        """Initialize the coordinator."""
        user = await self.config_entry.runtime_data.client.get_user()
        self.user_id = user.get("user", {}).get("id")
