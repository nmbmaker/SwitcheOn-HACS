import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed
from homeassistant.util import slugify

from .const import API_URL_ACTION, DOMAIN
from .sensor import build_device_info, get_device_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn switches (2-channel or 4-channel) from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    box_data = coordinator.data

    if not isinstance(box_data, dict):
        _LOGGER.error("SwitcheOn: Unexpected coordinator data: %s", box_data)
        return

    channels_count = int(box_data.get("channels") or 0)
    if channels_count <= 0 and box_data.get("hvacMode") is not None:
        # Pure thermostat hardware with 0 relay channels
        return
    if channels_count <= 0:
        channels_count = len(box_data.get("channelNames") or []) or 2

    switches = [
        SwitcheOnSwitch(coordinator, entry, i)
        for i in range(channels_count)
    ]
    async_add_entities(switches)


class SwitcheOnSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a SwitcheOn Relay (supports 2-ch and 4-ch models)."""

    _attr_has_entity_name = False

    def __init__(self, coordinator, entry, channel_index):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.channel_index = channel_index
        self.entry = entry
        self.box_id_bin = entry.data["box_id_bin"]
        self.device_name = get_device_name(entry)

        unique_prefix = entry.unique_id or self.box_id_bin
        device_slug = slugify(self.device_name)

        self._attr_unique_id = f"{unique_prefix}_sw{channel_index}"
        self.entity_id = f"switch.switcheon_{device_slug}_sw{channel_index}"

        box_data = coordinator.data if isinstance(coordinator.data, dict) else {}
        self._attr_device_info = build_device_info(entry, box_data)
        self._last_synced_name = self.name

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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Sync renamed channel labels into the HA Entity Registry on every poll."""
        current_name = self.name
        if current_name != self._last_synced_name:
            self._last_synced_name = current_name
            ent_reg = er.async_get(self.hass)
            reg_entry = ent_reg.async_get(self.entity_id)
            if reg_entry and reg_entry.original_name != current_name:
                ent_reg.async_update_entity(
                    self.entity_id, original_name=current_name
                )
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self):
        """Expose read-only High Power status configured in the SwitcheOn app."""
        box_data = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        exclusive_mask = int(box_data.get("channelsExclusive") or 0)
        return {
            "channel_position": f"SW{self.channel_index}",
            "high_power_channel": bool(exclusive_mask & (1 << self.channel_index)),
        }

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
        """Pull fresh box state, set this channel bit on, and PUT to SwitcheOn."""
        await self._pull_and_set_channel(turn_on=True)

    async def async_turn_off(self, **kwargs):
        """Pull fresh box state, clear this channel bit, and PUT to SwitcheOn."""
        await self._pull_and_set_channel(turn_on=False)

    async def _pull_and_set_channel(self, turn_on: bool) -> None:
        """Serialize GET -> bitmask calculation -> PUT so phone/concurrent toggles never collide."""
        async with self.coordinator.action_lock:
            try:
                fresh_box = await self.coordinator.async_fetch_box()
            except UpdateFailed as err:
                raise HomeAssistantError(
                    f"Failed to fetch latest SwitcheOn state before switching: {err}"
                ) from err
            except Exception as err:
                raise HomeAssistantError(
                    f"Unable to reach SwitcheOn cloud before switching: {err}"
                ) from err

            current_mask = self._get_effective_mask(fresh_box)
            channel_bit = 1 << self.channel_index
            exclusive_mask = int(fresh_box.get("channelsExclusive") or 0)

            if turn_on:
                if exclusive_mask & channel_bit:
                    requested_status = (current_mask & ~exclusive_mask) | channel_bit
                else:
                    requested_status = current_mask | channel_bit
            else:
                requested_status = current_mask & ~channel_bit

            session = async_get_clientsession(self.hass)
            payload = {
                "userIdBin": self.entry.data["user_id_bin"].strip(),
                "userSecret": self.entry.data["user_secret"].strip(),
                "boxIdBin": fresh_box.get("boxIdBin", self.box_id_bin),
                "requestedStatus": requested_status,
            }

            async with session.put(API_URL_ACTION, json=payload) as response:
                if 200 <= response.status < 300:
                    fresh_box["pendingStatus"] = requested_status
                    self.coordinator.async_set_updated_data(fresh_box)
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
