from functools import wraps
from datetime import datetime, timedelta

STATE_CLOSED = 'closed'
STATE_OPEN = 'open'
STATE_HALF_OPEN = 'half_open'


class CircuitBreaker(object):
    def __init__(self, expected_exception=Exception, failure_threshold=5, recover_timeout=30, name=None):
        self._expected_exception = expected_exception
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._recover_timeout = recover_timeout
        self._state = STATE_CLOSED
        self._opened = datetime.utcnow()
        self._name = name

    def __call__(self, wrapped):
        """
        Applies the circuit breaker decorator to a function
        """
        if self._name is None:
            self._name = wrapped.__name__

        @wraps(wrapped)
        def wrapper(*args, **kwargs):
            return self.call(wrapped, *args, **kwargs)

        return wrapper

    def call(self, func, *args, **kwargs):
        """
        Calls the decorated function and applies the circuit breaker rules on success or failure
        :param func: Decorated function
        """
        if not self.closed:
            raise CircuitBreakerError(self)
        try:
            result = func(*args, **kwargs)
        except self._expected_exception:
            self.on_failure()
            raise

        self.on_success()
        return result

    def on_success(self):
        """
        Close circuit after successful execution
        """
        self.close()

    def on_failure(self):
        """
        Count failure and open circuit, if threshold has been reached
        """
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self.open()

    def open(self):
        """
        Open the circuit breaker
        """
        self._state = STATE_OPEN
        self._opened = datetime.utcnow()

    def close(self):
        """
        Close the circuit breaker
        """
        self._state = STATE_CLOSED
        self._failure_count = 0

    @property
    def closed(self):
        """
        Check if state is CLOSED
        Set state to HALF_OPEN and allow the next execution, if recovery timeout has been reached
        """
        if self._state == STATE_OPEN and self.open_remaining <= 0:
            self._state = STATE_HALF_OPEN
            return True

        return self._state == STATE_CLOSED

    @property
    def open_until(self):
        """
        The datetime, when the circuit breaker will try to recover
        :return: datetime
        """
        return self._opened + timedelta(seconds=self._recover_timeout)

    @property
    def open_remaining(self):
        """
        Number of seconds (int) remaining, the circuit breaker stays in OPEN state
        :return: int
        """
        return (self.open_until - datetime.utcnow()).total_seconds()

    @property
    def failure_count(self):
        return self._failure_count

    @property
    def name(self):
        return self._name


class CircuitBreakerError(Exception):
    def __init__(self, circuit_breaker, *args, **kwargs):
        """
        :param circuit_breaker:
        :param args:
        :param kwargs:
        :return:
        """
        super().__init__(*args, **kwargs)
        self._circuit_breaker = circuit_breaker

    def __str__(self, *args, **kwargs):
        return 'CIRCUIT "%s" OPEN until %s (%d failures, %d sec remaining)' % (
            self._circuit_breaker.name,
            self._circuit_breaker.open_until,
            self._circuit_breaker.failure_count,
            round(self._circuit_breaker.open_remaining)
        )
