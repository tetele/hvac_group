"""Climate platform for HVAC group integration."""

import asyncio
import math

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
)
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.climate import (
    SERVICE_SET_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.group import GroupEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import EventType

from .const import (
    CONF_CURRENT_TEMPERATURE_ENTITY_ID,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_PRECISION,
    CONF_TARGET_TEMP_STEP,
    CONF_TOGGLE_COOLERS,
    CONF_TOGGLE_HEATERS,
    LOGGER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize HVAC group config entry."""

    name = config_entry.options.get(CONF_NAME)
    unique_id = config_entry.entry_id

    sensor_entity_id = config_entry.options.get(CONF_CURRENT_TEMPERATURE_ENTITY_ID)
    min_temp = float(config_entry.options.get(CONF_MIN_TEMP))
    max_temp = float(config_entry.options.get(CONF_MAX_TEMP))

    temperature_unit = hass.config.units.temperature_unit

    precision = config_entry.options.get(CONF_PRECISION, PRECISION_TENTHS)
    target_temperature_step = config_entry.options.get(
        CONF_TARGET_TEMP_STEP, PRECISION_HALVES
    )

    toggle_coolers = config_entry.options.get(CONF_TOGGLE_COOLERS, False)
    toggle_heaters = config_entry.options.get(CONF_TOGGLE_HEATERS, False)

    hvac_modes_entity_ids: dict[str, list[str]] = {}
    registry = er.async_get(hass)

    for hvac_mode in [HVACMode.HEAT, HVACMode.COOL]:
        target_entities = []
        if (
            hvac_mode in config_entry.options
            and len(config_entry.options[hvac_mode]) > 0
        ):
            for entity_id in config_entry.options[hvac_mode]:
                target_entities.append(er.async_validate_entity_id(registry, entity_id))
        if len(target_entities) > 0:
            hvac_modes_entity_ids.update({hvac_mode: target_entities})

    async_add_entities(
        [
            HvacGroupClimateEntity(
                unique_id,
                name,
                sensor_entity_id,
                min_temp,
                max_temp,
                temperature_unit,
                precision=precision,
                target_temperature_step=target_temperature_step,
                target_temp_high=max_temp,
                target_temp_low=min_temp,
                hvac_modes_entity_ids=hvac_modes_entity_ids,
                toggle_coolers=toggle_coolers,
                toggle_heaters=toggle_heaters,
            )
        ]
    )


class HvacGroupClimateEntity(GroupEntity, ClimateEntity, RestoreEntity):
    """HVAC Group Climate entity."""

    _mode_member_ids: dict[str, list[str]] = {}

    def __init__(
        self,
        unique_id: str,
        name: str,
        temperature_sensor_entity_id: str,
        min_temp: float,
        max_temp: float,
        temperature_unit: str,
        precision: float | None = None,
        target_temp_high: float | None = None,
        target_temp_low: float | None = None,
        target_temperature_step: float | None = None,
        hvac_modes_entity_ids: dict[str, list[str]] = {},
        toggle_coolers: bool = False,
        toggle_heaters: bool = False,
    ) -> None:
        """Initialize HVAC Group Climate."""
        self._attr_name = name
        self._attr_unique_id = unique_id

        self._entity_ids: list[str] = []  # GroupEntity

        self.temperature_sensor_entity_id = temperature_sensor_entity_id
        self._current_temperature: float = None  # TODO get sensor value
        self._temp_precision = precision
        self._temp_target_temperature_step = target_temperature_step
        self._attr_temperature_unit = temperature_unit

        self._hvac_mode = HVACMode.OFF
        self._attr_hvac_modes = [HVACMode.OFF]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

        if (
            HVACMode.HEAT in hvac_modes_entity_ids
            or HVACMode.COOL in hvac_modes_entity_ids
        ):
            self._attr_hvac_modes.append(HVACMode.HEAT_COOL)
            self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )

        self._is_cooling_active = False
        self._is_heating_active = False

        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temp_low = target_temp_low or min_temp
        self._target_temp_high = target_temp_high or max_temp

        self._toggle_heaters_on_threshold = toggle_heaters
        self._toggle_coolers_on_threshold = toggle_coolers

        self._temp_lock = asyncio.Lock()
        self._active = False

    @property
    def current_temperature(self) -> float:
        """Return the sensor temperature."""
        return self._current_temperature

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported."""

        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._is_heating_active:
            return HVACAction.HEATING
        elif self._is_cooling_active:
            return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation."""
        return self._hvac_mode

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._min_temp is not None:
            return self._min_temp

        # get default temp from super class
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._max_temp is not None:
            return self._max_temp

        # Get default temp from super class
        return super().max_temp

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if self._temp_precision is not None:
            return self._temp_precision
        return super().precision

    @property
    def target_temperature_low(self) -> float:
        """Return the low temperature we try to reach."""
        if self._target_temp_low is not None:
            return self._target_temp_low
        return self.min_temp

    @property
    def target_temperature_high(self) -> float:
        """Return the high temperature we try to reach."""
        if self._target_temp_high is not None:
            return self._target_temp_high
        return self.max_temp

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        if self._temp_target_temperature_step is not None:
            return self._temp_target_temperature_step
        # if a target_temperature_step is not defined, fallback to equal the precision
        return self.precision

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.temperature_sensor_entity_id],
                self._async_sensor_changed,
            )
        )

        @callback
        def _async_startup(*_):
            """Init on startup."""
            sensor_state = self.hass.states.get(self.temperature_sensor_entity_id)
            if sensor_state and sensor_state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                self._async_update_temp(sensor_state)
                self.async_write_ha_state()

        if self.hass.state == CoreState.running:
            _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        # Check If we have an old state
        if (old_state := await self.async_get_last_state()) is not None:
            # If we have no initial temperature, restore
            if self._target_temp_low is None or self._target_temp_high is None:
                # If we have a previously saved temperature
                if old_state.attributes.get(ATTR_TARGET_TEMP_LOW) is None:
                    self._target_temp_low = self.min_temp
                    LOGGER.warning(
                        "Undefined low target temperature, falling back to %s",
                        self._target_temp_low,
                    )
                else:
                    self._target_temp_low = float(
                        old_state.attributes[ATTR_TARGET_TEMP_LOW]
                    )
                if old_state.attributes.get(ATTR_TARGET_TEMP_HIGH) is None:
                    self._target_temp_high = self.max_temp
                    LOGGER.warning(
                        "Undefined high target temperature, falling back to %s",
                        self._target_temp_high,
                    )
                else:
                    self._target_temp_high = float(
                        old_state.attributes[ATTR_TARGET_TEMP_HIGH]
                    )
            if not self._hvac_mode and old_state.state:
                self._hvac_mode = old_state.state

        else:
            # No previous state, try and restore defaults
            if self._target_temp_low is None:
                self._target_temp_low = self.min_temp
            if self._target_temp_high is None:
                self._target_temp_high = self.max_temp
            LOGGER.warning(
                "No previously saved temperature, setting to %s, %s",
                self._target_temp_low,
                self._target_temp_high,
            )

        # Set default state to off
        if not self._hvac_mode:
            self._hvac_mode = HVACMode.OFF

    async def _async_sensor_changed(
        self, event: EventType[EventStateChangedData]
    ) -> None:
        """Handle temperature changes."""
        new_state = event.data["new_state"]
        if new_state is None or new_state.attributes[ATTR_CURRENT_TEMPERATURE] in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            return

        self._async_update_temp(new_state)
        await self._async_control_hvac()
        self.async_write_ha_state()

    @callback
    def _async_update_temp(self, state: State) -> None:
        """Update thermostat with latest state from sensor."""
        try:
            cur_temp = float(state.attributes[ATTR_CURRENT_TEMPERATURE])
            if not math.isfinite(cur_temp):
                raise ValueError(
                    f"Sensor has illegal state {state.attributes[ATTR_CURRENT_TEMPERATURE]}"
                )
            self._current_temperature = cur_temp
        except ValueError as ex:
            LOGGER.error("Unable to update from sensor: %s", ex)

    async def _async_control_hvac(self, force=False):
        """Check if we need to forward HVAC commands."""
        async with self._temp_lock:
            if not self._active and None not in (
                self._current_temperature,
                self._target_temp_low,
                self._target_temp_high,
            ):
                self._active = True
                LOGGER.info(
                    (
                        "Obtained current and target temperatures. "
                        "Climate group active. %s, %s, %s"
                    ),
                    self._current_temperature,
                    self._target_temp_low,
                    self._target_temp_high,
                )

            if not self._active or self._hvac_mode == HVACMode.OFF:
                return

            if (
                not self._toggle_coolers_on_threshold
                and not self._toggle_heaters_on_threshold
                and not force
            ):
                return

            too_cold = self._target_temp_low >= self._current_temperature
            too_hot = self._current_temperature >= self._target_temp_high
            if too_hot:
                if (
                    not self._is_cooling_active and self._toggle_coolers_on_threshold
                ) or force:
                    LOGGER.info(
                        "Turning on cooling %s",
                        ",".join(self._mode_member_ids[HVACMode.COOL]),
                    )
                    await self._async_coolers_turn_on()
                    self._is_cooling_active = True
            elif (
                self._is_cooling_active and self._toggle_coolers_on_threshold
            ) or force:
                LOGGER.info(
                    "Turning off cooling %s",
                    ",".join(self._mode_member_ids[HVACMode.COOL]),
                )
                self._is_cooling_active = False
                await self._async_coolers_turn_off()

            if too_cold:
                if (
                    not self._is_heating_active and self._toggle_heaters_on_threshold
                ) or force:
                    LOGGER.info(
                        "Turning on heating %s",
                        ",".join(self._mode_member_ids[HVACMode.HEAT]),
                    )
                    await self._async_heaters_turn_on()
                    self._is_heating_active = True
            elif (
                self._is_heating_active and self._toggle_heaters_on_threshold
            ) or force:
                LOGGER.info(
                    "Turning off heating %s",
                    ",".join(self._mode_member_ids[HVACMode.HEAT]),
                )
                self._is_heating_active = False
                await self._async_heaters_turn_off()

    async def _async_heaters_turn_on(self):
        """Turn heater devices on."""
        for entity_id in self._mode_member_ids[HVACMode.HEAT]:
            await self._async_turn_device(HVACMode.HEAT, entity_id)

    async def _async_heaters_turn_off(self):
        """Turn heater devices off."""
        for entity_id in self._mode_member_ids[HVACMode.HEAT]:
            await self._async_turn_device(HVACMode.OFF, entity_id)

    async def _async_coolers_turn_on(self):
        """Turn heater devices on."""
        for entity_id in self._mode_member_ids[HVACMode.COOL]:
            await self._async_turn_device(HVACMode.COOL, entity_id)

    async def _async_coolers_turn_off(self):
        """Turn heater devices off."""
        for entity_id in self._mode_member_ids[HVACMode.COOL]:
            await self._async_turn_device(HVACMode.OFF, entity_id)

    async def _async_turn_device(self, mode: HVACMode, entity_id: str) -> None:
        data = {ATTR_HVAC_MODE: mode}
        target = {ATTR_ENTITY_ID: entity_id}
        await self.hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            data,
            target=target,
            context=self._context,
        )

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the climate group state."""
