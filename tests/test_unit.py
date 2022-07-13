try:
    from unittest.mock import Mock, patch
except ImportError:
    from mock import Mock, patch

from pytest import raises

from circuitbreaker import CircuitBreaker, CircuitBreakerError, circuit


class FooError(Exception):
    def __init__(self, val=None):
        self.val = val


class BarError(Exception):
    pass


def test_circuitbreaker__str__():
    cb = CircuitBreaker(name='Foobar')
    assert str(cb) == 'Foobar'


def test_circuitbreaker_error__str__():
    cb = CircuitBreaker(name='Foobar')
    cb._last_failure = Exception()
    error = CircuitBreakerError(cb)

    assert str(error).startswith('Circuit "Foobar" OPEN until ')
    assert str(error).endswith('(0 failures, 30 sec remaining) (last_failure: Exception())')


def test_circuitbreaker_should_save_last_exception_on_failure_call():
    cb = CircuitBreaker(name='Foobar')

    func = Mock(side_effect=IOError)

    with raises(IOError):
        cb.call(func)

    assert isinstance(cb.last_failure, IOError)


def test_circuitbreaker_should_clear_last_exception_on_success_call():
    cb = CircuitBreaker(name='Foobar')
    cb._last_failure = IOError()
    assert isinstance(cb.last_failure, IOError)

    cb.call(lambda: True)

    assert cb.last_failure is None


def test_circuitbreaker_should_call_fallback_function_if_open():
    fallback = Mock(return_value=True)

    func = Mock(return_value=False, __name__="Mock")  # attribute __name__ required for 2.7 compat with functools.wraps

    CircuitBreaker.opened = lambda self: True

    cb = CircuitBreaker(name='WithFallback', fallback_function=fallback)
    decorated_func = cb.decorate(func)

    decorated_func()
    fallback.assert_called_once_with()


def test_circuitbreaker_should_not_call_function_if_open():
    fallback = Mock(return_value=True)

    func = Mock(return_value=False, __name__="Mock")  # attribute __name__ required for 2.7 compat with functools.wraps

    CircuitBreaker.opened = lambda self: True

    cb = CircuitBreaker(name='WithFallback', fallback_function=fallback)
    decorated_func = cb.decorate(func)

    assert decorated_func() == fallback.return_value
    assert not func.called


def mocked_function(*args, **kwargs):
    pass


def test_circuitbreaker_call_fallback_function_with_parameters():
    fallback = Mock(return_value=True)

    cb = circuit(name='with_fallback', fallback_function=fallback)

    # mock opened prop to see if fallback is called with correct parameters.
    cb.opened = lambda self: True
    func_decorated = cb.decorate(mocked_function)

    func_decorated('test2', test='test')

    # check args and kwargs are getting correctly to fallback function

    fallback.assert_called_once_with('test2', test='test')


@patch('circuitbreaker.CircuitBreaker.decorate')
def test_circuit_decorator_without_args(circuitbreaker_mock):
    def function():
        return True

    circuit(function)
    circuitbreaker_mock.assert_called_once_with(function)


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
    with raises(ValueError, match="expected_exception cannot be a string *"):
        circuit(10, 20, b"foobar")


def test_constructor_mistake_name_unicode():
    with raises(ValueError, match="expected_exception cannot be a string *"):
        circuit(10, 20, u"foobar")


def test_constructor_mistake_expected_exception():
    class Widget:
        pass

    with raises(ValueError, match="expected_exception does not look like a predicate*"):
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
