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
async def sync_or_async(is_async):
    async def _sync(value):
        return value
    async def _async(coro):
        return await coro
    return _async if is_async else _sync


@pytest.fixture
async def remote_call_return_value():
    return object()


@pytest.fixture
async def mock_remote_call(is_async, mocker, remote_call_return_value):
    mock_function = mocker.async_stub() if is_async else mocker.stub()
    mock_function.return_value = remote_call_return_value
    return mock_function


@pytest.fixture
def remote_call_function(is_async, mock_remote_call):
    if is_async:
        async def function(*args, **kwargs):
            return await mock_remote_call()
    else:
        def function(*args, **kwargs):
            return mock_remote_call()

    return function


@pytest.fixture
def circuit_success(is_async, mock_remote_call):
    if is_async:
        @CircuitBreaker()
        @overwrite_qualname("circuit_success")
        async def circuit_function():
            return await mock_remote_call()
    else:
        @CircuitBreaker()
        @overwrite_qualname("circuit_success")
        def circuit_function():
            return mock_remote_call()

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
def circuit_generator_failure(is_async, mock_remote_call):
    if is_async:
        @CircuitBreaker(failure_threshold=1, name="circuit_generator_failure")
        async def circuit_function():
            await mock_remote_call()
            yield 1
            raise IOError()
    else:
        @CircuitBreaker(failure_threshold=1, name="circuit_generator_failure")
        def circuit_function():
            mock_remote_call()
            yield 1
            raise IOError()

    return circuit_function


@pytest.fixture
def circuit_threshold_1(is_async, mock_remote_call):
    if is_async:
        @CircuitBreaker(failure_threshold=1, name="threshold_1")
        async def circuit_function():
            return await mock_remote_call()
    else:
        @CircuitBreaker(failure_threshold=1, name="threshold_1")
        def circuit_function():
            return mock_remote_call()

    return circuit_function


@pytest.fixture
def circuit_threshold_2_timeout_1(is_async, mock_remote_call):
    if is_async:
        @CircuitBreaker(failure_threshold=2, recovery_timeout=1, name="threshold_2")
        async def circuit_function():
            return await mock_remote_call()
    else:
        @CircuitBreaker(failure_threshold=2, recovery_timeout=1, name="threshold_2")
        def circuit_function():
            return mock_remote_call()

    return circuit_function


@pytest.fixture
def circuit_threshold_3_timeout_1(is_async, mock_remote_call):
    if is_async:
        @CircuitBreaker(failure_threshold=3, recovery_timeout=1, name="threshold_3")
        async def circuit_function():
            return await mock_remote_call()
    else:
        @CircuitBreaker(failure_threshold=3, recovery_timeout=1, name="threshold_3")
        def circuit_function():
            return mock_remote_call()

    return circuit_function
