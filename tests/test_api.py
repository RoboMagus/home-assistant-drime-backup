"""Tests for the Drime API."""

import uuid
from typing import Any
from unittest.mock import ANY, AsyncMock, call, patch

import aiohttp
import pytest
from homeassistant.helpers.json import json_dumps

from custom_components.drime.api import (
    DrimeApiClientAuthenticationError,
    DrimeApiClientRateLimitError,
    DrimeApiClientServerError,
    DrimeClient,
    _verify_response_or_raise,
)
from custom_components.drime.const import API_BASE_URL
from custom_components.drime.data import DrimeFileInfo


class MockResponse:
    """Test response."""

    def __init__(self, data: dict[str, Any] | None = None, status: int = 200) -> None:
        """Test response init."""
        self.status = status
        self.data = data

    async def json(self) -> dict[str, Any] | None:
        """Test response read."""
        return self.data

    def raise_for_status(self) -> None:
        """ClientResponse compat."""
        return


def test_verify_response_or_raise() -> None:
    """Test _verify_response_or_raise helper."""

    # OK: Does not raise
    _verify_response_or_raise(MockResponse(status=200))

    with pytest.raises(DrimeApiClientAuthenticationError):
        _verify_response_or_raise(MockResponse(status=401))

    with pytest.raises(DrimeApiClientRateLimitError):
        _verify_response_or_raise(MockResponse(status=429))

    with pytest.raises(DrimeApiClientServerError):
        _verify_response_or_raise(MockResponse(status=500))


async def test_get_user() -> None:
    """Test get_user."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.get_user()
        api_wrapper.assert_awaited_once_with("GET", "/cli/loggedUser")
        assert r == "_response_"


async def test_get_workspaces() -> None:
    """Test get_workspaces."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.get_workspaces()
        api_wrapper.assert_awaited_once_with("GET", "/me/workspaces")
        assert r == "_response_"


async def test_get_workspace() -> None:
    """Test get_workspace."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.get_workspace(42)
        api_wrapper.assert_awaited_once_with("GET", "/workspace/42")
        assert r == "_response_"


async def test_get_workspace_files() -> None:
    """Test get_workspace_files."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.get_workspace_files(42)
        api_wrapper.assert_awaited_once_with("GET", "/workspace_files", params={"workspaceId": 42})
        assert r == "_response_"


async def test_get_space_usage() -> None:
    """Test get_space_usage."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.get_space_usage()
        api_wrapper.assert_awaited_once_with("GET", "/user/space-usage", params={"workspaceId": 0})
        assert r == "_response_"


async def test_get_file_entries() -> None:
    """Test get_file_entries."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.get_file_entries("folder_hash")
        api_wrapper.assert_awaited_once_with(
            "GET", "/drive/file-entries", params={"workspaceId": 0, "perPage": 100, "folderId": "folder_hash"}
        )
        assert r == "_response_"


async def test_get_folders() -> None:
    """Test get_folders."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.get_folders(1234)
        api_wrapper.assert_awaited_once_with("GET", "/users/1234/folders", params={"workspaceId": 0})
        assert r == "_response_"


async def test_get_folder_id() -> None:
    """Test get_folder_id."""
    with (
        patch("custom_components.drime.api._get_folder_id", return_value="_gfi_return_value_") as get_folder_id,
        patch(
            "custom_components.drime.api.DrimeClient.get_folders", return_value={"folders": ["_gf_response_"]}
        ) as get_folders,
    ):
        client = DrimeClient("API_KEY", None)
        r = await client.get_folder_id("/path/to/folder/", 12345)
        get_folders.assert_awaited_once_with(12345)
        get_folder_id.assert_called_once_with("path/to/folder", ["_gf_response_"])
        assert r == "_gfi_return_value_"


async def test_get_folders_ids() -> None:
    """Test get_folders_ids."""
    with (
        patch(
            "custom_components.drime.api._get_folder_id", side_effect=["_gfi_1_", "_gfi_2_", "_gfi_3_"]
        ) as get_folder_id,
        patch(
            "custom_components.drime.api.DrimeClient.get_folders", return_value={"folders": ["_gf_response_"]}
        ) as get_folders,
    ):
        client = DrimeClient("API_KEY", None)
        r = await client.get_folders_ids(["/path/to/folder/", "/path/2", "path/with spaces "], 12345)
        get_folders.assert_awaited_once_with(12345)
        get_folder_id.assert_has_calls(
            [
                call("path/to/folder", ["_gf_response_"]),
                call("path/2", ["_gf_response_"]),
                call("path/with spaces", ["_gf_response_"]),
            ]
        )
        assert r == ["_gfi_1_", "_gfi_2_", "_gfi_3_"]


async def test_create_folder() -> None:
    """Test create_folder."""
    with patch(
        "custom_components.drime.api.DrimeClient._api_wrapper",
        return_value={"folder": {"id": 42, "name": "new_folder_name_result", "hash": "hash_result"}},
    ) as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.create_folder("new_folder_name", 123)
        api_wrapper.assert_awaited_once_with(
            "POST",
            "/folders",
            params={"workspaceId": 0},
            headers={"Content-Type": "application/json"},
            json={"name": "new_folder_name", "parentId": 123},
        )
        assert r == DrimeFileInfo(name="new_folder_name_result", hash="hash_result", id=42)


async def test_upload_file_simple() -> None:
    """Test upload_file_simple."""
    with (
        patch("uuid.uuid4", return_value=uuid.uuid4()),
        patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper,
    ):
        client = DrimeClient("API_KEY", None)
        r = await client.upload_file_simple(
            "/path/to/upload/to",
            "filename.json",
            json_dumps({"file": "content", "type": "JSON"}),
            "application/json",
            _size=42,
            workspace_id=9001,
        )
        expected_data = aiohttp.FormData()
        expected_data.add_field(
            "file",
            json_dumps({"file": "content", "type": "JSON"}),
            filename="filename.json",
            content_type="application/json",
        )
        expected_data.add_field("relativePath", "/path/to/upload/to/filename.json")
        expected_data.add_field("workspaceId", "9001")
        api_wrapper.assert_awaited_once_with("POST", "/uploads", data=ANY)
        assert await api_wrapper.await_args.kwargs["data"]().as_bytes() == await expected_data().as_bytes()
        assert r == "_response_"


async def test_create_multipart_upload() -> None:
    """Test create_multipart_upload."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.create_multipart_upload("path", "filename", "mime", 42, ".ext")
        api_wrapper.assert_awaited_once_with(
            "POST",
            "/s3/multipart/create",
            json={
                "filename": "filename",
                "mime": "mime",
                "size": 42,
                "extension": ".ext",
                "relativePath": "path",
                "workspaceId": 0,
            },
        )
        assert r == "_response_"


async def test_sign_part_urls() -> None:
    """Test sign_part_urls."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.sign_part_urls("key", "upload_id", [1, 2, 3])
        api_wrapper.assert_awaited_once_with(
            "POST",
            "/s3/multipart/batch-sign-part-urls",
            json={
                "key": "key",
                "uploadId": "upload_id",
                "partNumbers": [1, 2, 3],
            },
        )
        assert r == "_response_"


async def test_get_uploaded_parts() -> None:
    """Test get_uploaded_parts."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.get_uploaded_parts("key", "upload_id")
        api_wrapper.assert_awaited_once_with(
            "POST",
            "/s3/multipart/get-uploaded-parts",
            json={
                "key": "key",
                "uploadId": "upload_id",
            },
        )
        assert r == "_response_"


async def test_complete_multipart_upload() -> None:
    """Test complete_multipart_upload."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.complete_multipart_upload("key", "upload_id", [{"PN": 1, "ET": "e1"}, {"PN": 2, "ET": "e2"}])
        api_wrapper.assert_awaited_once_with(
            "POST",
            "/s3/multipart/complete",
            json={
                "key": "key",
                "uploadId": "upload_id",
                "parts": [{"PN": 1, "ET": "e1"}, {"PN": 2, "ET": "e2"}],
            },
        )
        assert r == "_response_"


async def test_abort_multipart_upload() -> None:
    """Test abort_multipart_upload."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.abort_multipart_upload("key", "upload_id")
        api_wrapper.assert_awaited_once_with(
            "POST",
            "/s3/multipart/abort",
            json={
                "key": "key",
                "uploadId": "upload_id",
            },
        )
        assert r == "_response_"


async def test_create_s3_entry() -> None:
    """Test create_s3_entry."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.create_s3_entry("uuid", "filename", 42, "mime", "extension", "path")
        api_wrapper.assert_awaited_once_with(
            "POST",
            "/s3/entries",
            json={
                "filename": "uuid",
                "size": 42,
                "clientName": "filename",
                "clientMime": "mime",
                "clientExtension": "extension",
                "relativePath": "path",
                "workspaceId": 0,
            },
        )
        assert r == "_response_"


async def test_delete_entries() -> None:
    """Test delete_entries."""
    with patch("custom_components.drime.api.DrimeClient._api_wrapper", return_value="_response_") as api_wrapper:
        client = DrimeClient("API_KEY", None)
        r = await client.delete_entries([1, 2, 5], permanent=True)
        api_wrapper.assert_awaited_once_with(
            "POST",
            "/file-entries/delete",
            json={"entryIds": [1, 2, 5], "deleteForever": True},
        )
        assert r == "_response_"


async def test_download_file() -> None:
    """Test download_file (Includes _stream_wrapper)."""
    aiohttp_session_mock = AsyncMock()
    aiohttp_session_mock.request = AsyncMock(return_value=MockResponse({"mock_response": True}, 200))
    client = DrimeClient("API_KEY", aiohttp_session_mock)
    r = await client.download_file("entry_hash")
    assert await r.json() == {"mock_response": True}
    aiohttp_session_mock.request.assert_awaited_once_with(
        method="GET",
        url=API_BASE_URL + "/file-entries/download/entry_hash",
        headers=ANY,
        params=None,
        json=None,
        timeout=ANY,
    )
