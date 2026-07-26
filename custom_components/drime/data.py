"""Custom types for Drime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .api import DrimeClient
    from .coordinator import DrimeUpdateCoordinator


type DrimeConfigEntry = ConfigEntry[DrimeConfigData]


@dataclass
class DrimeConfigData:
    """Data for the Drime integration."""

    client: DrimeClient
    coordinator: DrimeUpdateCoordinator


@dataclass
class DrimeData:
    """Data for the Drime integration."""

    percentage_used: float
    storage_used: int
    storage_available: int
    total_backup_size: int
    folder_sizes: dict[str, int]
