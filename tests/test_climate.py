"""The tests for the hvac_group climate platform."""
from unittest.mock import AsyncMock, patch
from typing import Any
import copy

import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.const import PRECISION_HALVES, PRECISION_TENTHS
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import NoEntitySpecifiedError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import EventStateChangedData
from homeassistant.helpers.typing import EventType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hvac_group import DOMAIN
from custom_components.hvac_group.climate import (
    HvacGroupClimateEntity,
    HvacGroupActuator,
    HvacGroupCooler,
    HvacGroupHeater,
    async_setup_entry,
)

# from homeassistant.components.climate import HVACMode


class MockHvacGroupClimateEntity(HvacGroupClimateEntity):
    """Mock HVAC Group to use in tests."""

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return 0


@pytest.fixture
def initialize_actuators(hass: HomeAssistant) -> None:
    """Fixture which sets actuators (heaters/coolers)."""

    hass.states.async_set(
        "climate.heater",
        "heat",
        {
            "min_temp": 11,
            "max_temp": 28,
            "temperature": 21,
            "current_temperature": 21.5,
            "supported_features": ClimateEntityFeature.TARGET_TEMPERATURE,
        },
    )
    hass.states.async_set(
        "climate.hvac1",
        "heat",
        {
            "min_temp": 13,
            "max_temp": 34,
            "target_temp_low": 20,
            "target_temp_high": 22,
            "current_temperature": 21.8,
            "supported_features": ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        },
    )
    hass.states.async_set(
        "climate.cooler",
        "cool",
        {
            "min_temp": 16,
            "max_temp": 30,
            "temperature": 23,
            "current_temperature": 21.2,
            "supported_features": ClimateEntityFeature.TARGET_TEMPERATURE,
        },
    )
    hass.states.async_set(
        "climate.hvac",
        "cool",
        {
            "min_temp": 15,
            "max_temp": 34,
            "target_temp_low": 21,
            "target_temp_high": 23,
            "current_temperature": 21,
            "supported_features": ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        },
    )


def _generate_event(
    hass: HomeAssistant,
    entity_id: str,
    state: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> EventType[EventStateChangedData]:
    """Generate an event which symbolizes a state change."""

    old_state = hass.states.get(entity_id) or State(entity_id, "")
    new_state = copy.copy(old_state)

    if state is not None:
        new_state.state = state

    if attributes is not None:
        new_state.attributes = new_state.attributes | attributes

    event = EventType(
        "EventStateChangedData",
        {
            "entity_id": entity_id,
            "new_state": new_state,
            "old_state": old_state,
        },
    )

    return event


@pytest.mark.asyncio
@pytest.fixture
async def hvac_group(hass: HomeAssistant) -> HvacGroupClimateEntity:
    """Fixture which contains a created component."""
    config = {
        "temperature_entity_id": "climate.heater",
        "heaters": ["climate.heater", "climate.hvac1"],
        "coolers": ["climate.cooler", "climate.hvac"],
        "toggle_coolers": False,
        "toggle_heaters": False,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        options=config,
    )
    mock_async_add_entities = AsyncMock(AddEntitiesCallback)

    await async_setup_entry(
        hass, config_entry=entry, async_add_entities=mock_async_add_entities
    )

    mock_async_add_entities.assert_called()

    hvac_entity: HvacGroupClimateEntity = mock_async_add_entities.call_args.args[0][0]

    return hvac_entity


@pytest.mark.asyncio
async def test_entry(hvac_group: HvacGroupClimateEntity, hass: HomeAssistant) -> None:
    """Test component creation."""

    assert hvac_group._temperature_sensor_entity_id == "climate.heater"

    assert hvac_group.precision == PRECISION_TENTHS
    assert hvac_group.target_temperature_step == PRECISION_HALVES
    assert hvac_group.temperature_unit == hass.config.units.temperature_unit
    assert HVACMode.OFF in hvac_group.hvac_modes
    assert HVACMode.HEAT_COOL in hvac_group.hvac_modes
    assert HVACMode.HEAT not in hvac_group.hvac_modes
    assert HVACMode.COOL not in hvac_group.hvac_modes


@pytest.mark.parametrize(
    ("temperature", "temp_low", "temp_high", "actuator_class", "expected"),
    [
        (21, None, None, HvacGroupCooler, 21),
        (None, 19, 26, HvacGroupCooler, 26),
        (21, None, None, HvacGroupHeater, 21),
        (None, 19, 26, HvacGroupHeater, 19),
        (21, None, None, HvacGroupActuator, 21),
        (None, 12, 16, HvacGroupActuator, None),
    ],
)
def test_guess_temperature(
    hass: HomeAssistant, temperature, temp_high, temp_low, actuator_class, expected
) -> None:
    """Test temperature guessing."""
    actuator = actuator_class(hass, "test.id")
    assert (
        actuator._guess_target_temperature(
            temperature=temperature,
            target_temp_low=temp_low,
            target_temp_high=temp_high,
        )
        == expected
    )


@pytest.mark.asyncio
async def test_control_hvac(
    initialize_actuators, hvac_group: HvacGroupClimateEntity, hass: HomeAssistant
) -> None:
    """Test control HVAC."""

    with patch.object(hvac_group, "_async_turn_device") as hvac_turn_device:
        try:
            await hvac_group._async_control_hvac()
        except NoEntitySpecifiedError:
            assert not hvac_turn_device.called
        else:
            pass

    with patch.object(hvac_group, "_async_turn_device") as hvac_turn_device, patch(
        "homeassistant.core.ServiceRegistry.async_call"
    ) as hass_service_call:
        try:
            await hvac_group.async_set_hvac_mode(HVACMode.HEAT_COOL)
        except NoEntitySpecifiedError:
            assert len(hvac_turn_device.mock_calls) == 4
            for call in hass_service_call.mock_calls:
                match call.kwargs["target"]["entity_id"]:
                    case "climate.cooler":
                        assert call.args[2] == {
                            "temperature": hvac_group.target_temperature_high
                        }
                    case "climate.heater":
                        assert call.args[2] == {
                            "temperature": hvac_group.target_temperature_low
                        }
                    case "climate.hvac":
                        assert call.args[2] == {
                            "target_temp_high": hvac_group.target_temperature_high,
                            "target_temp_low": hvac_group.target_temperature_low,
                        }
                    case "climate.hvac1":
                        assert call.args[2] == {
                            "target_temp_high": hvac_group.target_temperature_high,
                            "target_temp_low": hvac_group.target_temperature_low,
                        }

        else:
            pass

    with patch("homeassistant.core.ServiceRegistry.async_call") as hass_service_call:
        try:
            await hvac_group.async_set_temperature(
                target_temp_low=23, target_temp_high=25
            )
        except NoEntitySpecifiedError:
            assert hvac_group.target_temperature_low == 23
            assert hvac_group.target_temperature_high == 25
            for call in hass_service_call.mock_calls:
                match call.kwargs["target"]["entity_id"]:
                    case "climate.cooler":
                        assert call.args[2] == {
                            "temperature": hvac_group.target_temperature_high
                        }
                    case "climate.heater":
                        assert call.args[2] == {
                            "temperature": hvac_group.target_temperature_low
                        }
                    case "climate.hvac":
                        assert call.args[2] == {
                            "target_temp_high": hvac_group.target_temperature_high,
                            "target_temp_low": hvac_group.target_temperature_low,
                        }
                    case "climate.hvac1":
                        assert call.args[2] == {
                            "target_temp_high": hvac_group.target_temperature_high,
                            "target_temp_low": hvac_group.target_temperature_low,
                        }
        else:
            pass
