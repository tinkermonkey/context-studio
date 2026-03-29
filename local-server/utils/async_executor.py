"""
Utilities for running synchronous operations asynchronously in a thread pool.

This module provides helpers to prevent blocking the event loop when calling
synchronous libraries from async contexts.
"""

import asyncio
from functools import wraps
from typing import Callable, TypeVar, Any

T = TypeVar('T')


def run_sync_in_executor(func: Callable[..., T], *args: Any, **kwargs: Any) -> Any:
    """
    Run a synchronous function in the default thread pool executor.

    This prevents blocking the async event loop. Should be awaited in async contexts.

    Args:
        func: The synchronous function to run
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        A coroutine that will run the function in a thread pool and return the result

    Example:
        result = await run_sync_in_executor(blocking_func, arg1, arg2=value)
    """
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, func, *args)


def async_wrapper(func: Callable[..., T]) -> Callable[..., Any]:
    """
    Decorator to wrap a synchronous function to be called from async contexts.

    Automatically runs the function in a thread pool executor.

    Args:
        func: The synchronous function to wrap

    Returns:
        An async wrapper function

    Example:
        @async_wrapper
        def blocking_operation():
            return expensive_sync_call()

        result = await blocking_operation()
    """
    @wraps(func)
    async def async_func(*args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    return async_func
