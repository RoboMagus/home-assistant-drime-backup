"""Custom types for Drime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .api import DrimeClient
    from .coordinator import DrimeUpdateCoordinator


type DrimeConfigEntry = ConfigEntry[DrimeRuntimeData]


@dataclass(frozen=True, kw_only=True)
class ActiveBackupData:
    """Sensor data for active Backup uploads."""

    total_size: int
    uploaded: int
    name: str


@dataclass(frozen=True, kw_only=True)
class DrimeFileInfo:
    """Drime file info class."""

    name: str
    hash: str
    id: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create an instance from a JSON serialization."""
        return cls(
            name=data["name"],
            hash=data["hash"],
            id=data["id"],
        )


@dataclass
class DrimeRuntimeData:
    """Data for the Drime integration."""

    client: DrimeClient
    coordinator: DrimeUpdateCoordinator
    backup_folder: DrimeFileInfo


@dataclass
class DrimeData:
    """Data for the Drime integration."""

    percentage_used: float
    storage_used: int
    storage_available: int
    total_backup_size: int
    folder_sizes: dict[str, int]
