"""
Utilities for running synchronous operations asynchronously in a thread pool.

This module provides helpers to prevent blocking the event loop when calling
synchronous libraries from async contexts.
"""

import asyncio
from typing import Callable, TypeVar, Any, ParamSpec

P = ParamSpec("P")
T = TypeVar("T")


def run_sync_in_executor(func: Callable[P, T], *args: Any, **kwargs: Any) -> asyncio.Future[T]:
    """
    Run a synchronous function in the default thread pool executor.

    Safely handles both positional and keyword arguments by wrapping the call
    in a lambda before passing to loop.run_in_executor().

    Args:
        func: Synchronous function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        An awaitable Future that resolves to the function's return value

    Example:
        result = await run_sync_in_executor(blocking_func, arg1, arg2=value)
    """
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, lambda: func(*args, **kwargs))
