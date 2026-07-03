from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SwitcheOnTempSensor(coordinator, entry),
        SwitcheOnSignalSensor(coordinator, entry)
    ]
    async_add_entities(entities)

class SwitcheOnTempSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "Temperature"
        self._attr_unique_id = f"{entry.data['box_id_bin']}_temperature"
        
        is_celsius = coordinator.data.get("celcius", False)
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS if is_celsius else UnitOfTemperature.FAHRENHEIT
        
        # Group under the Device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data["box_id_bin"])},
            "name": entry.data.get("box_name", "SwitcheOn Box"),
            "manufacturer": "SwitcheOn",
        }

    @property
    def native_value(self):
        if self.coordinator.data:
            temp = self.coordinator.data.get("temp")
            if temp is not None:
                return round(temp, 1)
        return None

class SwitcheOnSignalSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "Signal Strength"
        self._attr_unique_id = f"{entry.data['box_id_bin']}_signal"
        
        # Group under the Device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data["box_id_bin"])},
            "name": entry.data.get("box_name", "SwitcheOn Box"),
            "manufacturer": "SwitcheOn",
        }

    @property
    def native_value(self):
        if self.coordinator.data:
            return self.coordinator.data.get("signalStrength")
        return None
