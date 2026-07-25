"""Backup platform for the Google Drive integration."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import asdict, dataclass
from functools import wraps
from time import time
from typing import Any, Self, override

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    OnProgressCallback,
    suggested_filename,
)
from homeassistant.const import CONF_PATH
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import ChunkAsyncStreamIterator
from homeassistant.util import slugify
from homeassistant.util.async_ import gather_with_limited_concurrency
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads_object

from .const import DOMAIN
from .data import DrimeConfigEntry

_LOGGER = logging.getLogger(__name__)

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(f"{DOMAIN}.backup_agent_listeners")

CACHE_TTL = 300
METADATA_DOWNLOAD_CONCURRENCY = 4


def suggested_filenames(backup: AgentBackup) -> tuple[str, str]:
    """Return the suggested filenames for the backup and metadata."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{base_name}.tar", f"{base_name}.metadata.json"


def get_backup_file_pairs(folder_contents: list[dict[str, Any]]) -> list[BackupFilePair]:
    """Parse Drime '/drive/file-entries' output for backup file pairs."""
    pre_structured = {f["name"].removesuffix(".tar"): DrimeFileInfo.from_dict(f) for f in folder_contents}

    return [
        BackupFilePair(tar=t, meta=m)
        for n, m in pre_structured.items()
        if n.endswith(".metadata.json") and (t := pre_structured.get(n.removesuffix(".metadata.json")))
    ]


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return [DrimeBackupAgent(entry, hass) for entry in entries]


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """
    Register a listener to be called when agents are added or removed.

    :return: A function to unregister the listener.
    """
    hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[DATA_BACKUP_AGENT_LISTENERS].remove(listener)
        if not hass.data[DATA_BACKUP_AGENT_LISTENERS]:
            del hass.data[DATA_BACKUP_AGENT_LISTENERS]

    return remove_listener


@dataclass(frozen=True, kw_only=True)
class DrimeFileInfo:
    """Drime file info class."""

    name: str
    hash: str
    id: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create an instance from a JSON serialization."""
        return cls(
            name=data["name"],
            hash=data["hash"],
            id=data["id"],
        )


@dataclass(frozen=True, kw_only=True)
class BackupFilePair:
    """Drime backup file pair class."""

    tar: DrimeFileInfo
    meta: DrimeFileInfo


@dataclass(frozen=True, kw_only=True)
class DrimeAgentBackup(AgentBackup):
    """Drime Agent backup class."""

    meta_hash: str
    meta_id: int
    tar_hash: str
    tar_id: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create an instance from a JSON serialization."""
        return cls(
            **asdict(AgentBackup.from_dict(data)),
            meta_hash=data["meta_hash"],
            meta_id=data["meta_id"],
            tar_hash=data["tar_hash"],
            tar_id=data["tar_id"],
        )


class DrimeBackupAgent(BackupAgent):
    """Drime backup agent."""

    domain = DOMAIN

    def __init__(self, config_entry: DrimeConfigEntry, hass: HomeAssistant) -> None:
        """Initialize the cloud backup sync agent."""
        super().__init__()
        self.name = config_entry.title
        self.unique_id = slugify(config_entry.unique_id)
        self.hass = hass
        self._client = config_entry.runtime_data.client
        self._backup_path = config_entry.data.get(CONF_PATH, "/HomeAssistant")
        self._backup_folder_hash = None
        self._cache_expiration = time()

    async def get_backup_folder_hash(self) -> str:
        """Retrieve and cache folder hash for for backup directory."""
        if not self._backup_folder_hash:
            _LOGGER.debug("get_backup_folder_hash")
            user = await self._client.get_user()
            _, _, self._backup_folder_hash = await self._client.get_folder_id(
                self._backup_path, user.get("user", {}).get("id")
            )
        return self._backup_folder_hash

    @override
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        on_progress: OnProgressCallback,
        **kwargs: Any,
    ) -> None:
        """
        Upload a backup.

        :param open_stream: A function returning an async iterator that yields bytes.
        :param backup: Metadata about the backup that should be uploaded.
        """
        _LOGGER.error("async_download_backup NOT YET IMPLEMENTED")
        raise BackupAgentError("Failed to upload backup")

    @override
    async def async_list_backups(self, **kwargs: Any) -> list[DrimeAgentBackup]:
        """List backups."""
        return list((await self._list_cached_backups()).values())

    @override
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> DrimeAgentBackup:
        """Return a backup."""
        return await self._find_backup_by_id(backup_id)

    @override
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """
        Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """
        _LOGGER.debug("Downloading backup_id: %s", backup_id)
        backup = await self._find_backup_by_id(backup_id)

        start_time = time()
        response = await self._client.download_file(backup.tar_hash, timeout=10 * 60)
        elapsed_time = time() - start_time
        _LOGGER.debug("Downloaded backup_id %s: %s in %.2fs", backup_id, backup.name, elapsed_time)
        return response.content.iter_chunked(1024)

    @override
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """
        Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        _LOGGER.debug("Deleting backup_id: %s", backup_id)
        backup = await self._find_backup_by_id(backup_id)

        try:
            await self._client.delete_entries([backup.meta_id, backup.tar_id])
        except Exception as err:
            raise BackupAgentError(f"Failed to delete backup: {err}") from err

        _LOGGER.debug("Deleted backup '%s', with hashes (%s, %s)", backup.name, backup.meta_hash, backup.tar_hash)

        # reset cache
        self._cache_expiration = time()

    async def _list_cached_backups(self) -> dict[str, DrimeAgentBackup]:
        """List metadata files with a cache."""
        if time() <= self._cache_expiration:
            return self._cache_metadata_files

        async def _download_metadata(file_pair: BackupFilePair) -> DrimeAgentBackup | None:
            """Download metadata file."""
            response = await self._client.download_file(file_pair.meta.hash, timeout=30)
            metadata_bytes = await response.content.read()
            try:
                return DrimeAgentBackup.from_dict(
                    json_loads_object(metadata_bytes)
                    | {
                        "meta_id": file_pair.meta.id,
                        "meta_hash": file_pair.meta.hash,
                        "tar_id": file_pair.tar.id,
                        "tar_hash": file_pair.tar.hash,
                    }
                )
            except (*JSON_DECODE_EXCEPTIONS, KeyError, TypeError, ValueError) as err:
                _LOGGER.warning(
                    "Skipping invalid backup metadata file %s (%s): %s", file_pair.meta.name, file_pair.meta.hash, err
                )
                return None

        async def _list_metadata_files() -> dict[str, DrimeAgentBackup]:
            """List metadata files."""
            bfh = await self.get_backup_folder_hash()
            _LOGGER.debug("Fetching entries for backup folder hash: %s", bfh)
            backup_folder_contents = await self._client.get_file_entries(bfh)

            backup_files = get_backup_file_pairs(backup_folder_contents["data"])
            _LOGGER.debug(f"backup_files: {backup_files}")

            metadata_contents = await gather_with_limited_concurrency(
                METADATA_DOWNLOAD_CONCURRENCY,
                *(_download_metadata(f) for f in backup_files),
            )
            return {
                metadata_content.backup_id: metadata_content
                for metadata_content in metadata_contents
                if metadata_content
            }

        self._cache_metadata_files = await _list_metadata_files()
        self._cache_expiration = time() + CACHE_TTL
        return self._cache_metadata_files

    async def _find_backup_by_id(self, backup_id: str) -> DrimeAgentBackup:
        """Find a backup by its backup ID on remote."""
        backups = await self._list_cached_backups()
        if backup := backups.get(backup_id):
            return backup

        raise BackupNotFound(f"Backup {backup_id} not found")
