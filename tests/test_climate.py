"""The tests for the hvac_group climate platform."""

import pytest
from typing import Any
from unittest.mock import patch

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_MIN_TEMP,
    ATTR_MAX_TEMP,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_UNIQUE_ID,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.hvac_group.const import (
    CONF_HEATERS,
    CONF_COOLERS,
    CONF_TOGGLE_COOLERS,
    CONF_TOGGLE_HEATERS,
    CONF_CURRENT_TEMPERATURE_ENTITY_ID,
    DOMAIN,
)


HVAC_GROUP = "climate.hvac_group"
DEMO_HEATER_SINGLE_TEMP = "climate.heater_single_temp"
DEMO_HEATER_TEMP_RANGE = "climate.heater_temp_range"
DEMO_COOLER_SINGLE_TEMP = "climate.cooler_single_temp"
DEMO_COOLER_TEMP_RANGE = "climate.cooler_temp_range"
DEMO_COOLER_HEATER = "climate.cooler_heater"
DEMO_TEMP_SENSOR = "sensor.temperature_sensor"

DEMO_GENERIC_CLIMATE_ATTRIBUTES = {
    ATTR_MIN_TEMP: "17",
    ATTR_MAX_TEMP: "32",
}
DEMO_SINGLE_TEMP_CLIMATE_ATTRIBUTES = DEMO_GENERIC_CLIMATE_ATTRIBUTES | {
    ATTR_TEMPERATURE: "23",
    ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
}
DEMO_TEMP_RANGE_CLIMATE_ATTRIBUTES = DEMO_GENERIC_CLIMATE_ATTRIBUTES | {
    ATTR_TARGET_TEMP_LOW: "21",
    ATTR_TARGET_TEMP_HIGH: "23",
    ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
}

CONFIG_NO_TOGGLE = {
    CONF_PLATFORM: DOMAIN,
    CONF_NAME: "Test HVAC",
    CONF_HEATERS: [
        DEMO_HEATER_SINGLE_TEMP,
        DEMO_HEATER_TEMP_RANGE,
        DEMO_COOLER_HEATER,
    ],
    CONF_TOGGLE_HEATERS: False,
    CONF_COOLERS: [
        DEMO_COOLER_SINGLE_TEMP,
        DEMO_COOLER_TEMP_RANGE,
        DEMO_COOLER_HEATER,
    ],
    CONF_TOGGLE_COOLERS: False,
    CONF_CURRENT_TEMPERATURE_ENTITY_ID: DEMO_TEMP_SENSOR,
    CONF_UNIQUE_ID: "uniq-1",
}


# @pytest.fixture
# def calls(hass: HomeAssistant) -> list[ServiceCall]:
#     """Track calls to a mock service."""
#     return async_mock_service(hass, "climate", "set_temperature")


@pytest.fixture
@pytest.mark.asyncio
async def setup_dependencies(hass: HomeAssistant) -> None:
    """Set up dependencies like climate entities and temp sensor."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, {})

    hass.states.async_set(
        DEMO_COOLER_HEATER, "off", DEMO_SINGLE_TEMP_CLIMATE_ATTRIBUTES
    )
    hass.states.async_set(
        DEMO_COOLER_SINGLE_TEMP, "off", DEMO_SINGLE_TEMP_CLIMATE_ATTRIBUTES
    )
    hass.states.async_set(
        DEMO_COOLER_TEMP_RANGE, "off", DEMO_TEMP_RANGE_CLIMATE_ATTRIBUTES
    )
    hass.states.async_set(
        DEMO_HEATER_SINGLE_TEMP, "off", DEMO_SINGLE_TEMP_CLIMATE_ATTRIBUTES
    )
    hass.states.async_set(
        DEMO_HEATER_TEMP_RANGE, "off", DEMO_TEMP_RANGE_CLIMATE_ATTRIBUTES
    )
    hass.states.async_set(
        DEMO_TEMP_SENSOR, "22.5", {ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE}
    )
    await hass.async_block_till_done()


@pytest.fixture
@pytest.mark.asyncio
async def hvac_group_entry(setup_dependencies, hass: HomeAssistant) -> ConfigEntry:
    """Set up a group."""
    entry = MockConfigEntry(
        title="HVAC group 1",
        domain=DOMAIN,
        options=CONFIG_NO_TOGGLE,
        unique_id=CONFIG_NO_TOGGLE[CONF_UNIQUE_ID],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    return entry


async def test_setup(
    hass: HomeAssistant,
    hvac_group_entry,
) -> None:
    """Test a test."""

    assert hvac_group_entry.state is ConfigEntryState.LOADED
    hvac_group = hass.states.get("climate.test_hvac")
    assert hvac_group
    assert hvac_group.state == HVACMode.OFF
    assert float(hvac_group.attributes.get(ATTR_MIN_TEMP)) == float(
        DEMO_GENERIC_CLIMATE_ATTRIBUTES[ATTR_MIN_TEMP]
    )
    assert float(hvac_group.attributes.get(ATTR_MAX_TEMP)) == float(
        DEMO_GENERIC_CLIMATE_ATTRIBUTES[ATTR_MAX_TEMP]
    )
    assert float(hvac_group.attributes.get(ATTR_CURRENT_TEMPERATURE)) == 22.5

    with patch(
        "custom_components.hvac_group.climate.HvacGroupActuator._async_call_climate_service"
    ) as mock_call_climate_service:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_TARGET_TEMP_LOW: 21,
                ATTR_TARGET_TEMP_HIGH: 23,
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            },
            target={CONF_ENTITY_ID: "climate.test_hvac"},
            blocking=True,
        )

        assert mock_call_climate_service.call_count == 5


@pytest.mark.parametrize(
    "current_initial_command_output",
    # This is a tuple of (initial states, initial HVAC group service call, test command to HVAC group, expected output)
    # initial states is a dict entity_id: (state, attributes)
    # initial group service call is a dict of service call data
    # test command is a dict of service call data
    # expected output is a dict of entity_id: {service_call_attr: expected_sent_value}
    [
        # (
        #     {DEMO_TEMP_SENSOR: (22.5, {})},
        #     {
        #         ATTR_TARGET_TEMP_LOW: 21,
        #         ATTR_TARGET_TEMP_HIGH: 23,
        #         ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
        #     },
        #     {
        #         ATTR_TARGET_TEMP_LOW: 21,
        #         ATTR_TARGET_TEMP_HIGH: 23,
        #         ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
        #     },
        #     {
        #         DEMO_COOLER_SINGLE_TEMP: {
        #             ATTR_TEMPERATURE: 23,
        #             ATTR_HVAC_MODE: HVACMode.COOL,
        #         },
        #         DEMO_COOLER_TEMP_RANGE: {
        #             ATTR_TARGET_TEMP_LOW: 21,
        #             ATTR_TARGET_TEMP_HIGH: 23,
        #             ATTR_HVAC_MODE: HVACMode.COOL,
        #         },
        #         DEMO_HEATER_SINGLE_TEMP: {
        #             ATTR_TEMPERATURE: 21,
        #             ATTR_HVAC_MODE: HVACMode.HEAT,
        #         },
        #         DEMO_HEATER_TEMP_RANGE: {
        #             ATTR_TARGET_TEMP_LOW: 21,
        #             ATTR_TARGET_TEMP_HIGH: 23,
        #             ATTR_HVAC_MODE: HVACMode.HEAT,
        #         },
        #         DEMO_COOLER_HEATER: {
        #             ATTR_TEMPERATURE: 21,
        #             ATTR_HVAC_MODE: HVACMode.HEAT,
        #         },
        #     },
        # ),
        (
            {DEMO_TEMP_SENSOR: (22.5, {})},
            {},  # no initial group setup
            {
                ATTR_TARGET_TEMP_LOW: 21,
                ATTR_TARGET_TEMP_HIGH: 23,
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            },
            {
                DEMO_COOLER_SINGLE_TEMP: {
                    ATTR_TEMPERATURE: 23,
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
                DEMO_COOLER_TEMP_RANGE: {
                    ATTR_TARGET_TEMP_LOW: 21,
                    ATTR_TARGET_TEMP_HIGH: 23,
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
                DEMO_HEATER_SINGLE_TEMP: {
                    ATTR_TEMPERATURE: 21,
                    ATTR_HVAC_MODE: HVACMode.HEAT,
                },
                DEMO_HEATER_TEMP_RANGE: {
                    ATTR_TARGET_TEMP_LOW: 21,
                    ATTR_TARGET_TEMP_HIGH: 23,
                    ATTR_HVAC_MODE: HVACMode.HEAT,
                },
                DEMO_COOLER_HEATER: {
                    ATTR_TEMPERATURE: 21,
                    ATTR_HVAC_MODE: HVACMode.HEAT,
                },
            },
        ),
        (
            {DEMO_TEMP_SENSOR: (22.5, {})},
            {},  # no initial group setup
            {
                ATTR_TARGET_TEMP_LOW: 21,
                ATTR_TARGET_TEMP_HIGH: 23,
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            },
            {
                DEMO_COOLER_SINGLE_TEMP: {
                    ATTR_TEMPERATURE: 23,
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
                DEMO_COOLER_TEMP_RANGE: {
                    ATTR_TARGET_TEMP_LOW: 21,
                    ATTR_TARGET_TEMP_HIGH: 23,
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
                DEMO_HEATER_SINGLE_TEMP: {
                    ATTR_TEMPERATURE: 21,
                    ATTR_HVAC_MODE: HVACMode.HEAT,
                },
                DEMO_HEATER_TEMP_RANGE: {
                    ATTR_TARGET_TEMP_LOW: 21,
                    ATTR_TARGET_TEMP_HIGH: 23,
                    ATTR_HVAC_MODE: HVACMode.HEAT,
                },
                DEMO_COOLER_HEATER: {
                    ATTR_TEMPERATURE: 21,
                    ATTR_HVAC_MODE: HVACMode.HEAT,
                },
            },
        ),
        (
            {DEMO_TEMP_SENSOR: (22.5, {})},
            {
                ATTR_TARGET_TEMP_LOW: 21,
                ATTR_TARGET_TEMP_HIGH: 23,
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            },
            {DEMO_TEMP_SENSOR: (25, {})},  # just update the current temp
            {
                DEMO_COOLER_SINGLE_TEMP: {
                    ATTR_TEMPERATURE: 23,
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
                DEMO_COOLER_TEMP_RANGE: {
                    ATTR_TARGET_TEMP_LOW: 21,
                    ATTR_TARGET_TEMP_HIGH: 23,
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
                DEMO_HEATER_SINGLE_TEMP: {
                    ATTR_TEMPERATURE: 21,
                    ATTR_HVAC_MODE: HVACMode.HEAT,
                },
                DEMO_HEATER_TEMP_RANGE: {
                    ATTR_TARGET_TEMP_LOW: 21,
                    ATTR_TARGET_TEMP_HIGH: 23,
                    ATTR_HVAC_MODE: HVACMode.HEAT,
                },
                DEMO_COOLER_HEATER: {
                    ATTR_TEMPERATURE: 23,
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_call_forwarding(
    hass: HomeAssistant,
    hvac_group_entry: ConfigEntry,
    current_initial_command_output,
) -> None:
    """Test whether the actuators get a correct service call."""

    (
        initial_states,
        initial_group_args,
        command_args,
        output,
    ) = current_initial_command_output

    for entity_id, initial_state in initial_states.items():
        state, attributes = initial_state
        hass.states.async_set(entity_id, state, attributes)
    await hass.async_block_till_done()

    if initial_group_args:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_TARGET_TEMP_LOW: initial_group_args.get(ATTR_TARGET_TEMP_LOW, 21),
                ATTR_TARGET_TEMP_HIGH: initial_group_args.get(
                    ATTR_TARGET_TEMP_HIGH, 23
                ),
                ATTR_HVAC_MODE: initial_group_args.get(
                    ATTR_HVAC_MODE, HVACMode.HEAT_COOL
                ),
            },
            target={CONF_ENTITY_ID: "climate.test_hvac"},
            blocking=True,
        )
        await hass.async_block_till_done()

    with patch(
        "custom_components.hvac_group.climate.HvacGroupActuator._async_call_climate_service"
    ) as mock_call_climate_service:
        # command_args is a dict with keys representing actuators or the temp sensor
        service_call_data = {}
        if command_args.get(ATTR_TARGET_TEMP_LOW):
            service_call_data[ATTR_TARGET_TEMP_LOW] = command_args[ATTR_TARGET_TEMP_LOW]
        if command_args.get(ATTR_TARGET_TEMP_HIGH):
            service_call_data[ATTR_TARGET_TEMP_HIGH] = command_args[
                ATTR_TARGET_TEMP_HIGH
            ]
        if command_args.get(ATTR_HVAC_MODE):
            service_call_data[ATTR_HVAC_MODE] = command_args[ATTR_HVAC_MODE]

        # Send the command if any required args are present
        if service_call_data:
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                service_call_data,
                target={CONF_ENTITY_ID: "climate.test_hvac"},
                blocking=True,
            )

        # Update temp sensor if required. Data is a tuple (state, attributes)
        if temp_sensor_update := command_args.get(DEMO_TEMP_SENSOR):
            hass.states.async_set(
                DEMO_TEMP_SENSOR, temp_sensor_update[0], temp_sensor_update[1]
            )

        # Check if calls to climate.set_temperature include the expected args
        for call in mock_call_climate_service.call_args_list:
            expected_args: dict[str, Any] = output.get(call.args[0], {})
            assert (
                expected_args.items() <= call.args[2].items()
            ), f"{call.args[0]} expected a call with {expected_args}, actual value was {call.args[2]}"
