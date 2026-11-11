from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from .const import DOMAIN
from .coordinator import SwitcheOnCoordinator
from .sensor import get_device_name

PLATFORMS = ["switch", "sensor", "binary_sensor", "image"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SwitcheOn from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Migrate any cached 'switcheon_my_switcheon_*' entity IDs to the real device slug
    device_slug = slugify(get_device_name(entry))
    if device_slug and device_slug != "my_switcheon":
        ent_reg = er.async_get(hass)
        for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
            if "switcheon_my_switcheon_" in reg_entry.entity_id:
                new_id = reg_entry.entity_id.replace(
                    "switcheon_my_switcheon_", f"switcheon_{device_slug}_", 1
                )
                if ent_reg.async_get(new_id) is None:
                    ent_reg.async_update_entity(
                        reg_entry.entity_id, new_entity_id=new_id
                    )

    coordinator = SwitcheOnCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
