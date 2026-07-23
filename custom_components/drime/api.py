"""Sample API Client."""

from __future__ import annotations

from typing import Any

import aiohttp


API_URL = "https://app.drime.cloud/api/v1"


class DrimeClient:
    """Drime API Client."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Drime API Client."""
        self._api_key = api_key
        self._session = session

    async def get_user(self) -> Any:
        endpoint = "/cli/loggedUser"
        resp = await self._session.get(
            url=API_URL + endpoint, headers={"Authorization": f"Bearer {self._api_key}"}
        )
        return await resp.json()

    async def get_workspaces(self) -> Any:
        endpoint = "/me/workspaces"
        resp = await self._session.get(
            url=API_URL + endpoint, headers={"Authorization": f"Bearer {self._api_key}"}
        )
        return await resp.json()

    async def get_space_usage(self, workspace_id: int = 0) -> Any:
        endpoint = "/user/space-usage"
        resp = await self._session.get(
            url=API_URL + endpoint,
            params={"workspaceId": workspace_id},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        return await resp.json()
