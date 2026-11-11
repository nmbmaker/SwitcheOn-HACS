import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONTROL_URL = "https://www.switcheon.com/api/req"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn switches from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    qr_token = entry.data["qr_token"].upper()

    box_data = next(
        (
            b
            for b in coordinator.data.get("boxes", [])
            if b.get("boxIdText", "").upper() == qr_token
        ),
        coordinator.data["boxes"][0],
    )

    channels_count = box_data["channels"]
    switches = [
        SwitcheOnSwitch(coordinator, entry, i) for i in range(channels_count)
    ]
    async_add_entities(switches)


class SwitcheOnSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a SwitcheOn Relay."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, channel_index):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.channel_index = channel_index
        self.entry = entry
        self.qr_token = entry.data["qr_token"].upper()
        self.device_name = entry.data["device_name"]

        box_data = self._get_box_data()
        self.channel_name = box_data["channelNames"][channel_index]

        self._attr_name = self.channel_name
        self._attr_unique_id = f"{self.qr_token}_channel_{channel_index}"
        self.entity_id = (
            f"switch.{slugify(self.device_name)}_{slugify(self.channel_name)}"
        )

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.qr_token)},
            "name": self.device_name,
            "manufacturer": "SwitcheOn",
            "model": "SwitcheOn Box",
        }

    def _get_box_data(self):
        """Find the specific box matching this entry's QR token."""
        boxes = self.coordinator.data.get("boxes", [])
        for box in boxes:
            if box.get("boxIdText", "").upper() == self.qr_token:
                return box
        return boxes[0]

    def _get_effective_mask(self, box_data):
        """Use pendingStatus while a cellular command is in flight, else currentStatus."""
        pending = box_data.get("pendingStatus")
        if pending is not None:
            return pending
        return box_data.get("currentStatus", 0)

    @property
    def is_on(self):
        """Return true if switch is on (or pending on)."""
        box_data = self._get_box_data()
        status_mask = self._get_effective_mask(box_data)
        return bool(status_mask & (1 << self.channel_index))

    async def async_turn_on(self, **kwargs):
        """Turn the switch on via SwitcheOn API."""
        box_data = self._get_box_data()
        current_mask = self._get_effective_mask(box_data)
        new_status = current_mask | (1 << self.channel_index)
        await self._send_status_update(box_data, new_status)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off via SwitcheOn API."""
        box_data = self._get_box_data()
        current_mask = self._get_effective_mask(box_data)
        new_status = current_mask & ~(1 << self.channel_index)
        await self._send_status_update(box_data, new_status)

    async def _send_status_update(self, box_data, requested_status):
        """Send the requestedStatus bitmask to https://www.switcheon.com/api/req."""
        session = async_get_clientsession(self.hass)

        user_id_bin = (
            self.entry.data.get("user_id_bin")
            or self.entry.data.get("userIdBin")
        )
        user_secret = (
            self.entry.data.get("user_secret")
            or self.entry.data.get("userSecret")
        )

        payload = {
            "userIdBin": user_id_bin,
            "userSecret": user_secret,
            "boxIdBin": box_data["boxIdBin"],
            "requestedStatus": requested_status,
        }

        async with session.put(CONTROL_URL, json=payload) as response:
            if response.status in (200, 204):
                # Hold UI state via pendingStatus until the cellular box confirms
                box_data["pendingStatus"] = requested_status
                self.async_write_ha_state()
                await self.coordinator.async_request_refresh()
            else:
                response_text = await response.text()
                _LOGGER.error(
                    "SwitcheOn control failed (%s) at %s: %s",
                    response.status,
                    CONTROL_URL,
                    response_text,
                )
                raise HomeAssistantError(
                    f"SwitcheOn API error {response.status}: {response_text}"
                )
