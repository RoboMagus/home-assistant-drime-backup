"""Adds config flow for Drime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PATH
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.loader import async_get_loaded_integration

from .api import DrimeApiClientAuthenticationError, DrimeClient

if TYPE_CHECKING:
    from .data import DrimeConfigEntry


class PathNotFoundError(Exception):
    """Error to indicate path does not exist on Drime."""


class DrimeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Drime."""

    VERSION = 1

    @override
    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                api_resp = await self._test_credentials(
                    api_key=user_input[CONF_API_KEY],
                )
                _uid = api_resp.get("user", {}).get("id")
                _subscription = (
                    api_resp.get("user", {}).get("subscriptions", [{}])[0].get("product", {}).get("name", None)
                )

                await self._create_folder_if_not_exists(user_input[CONF_PATH], user_input[CONF_API_KEY], _uid)
            except DrimeApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "invalid_auth"
            except Exception as exception:  # noqa: BLE001
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id=str(_uid))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Drime-{_uid}",
                    data=user_input | {CONF_NAME: _subscription, CONF_USER_ID: _uid},
                )

        integration = async_get_loaded_integration(self.hass, DOMAIN)
        assert integration.documentation is not None, (  # noqa: S101
            "Integration documentation URL is not set in manifest.json"
        )

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "documentation_url": integration.documentation,
            },
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY,
                        default=(user_input or {}).get(CONF_API_KEY, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Required(
                        CONF_PATH,
                        default=(user_input or {}).get(CONF_PATH, DEFAULT_BACKUP_PATH),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration flow."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: DrimeConfigEntry,
    ) -> DrimeOptionsFlowHandler:
        """Get the options flow for this handler."""
        return DrimeOptionsFlowHandler()

    async def _test_credentials(self, api_key: str) -> dict[str, Any]:
        """Validate credentials."""
        client = DrimeClient(
            api_key=api_key,
            session=async_create_clientsession(self.hass),
        )
        user = await client.get_user()
        LOGGER.debug(user)
        return user

    async def _create_folder_if_not_exists(self, path: str, api_key: str, user_id: int) -> None:
        """Create root folder if it doesn't exist."""
        client = DrimeClient(
            api_key=api_key,
            session=async_create_clientsession(self.hass),
        )
        path = path.strip(" /")
        folder_info = await client.get_folder_id(path, user_id)
        if folder_info.name == path:
            LOGGER.debug("Backup directory found: %s (%s)", path, folder_info.hash)
            return

        LOGGER.info("Creating backup directory '%s'", path)
        path_remainder = [d for d in path.removeprefix(folder_info.name).strip(" /").split("/") if d.strip()]
        for d in path_remainder:
            LOGGER.debug("Creating dir %s on parent %d", d, folder_info.id)
            folder_info = await client.create_folder(d, folder_info.id)
        LOGGER.debug("Created backup directory %s (%s)", path, folder_info.hash)


class DrimeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        self.options = self.config_entry.options.copy()
        self.api_key = self.config_entry.data[CONF_API_KEY]
        self.user_id = self.config_entry.data[CONF_USER_ID]

        _errors = {}
        if user_input is not None:
            try:
                folders_resp = await self._test_folders(folders=user_input[CONF_EXTRA_PATHS])
                extra_paths = {f"/{f.name}": f.hash for f in folders_resp}
            except PathNotFoundError as exception:
                LOGGER.warning("Drime Options Flow path not found: %s", exception)
                _errors["base"] = f"Path not found: {exception}"
            except Exception as exception:  # noqa: BLE001
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{self.config_entry.title}-Options", data={CONF_EXTRA_PATHS: extra_paths}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_EXTRA_PATHS,
                        default=list(self.options.get(CONF_EXTRA_PATHS, {}).keys()),
                    ): SelectSelector(
                        SelectSelectorConfig(options=[], custom_value=True, multiple=True, mode=SelectSelectorMode.LIST)
                    ),
                }
            ),
            errors=_errors,
        )

    async def _test_folders(self, folders: list[str]) -> Any:
        """Validate requested folders."""
        if not folders:
            return []

        client = DrimeClient(
            api_key=self.api_key,
            session=async_create_clientsession(self.hass),
        )

        fids = await client.get_folders_ids(folders, self.user_id)
        for i, folder in enumerate(folders):
            if folder.strip(" /") == fids[i].name.strip(" /"):
                LOGGER.debug("Hash for extra path %s: %s", folder, fids[i].hash)
            else:
                LOGGER.debug("Path not found: %s (%s)", folder, fids[i].name)
                raise PathNotFoundError(folder)
        return fids
