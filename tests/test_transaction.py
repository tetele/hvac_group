"""Test transactions."""

from collections.abc import Coroutine
import pytest

from custom_components.hvac_group.transaction import Transaction, TransactionException


def test_begin() -> None:
    """Test beginning a transaction."""
    t = Transaction()

    assert not t.in_progress
    assert not t.coros

    t.begin()
    assert t.in_progress
    assert not t.coros

    async def new_coro() -> None:
        pass

    t.add(new_coro)
    assert new_coro in t.coros

    with pytest.raises(TransactionException):
        t.begin()


async def test_commit() -> None:
    """Test committing a transaction."""
    t = Transaction()

    with pytest.raises(TransactionException):
        await t.commit()

    t.begin()
    assert t.in_progress

    coroutines: list[Coroutine] = []

    def generate_new_coro() -> Coroutine:
        async def new_coro() -> int:
            return 12

        coro = new_coro()
        coroutines.append(coro)

        return coro

    t.add(generate_new_coro())

    result = await t.commit()
    assert result == [12]
    assert not t.in_progress
    assert not t.coros

    assert len(coroutines) == 1
    with pytest.raises(RuntimeError):
        await coroutines[0]


async def test_cancel() -> None:
    """Test cancelling a transaction."""
    t = Transaction()

    with pytest.raises(TransactionException):
        t.cancel()

    t.begin()

    coroutines: list[Coroutine] = []

    def generate_new_coro() -> Coroutine:
        async def new_coro() -> int:
            return 12

        coro = new_coro()
        coroutines.append(coro)

        return coro

    t.add(generate_new_coro())

    t.cancel()
    assert not t.in_progress
    assert not t.coros

    assert len(coroutines) == 1
    with pytest.raises(RuntimeError):
        await coroutines[0]
