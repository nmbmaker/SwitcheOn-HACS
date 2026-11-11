import logging

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed
from homeassistant.util import slugify

from .const import API_URL_ACTION, DOMAIN
from .sensor import build_device_info, get_device_name

_LOGGER = logging.getLogger(__name__)

# Standard SwitcheOn HVAC integer mappings (0=Off, 1=Heat, 2=Cool, 3=Auto)
API_TO_HVAC_MODE = {
    0: HVACMode.OFF,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
    3: HVACMode.HEAT_COOL,
}
HVAC_MODE_TO_API = {v: k for k, v in API_TO_HVAC_MODE.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SwitcheOn climate entity only if hardware exposes HVAC fields."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    box_data = coordinator.data

    if not isinstance(box_data, dict) or box_data.get("hvacMode") is None:
        return

    async_add_entities([SwitcheOnThermostat(coordinator, entry)])


class SwitcheOnThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of a SwitcheOn Cellular Thermostat."""

    _attr_has_entity_name = False
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
    ]
    _attr_fan_modes = [FAN_AUTO, FAN_ON]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = 1.0

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self.entry = entry
        self.box_id_bin = entry.data["box_id_bin"]
        unique_prefix = entry.unique_id or self.box_id_bin
        device_name = get_device_name(entry)
        device_slug = slugify(device_name)

        box_data = coordinator.data if isinstance(coordinator.data, dict) else {}
        self._attr_device_info = build_device_info(entry, box_data)

        self._attr_name = f"{device_name} Thermostat"
        self._attr_unique_id = f"{unique_prefix}_thermostat"
        self.entity_id = f"climate.switcheon_{device_slug}_thermostat"

    @property
    def temperature_unit(self) -> str:
        box = self.coordinator.data
        is_celsius = box.get("celcius", False) if isinstance(box, dict) else False
        return UnitOfTemperature.CELSIUS if is_celsius else UnitOfTemperature.FAHRENHEIT

    @property
    def current_temperature(self) -> float | None:
        box = self.coordinator.data
        return box.get("temp") if isinstance(box, dict) else None

    def _effective(self, box: dict, pending_key: str, current_key: str):
        val = box.get(pending_key)
        return val if val is not None else box.get(current_key)

    @property
    def hvac_mode(self) -> HVACMode | None:
        box = self.coordinator.data
        if not isinstance(box, dict):
            return None
        raw_mode = self._effective(box, "pendingHvacMode", "hvacMode")
        if raw_mode is None:
            return None
        return API_TO_HVAC_MODE.get(int(raw_mode), HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction | None:
        box = self.coordinator.data
        if not isinstance(box, dict):
            return None
        status = box.get("hvacStatus")
        if status == 1:
            return HVACAction.HEATING
        if status == 2:
            return HVACAction.COOLING
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    @property
    def target_temperature(self) -> float | None:
        box = self.coordinator.data
        if not isinstance(box, dict):
            return None
        mode = self.hvac_mode
        if mode == HVACMode.HEAT:
            return self._effective(box, "pendingHvacHeatTarget", "hvacHeatTarget")
        if mode == HVACMode.COOL:
            return self._effective(box, "pendingHvacCoolTarget", "hvacCoolTarget")
        return None

    @property
    def target_temperature_low(self) -> float | None:
        box = self.coordinator.data
        if not isinstance(box, dict) or self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        return self._effective(box, "pendingHvacHeatTarget", "hvacHeatTarget")

    @property
    def target_temperature_high(self) -> float | None:
        box = self.coordinator.data
        if not isinstance(box, dict) or self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        return self._effective(box, "pendingHvacCoolTarget", "hvacCoolTarget")

    @property
    def fan_mode(self) -> str | None:
        box = self.coordinator.data
        if not isinstance(box, dict):
            return None
        fan_val = self._effective(box, "pendingHvacFanSpeed", "hvacFanSpeed")
        return FAN_ON if fan_val == 1 else FAN_AUTO

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in HVAC_MODE_TO_API:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        await self._push_hvac_update(mode=HVAC_MODE_TO_API[hvac_mode])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self._push_hvac_update(fan=1 if fan_mode == FAN_ON else 0)

    async def async_set_temperature(self, **kwargs) -> None:
        heat = kwargs.get("target_temp_low")
        cool = kwargs.get("target_temp_high")
        single = kwargs.get(ATTR_TEMPERATURE)

        if single is not None:
            if self.hvac_mode == HVACMode.COOL:
                cool = single
            else:
                heat = single

        await self._push_hvac_update(heat_target=heat, cool_target=cool)

    async def _push_hvac_update(
        self,
        mode: int | None = None,
        fan: int | None = None,
        heat_target: float | None = None,
        cool_target: float | None = None,
    ) -> None:
        """Pull fresh thermostat state, apply requested changes, and PUT /api/req."""
        async with self.coordinator.action_lock:
            try:
                fresh_box = await self.coordinator.async_fetch_box()
            except UpdateFailed as err:
                raise HomeAssistantError(f"Failed fetching thermostat state: {err}") from err

            req_mode = (
                mode
                if mode is not None
                else self._effective(fresh_box, "pendingHvacMode", "hvacMode")
            )
            req_fan = (
                fan
                if fan is not None
                else self._effective(fresh_box, "pendingHvacFanSpeed", "hvacFanSpeed")
            )
            req_heat = (
                round(heat_target)
                if heat_target is not None
                else self._effective(fresh_box, "pendingHvacHeatTarget", "hvacHeatTarget")
            )
            req_cool = (
                round(cool_target)
                if cool_target is not None
                else self._effective(fresh_box, "pendingHvacCoolTarget", "hvacCoolTarget")
            )

            payload = {
                "userIdBin": self.entry.data["user_id_bin"].strip(),
                "userSecret": self.entry.data["user_secret"].strip(),
                "boxIdBin": fresh_box.get("boxIdBin", self.box_id_bin),
                "requestedHvacMode": req_mode,
                "requestedHvacFanSpeed": req_fan,
                "requestedHvacHeatTarget": req_heat,
                "requestedHvacCoolTarget": req_cool,
            }

            session = async_get_clientsession(self.hass)
            async with session.put(API_URL_ACTION, json=payload) as resp:
                if 200 <= resp.status < 300:
                    fresh_box["pendingHvacMode"] = req_mode
                    fresh_box["pendingHvacFanSpeed"] = req_fan
                    fresh_box["pendingHvacHeatTarget"] = req_heat
                    fresh_box["pendingHvacCoolTarget"] = req_cool
                    self.coordinator.async_set_updated_data(fresh_box)
                else:
                    text = await resp.text()
                    _LOGGER.error("SwitcheOn HVAC PUT failed (%s): %s", resp.status, text)
                    raise HomeAssistantError(f"SwitcheOn HVAC error {resp.status}: {text}")
