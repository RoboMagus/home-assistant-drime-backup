"""Constants for Drime."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "drime"

API_BASE_URL = "https://app.drime.cloud/api/v1"

CONF_EXTRA_PATHS = "extra_paths"
CONF_USER_ID = "user_id"
DEFAULT_BACKUP_PATH = "/HomeAssistant"
