from asyncio import iscoroutinefunction
from inspect import isgeneratorfunction, isasyncgenfunction

import pytest

from circuitbreaker import CircuitBreaker, CircuitBreakerError, circuit


@pytest.fixture
def resolve_circuitbreaker_call_method(function_type):
    def cb_call(circuit_breaker):
        mapping = {
            "sync-function": circuit_breaker.call,
            "sync-generator": circuit_breaker.call_generator,
            "async-function": circuit_breaker.call_async,
            "async-generator": circuit_breaker.call_async_generator,
        }
        return mapping[function_type]

    return cb_call


class FooError(Exception):
    def __init__(self, val=None):
        self.val = val


class BarError(Exception):
    pass


def test_circuitbreaker__str__():
    cb = CircuitBreaker(name='Foobar')
    assert str(cb) == 'Foobar'


def test_circuitbreaker_unnamed__str__():
    cb = CircuitBreaker()
    assert str(cb) == 'unnamed_CircuitBreaker'


def test_circuitbreaker_error__str__():
    cb = CircuitBreaker(name='Foobar')
    cb._last_failure = Exception()
    error = CircuitBreakerError(cb)

    assert str(error).startswith('Circuit "Foobar" OPEN until ')
    assert str(error).endswith('(0 failures, 30 sec remaining) (last_failure: Exception())')


async def test_circuitbreaker_wrapper_matches_function_type(function, is_async, is_generator):
    cb = CircuitBreaker(name='Foobar')
    wrapper = cb(function)

    assert (
        isgeneratorfunction(function) == isgeneratorfunction(wrapper)
        == (not is_async and is_generator)
    )
    assert (
        iscoroutinefunction(function) == iscoroutinefunction(wrapper)
        == (is_async and not is_generator)
    )
    assert (
        isasyncgenfunction(function) == isasyncgenfunction(wrapper)
        == (is_async and is_generator)
    )


async def test_circuitbreaker_should_save_last_exception_on_failure_call(
    resolve_call, resolve_circuitbreaker_call_method, function, function_call_error
):
    cb = CircuitBreaker(name='Foobar')

    cb_call = resolve_circuitbreaker_call_method(cb)
    with pytest.raises(function_call_error):
        await resolve_call(cb_call(function))

    assert isinstance(cb.last_failure, function_call_error)


async def test_circuitbreaker_should_clear_last_exception_on_success_call(
    resolve_call, resolve_circuitbreaker_call_method, function
):
    cb = CircuitBreaker(name='Foobar')
    cb._last_failure = IOError()
    assert isinstance(cb.last_failure, IOError)

    cb_call = resolve_circuitbreaker_call_method(cb)
    await resolve_call(cb_call(function))

    assert cb.last_failure is None


async def test_circuitbreaker_should_call_fallback_function_if_open(
    resolve_call, function, fallback_function, mock_fallback_call, fallback_call_return_value
):
    CircuitBreaker.opened = lambda self: True

    cb = CircuitBreaker(name='WithFallback', fallback_function=fallback_function)
    decorated_func = cb.decorate(function)

    assert await resolve_call(decorated_func()) == fallback_call_return_value
    mock_fallback_call.assert_called_once_with()


async def test_circuitbreaker_should_not_call_function_if_open(
    resolve_call, function, mock_function_call, fallback_function, fallback_call_return_value
):
    CircuitBreaker.opened = lambda self: True

    cb = CircuitBreaker(name='WithFallback', fallback_function=fallback_function)
    decorated_func = cb.decorate(function)

    assert await resolve_call(decorated_func()) == fallback_call_return_value
    assert not mock_function_call.called


async def test_circuitbreaker_call_fallback_function_with_parameters(
    resolve_call, function, fallback_function, mock_fallback_call, fallback_call_return_value
):
    # mock opened prop to see if fallback is called with correct parameters.
    CircuitBreaker.opened = lambda self: True

    cb = CircuitBreaker(name='WithFallback', fallback_function=fallback_function)
    decorated_func = cb.decorate(function)

    assert await resolve_call(decorated_func('test2', test='test')) == fallback_call_return_value

    # check args and kwargs are getting correctly to fallback function
    mock_fallback_call.assert_called_once_with('test2', test='test')


def test_circuit_decorator_without_args(mocker, function):
    decorate_patch = mocker.patch.object(CircuitBreaker, 'decorate')
    circuit(function)
    decorate_patch.assert_called_once_with(function)


def test_circuit_decorator_with_args():
    def function_fallback():
        return True

    breaker = circuit(10, 20, KeyError, 'foobar', function_fallback)

    assert breaker.is_failure(KeyError, None)
    assert not breaker.is_failure(Exception, None)
    assert not breaker.is_failure(FooError, None)
    assert breaker._failure_threshold == 10
    assert breaker._recovery_timeout == 20
    assert breaker._name == "foobar"
    assert breaker._fallback_function == function_fallback


def test_breaker_expected_exception_is_predicate():
    def is_four_foo(thrown_type, thrown_value):
        return thrown_value.val == 4

    breaker_four = circuit(expected_exception=is_four_foo)

    assert breaker_four.is_failure(FooError, FooError(4))
    assert not breaker_four.is_failure(FooError, FooError(2))


def test_breaker_default_constructor_traps_Exception():
    breaker = circuit()
    assert breaker.is_failure(Exception, Exception())
    assert breaker.is_failure(FooError, FooError())


def test_breaker_expected_exception_is_custom_exception():
    breaker = circuit(expected_exception=FooError)
    assert breaker.is_failure(FooError, FooError())
    assert not breaker.is_failure(Exception, Exception())


def test_breaker_constructor_expected_exception_is_exception_list():
    breaker = circuit(expected_exception=(FooError, BarError))
    assert breaker.is_failure(FooError, FooError())
    assert breaker.is_failure(BarError, BarError())
    assert not breaker.is_failure(Exception, Exception())


def test_constructor_mistake_name_bytes():
    with pytest.raises(ValueError, match="expected_exception cannot be a string *"):
        circuit(10, 20, b"foobar")


def test_constructor_mistake_name_unicode():
    with pytest.raises(ValueError, match="expected_exception cannot be a string *"):
        circuit(10, 20, u"foobar")


def test_constructor_mistake_expected_exception():
    class Widget:
        pass

    with pytest.raises(ValueError, match="expected_exception does not look like a predicate*"):
        circuit(10, 20, expected_exception=Widget)


def test_advanced_usage_circuitbreaker_subclass():
    class MyCircuitBreaker(CircuitBreaker):
        EXPECTED_EXCEPTION = FooError

    mybreaker = circuit(cls=MyCircuitBreaker)
    assert not mybreaker.is_failure(Exception, Exception())
    assert mybreaker.is_failure(FooError, FooError())


def test_advanced_usage_circuitbreaker_subclass_with_list():
    class MyCircuitBreaker(CircuitBreaker):
        EXPECTED_EXCEPTION = (FooError, BarError)

    mybreaker = circuit(cls=MyCircuitBreaker)
    assert not mybreaker.is_failure(Exception, Exception())
    assert mybreaker.is_failure(FooError, FooError())
    assert mybreaker.is_failure(BarError, BarError())


def test_advanced_usage_circuitbreaker_subclass_with_predicate():
    def is_foo_4(thrown_type, thrown_value):
        return issubclass(thrown_type, FooError) and thrown_value.val == 4

    class FooFourBreaker(CircuitBreaker):
        EXPECTED_EXCEPTION = is_foo_4

    breaker = circuit(cls=FooFourBreaker)
    assert not breaker.is_failure(Exception, Exception())
    assert not breaker.is_failure(FooError, FooError())
    assert breaker.is_failure(FooError, FooError(4))


def test_advanced_usage_circuitbreaker_default_expected_exception():
    class NervousBreaker(CircuitBreaker):
        FAILURE_THRESHOLD = 1

    breaker = circuit(cls=NervousBreaker)
    assert breaker._failure_threshold == 1
    assert breaker.is_failure(Exception, Exception())
