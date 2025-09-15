"""Unit tests for circuit breaker"""

import pytest
import asyncio
from unittest.mock import AsyncMock

# Add parent directories to path to find modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enrichment.unified.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerError


class TestCircuitBreaker:
    """Test circuit breaker functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=0.1,  # Short timeout for tests
            success_threshold=2
        )

    @pytest.mark.asyncio
    async def test_successful_calls_keep_circuit_closed(self):
        """Test that successful calls keep circuit closed"""
        async def successful_function():
            return "success"

        # Multiple successful calls
        for _ in range(5):
            result = await self.circuit_breaker.call(successful_function)
            assert result == "success"
            assert self.circuit_breaker.is_closed

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failure_threshold(self):
        """Test that circuit opens after failure threshold is reached"""
        async def failing_function():
            raise Exception("Test failure")

        # Circuit should be closed initially
        assert self.circuit_breaker.is_closed

        # Call failing function up to threshold
        for i in range(3):
            with pytest.raises(Exception):
                await self.circuit_breaker.call(failing_function)

            if i < 2:  # Before threshold
                assert self.circuit_breaker.is_closed
            else:  # At threshold
                assert self.circuit_breaker.is_open

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_calls_when_open(self):
        """Test that circuit breaker rejects calls when open"""
        async def failing_function():
            raise Exception("Test failure")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await self.circuit_breaker.call(failing_function)

        assert self.circuit_breaker.is_open

        # Additional calls should be rejected with CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await self.circuit_breaker.call(failing_function)

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open_after_timeout(self):
        """Test circuit transitions to half-open after timeout"""
        async def failing_function():
            raise Exception("Test failure")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await self.circuit_breaker.call(failing_function)

        assert self.circuit_breaker.is_open

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Next call should transition to half-open
        async def test_function():
            return "test"

        # This should work because circuit transitions to half-open
        result = await self.circuit_breaker.call(test_function)
        assert result == "test"
        assert self.circuit_breaker.is_half_open

    @pytest.mark.asyncio
    async def test_half_open_closes_after_success_threshold(self):
        """Test that half-open circuit closes after success threshold"""
        async def failing_function():
            raise Exception("Test failure")

        async def successful_function():
            return "success"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await self.circuit_breaker.call(failing_function)

        # Wait and transition to half-open
        await asyncio.sleep(0.2)

        # Need 2 successes to close (success_threshold=2)
        result1 = await self.circuit_breaker.call(successful_function)
        assert result1 == "success"
        assert self.circuit_breaker.is_half_open

        result2 = await self.circuit_breaker.call(successful_function)
        assert result2 == "success"
        assert self.circuit_breaker.is_closed

    @pytest.mark.asyncio
    async def test_half_open_returns_to_open_on_failure(self):
        """Test that half-open circuit returns to open on failure"""
        async def failing_function():
            raise Exception("Test failure")

        async def successful_function():
            return "success"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await self.circuit_breaker.call(failing_function)

        # Wait and transition to half-open
        await asyncio.sleep(0.2)
        await self.circuit_breaker.call(successful_function)
        assert self.circuit_breaker.is_half_open

        # Failure in half-open should return to open
        with pytest.raises(Exception):
            await self.circuit_breaker.call(failing_function)

        assert self.circuit_breaker.is_open

    @pytest.mark.asyncio
    async def test_success_resets_failure_count_in_closed_state(self):
        """Test that success resets failure count in closed state"""
        async def failing_function():
            raise Exception("Test failure")

        async def successful_function():
            return "success"

        # Have some failures (but not enough to open)
        for _ in range(2):
            with pytest.raises(Exception):
                await self.circuit_breaker.call(failing_function)

        assert self.circuit_breaker.is_closed
        assert self.circuit_breaker.failure_count == 2

        # Success should reset failure count
        await self.circuit_breaker.call(successful_function)
        assert self.circuit_breaker.failure_count == 0

        # Should be able to have failures again before opening
        for _ in range(2):
            with pytest.raises(Exception):
                await self.circuit_breaker.call(failing_function)

        assert self.circuit_breaker.is_closed  # Still closed because count was reset

    @pytest.mark.asyncio
    async def test_specific_exception_type_filtering(self):
        """Test that only expected exception types trigger circuit breaker"""
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            expected_exception=ValueError
        )

        async def value_error_function():
            raise ValueError("Value error")

        async def runtime_error_function():
            raise RuntimeError("Runtime error")

        # ValueError should trigger circuit breaker
        with pytest.raises(ValueError):
            await circuit_breaker.call(value_error_function)
        with pytest.raises(ValueError):
            await circuit_breaker.call(value_error_function)

        assert circuit_breaker.is_open

        # Reset for next test
        circuit_breaker.reset()

        # RuntimeError should not trigger circuit breaker
        for _ in range(5):
            with pytest.raises(RuntimeError):
                await circuit_breaker.call(runtime_error_function)

        assert circuit_breaker.is_closed  # Should still be closed

    def test_get_stats(self):
        """Test circuit breaker statistics"""
        stats = self.circuit_breaker.get_stats()

        expected_keys = {
            "state", "failure_count", "success_count",
            "last_failure_time", "failure_threshold",
            "recovery_timeout", "success_threshold"
        }

        assert set(stats.keys()) == expected_keys
        assert stats["state"] == CircuitState.CLOSED.value
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0
        assert stats["failure_threshold"] == 3
        assert stats["recovery_timeout"] == 0.1
        assert stats["success_threshold"] == 2

    def test_manual_reset(self):
        """Test manual circuit breaker reset"""
        # Set some state
        self.circuit_breaker.failure_count = 5
        self.circuit_breaker.state = CircuitState.OPEN
        self.circuit_breaker.last_failure_time = 123456

        # Reset should clear everything
        self.circuit_breaker.reset()

        assert self.circuit_breaker.is_closed
        assert self.circuit_breaker.failure_count == 0
        assert self.circuit_breaker.success_count == 0
        assert self.circuit_breaker.last_failure_time is None

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_async_function_args(self):
        """Test circuit breaker with function arguments"""
        async def function_with_args(x, y, multiplier=1):
            if x < 0:
                raise ValueError("Negative x not allowed")
            return (x + y) * multiplier

        # Test successful call with args
        result = await self.circuit_breaker.call(
            function_with_args, 5, 3, multiplier=2
        )
        assert result == 16  # (5 + 3) * 2

        # Test failure with args
        with pytest.raises(ValueError):
            await self.circuit_breaker.call(
                function_with_args, -1, 3, multiplier=2
            )

    @pytest.mark.asyncio
    async def test_concurrent_calls(self):
        """Test circuit breaker behavior with concurrent calls"""
        call_count = 0

        async def concurrent_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise Exception(f"Failure {call_count}")
            return f"Success {call_count}"

        # Start multiple concurrent calls
        tasks = []
        for _ in range(6):
            task = asyncio.create_task(
                self.circuit_breaker.call(concurrent_function)
            )
            tasks.append(task)

        # Wait for all tasks and collect results
        results = []
        for task in tasks:
            try:
                result = await task
                results.append(result)
            except Exception as e:
                results.append(type(e).__name__)

        # Should have some failures and some circuit breaker errors
        assert "Exception" in results
        assert "CircuitBreakerError" in results or any(
            "Success" in str(r) for r in results
        )

    @pytest.mark.asyncio
    async def test_should_attempt_reset_logic(self):
        """Test the internal logic for attempting reset"""
        async def failing_function():
            raise Exception("Test failure")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await self.circuit_breaker.call(failing_function)

        assert self.circuit_breaker.is_open
        assert not self.circuit_breaker._should_attempt_reset()

        # After timeout, should attempt reset
        await asyncio.sleep(0.2)
        assert self.circuit_breaker._should_attempt_reset()

    def test_circuit_state_properties(self):
        """Test circuit state property methods"""
        # Initially closed
        assert self.circuit_breaker.is_closed
        assert not self.circuit_breaker.is_open
        assert not self.circuit_breaker.is_half_open

        # Manually set to open
        self.circuit_breaker.state = CircuitState.OPEN
        assert not self.circuit_breaker.is_closed
        assert self.circuit_breaker.is_open
        assert not self.circuit_breaker.is_half_open

        # Manually set to half-open
        self.circuit_breaker.state = CircuitState.HALF_OPEN
        assert not self.circuit_breaker.is_closed
        assert not self.circuit_breaker.is_open
        assert self.circuit_breaker.is_half_open

    @pytest.mark.asyncio
    async def test_zero_failure_threshold(self):
        """Test circuit breaker with zero failure threshold"""
        circuit_breaker = CircuitBreaker(failure_threshold=0)

        async def failing_function():
            raise Exception("Test failure")

        # Should open immediately on first failure
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_function)

        assert circuit_breaker.is_open