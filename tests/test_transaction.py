"""Test transactions."""

import pytest

from homeassistant.core import HomeAssistant

from custom_components.hvac_group.actuator import HvacGroupHeater
from custom_components.hvac_group.transaction import (
    Transaction,
    TransactionException,
    TransactionActionType,
)


def test_begin(hass: HomeAssistant) -> None:
    """Test beginning a transaction."""
    t = Transaction()

    assert not t.in_progress
    assert not t.actions

    t.begin()
    assert t.in_progress
    assert not t.actions

    heater = HvacGroupHeater(hass, "climate.heater")

    t.add(heater, TransactionActionType.SET_HVAC_MODE, {"hvac_mode": "off"})
    assert heater.entity_id in t.actions

    with pytest.raises(TransactionException):
        t.begin()


async def test_commit(hass: HomeAssistant) -> None:
    """Test committing a transaction."""
    t = Transaction()

    with pytest.raises(TransactionException):
        await t.commit()

    t.begin()
    assert t.in_progress

    heater = HvacGroupHeater(hass, "climate.heater")

    t.add(heater, TransactionActionType.SET_HVAC_MODE, {"hvac_mode": "off"})
    t.add(heater, TransactionActionType.SET_HVAC_MODE, {"hvac_mode": "on"})

    result = await t.commit()
    target = result.get(heater.entity_id)
    assert target
    assert len(target.services) == 1
    assert TransactionActionType.SET_HVAC_MODE in target.services
    assert target.services[TransactionActionType.SET_HVAC_MODE] == {"hvac_mode": "on"}
    assert not t.in_progress
    assert not t.actions


async def test_cancel(hass: HomeAssistant) -> None:
    """Test cancelling a transaction."""
    t = Transaction()

    with pytest.raises(TransactionException):
        t.cancel()

    t.begin()

    heater = HvacGroupHeater(hass, "climate.heater")

    t.add(heater, TransactionActionType.SET_HVAC_MODE, {"hvac_mode": "off"})

    assert len(t.actions) == 1

    t.cancel()
    assert not t.in_progress
    assert not t.actions
