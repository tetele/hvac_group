"""The tests for the hvac_group climate platform."""
from unittest.mock import AsyncMock

import pytest
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.const import PRECISION_HALVES, PRECISION_TENTHS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hvac_group import DOMAIN
from custom_components.hvac_group.climate import (
    HvacGroupClimateEntity,
    async_setup_entry,
)

# from homeassistant.components.climate import HVACMode


class MockHvacGroupClimateEntity(HvacGroupClimateEntity):
    """Mock HVAC Group to use in tests."""

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return 0


@pytest.mark.asyncio
async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test component creation."""
    config = {
        "temperature_entity_id": "sensor.bedroom_temperature",
        "min_temp": "15",
        "max_temp": "30",
        "hvac_modes_entity_ids": {
            "heat": ["climate.heater", "climate.hvac1"],
            "cool": ["climate.cooler", "climate.hvac"],
        },
        "toggle_coolers": True,
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

    hvac_entity: HvacGroupClimateEntity = mock_async_add_entities.call_args[0][0][0]

    assert hvac_entity.temperature_sensor_entity_id == "sensor.bedroom_temperature"
    assert hvac_entity.min_temp == 15.0
    assert hvac_entity.max_temp == 30.0

    assert hvac_entity.precision == PRECISION_TENTHS
    assert hvac_entity.target_temperature_step == PRECISION_HALVES
    assert hvac_entity.temperature_unit == hass.config.units.temperature_unit
    assert HVACMode.OFF in hvac_entity.hvac_modes
    assert HVACMode.HEAT_COOL not in hvac_entity.hvac_modes
    assert HVACMode.HEAT not in hvac_entity.hvac_modes
    assert HVACMode.COOL not in hvac_entity.hvac_modes

    assert hvac_entity.hvac_mode == HVACMode.OFF
    assert hvac_entity.hvac_action == HVACAction.OFF
