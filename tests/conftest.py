import pytest

from circuitbreaker import CircuitBreaker, CircuitBreakerMonitor


def overwrite_qualname(value):
    def inner(function):
        function.__qualname__ = value
        return function
    return inner


@pytest.fixture
def clean_circuit_breaker_monitor():
    CircuitBreakerMonitor.circuit_breakers = {}


@pytest.fixture(params=[True, False], ids=["async", "sync"])
def is_async(request, clean_circuit_breaker_monitor):
    return request.param


@pytest.fixture
async def pseudo_remote_call(is_async):
    if is_async:
        async def pseudo_remote_call():
            return True
    else:
        def pseudo_remote_call():
            return True

    return pseudo_remote_call


@pytest.fixture
def circuit_success(is_async, pseudo_remote_call):
    if is_async:
        @CircuitBreaker()
        @overwrite_qualname("circuit_success")
        async def circuit_function():
            return await pseudo_remote_call()
    else:
        @CircuitBreaker()
        @overwrite_qualname("circuit_success")
        def circuit_function():
            return pseudo_remote_call()

    return circuit_function


@pytest.fixture
def circuit_failure(is_async):
    if is_async:
        @CircuitBreaker(failure_threshold=1, name="circuit_failure")
        async def circuit_function():
            raise IOError()
    else:
        @CircuitBreaker(failure_threshold=1, name="circuit_failure")
        def circuit_function():
            raise IOError()

    return circuit_function


@pytest.fixture
def circuit_generator_failure(is_async, pseudo_remote_call):
    if is_async:
        @CircuitBreaker(failure_threshold=1, name="circuit_generator_failure")
        async def circuit_function():
            await pseudo_remote_call()
            yield 1
            raise IOError()
    else:
        @CircuitBreaker(failure_threshold=1, name="circuit_generator_failure")
        def circuit_function():
            pseudo_remote_call()
            yield 1
            raise IOError()

    return circuit_function


@pytest.fixture
def circuit_threshold_1(is_async, pseudo_remote_call):
    if is_async:
        @CircuitBreaker(failure_threshold=1, name="threshold_1")
        async def circuit_function():
            return await pseudo_remote_call()
    else:
        @CircuitBreaker(failure_threshold=1, name="threshold_1")
        def circuit_function():
            return pseudo_remote_call()

    return circuit_function

@pytest.fixture
def circuit_threshold_2_timeout_1(is_async, pseudo_remote_call):
    if is_async:
        @CircuitBreaker(failure_threshold=2, recovery_timeout=1, name="threshold_2")
        async def circuit_function():
            return await pseudo_remote_call()
    else:
        @CircuitBreaker(failure_threshold=2, recovery_timeout=1, name="threshold_2")
        def circuit_function():
            return pseudo_remote_call()

    return circuit_function


@pytest.fixture
def circuit_threshold_3_timeout_1(is_async, pseudo_remote_call):
    if is_async:
        @CircuitBreaker(failure_threshold=3, recovery_timeout=1, name="threshold_3")
        async def circuit_function():
            return await pseudo_remote_call()
    else:
        @CircuitBreaker(failure_threshold=3, recovery_timeout=1, name="threshold_3")
        def circuit_function():
            return pseudo_remote_call()

    return circuit_function
