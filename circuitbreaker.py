# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from functools import wraps
from datetime import datetime
from typing import AnyStr, Iterable

import ctypes
import multiprocessing

STATE_CLOSED = b'closed'
STATE_OPEN = b'open'
STATE_HALF_OPEN = b'half-open'

EPOCH = datetime.utcfromtimestamp(0)


def unix_time_seconds(dt):
    return (dt - EPOCH).total_seconds()


class CircuitBreaker(object):
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 30
    EXPECTED_EXCEPTION = Exception

    def __init__(self,
                 failure_threshold=None,
                 recovery_timeout=None,
                 expected_exception=None,
                 name=None):
        """
        
        :param failure_threshold: The minimum number of failures before opening circuit
        :param recovery_timeout: The number of seconds to elapse before circuit 
                                 can be considered in HALF_OPEN state
        :param expected_exception: Any exception expected from the external network call
        :param name: The name of the circuit breaker
        """
        self._lock = multiprocessing.RLock()
        self._failure_count = multiprocessing.Value(ctypes.c_int, 0, lock=self._lock)
        self._failure_threshold = failure_threshold or self.FAILURE_THRESHOLD
        self._recovery_timeout = recovery_timeout or self.RECOVERY_TIMEOUT
        self._expected_exception = expected_exception or self.EXPECTED_EXCEPTION
        self._name = name
        self._state = multiprocessing.Value(ctypes.c_char_p, STATE_CLOSED, lock=self._lock)
        self._opened = multiprocessing.Value(ctypes.c_double, unix_time_seconds(datetime.utcnow()), lock=self._lock)

    def __call__(self, wrapped):
        return self.decorate(wrapped)

    def decorate(self, function):
        """
        Applies the circuit breaker to a function
        """
        if self._name is None:
            self._name = function.__name__

        CircuitBreakerMonitor.register(self)

        @wraps(function)
        def wrapper(*args, **kwargs):
            return self.call(function, *args, **kwargs)

        return wrapper

    def call(self, func, *args, **kwargs):
        """
        Calls the decorated function and applies the circuit breaker
        rules on success or failure
        :param func: Decorated function
        """
        if self.opened:
            raise CircuitBreakerError(self)
        try:
            result = func(*args, **kwargs)
        except self._expected_exception:
            self.__call_failed()
            raise

        self.__call_succeeded()
        return result

    def __call_succeeded(self):
        """
        Close circuit after successful execution and reset failure count
        """
        with self._lock:
            self._state.value = STATE_CLOSED
            self._failure_count.value = 0

    def __call_failed(self):
        """
        Count failure and open circuit, if threshold has been reached
        """
        with self._lock:
            self._failure_count.value += 1
            if self._failure_count.value >= self._failure_threshold:
                    self._state.value = STATE_OPEN
                    self._opened.value = unix_time_seconds(datetime.utcnow())

    @property
    def state(self):
        if self._state.value == STATE_OPEN and self.open_remaining <= 0:
            return STATE_HALF_OPEN

        return self._state.value

    @property
    def open_until(self):
        """
        The epoch of when the circuit breaker will try to recover
        :return: epoch float
        """
        return self._opened.value + self._recovery_timeout

    @property
    def open_remaining(self):
        """
        Number of seconds remaining, the circuit breaker stays in OPEN state
        :return: float
        """
        return self.open_until - unix_time_seconds(datetime.utcnow())

    @property
    def failure_count(self):
        return self._failure_count.value

    @property
    def closed(self):
        return self.state == STATE_CLOSED

    @property
    def opened(self):
        return self.state == STATE_OPEN

    @property
    def name(self):
        return self._name

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
        return 'Circuit "%s" OPEN until %s (%d failures, %d sec remaining)' % (
            self._circuit_breaker.name,
            self._circuit_breaker.open_until,
            self._circuit_breaker.failure_count,
            round(self._circuit_breaker.open_remaining)
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
            expected_exception=None,
            name=None,
            cls=CircuitBreaker):

    # if the decorator is used without parameters, the
    # wrapped function is provided as first argument
    if callable(failure_threshold):
        return cls().decorate(failure_threshold)
    else:
        return cls(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=name)
