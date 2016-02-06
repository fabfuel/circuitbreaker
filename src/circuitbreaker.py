from functools import wraps
from datetime import datetime, timedelta
from logging import getLogger

logger = getLogger('circuitbreaker')

STATE_OPEN = 'open'
STATE_HALFOPEN = 'halfopen'
STATE_CLOSED = 'closed'


class CircuitBreaker(object):
    def __init__(self, exception=Exception, failure_threshold=5, retry_timeout=30):
        self._exception = exception
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._retry_timeout = retry_timeout
        self._state = STATE_CLOSED
        self._opened = datetime.utcnow()

    def __call__(self, wrapped):
        @wraps(wrapped)
        def wrapper(*args, **kwargs):
            return self.call(wrapped, *args, **kwargs)
        return wrapper

    def call(self, func, *args, **kwargs):
        if self.is_open():
            print('  \__ %s failures' % self._failure_count)
            raise CircuitBreakerOpenError('CIRCUIT: open after %d failures until %s for another %s seconds' % (self._failure_threshold, self.open_until, self.open_remaining))

        try:
            result = func(*args, **kwargs)
        except self._exception as e:
            self._failure_count += 1

            if self._failure_count >= self._failure_threshold:
                self.open(e)

            raise
        else:
            self._state = STATE_CLOSED
            self._failure_count = 0
            return result

        finally:
            print('  \__ %s failures' % self._failure_count)

    def is_open(self):
        timeout = timedelta(seconds=self._retry_timeout)
        if self._state == STATE_OPEN and timeout < (datetime.utcnow() - self._opened):
            self._state = STATE_HALFOPEN
            return False

        return self._state == STATE_OPEN

    def open(self, exception):
        self._state = STATE_OPEN
        self._opened = datetime.utcnow()


    @property
    def open_until(self):
        return self._opened + timedelta(seconds=self._retry_timeout)

    @property
    def open_remaining(self):
        return (self.open_until - datetime.utcnow()).total_seconds()


class CircuitBreakerError(Exception):
    pass

class CircuitBreakerOpenError(CircuitBreakerError):
    pass
