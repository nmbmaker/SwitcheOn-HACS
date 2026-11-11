import asyncio
import aiohttp
import logging
from datetime import timedelta

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_URL_STATUS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SwitcheOnCoordinator(DataUpdateCoordinator):
    """Class to manage fetching SwitcheOn data and serializing commands."""

    def __init__(self, hass, entry):
        """Initialize."""
        interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=interval),
        )
        self.entry = entry
        self.action_lock = asyncio.Lock()

    async def async_fetch_box(self) -> dict:
        """Fetch the latest single matching box dict directly from SwitcheOn cloud."""
        params = {
            "UserIdBin": self.entry.data["user_id_bin"].strip(),
            "UserSecret": self.entry.data["user_secret"].strip(),
        }
        session = async_get_clientsession(self.hass)
        async with session.get(API_URL_STATUS, params=params) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"API returned status {resp.status}")

            data = await resp.json()
            boxes = data.get("boxes") or []
            for box in boxes:
                if box.get("boxIdBin") == self.entry.data["box_id_bin"]:
                    return box

            raise UpdateFailed(
                f"Box {self.entry.data['box_id_bin']} not found in account boxes"
            )

    async def _async_update_data(self):
        """Periodic background poll."""
        try:
            return await self.async_fetch_box()
        except UpdateFailed:
            raise
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with SwitcheOn API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected SwitcheOn error: {err}") from err
