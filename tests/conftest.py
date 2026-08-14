"""Common fixtures for Drime Backup tests."""

from collections.abc import AsyncIterator, Generator
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PATH
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.drime.const import CONF_EXTRA_PATHS, CONF_USER_ID, DOMAIN
from custom_components.drime.data import DrimeData


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch("custom_components.drime.async_setup_entry", return_value=True) as mock_setup_entry:
        yield mock_setup_entry


def get_mock_config_entry(options=None) -> MockConfigEntry:
    """MockConfigEntry wrapper."""
    return MockConfigEntry(
        title="Drime-54321",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "54321|e4xs4rb6vtTrIcsDpguIEFuATYkXQ0POk9aDhMvQdZy7HsSY",  # Randomized string following API key format
            CONF_NAME: "subscription type goes here",
            CONF_USER_ID: "54321",
            CONF_PATH: "/HomeAssistant-Tests/backups",
        },
        options=options,
        entry_id="BNEMW2PRM49YHUVN2JIQR55Z10",
    )


@pytest.fixture
def mock_config_entry(options=None) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return get_mock_config_entry()


@pytest.fixture
def mock_config_entry_extra_paths() -> MockConfigEntry:
    """Return mocked config entry with extra paths option."""
    return get_mock_config_entry(options={CONF_EXTRA_PATHS: {"folder_1": "hash_1", "folder_2": "hash_2"}})


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Mock Drime API."""
    with patch("custom_components.drime.DrimeClient", autospec=True) as api_mock:
        yield api_mock


@pytest.fixture
def mock_coordinator(mock_config_entry) -> Generator[AsyncMock]:
    """Mock Drime coordinator."""
    with (
        patch(
            "custom_components.drime.DrimeUpdateCoordinator.config_entry",
            new_callable=PropertyMock,
            return_value=mock_config_entry,
            create=True,
        ),
        patch(
            "custom_components.drime.DrimeUpdateCoordinator.last_update_success",
            new_callable=PropertyMock,
            return_value=True,
            create=True,
        ),
        patch(
            "custom_components.drime.DrimeUpdateCoordinator.data",
            new_callable=PropertyMock,
            return_value=DrimeData(
                percentage_used=0, storage_used=0, storage_available=0, total_backup_size=0, folder_sizes={}
            ),
            create=True,
        ),
        patch(
            "custom_components.drime.DrimeUpdateCoordinator",
            autospec=True,
        ) as coordinator_mock,
    ):
        yield coordinator_mock
