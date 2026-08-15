"""Test the Drime Backup config flow."""

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, call, patch

from aiohttp import ClientProxyConnectionError
from aiohttp.client_reqrep import ConnectionKey
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PATH
from homeassistant.data_entry_flow import FlowResultType

from custom_components.drime.const import (
    CONF_EXTRA_PATHS,
    CONF_PROXY_URL,
    CONF_USER_ID,
    DOMAIN,
    SECTION_ADVANCED_SETTINGS,
)
from custom_components.drime.data import DrimeFileInfo

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


class MockResponse:
    """Test response."""

    def __init__(self, data: dict[str, Any], status: int = 200) -> None:
        """Test response init."""
        self.status = status
        self.data = data

    async def json(self) -> dict[str, Any]:
        """Test response read."""
        return self.data

    def raise_for_status(self) -> None:
        """ClientResponse compat."""
        return


async def test_basic_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test user flow."""

    with (
        patch(
            "custom_components.drime.DrimeClient.get_user",
            return_value={
                "user": {
                    "id": 15843,
                    "email": "user@example.com",
                    "display_name": "John Doe",
                    "first_name": "John",
                    "last_name": "Doe",
                    "subscriptions": [{"product": {"name": "SubscriptionProductName"}}],
                    "created_at": "2024-01-01T00:00:00.000000Z",
                    "updated_at": "2024-01-15T10:30:00.000000Z",
                }
            },
        ) as get_user,
        patch(
            "custom_components.drime.DrimeClient.get_folder_id",
            return_value=DrimeFileInfo(name="home-assistant/backup/path", hash="backup_folder_hash", id=123456),
        ) as get_folder_id,
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "super_secret_api_key",
                CONF_PATH: "/home-assistant/backup/path/",
                SECTION_ADVANCED_SETTINGS: {CONF_PROXY_URL: ""},
            },
        )
        get_user.assert_awaited_once()
        get_folder_id.assert_awaited_once_with("home-assistant/backup/path", 15843)

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Drime-15843"
        assert result["data"] == {
            CONF_API_KEY: "super_secret_api_key",
            CONF_PATH: "/home-assistant/backup/path/",
            SECTION_ADVANCED_SETTINGS: {CONF_PROXY_URL: ""},
            CONF_NAME: "SubscriptionProductName",
            CONF_USER_ID: 15843,
        }
        assert result["result"].unique_id == "15843"
        assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_create_directory(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test user flow."""

    with (
        patch(
            "custom_components.drime.DrimeClient.get_user",
            return_value={
                "user": {
                    "id": 15843,
                    "email": "user@example.com",
                    "display_name": "John Doe",
                    "first_name": "John",
                    "last_name": "Doe",
                    "subscriptions": [{"product": {"name": "SubscriptionProductName"}}],
                    "created_at": "2024-01-01T00:00:00.000000Z",
                    "updated_at": "2024-01-15T10:30:00.000000Z",
                }
            },
        ) as get_user,
        patch(
            "custom_components.drime.DrimeClient.get_folder_id",
            return_value=DrimeFileInfo(name="", hash="", id=0),
        ) as get_folder_id,
        patch(
            "custom_components.drime.DrimeClient.create_folder",
            side_effect=[
                DrimeFileInfo(name="irrelevant", hash="irrelevant", id=123),
                DrimeFileInfo(name="irrelevant", hash="irrelevant", id=456),
                DrimeFileInfo(name="irrelevant", hash="irrelevant", id=789),
            ],
        ) as create_folder,
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "super_secret_api_key",
                CONF_PATH: "/home-assistant/backup/path/",
                SECTION_ADVANCED_SETTINGS: {CONF_PROXY_URL: ""},
            },
        )
        get_user.assert_awaited_once()
        get_folder_id.assert_awaited_once_with("home-assistant/backup/path", 15843)

        create_folder.assert_has_awaits([call("home-assistant", 0), call("backup", 123), call("path", 456)])

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Drime-15843"
        assert result["data"] == {
            CONF_API_KEY: "super_secret_api_key",
            CONF_PATH: "/home-assistant/backup/path/",
            SECTION_ADVANCED_SETTINGS: {CONF_PROXY_URL: ""},
            CONF_NAME: "SubscriptionProductName",
            CONF_USER_ID: 15843,
        }
        assert result["result"].unique_id == "15843"
        assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_with_proxy(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test proxied user flow."""

    with (
        patch(
            "aiohttp.client.ClientSession.get",
            new_callable=AsyncMock,
            return_value=MockResponse(data={"ip": "127.0.0.1"}),
        ) as proxy_test,
        patch(
            "custom_components.drime.DrimeClient.get_user",
            return_value={
                "user": {
                    "id": 15843,
                    "email": "user@example.com",
                    "display_name": "John Doe",
                    "first_name": "John",
                    "last_name": "Doe",
                    "subscriptions": [{"product": {"name": "SubscriptionProductName"}}],
                    "created_at": "2024-01-01T00:00:00.000000Z",
                    "updated_at": "2024-01-15T10:30:00.000000Z",
                }
            },
        ) as get_user,
        patch(
            "custom_components.drime.DrimeClient.get_folder_id",
            return_value=DrimeFileInfo(name="home-assistant/backup/path", hash="backup_folder_hash", id=123456),
        ) as get_folder_id,
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "super_secret_api_key",
                CONF_PATH: "/home-assistant/backup/path/",
                SECTION_ADVANCED_SETTINGS: {CONF_PROXY_URL: "http://username:password@proxyhost:8080"},
            },
        )
        proxy_test.assert_awaited_once_with("https://api.ipify.org?format=json")
        get_user.assert_awaited_once()
        get_folder_id.assert_awaited_once_with("home-assistant/backup/path", 15843)

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Drime-15843"
        assert result["data"] == {
            CONF_API_KEY: "super_secret_api_key",
            CONF_PATH: "/home-assistant/backup/path/",
            SECTION_ADVANCED_SETTINGS: {CONF_PROXY_URL: "http://username:password@proxyhost:8080"},
            CONF_NAME: "SubscriptionProductName",
            CONF_USER_ID: 15843,
        }
        assert result["result"].unique_id == "15843"
        assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_proxy_error_1(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test proxied user flow."""

    with patch(
        "aiohttp.client.ClientSession.get",
        new_callable=AsyncMock,
        side_effect=asyncio.TimeoutError,
    ) as proxy_test:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "super_secret_api_key",
                CONF_PATH: "/home-assistant/backup/path/",
                SECTION_ADVANCED_SETTINGS: {CONF_PROXY_URL: "http://username:password@proxyhost:8080"},
            },
        )
        proxy_test.assert_awaited_once_with("https://api.ipify.org?format=json")

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "proxy_error"


async def test_user_flow_proxy_error_2(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test proxied user flow."""

    with (
        patch(
            "aiohttp.client.ClientSession.get",
            new_callable=AsyncMock,
            return_value=MockResponse(data={"ip": "127.0.0.1"}),
        ) as proxy_test,
        patch(
            "custom_components.drime.DrimeClient.get_user",
            side_effect=ClientProxyConnectionError(
                connection_key=ConnectionKey(
                    host="", port=8080, is_ssl=False, ssl=False, proxy="", proxy_auth=None, proxy_headers_hash=None
                ),
                os_error=OSError(),
            ),
        ) as get_user,
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "super_secret_api_key",
                CONF_PATH: "/home-assistant/backup/path/",
                SECTION_ADVANCED_SETTINGS: {CONF_PROXY_URL: "http://username:password@proxyhost:8080"},
            },
        )
        proxy_test.assert_awaited_once_with("https://api.ipify.org?format=json")
        get_user.assert_awaited_once()

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "proxy_error"


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test invalid auth user flow."""

    with (
        patch(
            "custom_components.drime.DrimeClient.get_user",
            return_value={"user": None},
        ) as get_user,
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "super_secret_api_key",
                CONF_PATH: "/home-assistant/backup/path/",
                SECTION_ADVANCED_SETTINGS: {CONF_PROXY_URL: ""},
            },
        )
        get_user.assert_awaited_once()

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"


async def test_user_flow_unknown_error(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test invalid auth user flow."""

    with (
        patch(
            "custom_components.drime.DrimeClient.get_user",
            side_effect=Exception("unknown"),
        ) as get_user,
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "super_secret_api_key",
                CONF_PATH: "/home-assistant/backup/path/",
                SECTION_ADVANCED_SETTINGS: {CONF_PROXY_URL: ""},
            },
        )
        get_user.assert_awaited_once()

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_options_flow(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test that the options flow works."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.drime.DrimeClient.get_folders_ids",
        return_value=[
            DrimeFileInfo(name="a/b", hash="ab_hash", id=1),
            DrimeFileInfo(name="c/d/e", hash="cde_hash", id=2),
        ],
    ) as get_fids:
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "init"
        assert mock_config_entry.options == {}

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_EXTRA_PATHS: ["/a/b", "c/d/e"]}
        )
        get_fids.assert_awaited_once_with(["/a/b", "c/d/e"], "54321")

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {CONF_EXTRA_PATHS: {"/a/b": "ab_hash", "/c/d/e": "cde_hash"}}


async def test_options_flow_empty(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test that the options flow works."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.drime.DrimeClient.get_folders_ids",
        return_value=None,
    ) as get_fids:
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "init"
        assert mock_config_entry.options == {}

        result = await hass.config_entries.options.async_configure(result["flow_id"], user_input={CONF_EXTRA_PATHS: []})
        get_fids.assert_not_called()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {CONF_EXTRA_PATHS: {}}


async def test_options_flow_path_not_found(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test that the options flow works."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.drime.DrimeClient.get_folders_ids",
        return_value=[
            DrimeFileInfo(name="a/b", hash="ab_hash", id=1),
            DrimeFileInfo(name="c", hash="c_hash", id=2),
        ],
    ) as get_fids:
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "init"
        assert mock_config_entry.options == {}

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_EXTRA_PATHS: ["/a/b", "c/d/e"]}
        )
        get_fids.assert_awaited_once_with(["/a/b", "c/d/e"], "54321")

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "Path not found: c/d/e"


async def test_options_flow_unknown_error(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test that the options flow works."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.drime.DrimeClient.get_folders_ids",
        side_effect=Exception("Unknown Error"),
    ) as get_fids:
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "init"
        assert mock_config_entry.options == {}

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_EXTRA_PATHS: ["/a/b", "c/d/e"]}
        )
        get_fids.assert_awaited_once_with(["/a/b", "c/d/e"], "54321")

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"
