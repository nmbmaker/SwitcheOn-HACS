from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .sensor import build_device_info, get_device_name


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn connectivity and command-pending binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SwitcheOnOnlineSensor(coordinator, entry),
        SwitcheOnCommandPendingSensor(coordinator, entry),
    ])


class SwitcheOnOnlineSensor(CoordinatorEntity, BinarySensorEntity):
    """Diagnostic connectivity sensor reading box 'online' flag and hardware metadata."""

    _attr_has_entity_name = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.box_id_bin = entry.data["box_id_bin"]
        unique_prefix = entry.unique_id or self.box_id_bin
        device_name = get_device_name(entry)
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

    @property
    def extra_state_attributes(self):
        """Expose modem IMEI, SIM ICCID, and active SwitcheOn app timer count."""
        box = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        automations = box.get("automations") or []
        users = box.get("users") or []
        return {
            "imei": str(box["imei"]) if box.get("imei") is not None else None,
            "iccid": str(box["iccid"]) if box.get("iccid") is not None else None,
            "device_type": box.get("deviceType"),
            "active_app_schedules_count": len(automations),
            "linked_users_count": len(users),
        }


class SwitcheOnCommandPendingSensor(CoordinatorEntity, BinarySensorEntity):
    """Diagnostic binary sensor indicating an LTE-M relay/HVAC command is in flight."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:progress-clock"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.box_id_bin = entry.data["box_id_bin"]
        unique_prefix = entry.unique_id or self.box_id_bin
        device_name = get_device_name(entry)
        device_slug = slugify(device_name)

        box_data = coordinator.data if isinstance(coordinator.data, dict) else {}
        self._attr_device_info = build_device_info(entry, box_data)

        self._attr_name = f"{device_name} Command Pending"
        self._attr_unique_id = f"{unique_prefix}_command_pending"
        self.entity_id = f"binary_sensor.switcheon_{device_slug}_command_pending"

    @property
    def is_on(self) -> bool | None:
        box = self.coordinator.data
        if not isinstance(box, dict):
            return None
        return any(
            box.get(key) is not None
            for key in (
                "pendingStatus",
                "pendingHvacMode",
                "pendingHvacFanSpeed",
                "pendingHvacCoolTarget",
                "pendingHvacHeatTarget",
            )
        )

    @property
    def extra_state_attributes(self):
        """Show raw pending vs confirmed bitmasks."""
        box = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        return {
            "current_status_mask": box.get("currentStatus"),
            "pending_status_mask": box.get("pendingStatus"),
        }
