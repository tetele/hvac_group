"""Tests for the HvacActuator and related classes."""

from unittest.mock import patch

from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from custom_components.hvac_group.actuator import (
    HvacActuatorType,
    HvacGroupActuatorDict,
    HvacGroupCooler,
    HvacGroupHeater,
)


async def test_init(hass: HomeAssistant) -> None:
    """Test initialization of components."""
    cooler = HvacGroupCooler(hass, "test.cooler")

    hass.states.async_set("test.cooler", "test", {})
    await hass.async_block_till_done()

    assert cooler.actuator_type == HvacActuatorType.COOLER
    assert cooler.entity_id == "test.cooler"
    assert cooler.state.entity_id == "test.cooler"
    assert cooler.state.state == "test"

    heater = HvacGroupHeater(hass, "test.heater")

    assert heater.actuator_type == HvacActuatorType.HEATER
    assert heater.entity_id == "test.heater"
    assert heater.state is None


def test_dict_creation(hass: HomeAssistant) -> None:
    """Test HvacActuatorDict creation."""

    coolers = HvacGroupActuatorDict({})

    coolers.update({"climate.1": HvacGroupCooler(hass, "climate.1")})
    coolers.update({"climate.2": HvacGroupCooler(hass, "climate.2")})

    assert coolers["climate.1"].actuator_type == HvacActuatorType.COOLER
    assert coolers["climate.2"].entity_id == "climate.2"


async def test_turn_on(hass: HomeAssistant) -> None:
    """Test the turn_on service on an actuator dict."""
    coolers = HvacGroupActuatorDict({})

    coolers.update({"climate.1": HvacGroupCooler(hass, "climate.1")})
    coolers.update({"climate.2": HvacGroupCooler(hass, "climate.2")})

    hass.states.async_set(
        "climate.1",
        "test",
        {ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE},
    )
    hass.states.async_set(
        "climate.2",
        "test",
        {ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE_RANGE},
    )
    await hass.async_block_till_done()

    with patch(
        "custom_components.hvac_group.actuator.HvacGroupActuator._async_call_climate_service"
    ) as mock_call_climate_service:
        await coolers.async_turn_on(
            target_temp_high=22, target_temp_low=20, context="asdf"
        )

        assert not mock_call_climate_service.called

        await coolers.async_commit()

        assert mock_call_climate_service.call_count == 2
        first_call = mock_call_climate_service.call_args_list[0][0]
        second_call = mock_call_climate_service.call_args_list[1][0]

        assert first_call[0] == "climate.1"
        assert first_call[1] == "set_temperature"
        assert first_call[2]["hvac_mode"] == HVACMode.COOL
        assert first_call[2]["temperature"] == 22

        assert second_call[0] == "climate.2"
        assert second_call[1] == "set_temperature"
        assert second_call[2]["hvac_mode"] == HVACMode.COOL
        assert second_call[2]["target_temp_high"] == 22
        assert second_call[2]["target_temp_low"] == 20

    heaters = HvacGroupActuatorDict({})

    heaters.update({"climate.1": HvacGroupHeater(hass, "climate.1")})
    heaters.update({"climate.2": HvacGroupHeater(hass, "climate.2")})

    hass.states.async_set(
        "climate.1",
        "test",
        {ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE},
    )
    hass.states.async_set(
        "climate.2",
        "test",
        {ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE_RANGE},
    )
    await hass.async_block_till_done()

    with patch(
        "custom_components.hvac_group.actuator.HvacGroupActuator._async_call_climate_service"
    ) as mock_call_climate_service:
        await heaters.async_turn_on(
            target_temp_high=22, target_temp_low=20, context="asdf"
        )

        assert not mock_call_climate_service.called

        await heaters.async_commit()

        assert mock_call_climate_service.call_count == 2
        first_call = mock_call_climate_service.call_args_list[0][0]
        second_call = mock_call_climate_service.call_args_list[1][0]

        assert first_call[0] == "climate.1"
        assert first_call[1] == "set_temperature"
        assert first_call[2]["hvac_mode"] == HVACMode.HEAT
        assert first_call[2]["temperature"] == 20

        assert second_call[0] == "climate.2"
        assert second_call[1] == "set_temperature"
        assert second_call[2]["hvac_mode"] == HVACMode.HEAT
        assert second_call[2]["target_temp_high"] == 22
        assert second_call[2]["target_temp_low"] == 20


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test the turn_off service on an actuator dict."""
    heaters = HvacGroupActuatorDict({})

    heaters.update({"climate.1": HvacGroupHeater(hass, "climate.1")})
    heaters.update({"climate.2": HvacGroupHeater(hass, "climate.2")})

    hass.states.async_set(
        "climate.1",
        "test",
        {ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE},
    )
    hass.states.async_set(
        "climate.2",
        "test",
        {ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE_RANGE},
    )
    await hass.async_block_till_done()

    with patch(
        "custom_components.hvac_group.actuator.HvacGroupActuator._async_call_climate_service"
    ) as mock_call_climate_service:
        await heaters.async_turn_off(
            target_temp_high=22, target_temp_low=20, context="asdf"
        )

        assert not mock_call_climate_service.called

        await heaters.async_commit()

        assert mock_call_climate_service.call_count == 2
        first_call = mock_call_climate_service.call_args_list[0][0]
        second_call = mock_call_climate_service.call_args_list[1][0]

        assert first_call[0] == "climate.1"
        assert first_call[1] == "set_temperature"
        assert first_call[2]["hvac_mode"] == HVACMode.OFF
        assert first_call[2]["temperature"] == 20

        assert second_call[0] == "climate.2"
        assert second_call[1] == "set_temperature"
        assert second_call[2]["hvac_mode"] == HVACMode.OFF
        assert second_call[2]["target_temp_high"] == 22
        assert second_call[2]["target_temp_low"] == 20
