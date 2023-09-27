"""pytest fixtures."""

from unittest.mock import patch
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.demo import DOMAIN as DEMO_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.setup import async_setup_component


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable loading custom integrations in all tests."""
    yield


@pytest.fixture(autouse=True)
@pytest.mark.asyncio
async def auto_setup_homeassistant(hass: HomeAssistant):
    """Automatically load homeassistant component."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()


@pytest.fixture
@pytest.mark.asyncio
async def only_climate_for_demo() -> None:
    """Enable only the climate platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.CLIMATE],
    ):
        yield


@pytest.fixture
@pytest.mark.asyncio
async def climate_entities(only_climate_for_demo, hass: HomeAssistant):
    """Generate some climate entities."""
    # assert await async_setup_component(hass, DEMO_DOMAIN, {DEMO_DOMAIN: {}})
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
                    "target_temp": 32,
                },
                {
                    "platform": "generic_thermostat",
                    "name": "Heater single target",
                    "heater": "switch.heater_single_target",
                    "target_sensor": "sensor.heater_single_target",
                    "min_temp": 20,
                    "max_temp": 35,
                    "ac_mode": False,
                },
            ]
        },
    )
    assert await async_setup_component(hass, DEMO_DOMAIN, {})
    await hass.async_block_till_done()
