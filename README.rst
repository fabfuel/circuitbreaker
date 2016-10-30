CircuitBreaker
--------------

.. image:: https://travis-ci.org/fabfuel/circuitbreaker.svg?branch=master
    :target: https://travis-ci.org/fabfuel/circuitbreaker

.. image:: https://scrutinizer-ci.com/g/fabfuel/circuitbreaker/badges/coverage.png?b=master
    :target: https://scrutinizer-ci.com/g/fabfuel/circuitbreaker

.. image:: https://scrutinizer-ci.com/g/fabfuel/circuitbreaker/badges/quality-score.png?b=master
    :target: https://scrutinizer-ci.com/g/fabfuel/circuitbreaker


This is an Python implementation of the "Circuit Breaker" Pattern (http://martinfowler.com/bliki/CircuitBreaker.html).
Inspired by Michael T. Nygard's highly recommendable book *Release It!* (https://pragprog.com/book/mnee/release-it).


Installation
------------

The project is available on PyPI. Simply run::

    $ pip install circuitbreaker


Usage
-----

This is the simplest example. Just decorate a function with the ``@circuit`` decorator::

    from circuitbreaker import circuit
    
    @circuit
    def external_call():
        ...


This decorator sets up a circuit breaker with the default settings. The circuit breaker:

- monitors the function execution and counts failures
- resets the failure count after every successful execution (while is is closed)
- opens and prevents further executions after 5 subsequent failures
- switches to half-open and allows one test-exection after 30 seconds recovery timeout
- closes if the test-execution succeeded
- considers all raised exceptions (based on class ``Exception``) as an expected failure
- is named "external_call" - the name of the function it decorates


What does *failure* mean?
=========================
A *failure* is a raised exception, which was not cought during the function call. 
By default, the circuit breaker listens for all exceptions based on the class ``Exception``. 
That means, that all exceptions raised during the function call are considered as an 
"expected failure" and will increase the failure count.

Get specific about the expected failure
=======================================
It is important, to be **as specific as possible**, when defining the expected exception. 
The main purpose of a circuit breaker is to protect your distributed system from a cascading failure.
That means, you probably want to open the circuit breaker only, if the integration point on the other
end is unavailable. So e.g. if there is an ``ConnectionError`` or a request ``Timeout``.

If you are e.g. using the requests library (http://docs.python-requests.org/) for making HTTP calls, 
its ``RequestException`` class would be a great choice for the ``expected_exception`` parameter.

All recognized exceptions will be reraised anyway, but the goal is, to let the circuit breaker only
recognize those exceptions which are related to the communication to your integration point.

When it comes to monitoring (see Monitoring_), it may lead to falsy conclusions, if a
circuit breaker opened, due to a local ``OSError`` or ``KeyError``, etc.


Configuration
-------------
The following configuration options can be adjusted via decorator parameters. For example::

    from circuitbreaker import circuit
    
    @circuit(failure_threshold=10, expected_exception=ConnectionError)
    def external_call():
        ...



failure threshold
=================
By default, the circuit breaker opens after 5 subsequent failures. You can adjust this value via the ``failure_threshold`` parameter.

recovery timeout
================
By default, the circuit breaker stays open for 30 seconds to allow the integration point to recover. You can adjust this value via the ``recovery_timeout`` parameter.

expected exception
==================
By default, the circuit breaker listens for all exceptions which are based on the ``Exception`` class. You can adjust this via the ``expected_exception`` parameter.

name
====
By default, the circuit breaker name is the name of the function it decorates. You can adjust the name via parameter ``name``.


Advanced Usage
--------------
If you apply circuit breakers to a couple of functions and you always set specific options other than the default values,
you can extend the ``CircuitBreaker`` class and create your own circuit breaker subclass instead::

    from circuitbreaker import CircuitBreaker
    
    class MyCircuitBreaker(CircuitBreaker):
        FAILURE_THRESHOLD = 10
        RECOVERY_TIMEOUT = 60
        EXPECTED_EXCEPTION = RequestException
        
        
Now you have two options to apply your circuit breaker to a function. As an Object directly::

    @MyCircuitBreaker()
    def external_call():
        ...

Please note, that the circuit breaker class has to be initialized, you have to use a class instance as decorator (``@MyCircuitBreaker()``), not the class itself (``@MyCircuitBreaker``).
        
Or via the decorator proxy::

    @circuit(cls=MyCircuitBreaker)
    def external_call():
        ...


.. _Monitoring:

Monitoring
----------
To keep track of the health of your application and the state of your circuit breakers, every circuit breaker registers itself at the ``CircuitBreakerMonitor``. You can receive all registered circuit breakers via ``CircuitBreakerMonitor.get_circuits()``.

To get an aggregated health status, you can ask the Monitor via ``CircuitBreakerMonitor.all_closed()``. Or you can retrieve the currently open circuits via ``CircuitBreakerMonitor.get_open()`` and the closed circuits via ``CircuitBreakerMonitor.get_closed()``.


Todo
----
- add unit tests
