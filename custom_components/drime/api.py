"""Sample API Client."""

from __future__ import annotations

import logging
import math
from json import dumps as json_dumps
from typing import TYPE_CHECKING, Any

import aiohttp
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .const import API_BASE_URL
from .data import DrimeFileInfo

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Coroutine

    from homeassistant.components.backup import OnProgressCallback

LOGGER = logging.getLogger(__name__)
PART_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
PRINT_UPLOADED_PARTS = False

api_retry = retry(
    retry=retry_if_exception_type((TimeoutError, aiohttp.ClientConnectorError)),
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=3, jitter=2, max=60),
    before_sleep=before_sleep_log(LOGGER, logging.WARNING),
    reraise=True,
)

s3_retry = retry(
    retry=retry_if_exception_type((TimeoutError, aiohttp.ClientConnectorError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, jitter=2, max=30),
    before_sleep=before_sleep_log(LOGGER, logging.WARNING),
    reraise=True,
)


class DrimeApiClientError(Exception):
    """Exception to indicate a general API error."""


class DrimeApiClientCommunicationError(DrimeApiClientError):
    """Exception to indicate a communication error."""


class DrimeApiClientRateLimitError(DrimeApiClientError):
    """Exception to indicate rate limitting."""


class DrimeApiClientServerError(DrimeApiClientError):
    """Exception to indicate a server error."""


class DrimeApiClientAuthenticationError(DrimeApiClientError):
    """Exception to indicate an authentication error."""


class DrimeUploadError(DrimeApiClientError):
    """Exception to indicate upload error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise DrimeApiClientAuthenticationError(msg)
    if response.status == 429:  # noqa: PLR2004
        msg = "Too many requests"
        raise DrimeApiClientRateLimitError(msg)
    if response.status >= 500:  # noqa: PLR2004
        msg = f"Server Error: {response.status}"
        raise DrimeApiClientServerError(msg)
    response.raise_for_status()


def _get_folder_id(path: str, folders: list[dict[str, Any]]) -> DrimeFileInfo:
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
            LOGGER.warning("Path not found @ %d: %s", i, path)
            return DrimeFileInfo(name="/".join(directory_tree[:i]), hash=folder_hash, id=current_folder_id or 0)

    LOGGER.info("Found: /%s", path)
    return DrimeFileInfo(name="/".join(directory_tree), hash=folder_hash, id=current_folder_id or 0)


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
        json: dict | None = None,
        data: dict | aiohttp.FormData | None = None,
        headers: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            response = await self._session.request(
                method=method,
                url=API_BASE_URL + endpoint,
                headers=self._auth_headers | (headers or {}),
                params=params,
                json=json,
                data=data,
                timeout=aiohttp.ClientTimeout(total=15),
            )
            _verify_response_or_raise(response)
            return await response.json()
        except (aiohttp.ClientConnectionError, aiohttp.ClientResponseError) as exception:
            msg = f"Error fetching information - {exception}"
            raise DrimeApiClientCommunicationError(msg) from exception
        except Exception as exception:
            msg = f"Something really wrong happened! - {exception}"
            raise DrimeApiClientError(msg) from exception

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
            response = await self._session.request(
                method=method,
                url=API_BASE_URL + endpoint,
                headers=self._auth_headers | (headers or {}),
                params=params,
                json=data,
                timeout=aiohttp.ClientTimeout(total=timeout or 60),
            )
            _verify_response_or_raise(response)
        except aiohttp.ClientError as exception:
            msg = f"Error fetching information - {exception}"
            raise DrimeApiClientCommunicationError(msg) from exception
        except Exception as exception:
            msg = f"Something really wrong happened! - {exception}"
            raise DrimeApiClientError(msg) from exception
        else:
            return response

    async def get_user(self) -> Any:
        """https://docs.drime.cloud/api-reference/user/get-logged-user."""
        return await self._api_wrapper("GET", "/cli/loggedUser")

    async def get_workspaces(self) -> Any:
        """https://docs.drime.cloud/api-reference/user/get-workspaces."""
        return await self._api_wrapper("GET", "/me/workspaces")

    async def get_workspace(self, workspace_id: int) -> Any:
        """https://docs.drime.cloud/api-reference/user/get-workspace."""
        return await self._api_wrapper("GET", f"/workspace/{int(workspace_id)}")

    async def get_workspace_files(self, workspace_id: int) -> Any:
        """https://docs.drime.cloud/api-reference/user/get-workspace-files."""
        return await self._api_wrapper("GET", "/workspace_files", params={"workspaceId": workspace_id})

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

    async def get_folder_id(self, path: str, user_id: int) -> DrimeFileInfo:
        """Get folder id."""
        folders = (await self.get_folders(user_id)).get("folders", [])
        fid = _get_folder_id(path.strip(" /"), folders)
        LOGGER.debug("get_folder_id(%s): %r", path, fid)
        return fid

    async def get_folders_ids(self, paths: list[str], user_id: int) -> list[DrimeFileInfo]:
        """Get folder id."""
        folders = (await self.get_folders(user_id)).get("folders", [])
        return [_get_folder_id(path.strip(" /"), folders) for path in paths]

    async def create_folder(self, name: str, parent_folder_id: int | None, workspace_id: int = 0) -> DrimeFileInfo:
        """https://docs.drime.cloud/api-reference/files/create-folder."""
        result = await self._api_wrapper(
            "POST",
            "/folders",
            params={"workspaceId": workspace_id},
            headers={"Content-Type": "application/json"},
            json={
                "name": name,
                "parentId": parent_folder_id or None,  # Root folder needs None instead of 0 for parent!
            },
        )
        return DrimeFileInfo.from_dict(result["folder"])

    @api_retry
    async def upload_file_simple(
        self, path: str, filename: str, content: Any, content_type: str, _size: int, workspace_id: int = 0
    ) -> Any:
        """https://docs.drime.cloud/api-reference/uploads/upload-file."""
        if not path.endswith("/"):
            path = path + "/"
        path += filename

        data = aiohttp.FormData()
        data.add_field("file", content, filename=filename, content_type=content_type)
        data.add_field("relativePath", path)
        if workspace_id:
            data.add_field("workspaceId", str(workspace_id))

        return await self._api_wrapper(
            "POST",
            "/uploads",
            data=data,
        )

    # Multipart Upload Flow:
    #  1. Create - Initialize the upload (create_multipart_upload)
    #  2. Sign - Get presigned URLs for each part (sign_part_urls)
    #   3. Upload - PUT each part to its URL
    #  4. Complete - Finalize the upload (complete_multipart_upload)
    #  5. Register - Create file entry (create_s3_entry)
    async def upload_file_multipart(  # noqa: PLR0915
        self,
        path: str,
        filename: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        on_progress: OnProgressCallback,
        content_type: str,
        file_size: int,
        workspace_id: int = 0,
    ) -> Any:
        """Wraping function to process multi-part uploads."""
        # Based on aws_s3 / cloudflare_r2 backup integrations

        if not path.endswith("/"):
            path = path + "/"
        path += filename

        num_parts = math.ceil(file_size / PART_SIZE_BYTES)

        extension = "tar"
        init_response = await self.create_multipart_upload(
            path, filename, content_type, file_size, extension, workspace_id
        )

        upload_id = init_response.get("uploadId")
        key = init_response.get("key")

        if not upload_id or not key:
            msg = "Failed to initialize multipart upload"
            raise DrimeUploadError(msg)

        LOGGER.debug("Initialized MultiPart upload: %s", key)

        signed_urls: dict[int, str] = {}

        async def get_signed_url(num: int) -> str:
            """Batch pre-signed urls."""
            if not (signed_url := signed_urls.pop(num, None)):
                batch_size = min(num_parts - num + 1, 12)
                part_numbers = list(range(num, num + batch_size))
                LOGGER.debug("Signing parts: %r", part_numbers)
                sign_response = await self.sign_part_urls(key, upload_id, part_numbers)
                signed_urls.update({u["partNumber"]: u["url"] for u in sign_response.get("urls", [])})

                signed_url = signed_urls.pop(num, None)
                if not signed_url:
                    msg = f"No signed URL for part {num}"
                    raise DrimeUploadError(msg)
            return signed_url

        @s3_retry
        async def upload_part(url: str, data: bytes) -> aiohttp.ClientResponse:
            return await self._session.request(
                method="PUT",
                url=url,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(len(data)),
                },
                data=data,
            )

        try:
            uploaded_parts: list[dict[str, Any]] = []
            part_number = 1
            buffer = bytearray()  # bytes buffer to store the data
            offset = 0  # start index of unread data inside buffer
            bytes_uploaded = 0

            stream = await open_stream()
            async for chunk in stream:
                buffer.extend(chunk)
                # Upload parts of exactly PART_SIZE_BYTES to ensure
                # all non-trailing parts have the same size (defensive implementation)
                view = memoryview(buffer)
                try:
                    while len(buffer) - offset >= PART_SIZE_BYTES:
                        start = offset
                        end = offset + PART_SIZE_BYTES
                        part_data = view[start:end]
                        offset = end

                        signed_url = await get_signed_url(part_number)
                        LOGGER.debug(
                            "Uploading part number %d / %d, size %d",
                            part_number,
                            num_parts,
                            len(part_data),
                        )
                        response = await upload_part(signed_url, part_data.tobytes())
                        etag = response.headers.get("ETag", "")
                        uploaded_parts.append({"PartNumber": part_number, "ETag": etag})
                        bytes_uploaded += len(part_data)
                        on_progress(bytes_uploaded=bytes_uploaded)
                        part_number += 1
                finally:
                    view.release()

                # Compact the buffer if the consumed offset
                # has grown large enough. This avoids
                # unnecessary memory copies when compacting
                # after every part upload.
                if offset and offset >= PART_SIZE_BYTES:
                    buffer = bytearray(buffer[offset:])
                    offset = 0

            # Upload the final buffer as the last part (no minimum size requirement)
            # Offset should be 0 after the last compaction, but we use it as the start
            # index to be defensive in case the buffer was not compacted.
            if offset < len(buffer):
                remaining_data = memoryview(buffer)[offset:]
                LOGGER.debug(
                    "Uploading final part number %d / %d, size %d",
                    part_number,
                    num_parts,
                    len(remaining_data),
                )
                signed_url = await get_signed_url(part_number)
                response = await upload_part(signed_url, remaining_data.tobytes())
                etag = response.headers.get("ETag", "")
                uploaded_parts.append({"PartNumber": part_number, "ETag": etag})
                bytes_uploaded += len(remaining_data)
                on_progress(bytes_uploaded=bytes_uploaded)

            if PRINT_UPLOADED_PARTS:
                parts_response = await self.get_uploaded_parts(key, upload_id)
                LOGGER.info(
                    json_dumps(
                        parts_response,
                        indent=2,
                        default=lambda _: "<< Not JSON Serializable >>",
                    )
                )

            LOGGER.debug("Complete with parts: %r", uploaded_parts)
            await self.complete_multipart_upload(key, upload_id, uploaded_parts)

            uuid = key.split("/")[-1]
            return await self.create_s3_entry(uuid, filename, file_size, content_type, extension, path, workspace_id)

        except Exception as e:
            LOGGER.exception("Multipart upload error! Calling abort.")
            try:
                abort_response = await self.abort_multipart_upload(key, upload_id)
                LOGGER.debug("Abort status: %s", abort_response)
            except Exception:
                LOGGER.exception("Exception during abort_multipart_upload:")
            msg = f"Multipart upload failed: {e}"
            raise DrimeUploadError(msg) from e

    @api_retry
    async def create_multipart_upload(
        self, path: str, filename: str, mime: str, size: int, extension: str, workspace_id: int = 0
    ) -> Any:
        """https://docs.drime.cloud/api-reference/multipart/create-multipart."""
        return await self._api_wrapper(
            "POST",
            "/s3/multipart/create",
            json={
                "filename": filename,
                "mime": mime,
                "size": size,
                "extension": extension,
                "relativePath": path,
                "workspaceId": workspace_id,
            },
        )

    @api_retry
    async def sign_part_urls(self, key: str, upload_id: str, part_numbers: list[int]) -> Any:
        """https://docs.drime.cloud/api-reference/multipart/sign-part-urls."""
        return await self._api_wrapper(
            "POST",
            "/s3/multipart/batch-sign-part-urls",
            json={"key": key, "uploadId": upload_id, "partNumbers": part_numbers},
        )

    @api_retry
    async def get_uploaded_parts(self, key: str, upload_id: str) -> Any:
        """https://docs.drime.cloud/api-reference/multipart/get-uploaded-parts."""
        return await self._api_wrapper(
            "POST",
            "/s3/multipart/get-uploaded-parts",
            json={"key": key, "uploadId": upload_id},
        )

    @api_retry
    async def complete_multipart_upload(self, key: str, upload_id: str, parts: list[dict[str, Any]]) -> Any:
        """https://docs.drime.cloud/api-reference/multipart/complete-multipart."""
        return await self._api_wrapper(
            "POST",
            "/s3/multipart/complete",
            json={"key": key, "uploadId": upload_id, "parts": parts},
        )

    @api_retry
    async def abort_multipart_upload(self, key: str, upload_id: str) -> Any:
        """https://docs.drime.cloud/api-reference/multipart/abort-multipart."""
        return await self._api_wrapper(
            "POST",
            "/s3/multipart/abort",
            json={"key": key, "uploadId": upload_id},
        )

    @api_retry
    async def create_s3_entry(
        self, uuid: str, filename: str, size: int, mime: str, extension: str, path: str, workspace_id: int = 0
    ) -> Any:
        """https://docs.drime.cloud/api-reference/uploads/create-s3-entry."""
        return await self._api_wrapper(
            "POST",
            "/s3/entries",
            json={
                "filename": uuid,
                "size": size,
                "clientName": filename,
                "clientMime": mime,
                "clientExtension": extension,
                "relativePath": path,
                "workspaceId": workspace_id,
            },
        )

    async def download_file(self, entry_hash: str, timeout: float | None = None) -> Any:  # noqa: ASYNC109
        """https://docs.drime.cloud/api-reference/files/download-file."""
        return await self._stream_wrapper("GET", f"/file-entries/download/{entry_hash}", timeout=timeout)

    @api_retry
    async def delete_entries(self, entry_ids: list[int], *, permanent: bool = False) -> Any:
        """https://docs.drime.cloud/api-reference/files/delete-entries."""
        return await self._api_wrapper(
            "POST", "/file-entries/delete", json={"entryIds": entry_ids, "deleteForever": permanent}
        )
