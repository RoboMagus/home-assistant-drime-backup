"""Adds config flow for Drime."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PATH
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.loader import async_get_loaded_integration

from .api import DrimeApiClientAuthenticationError, DrimeClient
from .const import CONF_EXTRA_PATHS, CONF_USER_ID, DEFAULT_BACKUP_PATH, DOMAIN, LOGGER
from .data import DrimeConfigEntry


class PathNotFound(Exception):
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
            except DrimeApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "invalid_auth"
            except Exception as exception:  # noqa: BLE001
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                _uid = api_resp.get("user", {}).get("id")
                _subscription = (
                    api_resp.get("user", {}).get("subscriptions", [{}])[0].get("product", {}).get("name", None)
                )
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
                extra_paths = {f"/{f[0]}": f[2] for f in folders_resp}
            except PathNotFound as exception:
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
            if folder.strip(" /") == fids[i][0].strip(" /"):
                LOGGER.debug("Hash for extra path %s: %s", folder, fids[i][2])
            else:
                LOGGER.debug("Path not found: %s (%s)", folder, fids[i][0])
                raise PathNotFound(folder)
        return fids
