"""Test Drime Backup sensors."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from homeassistant.helpers import entity_registry as er

from custom_components.drime.data import DrimeFileInfo

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

# ToDo:
#  - Test changes to Coordinator being reflected in sensor updates
# -  Test ActiveBackup convert_size...
