"""DrimeEntity class."""

from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DrimeUpdateCoordinator


class DrimeEntity(CoordinatorEntity[DrimeUpdateCoordinator]):
    """DrimeEntity class."""

    def __init__(self, coordinator: DrimeUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    str(coordinator.config_entry.domain),
                    str(coordinator.config_entry.entry_id),
                ),
            },
            name="Drime cloud",
            model=coordinator.config_entry.data[CONF_NAME],
            configuration_url="https://app.drime.cloud",
        )
