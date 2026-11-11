import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from .const import API_URL_ACTION, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn switches (2-channel or 4-channel) from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    box_data = coordinator.data

    if not isinstance(box_data, dict):
        _LOGGER.error("SwitcheOn: Unexpected coordinator data: %s", box_data)
        return

    channels_count = int(
        box_data.get("channels")
        or len(box_data.get("channelNames") or [])
        or 2
    )

    switches = [
        SwitcheOnSwitch(coordinator, entry, i, channels_count)
        for i in range(channels_count)
    ]
    async_add_entities(switches)


class SwitcheOnSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a SwitcheOn Relay (supports 2-ch and 4-ch models)."""

    _attr_has_entity_name = False

    def __init__(self, coordinator, entry, channel_index, channels_count):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.channel_index = channel_index
        self.entry = entry
        self.box_id_bin = entry.data["box_id_bin"]
        self.device_name = (
            entry.data.get("box_name") or entry.title or "SwitcheOn"
        ).strip()

        unique_prefix = entry.unique_id or self.box_id_bin
        device_slug = slugify(self.device_name)

        self._attr_unique_id = f"{unique_prefix}_sw{channel_index}"
        self.entity_id = f"switch.switcheon_{device_slug}_sw{channel_index}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_prefix)},
            "name": f"SwitcheOn {self.device_name}",
            "manufacturer": "SwitcheOn",
            "model": f"SwitcheOn {channels_count}-Channel Box",
        }

    @property
    def name(self):
        """Return dynamic friendly name from API (falls back to SW0..SW3 if blank)."""
        box_data = self.coordinator.data or {}
        channel_names = box_data.get("channelNames") or []
        raw_label = (
            channel_names[self.channel_index]
            if self.channel_index < len(channel_names)
            else None
        )
        clean_label = str(raw_label).strip() if raw_label is not None else ""
        if not clean_label:
            clean_label = f"SW{self.channel_index}"
        return f"{self.device_name} {clean_label}"

    def _get_effective_mask(self, box_data):
        """Use pendingStatus while a cellular command is in flight, else currentStatus."""
        pending = box_data.get("pendingStatus")
        if pending is not None:
            return int(pending)
        return int(box_data.get("currentStatus", 0))

    @property
    def is_on(self):
        """Return true if switch is on (or pending on)."""
        box_data = self.coordinator.data
        if not isinstance(box_data, dict):
            return None
        status_mask = self._get_effective_mask(box_data)
        return bool(status_mask & (1 << self.channel_index))

    async def async_turn_on(self, **kwargs):
        """Turn the switch on via SwitcheOn API."""
        box_data = self.coordinator.data
        if not isinstance(box_data, dict):
            raise HomeAssistantError("SwitcheOn box data is unavailable.")
        current_mask = self._get_effective_mask(box_data)
        new_status = current_mask | (1 << self.channel_index)
        await self._send_status_update(box_data, new_status)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off via SwitcheOn API."""
        box_data = self.coordinator.data
        if not isinstance(box_data, dict):
            raise HomeAssistantError("SwitcheOn box data is unavailable.")
        current_mask = self._get_effective_mask(box_data)
        new_status = current_mask & ~(1 << self.channel_index)
        await self._send_status_update(box_data, new_status)

    async def _send_status_update(self, box_data, requested_status):
        """Send the requestedStatus bitmask to https://www.switcheon.com/api/req."""
        session = async_get_clientsession(self.hass)

        payload = {
            "userIdBin": self.entry.data["user_id_bin"].strip(),
            "userSecret": self.entry.data["user_secret"].strip(),
            "boxIdBin": box_data.get("boxIdBin", self.box_id_bin),
            "requestedStatus": requested_status,
        }

        async with session.put(API_URL_ACTION, json=payload) as response:
            if 200 <= response.status < 300:
                box_data["pendingStatus"] = requested_status
                self.async_write_ha_state()
                await self.coordinator.async_request_refresh()
            else:
                response_text = await response.text()
                _LOGGER.error(
                    "SwitcheOn PUT failed (%s): %s",
                    response.status,
                    response_text,
                )
                raise HomeAssistantError(
                    f"SwitcheOn API error {response.status}: {response_text}"
                )
