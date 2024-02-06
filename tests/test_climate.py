"""The tests for the hvac_group climate platform."""

from typing import Any
from unittest.mock import patch
import pytest

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
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
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

CONFIG_DEFAULT_GROUP = {
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
}


# @pytest.fixture
# def calls(hass: HomeAssistant) -> list[ServiceCall]:
#     """Track calls to a mock service."""
#     return async_mock_service(hass, "climate", "set_temperature")


@pytest.fixture
@pytest.mark.asyncio
async def setup_dependencies(hass: HomeAssistant, setup_extras) -> None:
    """Set up dependencies like climate entities and temp sensor."""
    if setup_extras is None:
        setup_extras = {}

    assert await async_setup_component(hass, CLIMATE_DOMAIN, {})

    setup_defaults = {
        DEMO_COOLER_HEATER: ("off", DEMO_SINGLE_TEMP_CLIMATE_ATTRIBUTES),
        DEMO_COOLER_SINGLE_TEMP: ("off", DEMO_SINGLE_TEMP_CLIMATE_ATTRIBUTES),
        DEMO_COOLER_TEMP_RANGE: ("off", DEMO_TEMP_RANGE_CLIMATE_ATTRIBUTES),
        DEMO_HEATER_SINGLE_TEMP: ("off", DEMO_SINGLE_TEMP_CLIMATE_ATTRIBUTES),
        DEMO_HEATER_TEMP_RANGE: ("off", DEMO_TEMP_RANGE_CLIMATE_ATTRIBUTES),
        DEMO_TEMP_SENSOR: ("22.5", {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE}),
    }

    for entity_id, (state, attributes) in setup_defaults.items():
        if overrides := setup_extras.get(entity_id):
            state_override, attributes_override = overrides
            if state_override is not None:
                state = state_override
            if attributes_override:
                attributes.update(attributes_override)
        hass.states.async_set(entity_id, state, attributes)
    await hass.async_block_till_done()


@pytest.fixture
@pytest.mark.asyncio
async def hvac_group_entry(
    setup_dependencies, hass: HomeAssistant, group_extras
) -> ConfigEntry:
    """Set up a group."""
    if group_extras is None:
        group_extras = {}

    entry = MockConfigEntry(
        title=group_extras.get("title") or "HVAC group 1",
        domain=DOMAIN,
        options=CONFIG_DEFAULT_GROUP | group_extras.get("options", {}),
        unique_id=group_extras.get("unique_id") or "uniq-1",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    data = {}
    if target_temp_low := group_extras.get(ATTR_TARGET_TEMP_LOW):
        data[ATTR_TARGET_TEMP_LOW] = target_temp_low
    if target_temp_high := group_extras.get(ATTR_TARGET_TEMP_HIGH):
        data[ATTR_TARGET_TEMP_HIGH] = target_temp_high
    if target_temp := group_extras.get(ATTR_TEMPERATURE):
        data[ATTR_TEMPERATURE] = target_temp
    if hvac_mode := group_extras.get(ATTR_HVAC_MODE):
        data[ATTR_HVAC_MODE] = hvac_mode

    if data:
        entity_registry = er.async_get(hass)
        if entity_id := entity_registry.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, entry.entry_id
        ):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                service_data=data,
                target={CONF_ENTITY_ID: entity_id},
                blocking=True,
            )

    return entry


@pytest.mark.parametrize(("setup_extras", "group_extras"), [({}, {})])
@pytest.mark.asyncio
async def test_setup(
    hass: HomeAssistant,
    setup_extras,
    group_extras,
    hvac_group_entry,
) -> None:
    """Test platform setup."""

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
        "custom_components.hvac_group.actuator.HvacGroupActuator._async_call_climate_service"
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
    ("setup_extras", "group_extras", "command", "output"),
    [
        # Test 0 - Check temp ranges
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
        # Test 1 - check that common actuators become coolers when temp too high
        (
            {DEMO_TEMP_SENSOR: (22.5, {})},
            {
                ATTR_TARGET_TEMP_LOW: 21,
                ATTR_TARGET_TEMP_HIGH: 23,
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            },
            {DEMO_TEMP_SENSOR: (25, {})},  # just update the current temp
            {
                DEMO_COOLER_HEATER: {
                    ATTR_TEMPERATURE: 23,
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
            },
        ),
        # Test 2 - check cooler toggles
        (
            {DEMO_TEMP_SENSOR: (22.5, {})},
            {"options": {CONF_TOGGLE_COOLERS: True, CONF_TOGGLE_HEATERS: True}},
            {
                ATTR_TARGET_TEMP_LOW: 21,
                ATTR_TARGET_TEMP_HIGH: 23,
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            },
            {
                DEMO_COOLER_SINGLE_TEMP: {
                    ATTR_HVAC_MODE: HVACMode.OFF,
                },
                DEMO_COOLER_TEMP_RANGE: {
                    ATTR_HVAC_MODE: HVACMode.OFF,
                },
                DEMO_HEATER_SINGLE_TEMP: {
                    ATTR_HVAC_MODE: HVACMode.OFF,
                },
                DEMO_HEATER_TEMP_RANGE: {
                    ATTR_HVAC_MODE: HVACMode.OFF,
                },
                DEMO_COOLER_HEATER: {
                    ATTR_HVAC_MODE: HVACMode.OFF,
                },
            },
        ),
        # Test 3 - check cooler toggles, coolers active
        (
            {DEMO_TEMP_SENSOR: (27, {})},
            {"options": {CONF_TOGGLE_COOLERS: True, CONF_TOGGLE_HEATERS: True}},
            {
                ATTR_TARGET_TEMP_LOW: 21,
                ATTR_TARGET_TEMP_HIGH: 23,
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            },
            {
                DEMO_COOLER_SINGLE_TEMP: {
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
                DEMO_COOLER_TEMP_RANGE: {
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
                DEMO_HEATER_SINGLE_TEMP: {
                    ATTR_HVAC_MODE: HVACMode.OFF,
                },
                DEMO_HEATER_TEMP_RANGE: {
                    ATTR_HVAC_MODE: HVACMode.OFF,
                },
                DEMO_COOLER_HEATER: {
                    ATTR_HVAC_MODE: HVACMode.COOL,
                },
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_call_forwarding(
    hass: HomeAssistant,
    setup_extras,
    group_extras,
    command,
    output,
    hvac_group_entry: ConfigEntry,
) -> None:
    """Test whether the actuators get a correct service call."""

    hvac_group_entity_id = er.async_get(hass).async_get_entity_id(
        CLIMATE_DOMAIN, DOMAIN, hvac_group_entry.entry_id
    )
    assert hvac_group_entity_id

    with patch(
        "custom_components.hvac_group.actuator.HvacGroupActuator._async_call_climate_service"
    ) as mock_call_climate_service:
        # command_args is a dict with keys representing actuators or the temp sensor
        service_call_data = {}
        if command.get(ATTR_TARGET_TEMP_LOW):
            service_call_data[ATTR_TARGET_TEMP_LOW] = command[ATTR_TARGET_TEMP_LOW]
        if command.get(ATTR_TARGET_TEMP_HIGH):
            service_call_data[ATTR_TARGET_TEMP_HIGH] = command[ATTR_TARGET_TEMP_HIGH]
        if command.get(ATTR_HVAC_MODE):
            service_call_data[ATTR_HVAC_MODE] = command[ATTR_HVAC_MODE]

        # Send the command if any required args are present
        if service_call_data:
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                service_call_data,
                target={CONF_ENTITY_ID: hvac_group_entity_id},
                blocking=True,
            )

        # Update temp sensor if required. Data is a tuple (state, attributes)
        if temp_sensor_update := command.get(DEMO_TEMP_SENSOR):
            hass.states.async_set(
                DEMO_TEMP_SENSOR, temp_sensor_update[0], temp_sensor_update[1]
            )
        await hass.async_block_till_done()

        assert mock_call_climate_service.called

        # Check if calls to climate.set_temperature include the expected args
        for call in mock_call_climate_service.call_args_list:
            expected_args: dict[str, Any] = output.get(call.args[0], {})
            assert expected_args.items() <= call.args[2].items(), (
                f"{call.args[0]} expected a call with {expected_args}, "
                f"actual value was {call.args[2]}"
            )
