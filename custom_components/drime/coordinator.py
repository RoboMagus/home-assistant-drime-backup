"""DataUpdateCoordinator for Drime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


from .data import DrimeConfigEntry, DrimeData


class DrimeUpdateCoordinator(DataUpdateCoordinator[DrimeData]):
    """Class to manage fetching data from the API."""

    config_entry: DrimeConfigEntry

    async def _async_update_data(self) -> DrimeData:
        """Update data via library."""
        try:
            space_usage = await self.config_entry.runtime_data.client.get_space_usage()
            return DrimeData(space_usage["used"], space_usage["available"])
        except Exception as exception:
            raise UpdateFailed(exception) from exception
