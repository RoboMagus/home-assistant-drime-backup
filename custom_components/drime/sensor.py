"""Sensor platform for Drime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.util.unit_conversion import InformationConverter

from .const import CONF_EXTRA_PATHS
from .entity import DrimeEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DrimeUpdateCoordinator
    from .data import DrimeConfigEntry

CORE_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="storage_used",
        name="Storage used",
        icon="mdi:database",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
    ),
    SensorEntityDescription(
        key="storage_available",
        name="Total available storage",
        icon="mdi:database",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
    ),
    SensorEntityDescription(
        key="total_backup_size",
        name="Total size of backups",
        icon="mdi:database",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
    ),
    SensorEntityDescription(
        key="percentage_used",
        name="Storage used percent",
        icon="mdi:database",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: DrimeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    entities: list[DrimeSensor] = [
        DrimeSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in CORE_ENTITY_DESCRIPTIONS
    ]
    entities.extend(
        DrimeExtraPathSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=SensorEntityDescription(
                key=ehash,
                name=f"Total size of {path}",
                icon="mdi:database",
                device_class=SensorDeviceClass.DATA_SIZE,
                native_unit_of_measurement=UnitOfInformation.BYTES,
                suggested_display_precision=2,
                suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
            ),
        )
        for path, ehash in entry.options.get(CONF_EXTRA_PATHS, {}).items()
    )
    entities.append(
        ActiveBackupSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=SensorEntityDescription(
                key="active",
                name="Active backup upload",
                icon="mdi:upload-box",
                device_class=SensorDeviceClass.DATA_SIZE,
                native_unit_of_measurement=UnitOfInformation.BYTES,
                suggested_display_precision=2,
                suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
            ),
        )
    )
    async_add_entities(entities)


class DrimeSensor(DrimeEntity, SensorEntity):
    """drime Sensor class."""

    def __init__(
        self,
        coordinator: DrimeUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}_sensor"

    @property
    @override
    def native_value(self) -> int | None:
        """Return the native value of the sensor."""
        return getattr(self.coordinator.data, self.entity_description.key)


class DrimeExtraPathSensor(DrimeSensor):
    """drime Sensor class for extra path monitor."""

    def __init__(
        self,
        coordinator: DrimeUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator, entity_description)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_extra_{entity_description.key}_sensor"

    @property
    @override
    def native_value(self) -> int | None:
        """Return the native value of the sensor."""
        return self.coordinator.data.folder_sizes.get(self.entity_description.key)


class ActiveBackupSensor(DrimeSensor):
    """Sensor class for active backup states."""

    def __init__(
        self,
        coordinator: DrimeUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator, entity_description)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_active_backup_{entity_description.key}_sensor"

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.active_backup is not None

    @property
    @override
    def native_value(self) -> int | None:
        """Return the native value of the sensor."""
        return self.coordinator.active_backup.uploaded

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        backup = self.coordinator.active_backup
        return {
            "Backup name": backup.name,
            "Total size": self.convert_size(backup.total_size),
            "Start time": backup.upload_start_time,
        }

    def convert_size(self, size: int) -> int | float:
        """Convert attribute units to match sensor unit_of_measurement."""
        if (wanted := self.unit_of_measurement) != (native := self.native_unit_of_measurement):
            size = InformationConverter.convert(size, native, wanted)
            if dp := self._sensor_option_display_precision:
                size = round(size, dp)

        return size
