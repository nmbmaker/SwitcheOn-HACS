import re
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTemperature, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from .const import DOMAIN


def _extract_qr_token(entry):
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
    for key in ("device_name", "name", "box_name", "device", "custom_name", "title"):
        val = entry.data.get(key)
        if isinstance(val, str) and val.strip() and val.strip().lower() != "my switcheon":
            return val.strip()
    if entry.title and entry.title.strip().lower() not in ("switcheon", "my switcheon"):
        return entry.title.strip()
    return entry.title.strip() if entry.title else "box"


def _resolve_box(coordinator_data, qr_token):
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
    """Set up SwitcheOn sensors from a config entry."""
    entry_obj = hass.data[DOMAIN][entry.entry_id]
    coordinator = (
        entry_obj["coordinator"]
        if isinstance(entry_obj, dict) and "coordinator" in entry_obj
        else entry_obj
    )

    raw_qr = _extract_qr_token(entry)

    async_add_entities([
        SwitcheOnTempSensor(coordinator, entry, raw_qr),
        SwitcheOnSignalSensor(coordinator, entry, raw_qr),
    ])


class SwitcheOnBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor that resolves the right SwitcheOn box safely."""

    _attr_has_entity_name = False

    def __init__(self, coordinator, entry, raw_qr):
        super().__init__(coordinator)
        self.raw_qr = raw_qr
        box_data = _resolve_box(self.coordinator.data, self.raw_qr) or {}
        self.unique_prefix = self.raw_qr or box_data.get("boxIdText") or entry.entry_id
        self.device_name = _extract_device_name(entry)
        self.device_slug = slugify(self.device_name)

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.unique_prefix)},
            "name": f"SwitcheOn {self.device_name}",
            "manufacturer": "SwitcheOn",
            "model": "SwitcheOn Box",
        }


class SwitcheOnTempSensor(SwitcheOnBaseSensor):
    """Representation of the SwitcheOn Temperature Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, coordinator, entry, raw_qr):
        super().__init__(coordinator, entry, raw_qr)
        self._attr_name = f"{self.device_name} Temperature"
        self._attr_unique_id = f"{self.unique_prefix}_temp"
        self.entity_id = f"sensor.switcheon_{self.device_slug}_temperature"

    @property
    def native_value(self):
        box = _resolve_box(self.coordinator.data, self.raw_qr)
        return box.get("temp") if box else None

    @property
    def native_unit_of_measurement(self):
        box = _resolve_box(self.coordinator.data, self.raw_qr)
        is_celsius = box.get("celcius", False) if box else False
        return UnitOfTemperature.CELSIUS if is_celsius else UnitOfTemperature.FAHRENHEIT


class SwitcheOnSignalSensor(SwitcheOnBaseSensor):
    """Representation of the SwitcheOn Signal Sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH

    def __init__(self, coordinator, entry, raw_qr):
        super().__init__(coordinator, entry, raw_qr)
        self._attr_name = f"{self.device_name} Signal Strength"
        self._attr_unique_id = f"{self.unique_prefix}_signal"
        self.entity_id = f"sensor.switcheon_{self.device_slug}_signal_strength"

    @property
    def native_value(self):
        box = _resolve_box(self.coordinator.data, self.raw_qr)
        return box.get("signalStrength") if box else None

    @property
    def native_unit_of_measurement(self):
        return SIGNAL_STRENGTH_DECIBELS_MILLIWATT
