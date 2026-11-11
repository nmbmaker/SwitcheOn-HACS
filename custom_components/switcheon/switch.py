import logging
import re
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONTROL_URL = "https://www.switcheon.com/api/req"


def _extract_qr_token(entry):
    """Find the 32-char hex QR token in entry.data or entry.unique_id."""
    for key in ("qr_token", "qr_code", "token", "box_id", "boxIdText", "qr"):
        if key in entry.data and entry.data[key]:
            return str(entry.data[key]).strip()
    if entry.unique_id and re.fullmatch(r"[0-9a-fA-F]{32}", str(entry.unique_id).strip()):
        return str(entry.unique_id).strip()
    for val in entry.data.values():
        if isinstance(val, str) and re.fullmatch(r"[0-9a-fA-F]{32}", val.strip()):
            return val.strip()
    return str(entry.unique_id or "")


def _extract_device_name(entry):
    """Pull user-entered device name from entry.data or entry.title (e.g., N1538Z)."""
    for key in ("device_name", "name", "box_name", "device", "custom_name", "title"):
        val = entry.data.get(key)
        if isinstance(val, str) and val.strip() and val.strip().lower() != "my switcheon":
            return val.strip()
    if entry.title and entry.title.strip().lower() not in ("switcheon", "my switcheon"):
        return entry.title.strip()
    return entry.title.strip() if entry.title else "box"


def _extract_credentials(entry):
    """Find userIdBin and userSecret in entry.data regardless of key naming."""
    data = entry.data
    user_id_bin = None
    user_secret = None

    for k, v in data.items():
        if not isinstance(v, str):
            continue
        kl = k.lower()
        if "secret" in kl or "pass" in kl:
            user_secret = v.strip()
        elif "user" in kl or "bin" in kl:
            user_id_bin = v.strip()

    for v in data.values():
        if not isinstance(v, str):
            continue
        vs = v.strip()
        if not user_id_bin and vs.endswith("==") and len(vs) == 24:
            user_id_bin = vs
        elif (
            not user_secret
            and len(vs) == 32
            and not re.fullmatch(r"[0-9a-fA-F]{32}", vs)
        ):
            user_secret = vs

    return user_id_bin, user_secret


def _resolve_box(coordinator_data, qr_token):
    """Locate the matching box dict safely for multi-box setups."""
    if not isinstance(coordinator_data, dict):
        return None
    boxes = coordinator_data.get("boxes") or []
    if not boxes:
        return None
    if qr_token:
        target = qr_token.upper()
        for box in boxes:
            if str(box.get("boxIdText", "")).strip().upper() == target:
                return box
    return boxes[0]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn switches from a config entry."""
    entry_obj = hass.data[DOMAIN][entry.entry_id]
    coordinator = (
        entry_obj["coordinator"]
        if isinstance(entry_obj, dict) and "coordinator" in entry_obj
        else entry_obj
    )

    raw_qr = _extract_qr_token(entry)
    box_data = _resolve_box(coordinator.data, raw_qr)
    if not box_data:
        _LOGGER.error(
            "SwitcheOn: No box data found in coordinator. entry.data keys=%s",
            list(entry.data.keys()),
        )
        return

    channels_count = int(box_data.get("channels", 0))
    switches = [
        SwitcheOnSwitch(coordinator, entry, i, raw_qr)
        for i in range(channels_count)
    ]
    async_add_entities(switches)


class SwitcheOnSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a SwitcheOn Relay."""

    # Set False so Home Assistant strictly honors our explicit self.entity_id
    _attr_has_entity_name = False

    def __init__(self, coordinator, entry, channel_index, raw_qr):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.channel_index = channel_index
        self.entry = entry
        self.raw_qr = raw_qr
        self.device_name = _extract_device_name(entry)

        box_data = _resolve_box(self.coordinator.data, self.raw_qr) or {}
        channel_names = box_data.get("channelNames") or []
        raw_channel_name = (
            channel_names[channel_index]
            if channel_index < len(channel_names)
            else f"SW{channel_index}"
        )
        self.channel_name = raw_channel_name or f"SW{channel_index}"

        unique_prefix = self.raw_qr or box_data.get("boxIdText") or entry.entry_id
        device_slug = slugify(self.device_name)

        # UI Friendly Name: e.g. "N1538Z Laptop computer"
        self._attr_name = f"{self.device_name} {self.channel_name}"
        self._attr_unique_id = f"{unique_prefix}_sw{channel_index}"

        # Exact Entity ID: switch.switcheon_<device_name>_sw0
        self.entity_id = f"switch.switcheon_{device_slug}_sw{channel_index}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_prefix)},
            "name": f"SwitcheOn {self.device_name}",
            "manufacturer": "SwitcheOn",
            "model": "SwitcheOn Box",
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
        box_data = _resolve_box(self.coordinator.data, self.raw_qr)
        if not box_data:
            return None
        status_mask = self._get_effective_mask(box_data)
        return bool(status_mask & (1 << self.channel_index))

    async def async_turn_on(self, **kwargs):
        """Turn the switch on via SwitcheOn API."""
        box_data = _resolve_box(self.coordinator.data, self.raw_qr)
        if not box_data:
            raise HomeAssistantError("SwitcheOn box data is unavailable.")
        current_mask = self._get_effective_mask(box_data)
        new_status = current_mask | (1 << self.channel_index)
        await self._send_status_update(box_data, new_status)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off via SwitcheOn API."""
        box_data = _resolve_box(self.coordinator.data, self.raw_qr)
        if not box_data:
            raise HomeAssistantError("SwitcheOn box data is unavailable.")
        current_mask = self._get_effective_mask(box_data)
        new_status = current_mask & ~(1 << self.channel_index)
        await self._send_status_update(box_data, new_status)

    async def _send_status_update(self, box_data, requested_status):
        """Send the requestedStatus bitmask to https://www.switcheon.com/api/req."""
        session = async_get_clientsession(self.hass)
        user_id_bin, user_secret = _extract_credentials(self.entry)

        if not user_id_bin or not user_secret:
            _LOGGER.error(
                "SwitcheOn missing credentials! Available entry.data keys: %s",
                list(self.entry.data.keys()),
            )
            raise HomeAssistantError(
                f"Missing SwitcheOn credentials in entry.data keys: {list(self.entry.data.keys())}"
            )

        payload = {
            "userIdBin": user_id_bin,
            "userSecret": user_secret,
            "boxIdBin": box_data["boxIdBin"],
            "requestedStatus": requested_status,
        }

        async with session.put(CONTROL_URL, json=payload) as response:
            if response.status in (200, 204):
                box_data["pendingStatus"] = requested_status
                self.async_write_ha_state()
                await self.coordinator.async_request_refresh()
            else:
                response_text = await response.text()
                _LOGGER.error(
                    "SwitcheOn PUT failed (%s): %s | entry keys=%s",
                    response.status,
                    response_text,
                    list(self.entry.data.keys()),
                )
                raise HomeAssistantError(
                    f"SwitcheOn API error {response.status}: {response_text}"
                )
