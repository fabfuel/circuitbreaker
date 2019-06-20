from prometheus_client import Counter, Gauge
from circuitbreaker import STATE_CLOSED, STATE_OPEN, STATE_HALF_OPEN

"""
Prometheus Stats

Note: The initial state of the circuit breaker (ie. closed) will not be present
in the prom db till the first request comes through. The last request to be 
serviced will reflect the state of the circuit breaker.

Also, the circuit breaker metrics 'circuit_breaker_failure_total' and 
'circuit_breaker_success_total' have the labels name and state. The state 
represents the state of the circuit breaker when the success / failure took 
place. The states can be one of the following values:
1. STATE_CLOSED = b'closed'
2. STATE_OPEN = b'open'
3. STATE_HALF_OPEN = b'half-open'

"""

circuit_breaker_state = Gauge("circuit_breaker_state", "State of Circuit Breaker", ["name"])
circuit_breaker_failure_total = Counter("circuit_breaker_failure_total", "Count of failed remote calls", ["name", "state"])
circuit_breaker_success_total = Counter("circuit_breaker_success_total", "Count of success remote calls", ["name", "state"])

def record_circuit_breaker_state(name, state):
    if state == STATE_CLOSED:
        value = 0
    elif state == STATE_HALF_OPEN:
        value = 0.5
    elif state == STATE_OPEN:
        value = 1
    else:
        raise ValueError("unknown state found")

    circuit_breaker_state.labels(name=name).set(value)


def record_circuit_breaker_success_total(name, state):
    circuit_breaker_success_total.labels(name=name, state=state).inc()


def record_circuit_breaker_failure_total(name, state):
    circuit_breaker_failure_total.labels(name=name, state=state).inc()
