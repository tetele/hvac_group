"""Climate platform for HVAC group integration."""

from __future__ import annotations
import asyncio
from enum import StrEnum
from typing import Any
from collections.abc import Callable, Coroutine

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

    entity = HvacGroupClimateEntity(
        hass,
        unique_id,
        name,
        sensor_entity_id,
        temperature_unit,
        min_temp,
        max_temp,
        precision=precision,
        target_temperature_step=target_temperature_step,
        heaters=hvac_actuator_entity_ids.get(CONF_HEATERS, set()),
        coolers=hvac_actuator_entity_ids.get(CONF_COOLERS, set()),
        toggle_coolers=toggle_coolers,
        toggle_heaters=toggle_heaters,
    )

    async_add_entities([entity])


async def create_coro(function: Callable, *args, **kwargs) -> Any:
    """Create a coro wrapper used to patch methods in tests."""
    LOGGER.debug("Running coroutine %s(%s)", function, args)
    return await function(*args, **kwargs)


class HvacActuatorType(StrEnum):
    """HVAC group actuator type."""

    HEATER = "heater"
    COOLER = "cooler"


class HvacGroupActuator:
    """An actuator (heater/cooler) from a HVAC group."""

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Initialize a HVAC group actuator."""
        self.hass: HomeAssistant = hass

        self.actuator_type: HvacActuatorType | None = None
        self._context: Context | None = None

        self._entity_id: str = entity_id
        self.initialized: bool = False
        self.loaded: bool = False

        self._action_to_commit: Coroutine | None = None
        self._commit_semaphore = asyncio.Semaphore()

    @property
    def entity_id(self) -> str:
        """Return the actuator entity_id."""
        return self._entity_id

    @property
    def state(self) -> State:
        """Get the current state of the actuator."""
        return self.hass.states.get(self.entity_id)

    @property
    def commit_action(self) -> Coroutine | None:
        """Get the action to commit."""
        return self._action_to_commit

    async def _set_commit_action(self, action: Coroutine):
        """Set the action to commit."""
        async with self._commit_semaphore:
            if self._action_to_commit:
                LOGGER.debug("Closing commit action on %s", self._entity_id)
                self._action_to_commit.close()
            self._action_to_commit = action

    def set_context(self, context: Context | None) -> None:
        """Set the context."""
        self._context = context

    def _guess_target_temperature(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
    ) -> float | None:
        """Get a target temperature given a triplet of target temperature, target temp low and high."""
        return temperature

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode on an actuator."""
        await self._set_commit_action(
            create_coro(
                self._async_call_climate_service,
                self._entity_id,
                SERVICE_SET_HVAC_MODE,
                {ATTR_HVAC_MODE: hvac_mode},
            )
        )
        LOGGER.debug(
            "Creating commit action `set_hvac_mode` on %s %s",
            self.__class__,
            self._entity_id,
        )

    async def async_set_temperature(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
        hvac_mode: HVACMode | None = None,
    ) -> None:
        """Set the reference temperature of an actuator."""
        LOGGER.debug(
            "Attempting to set temperature of %s %s to (%s %s %s) and mode to %s",
            self.__class__,
            self._entity_id,
            temperature,
            target_temp_low,
            target_temp_high,
            hvac_mode,
        )
        # Prevent receiving both target temperature and target range
        assert None in (temperature, target_temp_high, target_temp_low)

        if self.state is None:
            LOGGER.warning(
                "Attempting to set temperature of unloaded climate entity %s. Aborting",
                self.entity_id,
            )
            return

        data = {}
        if ClimateEntityFeature.TARGET_TEMPERATURE_RANGE in self.state.attributes.get(
            ATTR_SUPPORTED_FEATURES, 0
        ):
            data = {
                ATTR_TARGET_TEMP_LOW: target_temp_low or temperature,
                ATTR_TARGET_TEMP_HIGH: target_temp_high or temperature,
            }
        else:
            data = {
                ATTR_TEMPERATURE: self._guess_target_temperature(
                    temperature, target_temp_low, target_temp_high
                )
            }

        if hvac_mode is not None:
            data.update({ATTR_HVAC_MODE: hvac_mode})

        await self._set_commit_action(
            create_coro(
                self._async_call_climate_service,
                self._entity_id,
                SERVICE_SET_TEMPERATURE,
                data,
            )
        )
        LOGGER.debug(
            "Creating commit action `set_temperature` on %s %s",
            self.__class__,
            self._entity_id,
        )

    async def _async_call_climate_service(
        self,
        entity_id: str | None,  # used only for tests
        service: str,
        data: dict[str, Any] | None,
    ) -> None:
        """Call a climate service."""
        await self.hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            data,
            target={ATTR_ENTITY_ID: self._entity_id},
            context=self._context,
            blocking=True,
        )

    async def async_turn_on(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
    ) -> None:
        """Turn on an actuator."""
        LOGGER.warning(
            "Generic actuator %s cannot be turned on, use set_hvac_mode instead.",
            self.entity_id,
        )

    async def async_turn_off(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
    ) -> None:
        """Turn off an actuator."""
        await self.async_set_temperature(
            temperature=temperature,
            target_temp_high=target_temp_high,
            target_temp_low=target_temp_low,
            hvac_mode=HVACMode.OFF,
        )

    async def async_commit(self) -> None:
        """Execute the last service call."""
        async with self._commit_semaphore:
            if self._action_to_commit is not None:
                await self._action_to_commit
                LOGGER.debug(
                    "Commit action run for %s %s. Removing",
                    self.__class__,
                    self._entity_id,
                )
                self._action_to_commit = None
            else:
                LOGGER.debug(
                    "No commit action for %s %s", self.__class__, self._entity_id
                )


class HvacGroupHeater(HvacGroupActuator):
    """A heater actuator for a HVAC group."""

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Initialize a HVAC group heater."""
        super().__init__(hass, entity_id)
        self.actuator_type = HvacActuatorType.HEATER

    async def async_turn_on(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
    ) -> None:
        """Turn on a heater."""
        await self.async_set_temperature(
            temperature=temperature,
            target_temp_high=target_temp_high,
            target_temp_low=target_temp_low,
            hvac_mode=HVACMode.HEAT,
        )

    def _guess_target_temperature(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
    ) -> float | None:
        """Get a target temperature given a triplet of target temperature, target temp low and high."""
        return temperature or target_temp_low


class HvacGroupCooler(HvacGroupActuator):
    """A cooler actuator for a HVAC group."""

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Initialize a HVAC group cooler."""
        super().__init__(hass, entity_id)
        self.actuator_type = HvacActuatorType.COOLER

    async def async_turn_on(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
    ) -> None:
        """Turn on a cooler."""
        await self.async_set_temperature(
            temperature=temperature,
            target_temp_high=target_temp_high,
            target_temp_low=target_temp_low,
            hvac_mode=HVACMode.COOL,
        )

    def _guess_target_temperature(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
    ) -> float | None:
        """Get a target temperature given a triplet of target temperature, target temp low and high."""
        return temperature or target_temp_high


class HvacGroupActuatorDict(dict[str, HvacGroupActuator]):
    """A special dictionary of actuators."""

    async def async_turn_on(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
        context: Context | None = None,
    ) -> None:
        """Turn on all HvacGroupActuator items of a dictionary."""
        for actuator in self.values():
            actuator.set_context(context)
            await actuator.async_turn_on(
                temperature=temperature,
                target_temp_high=target_temp_high,
                target_temp_low=target_temp_low,
            )

    async def async_turn_off(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
        context: Context | None = None,
    ) -> None:
        """Turn off all HvacGroupActuator items of a dictionary."""
        for actuator in self.values():
            actuator.set_context(context)
            await actuator.async_turn_off(
                temperature=temperature,
                target_temp_high=target_temp_high,
                target_temp_low=target_temp_low,
            )

    async def async_set_hvac_mode(
        self, hvac_mode: HVACMode, context: Context | None = None
    ) -> None:
        """Set HVAC mode for all HvacGroupActuator items of a dictionary."""
        for actuator in self.values():
            actuator.set_context(context)
            await actuator.async_set_hvac_mode(hvac_mode)

    async def async_set_temperature(
        self,
        temperature: float | None = None,
        target_temp_low: float | None = None,
        target_temp_high: float | None = None,
        hvac_mode: HVACMode | None = None,
        context: Context | None = None,
    ) -> None:
        """Set target temperature all HvacGroupActuator items of a dictionary."""
        for actuator in self.values():
            actuator.set_context(context)
            await actuator.async_set_temperature(
                temperature=temperature,
                target_temp_high=target_temp_high,
                target_temp_low=target_temp_low,
                hvac_mode=hvac_mode,
            )

    async def async_commit(self) -> None:
        """Commit state changes for all members."""
        for actuator in self.values():
            await actuator.async_commit()

    def mark_initialized(self) -> None:
        """Set all members as initialized."""
        for actuator in self.values():
            actuator.initialized = True


def state_diff(new: State, old: State) -> dict[str, Any]:
    """Compute the difference between 2 states."""

    if old is None:
        return {"state": new.state, "attributes": new.attributes}

    diff: dict[str, Any] = {"attributes": {}}
    if new.state != old.state:
        diff.update({"state": (new.state, old.state)})

    for key, value in new.attributes.items():
        if (new_attr := old.attributes.get(key)) != value:
            diff["attributes"].update({key: (value, new_attr)})

    for key in old.attributes:
        if key not in new.attributes:
            diff["attributes"].update({key: (None, old.attributes.get(key))})

    return diff


class HvacGroupClimateEntity(ClimateEntity, RestoreEntity):
    """HVAC group climate entity."""

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
        heaters: set[str] | None = None,
        coolers: set[str] | None = None,
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

        self._heaters: HvacGroupActuatorDict = HvacGroupActuatorDict()
        self._coolers: HvacGroupActuatorDict = HvacGroupActuatorDict()

        if heaters is None:
            heaters = set()
        if coolers is None:
            coolers = set()
        for heater_entity_id in heaters:
            self._add_heater(heater_entity_id)
        for cooler_entity_id in coolers:
            self._add_cooler(cooler_entity_id)

        self._is_heating = False
        self._is_cooling = False
        self._are_coolers_active = False
        self._are_heaters_active = False

        self._current_temperature: float | None = None
        self._min_temp = min_temp or DEFAULT_MIN_TEMP
        self._max_temp = max_temp or DEFAULT_MAX_TEMP
        self._target_temp_low = target_temp_low
        self._target_temp_high = target_temp_high

        self._target_temperature = target_temp_high
        if len(self._coolers) == 0:
            self._target_temperature = target_temp_low

        self._toggle_heaters_on_threshold = toggle_heaters if self._heaters else False
        self._toggle_coolers_on_threshold = toggle_coolers if self._coolers else False

        self._hvac_running_lock = asyncio.Lock()
        self._changing_actuators_lock = asyncio.Lock()
        self._active = False

        self._require_actuator_mass_refresh: bool = False
        self._state_restored = False

    @property
    def current_temperature(self) -> float | None:
        """Return the sensor temperature."""
        return self._current_temperature

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported."""

        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._is_heating:
            return HVACAction.HEATING
        if self._is_cooling:
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
        return None

    @property
    def target_temperature_high(self) -> float:
        """Return the high temperature we try to reach."""
        if self._target_temp_high is not None:
            return self._target_temp_high
        return None

    @property
    def target_temperature(self) -> float:
        """Return the target temperature we try to reach."""
        if self._target_temperature is not None:
            return self._target_temperature
        return None

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        if self._temp_target_temperature_step is not None:
            return self._temp_target_temperature_step
        # If a target_temperature_step is not defined, fallback to equal the precision
        return self.precision

    @property
    def common_actuators(self) -> HvacGroupActuatorDict:
        """Return a dict of actuators that are both heaters and coolers."""
        return self.heaters_that_are_also_coolers

    @property
    def heaters_that_are_also_coolers(self) -> HvacGroupActuatorDict:
        """Return a dict of heaters that are also coolers."""
        return HvacGroupActuatorDict(
            {
                entity_id: actuator
                for entity_id, actuator in self._heaters.items()
                if entity_id in self._coolers
            }
        )

    @property
    def coolers_that_are_also_heaters(self) -> HvacGroupActuatorDict:
        """Return a dict of coolers that are also heaters."""
        return HvacGroupActuatorDict(
            {
                entity_id: actuator
                for entity_id, actuator in self._coolers.items()
                if entity_id in self._heaters
            }
        )

    async def async_added_to_hass(self) -> None:  # noqa: C901
        """Register listeners."""

        for entity_id, heater in self._heaters.items():
            if heater.state is None:
                continue
            self.async_update_supported_features(
                entity_id, HvacActuatorType.HEATER, heater.state
            )
        for entity_id, cooler in self._coolers.items():
            if cooler.state is None:
                continue
            self.async_update_supported_features(
                entity_id, HvacActuatorType.COOLER, cooler.state
            )

        if (
            temp_sensor_state := self.hass.states.get(
                self._temperature_sensor_entity_id
            )
        ) is not None:
            await self.async_update_temperature_sensor(
                temp_sensor_state.entity_id, temp_sensor_state
            )

        async def async_apply_last_state_when_actuators_loaded() -> None:
            """Apply saved state when group members are loaded.

            Check whether all members have been initiatlized
            and apply the last saved state if they were.
            The reason for waiting is so that all the features are loaded.
            """

            if self._state_restored:
                return

            for heater in self._heaters.values():
                if not heater.loaded:
                    return
            for cooler in self._coolers.values():
                if not cooler.loaded:
                    return

            # Check If we have an old state
            if (old_state := await self.async_get_last_state()) is not None:
                # If we have no initial temperature, restore
                if (
                    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                    in self._attr_supported_features
                ):
                    target_temp_low = self._target_temp_low or old_state.attributes.get(
                        ATTR_TARGET_TEMP_LOW, self.min_temp
                    )
                    target_temp_high = (
                        self._target_temp_high
                        or old_state.attributes.get(
                            ATTR_TARGET_TEMP_HIGH, self.max_temp
                        )
                    )
                    await self.async_set_temperature(
                        target_temp_low=target_temp_low,
                        target_temp_high=target_temp_high,
                    )
                else:
                    default_temp = self.max_temp if self._coolers else self.min_temp
                    target_temp = self._target_temperature or old_state.attributes.get(
                        ATTR_TEMPERATURE, default_temp
                    )
                    await self.async_set_temperature(temperature=target_temp)

                if self._hvac_mode is None and old_state.state:
                    await self.async_set_hvac_mode(old_state.state)

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
            if self._hvac_mode is None:
                self._hvac_mode = HVACMode.OFF

            self._state_restored = True

        await async_apply_last_state_when_actuators_loaded()

        @callback
        async def async_actuator_state_changed_listener(
            event: EventType[EventStateChangedData],
        ) -> None:
            """Handle actuator updates, like min/max temp changes."""

            LOGGER.debug(
                "Actutator %s changed state: %s (context %s)",
                event.data["entity_id"],
                state_diff(event.data["new_state"], event.data["old_state"]),
                event.context.id,
            )

            entity_id = event.data["entity_id"]
            self.async_set_context(event.context)

            if entity_id in self._heaters:
                self.async_update_supported_features(
                    entity_id,
                    HvacActuatorType.HEATER,
                    event.data["new_state"],
                    event.data["old_state"],
                )

                if not self._heaters[entity_id].initialized:
                    self._require_actuator_mass_refresh = True

                if not self._heaters[entity_id].loaded:
                    self._heaters[entity_id].loaded = True

                await self.async_defer_or_update_ha_state()

            if entity_id in self._coolers:
                self.async_update_supported_features(
                    entity_id,
                    HvacActuatorType.COOLER,
                    event.data["new_state"],
                    event.data["old_state"],
                )

                if not self._coolers[entity_id].initialized:
                    self._require_actuator_mass_refresh = True

                if not self._coolers[entity_id].loaded:
                    self._coolers[entity_id].loaded = True

                await self.async_defer_or_update_ha_state()

            await async_apply_last_state_when_actuators_loaded()

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
            """Initialize the functioning of the group."""
            self._require_actuator_mass_refresh = True
            await self.async_defer_or_update_ha_state(update_actuators=True)

        self.async_on_remove(start.async_at_start(self.hass, _update_at_start))

    @callback
    async def async_defer_or_update_ha_state(
        self, update_actuators: bool = False
    ) -> None:
        """Only update once at start."""
        if not self.hass.is_running:
            return

        await self.async_run_hvac(update_actuators=update_actuators)
        # Commit changes. Note that common actuators have different HvacGroupActuator
        # instances, each with their own commit action
        await self._heaters.async_commit()
        await self._coolers.async_commit()
        self.async_write_ha_state()

    @callback
    def async_update_supported_features(
        self,
        entity_id: str,
        actuator_type: HvacActuatorType,
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
                float(new_state.attributes.get(ATTR_MAX_TEMP, self._min_temp)),
                max(
                    self._min_temp,
                    float(new_state.attributes.get(ATTR_MIN_TEMP, self._min_temp)),
                ),
            )
            if self._target_temp_low is not None:
                self._target_temp_low = max(self._target_temp_low, self._min_temp)

            self._max_temp = max(
                float(new_state.attributes.get(ATTR_MIN_TEMP, self._max_temp)),
                min(
                    self._max_temp,
                    float(new_state.attributes.get(ATTR_MAX_TEMP, self._max_temp)),
                ),
            )
            if self._target_temp_high is not None:
                self._target_temp_high = min(self._target_temp_high, self._max_temp)

            LOGGER.debug(
                (
                    "New min/max temps received from actuator %s: (%s, %s). "
                    "HVAC Group %s new min/max temps: %s, %s"
                ),
                entity_id,
                new_state.attributes.get(ATTR_MIN_TEMP, self._max_temp),
                new_state.attributes.get(ATTR_MAX_TEMP, self._min_temp),
                self.entity_id,
                self._min_temp,
                self._max_temp,
            )

        if old_state is None:
            self._update_hvac_modes(actuator_type, new_state)

    @callback
    async def async_update_temperature_sensor(
        self,
        entity_id: str,
        new_state: State | None,
        old_state: State | None = None,
    ) -> None:
        """Update sensor temperature."""
        if new_state is None:
            return

        # Current temperature can be retrieved from a `climate` or `sensor` entity
        new_temperature = (
            new_state.attributes.get(ATTR_CURRENT_TEMPERATURE)
            if new_state.domain == CLIMATE_DOMAIN
            else new_state.state
        )
        old_temperature = None
        if old_state is not None:
            old_temperature = (
                old_state.attributes.get(ATTR_CURRENT_TEMPERATURE)
                if old_state.domain == CLIMATE_DOMAIN
                else old_state.state
            )

        if new_temperature == old_temperature:
            return

        LOGGER.debug(
            "New temperature received from temp sensor %s: %s. Setting on HVAC Group %s",
            entity_id,
            new_temperature,
            self.entity_id,
        )

        self._current_temperature = (
            float(new_temperature) if new_temperature is not None else new_temperature
        )

        await self.async_defer_or_update_ha_state()

    @callback
    async def async_run_hvac(self, update_actuators: bool = False) -> None:
        """Update the actuators."""

        # If the update was requested because many actuators are being toggled, don't
        if self._changing_actuators_lock.locked():
            LOGGER.debug(
                "Cannot run HVAC %s because the actuators are being mass controlled",
                self.entity_id,
            )
            return

        async with self._hvac_running_lock:
            if (
                not self._active
                and None
                not in (
                    self._current_temperature,
                    self._hvac_mode,
                )
                and (
                    None not in (self._target_temp_low, self._target_temp_high)
                    or self._target_temperature is not None
                )
            ):
                self._active = True
                LOGGER.info(
                    (
                        "Obtained current and target temperatures (%s -> %s). "
                        "Setting mode %s on HVAC group %s."
                    ),
                    self._current_temperature,
                    f"{self._target_temp_low}-{self._target_temp_high}"
                    if ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                    in self._attr_supported_features
                    else f"{self._target_temperature}",
                    self._hvac_mode,
                    self.entity_id,
                )

            if not self._active:
                return

            await self.async_control_actuators(
                update_actuators=update_actuators,
                force_update_all=self._require_actuator_mass_refresh,
            )

    async def async_control_actuators(
        self, update_actuators: bool = False, force_update_all: bool = False
    ):
        """Control actuators based on needs."""

        try:
            if force_update_all:
                self._require_actuator_mass_refresh = False
                LOGGER.debug(
                    "Force updating the state of actuators of HVAC group %s",
                    self.entity_id,
                )

                await self._changing_actuators_lock.acquire()

                match self._hvac_mode:
                    case HVACMode.HEAT:
                        await self._async_turn_off_coolers(pure=True)
                        await self._async_turn_on_heaters()
                    case HVACMode.COOL:
                        await self._async_turn_off_heaters(pure=True)
                        await self._async_turn_on_coolers()
                    case HVACMode.HEAT_COOL:
                        await self._async_turn_on_heaters(pure=True)
                        await self._async_turn_on_coolers(pure=True)
                    case HVACMode.OFF:
                        await self._async_turn_off_coolers()
                        await self._async_turn_off_heaters(
                            pure=True
                        )  # avoid turning off common elements twice

                self._heaters.mark_initialized()
                self._coolers.mark_initialized()

                LOGGER.debug("Actuators initialized for HVAC group %s", self.entity_id)

            needs_cooling = False
            needs_heating = False

            # Assertions are just for shutting up mypy
            assert (
                self._target_temp_low and self._target_temp_high
            ) or self._target_temperature
            assert self._current_temperature

            too_cold = (
                self._target_temp_low or self._target_temperature
            ) >= self._current_temperature
            too_hot = self._current_temperature >= (
                self._target_temp_high or self._target_temperature
            )
            if too_hot and self._coolers:
                needs_cooling = True
                if (
                    (not self._are_coolers_active or update_actuators)
                    and self._toggle_coolers_on_threshold
                    and self._hvac_mode in [HVACMode.COOL, HVACMode.HEAT_COOL]
                ):
                    LOGGER.debug(
                        "Turning on cooling %s for HVAC group %s",
                        ",".join(self._coolers.keys()),
                        self.entity_id,
                    )
                    await self._async_turn_on_coolers()
            elif (
                self._are_coolers_active or update_actuators
            ) and self._toggle_coolers_on_threshold:
                LOGGER.debug(
                    "Turning off cooling %s for HVAC group %s",
                    ",".join(self._coolers.keys()),
                    self.entity_id,
                )
                await self._async_turn_off_coolers(pure=True)

            if too_cold and self._heaters:
                needs_heating = True
                if (
                    (not self._are_heaters_active or update_actuators)
                    and self._toggle_heaters_on_threshold
                    and self._hvac_mode in [HVACMode.HEAT, HVACMode.HEAT_COOL]
                ):
                    LOGGER.debug(
                        "Turning on heating %s for HVAC group %s",
                        ",".join(self._heaters.keys()),
                        self.entity_id,
                    )
                    await self._async_turn_on_heaters()
            elif (
                self._are_heaters_active or update_actuators
            ) and self._toggle_heaters_on_threshold:
                LOGGER.debug(
                    "Turning off heating %s for HVAC group %s",
                    ",".join(self._heaters.keys()),
                    self.entity_id,
                )
                await self._async_turn_off_heaters(pure=True)

            # You can't need heating and cooling simultaneously
            assert not needs_cooling or not needs_heating

            if needs_heating:
                if not self._is_heating and self._hvac_mode in [
                    HVACMode.HEAT,
                    HVACMode.HEAT_COOL,
                ]:
                    LOGGER.debug(
                        "Setting common actuators  %s as heaters for HVAC group %s",
                        ",".join(self.common_actuators.keys()),
                        self.entity_id,
                    )
                    await self._async_set_common_actuators_as_heaters()
                elif force_update_all and self._hvac_mode == HVACMode.HEAT_COOL:
                    LOGGER.debug(
                        "Setting common actuators  %s as heaters for HVAC group %s",
                        ",".join(self.common_actuators.keys()),
                        self.entity_id,
                    )
                    await self._async_set_common_actuators_as_heaters()
            elif needs_cooling:
                if not self._is_cooling and self._hvac_mode in [
                    HVACMode.COOL,
                    HVACMode.HEAT_COOL,
                ]:
                    LOGGER.debug(
                        "Setting common actuators  %s as coolers for HVAC group %s",
                        ",".join(self.common_actuators.keys()),
                        self.entity_id,
                    )
                    await self._async_set_common_actuators_as_coolers()
                elif force_update_all and self._hvac_mode == HVACMode.HEAT_COOL:
                    LOGGER.debug(
                        "Setting common actuators  %s as coolers for HVAC group %s",
                        ",".join(self.common_actuators.keys()),
                        self.entity_id,
                    )
                    await self._async_set_common_actuators_as_coolers()
            else:
                if (
                    (self._is_heating or update_actuators)
                    and self._toggle_heaters_on_threshold
                ) or (
                    (self._is_cooling or update_actuators)
                    and self._toggle_coolers_on_threshold
                ):
                    LOGGER.debug(
                        "Turning off common actuators  %s for HVAC group %s",
                        ",".join(self.common_actuators.keys()),
                        self.entity_id,
                    )
                    await self._async_turn_off_common_actuators()
                elif force_update_all and self._hvac_mode == HVACMode.HEAT_COOL:
                    LOGGER.debug(
                        "Setting common actuators  %s as heaters for HVAC group %s",
                        ",".join(self.common_actuators.keys()),
                        self.entity_id,
                    )
                    await self._async_set_common_actuators_as_heaters()

            self._is_cooling = needs_cooling
            self._is_heating = needs_heating
        finally:
            if self._changing_actuators_lock.locked():
                self._changing_actuators_lock.release()

    def _update_hvac_modes(self, actuator_type: HvacActuatorType, state: State) -> None:
        """Update the HVAC modes available for the group when a new actuator is loaded."""

        required_mode = (
            HVACMode.HEAT if actuator_type == HvacActuatorType.HEATER else HVACMode.COOL
        )
        opposite_mode = (
            HVACMode.COOL if actuator_type == HvacActuatorType.HEATER else HVACMode.HEAT
        )
        if not (
            required_mode in self._attr_hvac_modes
            or HVACMode.HEAT_COOL in self._attr_hvac_modes
        ):
            if opposite_mode in self._attr_hvac_modes:
                self._attr_hvac_modes.remove(opposite_mode)
                self._attr_hvac_modes.append(HVACMode.HEAT_COOL)
                self._attr_supported_features = (
                    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                )
            else:
                self._attr_hvac_modes.append(required_mode)

        if (
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            in state.attributes[ATTR_SUPPORTED_FEATURES]
            or ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            in self._attr_supported_features
        ):
            self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )
        else:
            self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def _add_heater(self, heater_entity_id: str) -> None:
        """Add a heater actuator referenced by entity_id."""
        if heater_entity_id in self._heaters:
            return

        heater = HvacGroupHeater(self.hass, heater_entity_id)
        self._heaters.update({heater_entity_id: heater})

        if heater.state:
            self._update_hvac_modes(HvacActuatorType.HEATER, heater.state)

    def _add_cooler(self, cooler_entity_id: str) -> None:
        """Add a heater actuator referenced by entity_id."""
        if cooler_entity_id in self._coolers:
            return

        cooler = HvacGroupCooler(self.hass, cooler_entity_id)
        self._coolers.update({cooler_entity_id: cooler})

        if cooler.state:
            self._update_hvac_modes(HvacActuatorType.HEATER, cooler.state)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode callback."""
        if hvac_mode not in self._attr_hvac_modes:
            LOGGER.warning("Unsupported hvac mode: %s", hvac_mode)
            return

        LOGGER.debug("Setting mode %s on HVAC group %s", hvac_mode, self.entity_id)

        self._hvac_mode = hvac_mode
        self._require_actuator_mass_refresh = True
        await self.async_defer_or_update_ha_state(update_actuators=True)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)

        if temp_low is not None:
            self._target_temp_low = temp_low

        if temp_high is not None:
            self._target_temp_high = temp_high

        if temp is not None:
            self._target_temperature = temp

        if hvac_mode is not None and hvac_mode in self._attr_hvac_modes:
            self._hvac_mode = hvac_mode

        LOGGER.debug(
            "Setting temperature (%s) on HVAC group %s",
            f"{temp_low}-{temp_high}"
            if ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            in self._attr_supported_features
            else f"{temp}",
            self.entity_id,
        )

        self._require_actuator_mass_refresh = True
        await self.async_defer_or_update_ha_state(update_actuators=True)

    async def _async_turn_on_coolers(self, pure: bool = False) -> None:
        """Turn on coolers. If `pure` is `True`, it only affects coolers which are not also heaters."""
        if not self._coolers:
            return

        self._are_coolers_active = True
        targets: HvacGroupActuatorDict = (
            HvacGroupActuatorDict(
                {
                    entity_id: cooler
                    for entity_id, cooler in self._coolers.items()
                    if entity_id not in self._heaters
                }
            )
            if pure
            else self._coolers
        )
        await targets.async_turn_on(
            temperature=self.target_temperature,
            target_temp_high=self.target_temperature_high,
            target_temp_low=self.target_temperature_low,
            context=self._context,
        )

    async def _async_turn_off_coolers(self, pure: bool = False) -> None:
        """Turn off coolers. If `pure` is `True`, it only affects coolers which are not also heaters."""
        if not self._coolers:
            return

        self._are_coolers_active = False
        targets: HvacGroupActuatorDict = (
            HvacGroupActuatorDict(
                {
                    entity_id: cooler
                    for entity_id, cooler in self._coolers.items()
                    if entity_id not in self._heaters
                }
            )
            if pure
            else self._coolers
        )
        await targets.async_turn_off(
            temperature=self.target_temperature,
            target_temp_high=self.target_temperature_high,
            target_temp_low=self.target_temperature_low,
            context=self._context,
        )

    async def _async_turn_on_heaters(self, pure: bool = False) -> None:
        """Turn on heaters. If `pure` is `True`, it only affects heaters which are not also coolers."""
        if not self._heaters:
            return

        self._are_heaters_active = True
        targets: HvacGroupActuatorDict = (
            HvacGroupActuatorDict(
                {
                    entity_id: heater
                    for entity_id, heater in self._heaters.items()
                    if entity_id not in self._coolers
                }
            )
            if pure
            else self._heaters
        )
        await targets.async_turn_on(
            temperature=self.target_temperature,
            target_temp_high=self.target_temperature_high,
            target_temp_low=self.target_temperature_low,
            context=self._context,
        )

    async def _async_turn_off_heaters(self, pure: bool = False) -> None:
        """Turn off heaters. If `pure` is `True`, it only affects heaters which are not also coolers."""
        if not self._heaters:
            return

        self._are_heaters_active = False
        targets: HvacGroupActuatorDict = (
            HvacGroupActuatorDict(
                {
                    entity_id: heater
                    for entity_id, heater in self._heaters.items()
                    if entity_id not in self._coolers
                }
            )
            if pure
            else self._heaters
        )
        await targets.async_turn_off(
            temperature=self.target_temperature,
            target_temp_high=self.target_temperature_high,
            target_temp_low=self.target_temperature_low,
            context=self._context,
        )

    async def _async_set_common_actuators_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn on common actuators to a certain HVAC mode."""
        await self.common_actuators.async_set_temperature(
            temperature=self.target_temperature,
            target_temp_high=self.target_temperature_high,
            target_temp_low=self.target_temperature_low,
            hvac_mode=hvac_mode,
            context=self._context,
        )

    async def _async_set_common_actuators_temperature(self) -> None:
        """Set temperature on common actuators."""
        await self.common_actuators.async_set_temperature(
            temperature=self.target_temperature,
            target_temp_high=self.target_temperature_high,
            target_temp_low=self.target_temperature_low,
            context=self._context,
        )

    async def _async_set_common_actuators_as_heaters(self) -> None:
        """Set common actuators to work as heaters."""
        await self.heaters_that_are_also_coolers.async_set_temperature(
            temperature=self.target_temperature,
            target_temp_high=self.target_temperature_high,
            target_temp_low=self.target_temperature_low,
            hvac_mode=HVACMode.HEAT,
            context=self._context,
        )

    async def _async_set_common_actuators_as_coolers(self) -> None:
        """Set common actuators to work as coolers."""
        await self.coolers_that_are_also_heaters.async_set_temperature(
            temperature=self.target_temperature,
            target_temp_high=self.target_temperature_high,
            target_temp_low=self.target_temperature_low,
            hvac_mode=HVACMode.COOL,
            context=self._context,
        )

    async def _async_turn_off_common_actuators(self) -> None:
        """Turn off common actuators."""
        await self.common_actuators.async_set_temperature(
            temperature=self.target_temperature,
            target_temp_high=self.target_temperature_high,
            target_temp_low=self.target_temperature_low,
            hvac_mode=HVACMode.OFF,
            context=self._context,
        )
