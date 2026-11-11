from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from .const import DOMAIN
from .sensor import build_device_info


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn connectivity binary sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SwitcheOnOnlineSensor(coordinator, entry)])


class SwitcheOnOnlineSensor(CoordinatorEntity, BinarySensorEntity):
    """Diagnostic connectivity sensor reading box 'online' flag."""

    _attr_has_entity_name = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.box_id_bin = entry.data["box_id_bin"]
        unique_prefix = entry.unique_id or self.box_id_bin
        device_name = (entry.data.get("box_name") or entry.title or "SwitcheOn").strip()
        device_slug = slugify(device_name)

        box_data = coordinator.data if isinstance(coordinator.data, dict) else {}
        self._attr_device_info = build_device_info(entry, box_data)

        self._attr_name = f"{device_name} Cellular Status"
        self._attr_unique_id = f"{unique_prefix}_online"
        self.entity_id = f"binary_sensor.switcheon_{device_slug}_cellular_status"

    @property
    def is_on(self) -> bool | None:
        box = self.coordinator.data
        if not isinstance(box, dict) or "online" not in box:
            return None
        return bool(box.get("online") == 1)
