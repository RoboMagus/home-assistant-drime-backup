"""Common fixtures for Drime Backup tests."""

from collections.abc import AsyncIterator, Generator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PATH

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.drime.const import CONF_USER_ID, DOMAIN


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch("custom_components.drime.async_setup_entry", return_value=True) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Drime-54321",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "54321|e4xs4rb6vtTrIcsDpguIEFuATYkXQ0POk9aDhMvQdZy7HsSY",  # Randomized string following API key format
            CONF_NAME: "subscription type goes here",
            CONF_USER_ID: "54321",
            CONF_PATH: "/HomeAssistant-Tests/backups",
        },
        entry_id="BNEMW2PRM49YHUVN2JIQR55Z10",
    )


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Mock Drime API."""
    with patch("custom_components.drime.DrimeClient", autospec=True) as api_mock:
        yield api_mock


@pytest.fixture
def mock_coordinator() -> Generator[AsyncMock]:
    """Mock Drime coordinator."""
    with patch(
        "custom_components.drime.DrimeUpdateCoordinator",
        autospec=True,
    ) as coordinator_mock:
        yield coordinator_mock
