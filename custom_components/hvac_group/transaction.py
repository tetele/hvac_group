"""Group of coros that need to be executed together or not at all."""

import asyncio
from collections.abc import Coroutine


class TransactionException(Exception):
    """Transaction exceptions."""

    pass


class Transaction:
    """Transaction class."""

    def __init__(self) -> None:
        """Create a new transaction."""
        self._in_progress: bool = False
        self._coros: list[Coroutine] = []

    @property
    def in_progress(self) -> bool:
        """True if transaction has begun."""
        return self._in_progress

    @property
    def coros(self) -> list[Coroutine]:
        """The list of coros."""
        return self._coros

    def begin(self) -> None:
        """Begin a transaction."""

        if self._in_progress:
            raise TransactionException("Transaction is already in progress")

        self._in_progress = True
        self._coros = []

    def add(self, coro: Coroutine) -> None:
        """Add a coroutine to the list of coros to be committed."""

        self._coros.append(coro)

    def cancel(self) -> None:
        """Cancel a transaction and all coros within."""

        if not self._in_progress:
            raise TransactionException(
                "Transaction has not begun, so it cannot be cancelled"
            )

        for coro in self._coros:
            coro.close()

        self._in_progress = False
        self._coros = []

    async def commit(self) -> asyncio.Future[list]:
        """Commit a transaction and execute all coros within."""

        if not self._in_progress:
            raise TransactionException(
                "Transaction has not begun, so it cannot be committed"
            )

        result = await asyncio.gather(*self._coros)
        self._in_progress = False
        self._coros = []

        return result
