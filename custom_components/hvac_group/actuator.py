"""HvacActuator library and dependencies."""

import asyncio
from collections.abc import Callable, Coroutine
from enum import StrEnum
from functools import reduce
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.core import Context, HomeAssistant, State

from .const import LOGGER


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
        if ClimateEntityFeature.TARGET_TEMPERATURE_RANGE & self.state.attributes.get(
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

    async def async_call_climate_service(
        self, service: str, data: dict[str, Any]
    ) -> None:
        """Public wrapper for calling a climate service."""
        await self._async_call_climate_service(
            entity_id=self._entity_id, service=service, data=data
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

    @property
    def loaded(self) -> bool:
        """State whether a dict of actuators was loaded or not."""

        return reduce(
            lambda prev, cur: prev and cur,
            (act.loaded for act in self.values()),
            True,
        )

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


async def create_coro(function: Callable, *args, **kwargs) -> Any:
    """Create a coro wrapper used to patch methods in tests."""
    LOGGER.debug("Running coroutine %s(%s)", function, args)
    return await function(*args, **kwargs)
