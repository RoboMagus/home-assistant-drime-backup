"""Sample API Client."""

from __future__ import annotations

import json
from typing import Any

import aiohttp
import async_timeout

from .const import API_BASE_URL, LOGGER


class DrimeApiClientError(Exception):
    """Exception to indicate a general API error."""


class DrimeApiClientCommunicationError(
    DrimeApiClientError,
):
    """Exception to indicate a communication error."""


class DrimeApiClientAuthenticationError(
    DrimeApiClientError,
):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise DrimeApiClientAuthenticationError(
            msg,
        )
    response.raise_for_status()


class DrimeClient:
    """Drime API Client."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Drime API Client."""
        self._session = session
        self._auth_headers = {"Authorization": f"Bearer {api_key}"}

    async def _api_wrapper(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        headers: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=API_BASE_URL + endpoint,
                    headers=self._auth_headers | (headers or {}),
                    params=params,
                    json=data,
                )
                _verify_response_or_raise(response)
                data = await response.json()
                LOGGER.debug(
                    "%s %s: %d >>\n%s",
                    response.method,
                    response.url,
                    response.status,
                    json.dumps(
                        data,
                        sort_keys=True,
                        indent=2,
                        default=lambda _: "<< Not JSON Serializable >>",
                    ),
                )
                return data
        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise DrimeApiClientCommunicationError(
                msg,
            ) from exception
        except aiohttp.ClientError as exception:
            msg = f"Error fetching information - {exception}"
            raise DrimeApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:
            msg = f"Something really wrong happened! - {exception}"
            raise DrimeApiClientError(
                msg,
            ) from exception

    async def get_user(self) -> Any:
        """https://docs.drime.cloud/api-reference/user/get-logged-user."""
        return await self._api_wrapper("GET", "/cli/loggedUser")

    async def get_workspaces(self) -> Any:
        """https://docs.drime.cloud/api-reference/user/get-workspaces."""
        return await self._api_wrapper("GET", "/me/workspaces")

    async def get_space_usage(self, workspace_id: int = 0) -> Any:
        """https://docs.drime.cloud/api-reference/user/get-space-usage."""
        return await self._api_wrapper("GET", "/user/space-usage", params={"workspaceId": workspace_id})
