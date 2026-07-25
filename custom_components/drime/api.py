"""Sample API Client."""

from __future__ import annotations

import json
from typing import Any

import aiohttp
import asyncio

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


def _get_folder_id(path: str, folders: list[dict[str, Any]]) -> tuple[str, int, str]:
    """Parse path to find id of (nested) folder."""
    current_folder_id = None
    directory_tree = [d for d in path.split("/") if d.strip()]
    folder_hash = ""
    for i, d in enumerate(directory_tree):
        d_found = False
        for f in folders:
            if f["parent_id"] == current_folder_id and f["name"] == d:
                LOGGER.debug(
                    "%d | Found '/%s' = %d / %s",
                    current_folder_id or 0,
                    f["name"],
                    f["id"],
                    f["hash"],
                )
                current_folder_id = f["id"]
                folder_hash = f["hash"]
                d_found = True
                break
        if not d_found:
            LOGGER.warning(f"Path not found @ {i}: {path}")
            return ("/".join(directory_tree[:i]), current_folder_id or 0, folder_hash)

    LOGGER.info(f"Found: /{path}")
    return ("/".join(directory_tree), current_folder_id or 0, folder_hash)


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
            async with asyncio.timeout(15):
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

    async def _stream_wrapper(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        headers: dict | None = None,
        params: dict | None = None,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> Any:
        """Get information from the API."""
        try:
            async with asyncio.timeout(timeout or 60):
                response = await self._session.request(
                    method=method,
                    url=API_BASE_URL + endpoint,
                    headers=self._auth_headers | (headers or {}),
                    params=params,
                    json=data,
                )
                _verify_response_or_raise(response)
                return response
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

    async def get_workspace(self, workspace_id: int) -> Any:
        """https://docs.drime.cloud/api-reference/user/get-workspace."""
        return await self._api_wrapper("GET", f"/workspace/{workspace_id}")

    async def get_space_usage(self, workspace_id: int = 0) -> Any:
        """https://docs.drime.cloud/api-reference/user/get-space-usage."""
        return await self._api_wrapper("GET", "/user/space-usage", params={"workspaceId": workspace_id})

    async def get_file_entries(self, folder_hash: str | None = None, workspace_id: int = 0) -> Any:
        """https://docs.drime.cloud/api-reference/files/get-file-entries."""
        return await self._api_wrapper(
            "GET", "/drive/file-entries", params={"workspaceId": workspace_id, "perPage": 100, "folderId": folder_hash}
        )

    async def get_folders(self, user_id: int, workspace_id: int = 0) -> Any:
        """https://docs.drime.cloud/api-reference/files/get-user-folders."""
        return await self._api_wrapper(
            "GET",
            f"/users/{user_id}/folders",
            params={"workspaceId": workspace_id},
        )

    async def get_folder_id(self, path: str, user_id: int) -> Any:
        """Get folder id."""
        folders = (await self.get_folders(user_id)).get("folders", [])
        fid = _get_folder_id(path.strip(" /"), folders)
        LOGGER.warning(fid)
        return fid

    async def download_file(self, entry_hash: str, timeout: float | None = None) -> Any:  # noqa: ASYNC109
        """https://docs.drime.cloud/api-reference/files/download-file."""
        return await self._stream_wrapper("GET", f"/file-entries/download/{entry_hash}", timeout=timeout)

    async def delete_entries(self, entry_ids: list[int]) -> Any:
        """https://docs.drime.cloud/api-reference/files/delete-entries."""
        return await self._api_wrapper("POST", "/file-entries/delete", data={"entryIds": entry_ids})
