import aiohttp
import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, API_URL_STATUS, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

class SwitcheOnCoordinator(DataUpdateCoordinator):
    """Class to manage fetching SwitcheOn data."""

    def __init__(self, hass, entry):
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.entry = entry

    async def _async_update_data(self):
        """Fetch data from SwitcheOn API."""
        params = {
            "UserIdBin": self.entry.data["user_id_bin"],
            "UserSecret": self.entry.data["user_secret"]
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(API_URL_STATUS, params=params) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"API returned status {resp.status}")
                    
                    data = await resp.json()
                    
                    # Extract our specific box from the response array
                    boxes = data.get("boxes", [])
                    for box in boxes:
                        if box.get("boxIdBin") == self.entry.data["box_id_bin"]:
                            return box
                            
                    raise UpdateFailed("Box ID not found in API response")
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")