"""Test config flow for the HVAC Group integration."""
import pytest

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.config_entries import ConfigEntry, ConfigEntryState

from custom_components.hvac_group import DOMAIN


@pytest.mark.asyncio
async def test_config_flow(enable_custom_integrations, hass: HomeAssistant):
    """Test HVAC Group config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "test hvac", "temperature_entity_id": "climate.bedroom_ac"},
    )

    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    config_entry: ConfigEntry = result["result"]
    assert config_entry.state == ConfigEntryState.LOADED

    assert hass.states.get(f"{CLIMATE_DOMAIN}.test_hvac")
