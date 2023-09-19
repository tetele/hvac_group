"""Test config flow for the HVAC Group integration."""
import pytest

from homeassistant import config_entries
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    HVACAction,
    HVACMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.config_entries import ConfigEntry, ConfigEntryState

from custom_components.hvac_group import DOMAIN


@pytest.mark.asyncio
async def test_1(climate_entities, hass: HomeAssistant):
    """Test test."""

    await hass.async_block_till_done()
    assert hass.states.get("climate.heater_single_target")
    assert hass.states.get("climate.cooler_single_target")


@pytest.mark.asyncio
async def test_2(
    heater_single_target,
    heater_ranged_target,
    cooler_single_target,
    hass: HomeAssistant,
):
    """Test test 2."""

    await hass.async_block_till_done()
    assert hass.states.get("climate.heater_single_target")
    assert hass.states.get("climate.cooler_single_target")


@pytest.mark.asyncio
async def test_config_flow(
    heater_single_target,
    heater_ranged_target,
    cooler_single_target,
    # climate_entities,
    hass: HomeAssistant,
):
    """Test HVAC Group config flow."""
    await hass.async_start()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "test hvac",
            "temperature_entity_id": "climate.cooler_single_target",
            "coolers": ["climate.cooler_single_target"],
            "heaters": [
                "climate.heater_single_target",
                "climate.heater_ranged_target",
            ],
        },
    )

    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    config_entry: ConfigEntry = result["result"]
    assert config_entry.state == ConfigEntryState.LOADED

    hvac_group = hass.states.get(f"{CLIMATE_DOMAIN}.test_hvac")
    assert hvac_group

    # Test available HVAC modes
    assert HVACMode.HEAT_COOL in hvac_group.attributes.get("hvac_modes")
    assert hvac_group.state == HVACMode.OFF
    assert hvac_group.attributes.get("hvac_action") == HVACAction.OFF
    assert hvac_group.attributes.get("min_temp") == 15
    assert hvac_group.attributes.get("max_temp") == 32
