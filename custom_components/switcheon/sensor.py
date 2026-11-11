from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        SwitcheOnTempSensor(coordinator, entry),
        SwitcheOnSignalSensor(coordinator, entry),
    ])


class SwitcheOnBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor reading the unwrapped SwitcheOn box dictionary."""

    _attr_has_entity_name = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.box_id_bin = entry.data["box_id_bin"]
        self.unique_prefix = entry.unique_id or self.box_id_bin
        self.device_name = (
            entry.data.get("box_name") or entry.title or "SwitcheOn"
        ).strip()
        self.device_slug = slugify(self.device_name)

        box_data = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        channels_count = int(
            box_data.get("channels")
            or len(box_data.get("channelNames") or [])
            or 2
        )

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.unique_prefix)},
            "name": f"SwitcheOn {self.device_name}",
            "manufacturer": "SwitcheOn",
            "model": f"SwitcheOn {channels_count}-Channel Box",
        }


class SwitcheOnTempSensor(SwitcheOnBaseSensor):
    """Representation of the SwitcheOn Temperature Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE

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
    """Representation of the SwitcheOn Signal Sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH

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
