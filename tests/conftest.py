"""pytest fixtures."""

import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from pytest_homeassistant_custom_component.common import MockConfigEntry


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable loading custom integrations in all tests."""
    yield


@pytest.fixture
@pytest.mark.asyncio
async def climate_entities(enable_custom_integrations, hass: HomeAssistant):
    """Generate some climate entities."""
    entry1 = MockConfigEntry(
        domain="climate",
        title="HVAC group 1",
        unique_id="123456789",
        data={
            "platform": "generic_thermostat",
            "name": "Heater single target",
            "heater": "switch.heater_single_target",
            "target_sensor": "sensor.heater_single_target",
            "min_temp": 20,
            "max_temp": 30,
            "ac_mode": False,
        },
    )
    entry1.add_to_hass(hass)
    await hass.config_entries.async_setup(entry1.entry_id)

    entry2 = MockConfigEntry(
        domain="climate",
        title="HVAC group 2",
        unique_id="098765432",
        data={
            "platform": "generic_thermostat",
            "name": "Cooler single target",
            "heater": "switch.cooler_single_target",
            "target_sensor": "sensor.cooler_single_target",
            "min_temp": 16,
            "max_temp": 28,
            "ac_mode": True,
        },
    )
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)

    await hass.async_block_till_done()


@pytest.fixture
@pytest.mark.asyncio
async def heater_single_target(enable_custom_integrations, hass: HomeAssistant):
    """Generate a heater with a simple (non-ranged) target temperature."""
    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: {
                "platform": "generic_thermostat",
                "name": "Heater single target",
                "heater": "switch.heater_single_target",
                "target_sensor": "sensor.heater_single_target",
                "min_temp": 20,
                "max_temp": 30,
                "ac_mode": False,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
@pytest.mark.asyncio
async def heater_ranged_target(enable_custom_integrations, hass: HomeAssistant):
    """Generate a heater with a ranged (min-max) target temperature."""
    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: {
                "platform": "demo",
                "name": "Heater ranged target",
                "heater": "switch.heater_ranged_target",
                "target_sensor": "sensor.heater_ranged_target",
                "min_temp": 20,
                "max_temp": 30,
                "target_temp_low": 23,
                "target_temp_high": 25,
                "ac_mode": False,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
@pytest.mark.asyncio
async def cooler_single_target(enable_custom_integrations, hass: HomeAssistant):
    """Generate a cooler with a simple (non-ranged) target temperature."""
    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: {
                "platform": "generic_thermostat",
                "name": "Cooler single target",
                "heater": "switch.cooler_single_target",
                "target_sensor": "sensor.cooler_single_target",
                "min_temp": 15,
                "max_temp": 32,
                "ac_mode": True,
            }
        },
    )
    await hass.async_block_till_done()
