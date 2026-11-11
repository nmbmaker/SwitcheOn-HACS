import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .const import API_URL_LINK, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import SwitcheOnCoordinator
from .sensor import get_device_name

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "sensor", "binary_sensor", "button", "image", "climate"]


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

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply updated options (such as polling interval) immediately."""
    coordinator: SwitcheOnCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        coordinator.update_interval = timedelta(seconds=interval)
        await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unlink Home Assistant user from this SwitcheOn box when deleted in HA."""
    user_id_bin = (entry.data.get("user_id_bin") or "").strip()
    user_secret = (entry.data.get("user_secret") or "").strip()
    box_id_bin = (entry.data.get("box_id_bin") or "").strip()

    if not (user_id_bin and user_secret and box_id_bin):
        return

    session = async_get_clientsession(hass)
    payload = {
        "userIdBin": user_id_bin,
        "userSecret": user_secret,
        "boxIdBin": box_id_bin,
    }
    params = {
        "UserIdBin": user_id_bin,
        "UserSecret": user_secret,
        "BoxIdBin": box_id_bin,
    }

    try:
        async with session.delete(API_URL_LINK, json=payload, params=params) as resp:
            if 200 <= resp.status < 300:
                _LOGGER.info("Unlinked SwitcheOn box %s from cloud user list", entry.title)
            else:
                _LOGGER.debug(
                    "SwitcheOn DELETE /api/BoxUser returned %s on removal", resp.status
                )
    except Exception as err:
        _LOGGER.debug("Could not unlink SwitcheOn box during entry removal: %s", err)
