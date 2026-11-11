from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn switches from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    channels_count = coordinator.data["boxes"][0]["channels"]
    
    switches = []
    for i in range(channels_count):
        switches.append(SwitcheOnSwitch(coordinator, entry, i))
        
    async_add_entities(switches)


class SwitcheOnSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a SwitcheOn Relay."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, channel_index):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.channel_index = channel_index
        self.entry = entry
        self.qr_token = entry.data["qr_token"]
        self.device_name = entry.data["device_name"]
        
        self.channel_name = coordinator.data["boxes"][0]["channelNames"][channel_index]
        
        self._attr_name = self.channel_name
        self._attr_unique_id = f"{self.qr_token}_channel_{channel_index}"
        self.entity_id = f"switch.{slugify(self.device_name)}_{slugify(self.channel_name)}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.qr_token)},
            "name": self.device_name,
            "manufacturer": "SwitcheOn",
            "model": "SwitcheOn Box",
        }

    @property
    def is_on(self):
        """Return true if switch is on."""
        status_mask = self.coordinator.data["boxes"][0]["currentStatus"]
        return bool(status_mask & (1 << self.channel_index))

    async def async_turn_on(self, **kwargs):
        """Turn the switch on via SwitcheOn API."""
        box_data = self.coordinator.data["boxes"][0]
        current_status = box_data["currentStatus"]
        new_status = current_status | (1 << self.channel_index)
        
        await self._send_status_update(new_status)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off via SwitcheOn API."""
        box_data = self.coordinator.data["boxes"][0]
        current_status = box_data["currentStatus"]
        new_status = current_status & ~(1 << self.channel_index)
        
        await self._send_status_update(new_status)

    async def _send_status_update(self, new_status):
        """Send the updated status bitmask to the SwitcheOn API."""
        box_data = self.coordinator.data["boxes"][0]
        session = async_get_clientsession(self.hass)
        url = "https://www.switcheon.com/api/BoxUser"
        
        payload = {
            "userIdBin": self.entry.data["user_id_bin"],
            "boxIdBin": box_data["boxIdBin"],
            "currentStatus": new_status,
        }
        
        async with session.put(url, json=payload) as response:
            if response.status == 200:
                await self.coordinator.async_request_refresh()
            else:
                response_text = await response.text()
                raise Exception(f"Failed to control SwitcheOn device: {response.status} - {response_text}")
