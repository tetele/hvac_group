"""Test config flow for the HVAC Group integration."""
import pytest

from homeassistant import config_entries
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_HIGH,
    DOMAIN as CLIMATE_DOMAIN,
    HVACAction,
    HVACMode,
    SERVICE_SET_TEMPERATURE,
    SERVICE_SET_HVAC_MODE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID

from custom_components.hvac_group import DOMAIN


@pytest.fixture
@pytest.mark.asyncio
async def hvac_group_config_entry(request, hass: HomeAssistant) -> FlowResult:
    """HVAC group fixture."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "test hvac",
        }
        | request.param,
    )

    await hass.async_block_till_done()

    return result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hvac_group_config_entry",
    [
        {
            "temperature_entity_id": "climate.cooler_single_target",
            "coolers": ["climate.cooler_single_target"],
            "heaters": [
                "climate.heater_single_target",
                "climate.ecobee",
            ],
        }
    ],
    indirect=True,
)
async def test_config_flow(
    climate_entities,
    hvac_group_config_entry,
    hass: HomeAssistant,
):
    """Test HVAC Group config flow."""

    hass.states.async_set("sensor.cooler_single_target", 21)

    assert hvac_group_config_entry["type"] == FlowResultType.CREATE_ENTRY
    config_entry: ConfigEntry = hvac_group_config_entry["result"]
    assert config_entry.state == ConfigEntryState.LOADED

    hvac_group = hass.states.get(f"{CLIMATE_DOMAIN}.test_hvac")
    assert hvac_group

    # Test available HVAC modes
    assert HVACMode.HEAT_COOL in hvac_group.attributes.get("hvac_modes")
    assert hvac_group.state == HVACMode.OFF
    assert hvac_group.attributes.get("hvac_action") == HVACAction.OFF
    assert hvac_group.attributes.get("min_temp") == 20
    assert hvac_group.attributes.get("max_temp") == 32

    # Test turning on
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        service_data={ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        target={ATTR_ENTITY_ID: "climate.test_hvac"},
    )
    await hass.async_block_till_done()

    # Test temperature setting
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        service_data={ATTR_TARGET_TEMP_LOW: 22, ATTR_TARGET_TEMP_HIGH: 25},
        target={ATTR_ENTITY_ID: "climate.test_hvac"},
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get("climate.cooler_single_target").attributes.get("temperature")
        == 32
    )  # because the cooler wasn't needed, so the temperature is the default
    assert (
        hass.states.get("climate.heater_single_target").attributes.get("temperature")
        == 22
    )
    assert hass.states.get("climate.ecobee").attributes.get("target_temp_low") == 22
    assert hass.states.get("climate.ecobee").attributes.get("target_temp_high") == 25


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hvac_group_config_entry",
    [
        {
            "temperature_entity_id": "climate.cooler_single_target",
            "coolers": ["climate.cooler_single_target"],
            "heaters": [
                "climate.heater_single_target",
                "climate.ecobee",
            ],
            "toggle_heaters": True,
            "toggle_coolers": True,
        }
    ],
    indirect=True,
)
async def test_toggle_actuators(
    climate_entities,
    hvac_group_config_entry,
    hass: HomeAssistant,
) -> None:
    """Test actuator toggling."""

    hass.states.async_set("sensor.cooler_single_target", 21)

    config_entry: ConfigEntry = hvac_group_config_entry["result"]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        service_data={ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        target={ATTR_ENTITY_ID: "climate.test_hvac"},
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        service_data={ATTR_TARGET_TEMP_LOW: 22, ATTR_TARGET_TEMP_HIGH: 25},
        target={ATTR_ENTITY_ID: "climate.test_hvac"},
    )
    await hass.async_block_till_done()

    hass.states.get(f"{CLIMATE_DOMAIN}.test_hvac")

    for heater in config_entry.options["heaters"]:
        heater_state = hass.states.get(heater)
        assert heater_state
        assert heater_state.state == HVACMode.HEAT
    for cooler in config_entry.options["coolers"]:
        cooler_state = hass.states.get(cooler)
        assert cooler_state
        assert cooler_state.state == HVACMode.OFF
