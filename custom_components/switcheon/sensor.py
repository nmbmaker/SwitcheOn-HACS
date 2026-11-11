from datetime import date, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify
from .const import DOMAIN


def build_device_info(entry, box_data: dict) -> DeviceInfo:
    """Build consistent DeviceInfo across all SwitcheOn platforms."""
    box_id_bin = entry.data["box_id_bin"]
    unique_prefix = entry.unique_id or box_id_bin
    device_name = (entry.data.get("box_name") or entry.title or "SwitcheOn").strip()
    channels_count = int(
        box_data.get("channels") or len(box_data.get("channelNames") or []) or 2
    )
    sw_ver = box_data.get("swVersion")
    modem_fw = box_data.get("firmware")

    return DeviceInfo(
        identifiers={(DOMAIN, unique_prefix)},
        name=f"SwitcheOn {device_name}",
        manufacturer="SwitcheOn",
        model=f"SwitcheOn {channels_count}-Channel Box",
        sw_version=str(sw_ver) if sw_ver is not None else None,
        hw_version=str(modem_fw) if modem_fw else None,
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        SwitcheOnTempSensor(coordinator, entry),
        SwitcheOnSignalSensor(coordinator, entry),
        SwitcheOnRenewalSensor(coordinator, entry),
        SwitcheOnLastUpdatedSensor(coordinator, entry),
    ])


class SwitcheOnBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor reading the unwrapped SwitcheOn box dictionary."""

    _attr_has_entity_name = False

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.entry = entry
        self.box_id_bin = entry.data["box_id_bin"]
        self.unique_prefix = entry.unique_id or self.box_id_bin
        self.device_name = (
            entry.data.get("box_name") or entry.title or "SwitcheOn"
        ).strip()
        self.device_slug = slugify(self.device_name)

        box_data = coordinator.data if isinstance(coordinator.data, dict) else {}
        self._attr_device_info = build_device_info(entry, box_data)


class SwitcheOnTempSensor(SwitcheOnBaseSensor):
    """Representation of the SwitcheOn Temperature Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{self.device_name} Temperature"
        self._attr_unique_id = f"{self.unique_prefix}_temp"
        self.entity_id = f"sensor.switcheon_{self.device_slug}_temperature"

    @property
    def native_value(self):
        box = self.coordinator.data
        return box.get("temp") if isinstance(box, dict) else None

    @property
    def native_unit_of_measurement(self):
        box = self.coordinator.data
        is_celsius = box.get("celcius", False) if isinstance(box, dict) else False
        return UnitOfTemperature.CELSIUS if is_celsius else UnitOfTemperature.FAHRENHEIT


class SwitcheOnSignalSensor(SwitcheOnBaseSensor):
    """Representation of the SwitcheOn Cellular Signal Sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{self.device_name} Signal Strength"
        self._attr_unique_id = f"{self.unique_prefix}_signal"
        self.entity_id = f"sensor.switcheon_{self.device_slug}_signal_strength"

    @property
    def native_value(self):
        box = self.coordinator.data
        return box.get("signalStrength") if isinstance(box, dict) else None

    @property
    def native_unit_of_measurement(self):
        return SIGNAL_STRENGTH_DECIBELS_MILLIWATT


class SwitcheOnRenewalSensor(SwitcheOnBaseSensor):
    """Diagnostic date sensor reading 'paidUntil' and 'latestInfo'."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{self.device_name} Renewal Date"
        self._attr_unique_id = f"{self.unique_prefix}_renewal_date"
        self.entity_id = f"sensor.switcheon_{self.device_slug}_renewal_date"

    @property
    def native_value(self) -> date | None:
        box = self.coordinator.data
        if not isinstance(box, dict):
            return None
        paid_until = box.get("paidUntil")
        if not paid_until:
            return None
        parsed_dt = dt_util.parse_datetime(str(paid_until))
        if parsed_dt:
            return parsed_dt.date()
        return dt_util.parse_date(str(paid_until)[:10])

    @property
    def extra_state_attributes(self):
        """Expose renewal status message, auto-renew flag, and box location."""
        box = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        latest_info = box.get("latestInfo") or {}
        info_text = latest_info.get("info") if isinstance(latest_info, dict) else None
        owner = box.get("owner") or {}
        owner_name = f"{owner.get('firstname', '')} {owner.get('lastname', '')}".strip()

        return {
            "subscription_info": info_text,
            "auto_renew": bool(info_text and "renew automatically" in info_text.lower()),
            "box_location": box.get("location"),
            "owner": owner_name or None,
        }


class SwitcheOnLastUpdatedSensor(SwitcheOnBaseSensor):
    """Diagnostic timestamp sensor showing last cellular check-in ('updated')."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = f"{self.device_name} Last Check-In"
        self._attr_unique_id = f"{self.unique_prefix}_last_updated"
        self.entity_id = f"sensor.switcheon_{self.device_slug}_last_checkin"

    @property
    def native_value(self) -> datetime | None:
        box = self.coordinator.data
        if not isinstance(box, dict) or not box.get("updated"):
            return None
        return dt_util.parse_datetime(str(box["updated"]))
