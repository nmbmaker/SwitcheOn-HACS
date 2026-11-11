from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .sensor import build_device_info, get_device_name


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the SwitcheOn manual refresh button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SwitcheOnRefreshButton(coordinator, entry)])


class SwitcheOnRefreshButton(CoordinatorEntity, ButtonEntity):
    """Button to trigger an immediate SwitcheOn cloud status poll."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        box_id_bin = entry.data["box_id_bin"]
        unique_prefix = entry.unique_id or box_id_bin
        device_name = get_device_name(entry)
        device_slug = slugify(device_name)

        box_data = coordinator.data if isinstance(coordinator.data, dict) else {}
        self._attr_device_info = build_device_info(entry, box_data)

        self._attr_name = f"{device_name} Refresh"
        self._attr_unique_id = f"{unique_prefix}_refresh"
        self.entity_id = f"button.switcheon_{device_slug}_refresh"

    async def async_press(self) -> None:
        """Force an immediate poll from GET /api/User."""
        await self.coordinator.async_refresh()
