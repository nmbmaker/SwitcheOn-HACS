from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "user_id_bin",
    "user_secret",
    "box_id_bin",
    "qr_url",
    "userIdBin",
    "userSecret",
    "boxIdBin",
    "boxIdText",
    "imei",
    "iccid",
    "owner",
    "users",
    "url",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a SwitcheOn config entry."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    box_data = coordinator.data if coordinator else None

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": dict(entry.options),
        "poll_interval_seconds": (
            coordinator.update_interval.total_seconds()
            if coordinator and coordinator.update_interval
            else None
        ),
        "box_data": async_redact_data(box_data, TO_REDACT)
        if isinstance(box_data, dict)
        else box_data,
    }
