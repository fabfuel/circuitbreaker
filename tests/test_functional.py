import pytest

from circuitbreaker import (
    CircuitBreakerError,
    CircuitBreakerMonitor,
    STATE_CLOSED,
    STATE_HALF_OPEN,
    STATE_OPEN,
)


async def test_circuit_pass_through(sync_or_async, circuit_success, remote_call_return_value):
    assert await sync_or_async(circuit_success()) is remote_call_return_value


@pytest.mark.usefixtures(
    "circuit_success",
    "circuit_failure",
    "circuit_generator_failure",
    "circuit_threshold_1",
    "circuit_threshold_2_timeout_1",
    "circuit_threshold_3_timeout_1",
)
async def test_circuitbreaker_monitor(sync_or_async, circuit_failure):
    assert CircuitBreakerMonitor.all_closed() is True
    assert len(list(CircuitBreakerMonitor.get_circuits())) == 6
    assert len(list(CircuitBreakerMonitor.get_closed())) == 6
    assert len(list(CircuitBreakerMonitor.get_open())) == 0

    with pytest.raises(IOError):
        await sync_or_async(circuit_failure())

    assert CircuitBreakerMonitor.all_closed() is False
    assert len(list(CircuitBreakerMonitor.get_circuits())) == 6
    assert len(list(CircuitBreakerMonitor.get_closed())) == 5
    assert len(list(CircuitBreakerMonitor.get_open())) == 1


async def test_threshold_hit_prevents_consequent_calls(
    sync_or_async, mock_remote_call, circuit_threshold_1
):
    mock_remote_call.side_effect = IOError('Connection refused')
    circuitbreaker = CircuitBreakerMonitor.get('threshold_1')

    assert circuitbreaker.closed

    with pytest.raises(IOError):
        await sync_or_async(circuit_threshold_1())

    assert circuitbreaker.opened

    with pytest.raises(CircuitBreakerError):
        await sync_or_async(circuit_threshold_1())

    mock_remote_call.assert_called_once_with()


async def test_circuitbreaker_recover_half_open(
    sync_or_async, mock_remote_call, circuit_threshold_3_timeout_1, sleep
):
    circuitbreaker = CircuitBreakerMonitor.get('threshold_3')

    # initial state: closed
    assert circuitbreaker.closed
    assert circuitbreaker.state == STATE_CLOSED

    # no exception -> success
    assert await sync_or_async(circuit_threshold_3_timeout_1())

    # from now all subsequent calls will fail
    mock_remote_call.side_effect = IOError('Connection refused')

    # 1. failed call -> original exception
    with pytest.raises(IOError):
        assert await sync_or_async(circuit_threshold_3_timeout_1())

    assert circuitbreaker.closed
    assert circuitbreaker.failure_count == 1

    # 2. failed call -> original exception
    with pytest.raises(IOError):
        assert await sync_or_async(circuit_threshold_3_timeout_1())
    assert circuitbreaker.closed
    assert circuitbreaker.failure_count == 2

    # 3. failed call -> original exception
    with pytest.raises(IOError):
        assert await sync_or_async(circuit_threshold_3_timeout_1())

    # Circuit breaker opens, threshold has been reached
    assert circuitbreaker.opened
    assert circuitbreaker.state == STATE_OPEN
    assert circuitbreaker.failure_count == 3
    assert 0 < circuitbreaker.open_remaining <= 1

    # 4. failed call -> not passed to function -> CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        assert await sync_or_async(circuit_threshold_3_timeout_1())
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 3
    assert 0 < circuitbreaker.open_remaining <= 1

    # 5. failed call -> not passed to function -> CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        assert await sync_or_async(circuit_threshold_3_timeout_1())
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
    with pytest.raises(IOError):
        assert await sync_or_async(circuit_threshold_3_timeout_1())
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 4
    assert 0 < circuitbreaker.open_remaining <= 1

    # State open > not passed to function -> CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        assert await sync_or_async(circuit_threshold_3_timeout_1())


async def test_circuitbreaker_reopens_after_successful_calls(
    sync_or_async, mock_remote_call, circuit_threshold_2_timeout_1, sleep
):
    circuitbreaker = CircuitBreakerMonitor.get('threshold_2')

    assert str(circuitbreaker) == 'threshold_2'

    # initial state: closed
    assert circuitbreaker.closed
    assert circuitbreaker.state == STATE_CLOSED
    assert circuitbreaker.failure_count == 0

    # successful call -> no exception
    assert await sync_or_async(circuit_threshold_2_timeout_1())

    # from now all subsequent calls will fail
    mock_remote_call.side_effect = IOError('Connection refused')

    # 1. failed call -> original exception
    with pytest.raises(IOError):
        await sync_or_async(circuit_threshold_2_timeout_1())
    assert circuitbreaker.closed
    assert circuitbreaker.failure_count == 1

    # 2. failed call -> original exception
    with pytest.raises(IOError):
        await sync_or_async(circuit_threshold_2_timeout_1())

    # Circuit breaker opens, threshold has been reached
    assert circuitbreaker.opened
    assert circuitbreaker.state == STATE_OPEN
    assert circuitbreaker.failure_count == 2
    assert 0 < circuitbreaker.open_remaining <= 1

    # 4. failed call -> not passed to function -> CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        await sync_or_async(circuit_threshold_2_timeout_1())
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 2
    assert 0 < circuitbreaker.open_remaining <= 1

    # from now all subsequent calls will succeed
    mock_remote_call.side_effect = None

    # but recover timeout has not been reached -> still open
    # 5. failed call -> not passed to function -> CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        await sync_or_async(circuit_threshold_2_timeout_1())
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
    assert await sync_or_async(circuit_threshold_2_timeout_1())

    # circuit closed and reset'ed
    assert circuitbreaker.closed
    assert circuitbreaker.state == STATE_CLOSED
    assert circuitbreaker.failure_count == 0

    # some another successful calls
    assert await sync_or_async(circuit_threshold_2_timeout_1())
    assert await sync_or_async(circuit_threshold_2_timeout_1())
    assert await sync_or_async(circuit_threshold_2_timeout_1())


async def test_circuitbreaker_handles_generator_functions(
    is_async, mock_remote_call, circuit_generator_failure
):
    circuitbreaker = CircuitBreakerMonitor.get("circuit_generator_failure")
    assert circuitbreaker.closed

    with pytest.raises(IOError):
        if is_async:
            [_ async for _ in circuit_generator_failure()]
        else:
            list(circuit_generator_failure())

    assert circuitbreaker.opened

    with pytest.raises(CircuitBreakerError):
        if is_async:
            [_ async for _ in circuit_generator_failure()]
        else:
            list(circuit_generator_failure())

    mock_remote_call.assert_called_once_with()
