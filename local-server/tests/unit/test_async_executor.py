import asyncio
import os
import sys
import pytest
from utils.async_executor import run_sync_in_executor

def blocking_function(a, b, c=None):
    """Test function that blocks."""
    return f"a={a}, b={b}, c={c}"


def failing_function():
    """Test function that raises an exception."""
    raise ValueError("Test error")


def slow_function(duration):
    """Simulates a slow blocking operation."""
    import time

    time.sleep(duration)
    return duration


@pytest.mark.asyncio
async def test_run_sync_in_executor_positional_args():
    """Test executor handles positional arguments correctly."""
    result = await run_sync_in_executor(blocking_function, 1, 2)
    assert result == "a=1, b=2, c=None"


@pytest.mark.asyncio
async def test_run_sync_in_executor_keyword_args():
    """Test executor handles keyword arguments correctly."""
    result = await run_sync_in_executor(blocking_function, 1, 2, c=3)
    assert result == "a=1, b=2, c=3"


@pytest.mark.asyncio
async def test_run_sync_in_executor_mixed_args():
    """Test executor handles mixed positional and keyword arguments."""
    result = await run_sync_in_executor(blocking_function, 1, b=2, c=3)
    assert result == "a=1, b=2, c=3"


@pytest.mark.asyncio
async def test_run_sync_in_executor_exception_propagates():
    """Test that exceptions from sync function are properly propagated."""
    with pytest.raises(ValueError, match="Test error"):
        await run_sync_in_executor(failing_function)


@pytest.mark.asyncio
async def test_run_sync_in_executor_concurrent_calls():
    """Test that multiple executor calls run concurrently."""
    # Run two slow functions concurrently
    start = asyncio.get_event_loop().time()
    results = await asyncio.gather(
        run_sync_in_executor(slow_function, 0.1),
        run_sync_in_executor(slow_function, 0.1),
    )
    elapsed = asyncio.get_event_loop().time() - start

    assert results == [0.1, 0.1]
    # If they ran sequentially, it would take ~0.2s. Concurrent should be ~0.1-0.15s
    assert elapsed < 0.18


@pytest.mark.asyncio
async def test_run_sync_in_executor_return_type():
    """Test executor returns correct type."""
    result = await run_sync_in_executor(lambda: 42)
    assert result == 42
    assert isinstance(result, int)


@pytest.mark.asyncio
async def test_run_sync_in_executor_none_return():
    """Test executor handles None return values."""

    def returns_none():
        pass

    result = await run_sync_in_executor(returns_none)
    assert result is None
