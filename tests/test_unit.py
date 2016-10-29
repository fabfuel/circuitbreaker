from circuitbreaker import CircuitBreaker, CircuitBreakerError


def test_circuitbreaker__str__():
    cb = CircuitBreaker(name='Foobar')
    assert str(cb) == 'Foobar'


def test_circuitbreaker_error__str__():
    cb = CircuitBreaker(name='Foobar')
    error = CircuitBreakerError(cb)

    assert str(error).startswith('Circuit "Foobar" OPEN until ')
    assert str(error).endswith('(0 failures, 30 sec remaining)')
