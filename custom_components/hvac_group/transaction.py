"""Group of actions that need to be executed together or not at all."""

import asyncio
from collections.abc import Coroutine
from enum import StrEnum
from typing import Any

from homeassistant.components.climate import (
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.core import Context

from .actuator import HvacGroupActuator


class TransactionException(Exception):
    """Transaction exceptions."""


class TransactionActionType(StrEnum):
    """An action that can be executed in the context of a transaction."""

    SET_TEMPERATURE = SERVICE_SET_TEMPERATURE
    SET_HVAC_MODE = SERVICE_SET_HVAC_MODE


class TransactionTarget:
    """A HvacGroupActuator as a transaction target."""

    def __init__(self, target: HvacGroupActuator) -> None:
        """Create a new transaction target."""
        self.target = target
        self.services: dict[str, dict[str, Any]] = {}


class Transaction:
    """Transaction class."""

    def __init__(self) -> None:
        """Create a new transaction."""
        self._in_progress: bool = False
        self._actions: dict[str, TransactionTarget] = {}
        self._context: Context | None = None

    @property
    def in_progress(self) -> bool:
        """True if transaction has begun."""
        return self._in_progress

    @property
    def actions(self) -> list[Coroutine]:
        """The list of actions."""
        return self._actions

    @property
    def context(self) -> Context | None:
        """The transaction context."""
        return self._context

    def set_context(self, context: Context) -> None:
        """Set the transaction context."""
        self._context = context

    def begin(self, context: Context | None = None) -> None:
        """Begin a transaction."""

        if self._in_progress:
            raise TransactionException("Transaction is already in progress")

        self._context = context
        self._in_progress = True
        self._actions = {}

    def add(
        self,
        target: HvacGroupActuator,
        action_type: TransactionActionType,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Add an action to the list of actions to be committed."""

        if not self._in_progress:
            raise TransactionException(
                "Transaction has not begun, so actions cannot be added"
            )

        if data is None:
            data = {}

        transaction_target = self._actions.get(
            target.entity_id, TransactionTarget(target)
        )
        transaction_target.services.update(
            {action_type: transaction_target.services.get(action_type, {}) | data}
        )

        self._actions.update({target.entity_id: transaction_target})

    def cancel(self) -> None:
        """Cancel a transaction and all actions within."""

        if not self._in_progress:
            raise TransactionException(
                "Transaction has not begun, so it cannot be cancelled"
            )

        self._in_progress = False
        self._actions = {}

    async def commit(self) -> asyncio.Future[list]:
        """Commit a transaction and execute all actions within."""

        if not self._in_progress:
            raise TransactionException(
                "Transaction has not begun, so it cannot be committed"
            )

        result = self._actions
        for target in self._actions.values():
            for service, data in target.services.items():
                target.target.async_call_climate_service(service, data)
        self._in_progress = False
        self._actions = {}

        return result
