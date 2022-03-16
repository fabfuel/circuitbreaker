# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from functools import wraps
from datetime import datetime, timedelta
from inspect import isgeneratorfunction, isclass
from typing import AnyStr, Iterable
from math import ceil, floor

try:
    from time import monotonic
except ImportError:
    from monotonic import monotonic

STATE_CLOSED = 'closed'
STATE_OPEN = 'open'
STATE_HALF_OPEN = 'half_open'

def in_exception_list(*exc_types):
    """Build a predicate function that checks if an exception is a subtype from a list"""
    def matches_types(thrown_type, thrown_value):
        return any(issubclass(thrown_type, et) for et in exc_types)
    return matches_types

class CircuitBreaker(object):
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 30
    FALLBACK_FUNCTION = None

    def __init__(self,
                 failure_threshold=None,
                 recovery_timeout=None,
                 failure_if=None,
                 name=None,
                 fallback_function=None
                 ):
        """
        Construct a circuit breaker.

            :param failure_threshold: break open after this many failures
            :param recovery_timout: close after this many seconds
            :param failure_if: either an Exception type, iterable of exception types, or a predicate function.
                      If an exception or iterable of exception types, a failure will be triggered when a thrown
                      exception matches a type.

                      If this is a predicate function, it should have the signature (class, Exception) -> bool,
                      where the args are the exception type and the exception value. Return value True
                      indicates a failure in the underlying function.

            :param name: name for this circuitbreaker
            :param fallback_function: called when the circuit is opened

           :return: Circuitbreaker instance
           :rtype: Circuitbreaker
        """
        self._last_failure = None
        self._failure_count = 0
        self._failure_threshold = failure_threshold or self.FAILURE_THRESHOLD
        self._recovery_timeout = recovery_timeout or self.RECOVERY_TIMEOUT

        # default to plain old Exception
        failure_if = failure_if or Exception

        # auto-construct a failure predicate, depending on the type of the 'failure_if' param
        if isclass(failure_if) and issubclass(failure_if, Exception):
            def check_exception(thrown_type, _):
                return issubclass(thrown_type, failure_if)
            self.is_failure = check_exception
        else:
            # Check for iterable
            # https://stackoverflow.com/questions/1952464/in-python-how-do-i-determine-if-an-object-is-iterable
            try:
                iter(failure_if)
            except TypeError:
                # not iterable. assume it's a predicate function 
                assert callable(failure_if), "failure_if must be a callable(throw_type, throw_value)"
                self.is_failure = failure_if
            else:
                # iterable of Exceptions
                assert not isinstance(failure_if, str) # paranoid guard against a mistake
                self.is_failure = in_exception_list(failure_if)

        self._fallback_function = fallback_function or self.FALLBACK_FUNCTION
        self._name = name
        self._state = STATE_CLOSED
        self._opened = monotonic()

    def __call__(self, wrapped):
        return self.decorate(wrapped)

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc_value, _traceback):
        if exc_type and self.is_failure(exc_type, exc_value):
            # exception was raised and is our concern
            self._last_failure = exc_value
            self.__call_failed()
        else:
            self.__call_succeeded()
        return False  # return False to raise exception if any

    def decorate(self, function):
        """
        Applies the circuit breaker to a function
        """
        if self._name is None:
            self._name = function.__name__

        CircuitBreakerMonitor.register(self)

        if isgeneratorfunction(function):
            call = self.call_generator
        else:
            call = self.call

        @wraps(function)
        def wrapper(*args, **kwargs):
            if self.opened:
                if self.fallback_function:
                    return self.fallback_function(*args, **kwargs)
                raise CircuitBreakerError(self)
            return call(function, *args, **kwargs)

        return wrapper

    def call(self, func, *args, **kwargs):
        """
        Calls the decorated function and applies the circuit breaker
        rules on success or failure
        :param func: Decorated function
        """
        with self:
            return func(*args, **kwargs)

    def call_generator(self, func, *args, **kwargs):
        """
        Calls the decorated generator function and applies the circuit breaker
        rules on success or failure
        :param func: Decorated generator function
        """
        with self:
            for el in func(*args, **kwargs):
                yield el

    def __call_succeeded(self):
        """
        Close circuit after successful execution and reset failure count
        """
        self._state = STATE_CLOSED
        self._last_failure = None
        self._failure_count = 0

    def __call_failed(self):
        """
        Count failure and open circuit, if threshold has been reached
        """
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._state = STATE_OPEN
            self._opened = monotonic()

    @property
    def state(self):
        if self._state == STATE_OPEN and self.open_remaining <= 0:
            return STATE_HALF_OPEN
        return self._state

    @property
    def open_until(self):
        """
        The approximate datetime when the circuit breaker will try to recover
        :return: datetime
        """
        return datetime.utcnow() + timedelta(seconds=self.open_remaining)

    @property
    def open_remaining(self):
        """
        Number of seconds remaining, the circuit breaker stays in OPEN state
        :return: int
        """
        remain = (self._opened + self._recovery_timeout) - monotonic()
        return ceil(remain) if remain > 0 else floor(remain)

    @property
    def failure_count(self):
        return self._failure_count

    @property
    def closed(self):
        return self.state == STATE_CLOSED

    @property
    def opened(self):
        return self.state == STATE_OPEN

    @property
    def name(self):
        return self._name

    @property
    def last_failure(self):
        return self._last_failure

    @property
    def fallback_function(self):
        return self._fallback_function

    def __str__(self, *args, **kwargs):
        return self._name


class CircuitBreakerError(Exception):
    def __init__(self, circuit_breaker, *args, **kwargs):
        """
        :param circuit_breaker:
        :param args:
        :param kwargs:
        :return:
        """
        super(CircuitBreakerError, self).__init__(*args, **kwargs)
        self._circuit_breaker = circuit_breaker

    def __str__(self, *args, **kwargs):
        return 'Circuit "%s" OPEN until %s (%d failures, %d sec remaining) (last_failure: %r)' % (
            self._circuit_breaker.name,
            self._circuit_breaker.open_until,
            self._circuit_breaker.failure_count,
            round(self._circuit_breaker.open_remaining),
            self._circuit_breaker.last_failure,
        )


class CircuitBreakerMonitor(object):
    circuit_breakers = {}

    @classmethod
    def register(cls, circuit_breaker):
        cls.circuit_breakers[circuit_breaker.name] = circuit_breaker

    @classmethod
    def all_closed(cls):
        # type: () -> bool
        return len(list(cls.get_open())) == 0

    @classmethod
    def get_circuits(cls):
        # type: () -> Iterable[CircuitBreaker]
        return cls.circuit_breakers.values()

    @classmethod
    def get(cls, name):
        # type: (AnyStr) -> CircuitBreaker
        return cls.circuit_breakers.get(name)

    @classmethod
    def get_open(cls):
        # type: () -> Iterable[CircuitBreaker]
        for circuit in cls.get_circuits():
            if circuit.opened:
                yield circuit

    @classmethod
    def get_closed(cls):
        # type: () -> Iterable[CircuitBreaker]
        for circuit in cls.get_circuits():
            if circuit.closed:
                yield circuit


def circuit(failure_threshold=None,
            recovery_timeout=None,
            failure_if=None,
            name=None,
            fallback_function=None,
            cls=CircuitBreaker):

    # if the decorator is used without parameters, the
    # wrapped function is provided as first argument
    if callable(failure_threshold):
        return cls().decorate(failure_threshold)
    else:
        return cls(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            failure_if=failure_if,
            name=name,
            fallback_function=fallback_function)
