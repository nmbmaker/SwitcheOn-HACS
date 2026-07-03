import logging
import aiohttp
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, API_URL_ACTION

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the SwitcheOn switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    channels = coordinator.data.get("channels", 0)
    names = coordinator.data.get("channelNames", [])
    
    entities = []
    for i in range(channels):
        name = names[i] if i < len(names) else f"Relay {i+1}"
        entities.append(SwitcheOnRelay(coordinator, entry, i, name))
        
    async_add_entities(entities)

class SwitcheOnRelay(CoordinatorEntity, SwitchEntity):
    """Representation of a SwitcheOn Relay."""
    
    # This tells HA to automatically prepend the Device Name to this switch's name!
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, channel_index, name):
        super().__init__(coordinator)
        self.entry = entry
        self.channel_index = channel_index
        self.bit_value = 1 << channel_index
        
        self._attr_name = name
        self._attr_unique_id = f"{entry.data['box_id_bin']}_relay_{channel_index}"
        
        # This groups the switch under a single physical Device in Home Assistant
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data["box_id_bin"])},
            "name": entry.data.get("box_name", "SwitcheOn Box"),
            "manufacturer": "SwitcheOn",
        }

    @property
    def is_on(self):
        """Return true if the switch is on."""
        if self.coordinator.data is None:
            return False
        current_status = self.coordinator.data.get("currentStatus", 0)
        return bool(current_status & self.bit_value)

    async def async_turn_on(self, **kwargs):
        await self._send_action(True)

    async def async_turn_off(self, **kwargs):
        await self._send_action(False)

    async def _send_action(self, target_state):
        current_status = self.coordinator.data.get("currentStatus", 0)
        
        if target_state:
            new_status = current_status | self.bit_value
        else:
            new_status = current_status & ~self.bit_value
        
        payload = {
            "userIdBin": self.entry.data["user_id_bin"],
            "userSecret": self.entry.data["user_secret"],
            "boxIdBin": self.entry.data["box_id_bin"],
            "requestedStatus": new_status
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL_ACTION, json=payload) as resp:
                    if resp.status == 200:
                        await self.coordinator.async_request_refresh()
                    else:
                        _LOGGER.error("Failed to toggle relay. Status: %s", resp.status)
        except Exception as err:
            _LOGGER.error("Error communicating with SwitcheOn API: %s", err)
