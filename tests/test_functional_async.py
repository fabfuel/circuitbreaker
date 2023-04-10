from asyncio import sleep

try:
    from unittest.mock import Mock, patch
except ImportError:
    from mock import Mock, patch

from pytest import raises

from circuitbreaker import CircuitBreaker, CircuitBreakerError, \
    CircuitBreakerMonitor, STATE_CLOSED, STATE_HALF_OPEN, STATE_OPEN


async def pseudo_remote_call():
    return True


@CircuitBreaker()
async def circuit_success():
    return await pseudo_remote_call()


@CircuitBreaker(failure_threshold=1, name="circuit_failure")
async def circuit_failure():
    raise IOError()


@CircuitBreaker(failure_threshold=1, name="circuit_generator_failure")
async def circuit_generator_failure():
    await pseudo_remote_call()
    yield 1
    raise IOError()


@CircuitBreaker(failure_threshold=1, name="threshold_1")
async def circuit_threshold_1():
    return await pseudo_remote_call()


@CircuitBreaker(failure_threshold=2, recovery_timeout=1, name="threshold_2")
async def circuit_threshold_2_timeout_1():
    return await pseudo_remote_call()


@CircuitBreaker(failure_threshold=3, recovery_timeout=1, name="threshold_3")
async def circuit_threshold_3_timeout_1():
    return await pseudo_remote_call()


async def test_circuit_pass_through():
    assert await circuit_success() is True


async def test_circuitbreaker_monitor():
    assert CircuitBreakerMonitor.all_closed() is True
    assert len(list(CircuitBreakerMonitor.get_circuits())) == 6
    assert len(list(CircuitBreakerMonitor.get_closed())) == 6
    assert len(list(CircuitBreakerMonitor.get_open())) == 0

    with raises(IOError):
        await circuit_failure()

    assert CircuitBreakerMonitor.all_closed() is False
    assert len(list(CircuitBreakerMonitor.get_circuits())) == 6
    assert len(list(CircuitBreakerMonitor.get_closed())) == 5
    assert len(list(CircuitBreakerMonitor.get_open())) == 1


@patch('test_functional_async.pseudo_remote_call', return_value=True)
async def test_threshold_hit_prevents_consequent_calls(mock_remote):
    # type: (Mock) -> None
    mock_remote.side_effect = IOError('Connection refused')
    circuitbreaker = CircuitBreakerMonitor.get('threshold_1')

    assert circuitbreaker.closed

    with raises(IOError):
        await circuit_threshold_1()

    assert circuitbreaker.opened

    with raises(CircuitBreakerError):
        await circuit_threshold_1()

    mock_remote.assert_called_once_with()


@patch('test_functional_async.pseudo_remote_call', return_value=True)
async def test_circuitbreaker_recover_half_open(mock_remote):
    # type: (Mock) -> None
    circuitbreaker = CircuitBreakerMonitor.get('threshold_3')

    # initial state: closed
    assert circuitbreaker.closed
    assert circuitbreaker.state == STATE_CLOSED

    # no exception -> success
    assert await circuit_threshold_3_timeout_1()

    # from now all subsequent calls will fail
    mock_remote.side_effect = IOError('Connection refused')

    # 1. failed call -> original exception
    with raises(IOError):
        await circuit_threshold_3_timeout_1()
    assert circuitbreaker.closed
    assert circuitbreaker.failure_count == 1

    # 2. failed call -> original exception
    with raises(IOError):
        await circuit_threshold_3_timeout_1()
    assert circuitbreaker.closed
    assert circuitbreaker.failure_count == 2

    # 3. failed call -> original exception
    with raises(IOError):
        await circuit_threshold_3_timeout_1()

    # Circuit breaker opens, threshold has been reached
    assert circuitbreaker.opened
    assert circuitbreaker.state == STATE_OPEN
    assert circuitbreaker.failure_count == 3
    assert 0 < circuitbreaker.open_remaining <= 1

    # 4. failed call -> not passed to function -> CircuitBreakerError
    with raises(CircuitBreakerError):
        await circuit_threshold_3_timeout_1()
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 3
    assert 0 < circuitbreaker.open_remaining <= 1

    # 5. failed call -> not passed to function -> CircuitBreakerError
    with raises(CircuitBreakerError):
        await circuit_threshold_3_timeout_1()
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 3
    assert 0 < circuitbreaker.open_remaining <= 1

    # wait for 1 second (recover timeout)
    await sleep(1)

    # circuit half-open -> next call will be passed through
    assert not circuitbreaker.closed
    assert circuitbreaker.open_remaining < 0
    assert circuitbreaker.state == STATE_HALF_OPEN

    # State half-open -> function is executed -> original exception
    with raises(IOError):
        await circuit_threshold_3_timeout_1()
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 4
    assert 0 < circuitbreaker.open_remaining <= 1

    # State open > not passed to function -> CircuitBreakerError
    with raises(CircuitBreakerError):
        await circuit_threshold_3_timeout_1()


@patch('test_functional_async.pseudo_remote_call', return_value=True)
async def test_circuitbreaker_reopens_after_successful_calls(mock_remote):
    # type: (Mock) -> None
    circuitbreaker = CircuitBreakerMonitor.get('threshold_2')

    assert str(circuitbreaker) == 'threshold_2'

    # initial state: closed
    assert circuitbreaker.closed
    assert circuitbreaker.state == STATE_CLOSED
    assert circuitbreaker.failure_count == 0

    # successful call -> no exception
    assert await circuit_threshold_2_timeout_1()

    # from now all subsequent calls will fail
    mock_remote.side_effect = IOError('Connection refused')

    # 1. failed call -> original exception
    with raises(IOError):
        await circuit_threshold_2_timeout_1()
    assert circuitbreaker.closed
    assert circuitbreaker.failure_count == 1

    # 2. failed call -> original exception
    with raises(IOError):
        await circuit_threshold_2_timeout_1()

    # Circuit breaker opens, threshold has been reached
    assert circuitbreaker.opened
    assert circuitbreaker.state == STATE_OPEN
    assert circuitbreaker.failure_count == 2
    assert 0 < circuitbreaker.open_remaining <= 1

    # 4. failed call -> not passed to function -> CircuitBreakerError
    with raises(CircuitBreakerError):
        await circuit_threshold_2_timeout_1()
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 2
    assert 0 < circuitbreaker.open_remaining <= 1

    # from now all subsequent calls will succeed
    mock_remote.side_effect = None

    # but recover timeout has not been reached -> still open
    # 5. failed call -> not passed to function -> CircuitBreakerError
    with raises(CircuitBreakerError):
        await circuit_threshold_2_timeout_1()
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 2
    assert 0 < circuitbreaker.open_remaining <= 1

    # wait for 1 second (recover timeout)
    await sleep(1)

    # circuit half-open -> next call will be passed through
    assert not circuitbreaker.closed
    assert circuitbreaker.failure_count == 2
    assert circuitbreaker.open_remaining < 0
    assert circuitbreaker.state == STATE_HALF_OPEN

    # successful call
    assert await circuit_threshold_2_timeout_1()

    # circuit closed and reset'ed
    assert circuitbreaker.closed
    assert circuitbreaker.state == STATE_CLOSED
    assert circuitbreaker.failure_count == 0

    # some another successful calls
    assert await circuit_threshold_2_timeout_1()
    assert await circuit_threshold_2_timeout_1()
    assert await circuit_threshold_2_timeout_1()


@patch("test_functional_async.pseudo_remote_call", return_value=True)
async def test_circuitbreaker_handles_generator_functions(mock_remote):
    # type: (Mock) -> None
    circuitbreaker = CircuitBreakerMonitor.get("circuit_generator_failure")
    assert circuitbreaker.closed

    with raises(IOError):
        [_ async for _ in circuit_generator_failure()]

    assert circuitbreaker.opened

    with raises(CircuitBreakerError):
        [_ async for _ in circuit_generator_failure()]

    mock_remote.assert_called_once_with()
