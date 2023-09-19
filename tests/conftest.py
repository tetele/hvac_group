"""pytest fixtures."""

import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


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
    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: [
                {
                    "platform": "generic_thermostat",
                    "name": "Cooler single target",
                    "heater": "switch.cooler_single_target",
                    "target_sensor": "sensor.cooler_single_target",
                    "min_temp": 15,
                    "max_temp": 32,
                    "ac_mode": True,
                },
                {
                    "platform": "generic_thermostat",
                    "name": "Heater single target",
                    "heater": "switch.heater_single_target",
                    "target_sensor": "sensor.heater_single_target",
                    "min_temp": 20,
                    "max_temp": 30,
                    "ac_mode": False,
                },
                {
                    "platform": "generic_thermostat",
                    "name": "Heater ranged target",
                    "heater": "switch.heater_ranged_target",
                    "target_sensor": "sensor.heater_ranged_target",
                    "min_temp": 20,
                    "max_temp": 30,
                    "ac_mode": False,
                },
            ]
        },
    )
    await hass.async_block_till_done()
