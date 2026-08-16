"""Test Drime Backup sensors."""

from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er
from homeassistant.util.hass_dict import HassKey

from custom_components.drime.data import ActiveBackupData, DrimeData, DrimeFileInfo, DrimeRuntimeData

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


ENTITY_IDS = [
    "sensor.drime_cloud_active_backup_upload",
    "sensor.drime_cloud_storage_used",
    "sensor.drime_cloud_storage_used_percent",
    "sensor.drime_cloud_total_available_storage",
    "sensor.drime_cloud_total_size_of_backups",
    "sensor.drime_cloud_total_size_of_folder_1",
    "sensor.drime_cloud_total_size_of_folder_2",
]


async def test_sensor_updates(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_coordinator: AsyncMock,
    mock_config_entry_extra_paths: MockConfigEntry,
    mock_setup_entry,
) -> None:
    """Test sensor updates."""
    config_entry = mock_config_entry_extra_paths

    config_entry.runtime_data = DrimeRuntimeData(
        client=mock_api,
        coordinator=mock_coordinator,
        backup_folder=DrimeFileInfo(name="/foobar", hash="foobar_hash", id=0),
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_forward_entry_setups(config_entry, ["sensor"])

    entities = er.async_get(hass).entities.get_entries_for_config_entry_id(config_entry.entry_id)
    assert len(entities) == 7

    mock_coordinator.active_backup = None
    mock_coordinator.data = DrimeData(
        percentage_used=42.9,
        storage_used=20 * 1024**3,
        storage_available=8 * 1024**4,
        total_backup_size=4 * 1024**3,
        folder_sizes={"hash_1": int(0.5 * 1024**3), "hash_2": 60 * 1024**3, "unused_hash": 90001},
    )

    entities = {entity_id: hass.data[HassKey("sensor")].get_entity(entity_id) for entity_id in ENTITY_IDS}

    # Active backup upload:
    assert entities["sensor.drime_cloud_active_backup_upload"].available == False

    # Storage usage sensors:
    assert entities["sensor.drime_cloud_storage_used"].state == 20
    assert entities["sensor.drime_cloud_storage_used_percent"].state == 42.9
    assert entities["sensor.drime_cloud_total_available_storage"].state == 8192
    assert entities["sensor.drime_cloud_total_size_of_backups"].state == 4
    assert entities["sensor.drime_cloud_total_size_of_folder_1"].state == 0.5
    assert entities["sensor.drime_cloud_total_size_of_folder_2"].state == 60

    mock_coordinator.active_backup = ActiveBackupData(
        total_size=3 * 1024**3,
        uploaded=25 * 1024**2,
        name="BackupTestName",
        upload_start_time=datetime(2026, 7, 18, 13, 37),
    )
    active_backup_upload_entity = entities["sensor.drime_cloud_active_backup_upload"]
    assert active_backup_upload_entity.available == True
    assert active_backup_upload_entity.state == 25
    assert active_backup_upload_entity.extra_state_attributes["Backup name"] == "BackupTestName"
    assert active_backup_upload_entity.extra_state_attributes["Total size"] == 3072  # using convert_size
    assert active_backup_upload_entity.extra_state_attributes["Start time"] == datetime(2026, 7, 18, 13, 37)

    mock_coordinator.active_backup = None
    assert entities["sensor.drime_cloud_active_backup_upload"].available == False
