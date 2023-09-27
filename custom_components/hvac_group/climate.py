"""Climate platform for HVAC group integration."""

import asyncio
from enum import StrEnum
from typing import Any

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_MIN_TEMP,
    ATTR_MAX_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CONF_NAME,
    PRECISION_HALVES,
    PRECISION_TENTHS,
)
from homeassistant.core import Context, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import start
from homeassistant.helpers.typing import EventType

from .const import (
    CONF_CURRENT_TEMPERATURE_ENTITY_ID,
    CONF_COOLERS,
    CONF_HEATERS,
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
    min_temp = config_entry.options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)
    max_temp = config_entry.options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)

    temperature_unit = hass.config.units.temperature_unit

    precision = config_entry.options.get(CONF_PRECISION, PRECISION_TENTHS)
    target_temperature_step = config_entry.options.get(
        CONF_TARGET_TEMP_STEP, PRECISION_HALVES
    )

    toggle_coolers = config_entry.options.get(CONF_TOGGLE_COOLERS, False)
    toggle_heaters = config_entry.options.get(CONF_TOGGLE_HEATERS, False)

    hvac_actuator_entity_ids: dict[str, set[str]] = {}
    registry = er.async_get(hass)

    for hvac_actuator_type in [CONF_HEATERS, CONF_COOLERS]:
        target_entities = set()
        if (
            hvac_actuator_type in config_entry.options
            and len(config_entry.options[hvac_actuator_type]) > 0
        ):
            for entity_id in config_entry.options[hvac_actuator_type]:
                validated_entity_id = er.async_validate_entity_id(registry, entity_id)
                target_entities.add(validated_entity_id)
        if len(target_entities) > 0:
            hvac_actuator_entity_ids.update({hvac_actuator_type: target_entities})

    async_add_entities(
        [
            HvacGroupClimateEntity(
                hass,
                unique_id,
                name,
                sensor_entity_id,
                temperature_unit,
                min_temp,
                max_temp,
                precision=precision,
                target_temperature_step=target_temperature_step,
                heaters=hvac_actuator_entity_ids[CONF_HEATERS],
                coolers=hvac_actuator_entity_ids[CONF_COOLERS],
                toggle_coolers=toggle_coolers,
                toggle_heaters=toggle_heaters,
            )
        ]
    )


class HvacActuatorType(StrEnum):
    """HVAC group actuator type."""

    HEATER = "heater"
    COOLER = "cooler"


class HvacGroupActuator:
    """An actuator (heater/cooler) from a HVAC group."""

    actuator_type: HvacActuatorType | None = None

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Initialize a HVAC group actuator."""
        self.hass = hass

        self._entity_id = entity_id

    @property
    def entity_id(self) -> str:
        """Return the actuator entity_id."""
        return self._entity_id

    @property
    def state(self) -> State:
        """Get the current state of the actuator."""
        return self.hass.states.get(self.entity_id)

    async def set_hvac_mode(
        self, hvac_mode: HVACMode, context: Context | None = None
    ) -> None:
        """Set the HVAC mode on an actuator."""
        await self.hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: hvac_mode},
            target={ATTR_ENTITY_ID: self.entity_id},
            context=context,
            blocking=True,
        )

    async def set_temperature(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
        context: Context | None = None,
    ) -> None:
        """Set the reference temperature of an actuator."""
        # Prevent receiving both target temperature and target range
        assert None in (temperature, target_temp_high, target_temp_low)

        data = {}
        if (
            self.state.attributes.get(ATTR_SUPPORTED_FEATURES)
            & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        ):
            data = {
                ATTR_TARGET_TEMP_LOW: target_temp_low or temperature,
                ATTR_TARGET_TEMP_HIGH: target_temp_high or temperature,
            }
        elif isinstance(self, HvacGroupHeater):
            data = {ATTR_TEMPERATURE: target_temp_low or temperature}
        else:
            data = {ATTR_TEMPERATURE: target_temp_high or temperature}

        await self.hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            data,
            target={ATTR_ENTITY_ID: self.entity_id},
            context=context,
            blocking=True,
        )

    def supports_ranged_target_temperature(self) -> bool:
        """Return true if the actuator supports low/high target temperature."""
        return bool(
            self.state.attributes.get(ATTR_SUPPORTED_FEATURES)
            & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        )

    async def turn_on(self, context: Context | None = None) -> None:
        """Turn on an actuator."""
        hvac_mode = (
            HVACMode.HEAT if isinstance(self, HvacGroupHeater) else HVACMode.COOL
        )
        await self.set_hvac_mode(hvac_mode, context)

    async def turn_off(self, context: Context | None = None) -> None:
        """Turn off an actuator."""
        await self.set_hvac_mode(HVACMode.OFF, context)


class HvacGroupHeater(HvacGroupActuator):
    """A heater actuator for a HVAC group."""

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Initialize a HVAC group heater."""
        super().__init__(hass, entity_id)
        self.actuator_type = HvacActuatorType.HEATER


class HvacGroupCooler(HvacGroupActuator):
    """A cooler actuator for a HVAC group."""

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Initialize a HVAC group cooler."""
        super().__init__(hass, entity_id)
        self.actuator_type = HvacActuatorType.COOLER


class HvacGroupActuatorDict(dict[str, HvacGroupActuator]):
    """A special dictionary of actuators."""

    async def async_turn_on(self, context: Context | None = None) -> None:
        """Turn on all items of a dictionary."""
        for actuator in self.values():
            await actuator.turn_on(context)

    async def async_turn_off(self, context: Context | None = None) -> None:
        """Turn off all items of a dictionary."""
        for actuator in self.values():
            await actuator.turn_off(context)


class HvacGroupClimateEntity(ClimateEntity, RestoreEntity):
    """HVAC group climate entity."""

    _heaters: HvacGroupActuatorDict = HvacGroupActuatorDict()
    _coolers: HvacGroupActuatorDict = HvacGroupActuatorDict()

    _loaded = False

    def __init__(
        self,
        hass: HomeAssistant,
        unique_id: str,
        name: str,
        temperature_sensor_entity_id: str,
        temperature_unit: str | None = None,
        min_temp: float | None = None,
        max_temp: float | None = None,
        precision: float | None = None,
        target_temp_high: float | None = None,
        target_temp_low: float | None = None,
        target_temperature_step: float | None = None,
        heaters: set[str] = None,
        coolers: set[str] = None,
        hvac_mode: HVACMode | None = None,
        toggle_coolers: bool = False,
        toggle_heaters: bool = False,
    ) -> None:
        """Initialize HVAC Group Climate."""
        self.hass = hass

        self._attr_name = name
        self._attr_unique_id = unique_id

        self._temperature_sensor_entity_id = temperature_sensor_entity_id
        self._temp_precision = precision or PRECISION_TENTHS
        self._temp_target_temperature_step = target_temperature_step
        self._attr_temperature_unit = temperature_unit

        self._hvac_mode = hvac_mode
        self._attr_hvac_modes = [HVACMode.OFF]

        if heaters is None:
            heaters = set()
        if coolers is None:
            coolers = set()
        for heater_entity_id in heaters:
            self._add_heater(heater_entity_id)
        for cooler_entity_id in coolers:
            self._add_cooler(cooler_entity_id)

        self._is_cooling_active = False
        self._is_heating_active = False

        self._current_temperature = None
        self._min_temp = min_temp or DEFAULT_MIN_TEMP
        self._max_temp = max_temp or DEFAULT_MAX_TEMP
        self._target_temp_low = target_temp_low
        self._target_temp_high = target_temp_high

        self._toggle_heaters_on_threshold = toggle_heaters
        self._toggle_coolers_on_threshold = toggle_coolers

        self._temp_lock = asyncio.Lock()
        self._active = False

    @property
    def current_temperature(self) -> float | None:
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
        """Register listeners."""

        for entity_id, heater in self._heaters.items():
            if heater.state is None:
                continue
            self.async_update_supported_features(entity_id, heater.state)
        for entity_id, cooler in self._coolers.items():
            if cooler.state is None:
                continue
            self.async_update_supported_features(entity_id, cooler.state)

        @callback
        async def async_actuator_state_changed_listener(
            event: EventType[EventStateChangedData],
        ) -> None:
            """Handle child updates."""
            self.async_set_context(event.context)
            self.async_update_supported_features(
                event.data["entity_id"],
                event.data["new_state"],
                event.data["old_state"],
            )
            await self.async_defer_or_update_ha_state()

        @callback
        async def async_sensor_state_changed_listener(
            event: EventType[EventStateChangedData],
        ) -> None:
            """Handle temperature sensor updates."""
            self.async_set_context(event.context)
            await self.async_update_temperature_sensor(
                event.data["entity_id"],
                event.data["new_state"],
                event.data["old_state"],
            )
            await self.async_defer_or_update_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                set().union(self._heaters.keys(), self._coolers.keys()),
                async_actuator_state_changed_listener,
            )
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._temperature_sensor_entity_id,
                async_sensor_state_changed_listener,
            )
        )

        async def _update_at_start(_: HomeAssistant) -> None:
            await self.async_run_hvac()
            self.async_write_ha_state()

        self.async_on_remove(start.async_at_start(self.hass, _update_at_start))

        # Check If we have an old state
        if (old_state := await self.async_get_last_state()) is not None:
            # If we have no initial temperature, restore
            if self._target_temp_low is None:
                self._target_temp_low = old_state.attributes.get(
                    ATTR_TARGET_TEMP_LOW, self.min_temp
                )
            if self._target_temp_high is None:
                self._target_temp_high = old_state.attributes.get(
                    ATTR_TARGET_TEMP_HIGH, self.max_temp
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

    @callback
    async def async_defer_or_update_ha_state(self) -> None:
        """Only update once at start."""
        if not self.hass.is_running:
            return

        await self.async_run_hvac()
        self.async_write_ha_state()

    @callback
    def async_update_supported_features(
        self,
        entity_id: str,
        new_state: State | None,
        old_state: State | None = None,
    ) -> None:
        """Update supported features."""
        if new_state is None:
            return

        if (
            old_state is None
            or old_state.attributes.get(ATTR_MIN_TEMP)
            != new_state.attributes.get(ATTR_MIN_TEMP)
            or old_state.attributes.get(ATTR_MAX_TEMP)
            != new_state.attributes.get(ATTR_MAX_TEMP)
        ):
            self._min_temp = min(
                new_state.attributes.get(ATTR_MAX_TEMP, self._min_temp),
                max(
                    self._min_temp,
                    new_state.attributes.get(ATTR_MIN_TEMP, self._min_temp),
                ),
            )
            self._max_temp = max(
                new_state.attributes.get(ATTR_MIN_TEMP, self._max_temp),
                min(
                    self._max_temp,
                    new_state.attributes.get(ATTR_MAX_TEMP, self._max_temp),
                ),
            )
            if self._target_temp_low is not None:
                self._target_temp_low = max(self._target_temp_low, self._min_temp)
            if self._target_temp_high is not None:
                self._target_temp_high = min(self._target_temp_high, self._max_temp)

    @callback
    async def async_update_temperature_sensor(
        self,
        entity_id: str,
        new_state: State | None,
        old_state: State | None,
    ) -> None:
        """Update sensor temperature."""
        if new_state is None:
            return

        current_temperature = (
            new_state.attributes.get(ATTR_CURRENT_TEMPERATURE)
            if new_state.domain == CLIMATE_DOMAIN
            else new_state.state
        )

        self._current_temperature = current_temperature
        await self.async_run_hvac()

    @callback
    async def async_run_hvac(self, force: bool = False) -> None:
        """Update the actuators."""

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

            if not self._active:
                return

            assert self._target_temp_low
            assert self._target_temp_high
            assert self._current_temperature
            too_cold = self._target_temp_low >= self._current_temperature
            too_hot = self._current_temperature >= self._target_temp_high
            if too_hot:
                if (
                    not self._is_cooling_active and self._toggle_coolers_on_threshold
                ) or force:
                    LOGGER.info(
                        "Turning on cooling %s",
                        ",".join(self._coolers.keys()),
                    )
                    await self._coolers.async_turn_on(self._context)
                    self._is_cooling_active = True
            elif (
                self._is_cooling_active and self._toggle_coolers_on_threshold
            ) or force:
                LOGGER.info(
                    "Turning off cooling %s",
                    ",".join(self._coolers.keys()),
                )
                self._is_cooling_active = False
                await self._coolers.async_turn_off(self._context)

            if too_cold:
                if (
                    not self._is_heating_active and self._toggle_heaters_on_threshold
                ) or force:
                    LOGGER.info(
                        "Turning on heating %s",
                        ",".join(self._heaters.keys()),
                    )
                    await self._heaters.async_turn_on(self._context)
                    self._is_heating_active = True
            elif (
                self._is_heating_active and self._toggle_heaters_on_threshold
            ) or force:
                LOGGER.info(
                    "Turning off heating %s",
                    ",".join(self._heaters.keys()),
                )
                self._is_heating_active = False
                await self._heaters.async_turn_off(self._context)

    def _add_heater(self, heater_entity_id: str) -> None:
        """Add a heater actuator referenced by entity_id."""
        if heater_entity_id in self._heaters:
            return

        heater = HvacGroupHeater(self.hass, heater_entity_id)
        self._heaters.update({heater_entity_id: heater})

        if not (
            HVACMode.HEAT in self._attr_hvac_modes
            or HVACMode.HEAT_COOL in self._attr_hvac_modes
        ):
            if HVACMode.COOL in self._attr_hvac_modes:
                self._attr_hvac_modes.remove(HVACMode.COOL)
                self._attr_hvac_modes.append(HVACMode.HEAT_COOL)
                self._attr_supported_features = (
                    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                )
            else:
                self._attr_hvac_modes.append(HVACMode.HEAT)
                self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def _add_cooler(self, cooler_entity_id: str) -> None:
        """Add a heater actuator referenced by entity_id."""
        if cooler_entity_id in self._coolers:
            return

        cooler = HvacGroupCooler(self.hass, cooler_entity_id)
        self._coolers.update({cooler_entity_id: cooler})

        if not (
            HVACMode.COOL in self._attr_hvac_modes
            or HVACMode.HEAT_COOL in self._attr_hvac_modes
        ):
            if HVACMode.HEAT in self._attr_hvac_modes:
                self._attr_hvac_modes.remove(HVACMode.HEAT)
                self._attr_hvac_modes.append(HVACMode.HEAT_COOL)
                self._attr_supported_features = (
                    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                )
            else:
                self._attr_hvac_modes.append(HVACMode.COOL)
                self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode callback."""
        if hvac_mode in (HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL):
            self._hvac_mode = hvac_mode
            match hvac_mode:
                case HVACMode.HEAT:
                    # Firstly turn off coolers so that if a device is both a cooler and a heater to make sure to start it in the proper mode
                    await self._coolers.async_turn_off(self._context)
                    await self._heaters.async_turn_on(self._context)
                    self._is_cooling_active = False
                    self._is_heating_active = True
                case HVACMode.COOL:
                    await self._heaters.async_turn_off(self._context)
                    await self._coolers.async_turn_on(self._context)
                    self._is_cooling_active = True
                    self._is_heating_active = False
                case HVACMode.HEAT_COOL:
                    await self._coolers.async_turn_on(self._context)
                    await self._heaters.async_turn_on(self._context)
                    self._is_cooling_active = True
                    self._is_heating_active = True
            await self.async_run_hvac()
        elif hvac_mode == HVACMode.OFF:
            self._hvac_mode = HVACMode.OFF
            await self._coolers.async_turn_off(self._context)
            await self._heaters.async_turn_off(self._context)
        else:
            LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return

        await self._async_set_actuator_temperatures()

        # Ensure we update the current operation after changing the mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if temp_low is None and temp_high is None:
            return
        if temp_low is not None:
            self._target_temp_low = temp_low

        if temp_high is not None:
            self._target_temp_high = temp_high

        await self._async_set_actuator_temperatures()
        await self.async_run_hvac()

        self.async_write_ha_state()

    async def _async_set_actuator_temperatures(self):
        """Update temperatures on heaters/coolers based on operation mode."""
        for heater in self._heaters.values():
            if not heater.supports_ranged_target_temperature():
                if heater.state.state != HVACMode.HEAT:
                    continue
            await heater.set_temperature(
                target_temp_low=self._target_temp_low,
                target_temp_high=self._target_temp_high,
                context=self._context,
            )
        for cooler in self._coolers.values():
            if not cooler.supports_ranged_target_temperature():
                if cooler.state.state != HVACMode.COOL:
                    continue
            await cooler.set_temperature(
                target_temp_low=self._target_temp_low,
                target_temp_high=self._target_temp_high,
                context=self._context,
            )
