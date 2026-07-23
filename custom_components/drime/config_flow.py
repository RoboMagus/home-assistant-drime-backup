"""Adds config flow for Drime."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import (
    DrimeClient,
)
from .const import DOMAIN, LOGGER


class DrimeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Drime."""

    VERSION = 1

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
            # except IntegrationBlueprintApiClientAuthenticationError as exception:
            #     LOGGER.warning(exception)
            #     _errors["base"] = "auth"
            # except IntegrationBlueprintApiClientCommunicationError as exception:
            #     LOGGER.error(exception)
            #     _errors["base"] = "connection"
            # except IntegrationBlueprintApiClientError as exception:
            #     LOGGER.exception(exception)
            #     _errors["base"] = "unknown"
            except Exception as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                _uid = api_resp.get("user", {}).get("id")
                _subscription = (
                    api_resp.get("user", {})
                    .get("subscriptions", [{}])[0]
                    .get("product", {})
                    .get("name", None)
                )
                await self.async_set_unique_id(unique_id=str(_uid))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Drime-{_uid}",
                    data=user_input | {CONF_NAME: _subscription},
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
                },
            ),
            errors=_errors,
        )

    async def _test_credentials(self, api_key: str):
        """Validate credentials."""
        client = DrimeClient(
            api_key=api_key,
            session=async_create_clientsession(self.hass),
        )
        user = await client.get_user()
        LOGGER.debug(user)
        return user
