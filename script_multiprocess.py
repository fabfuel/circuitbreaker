"""
You can ignore this file. It is just present to help run a simple program to
test two processes communciating with one another
"""
from circuitbreaker import CircuitBreaker

import os
import multiprocessing
import time

prefix = "unforked"

def p(message):
    print(prefix + ": " + message)

p("program starting")
v = multiprocessing.Value('i')
p("about to fork")
v.value = 0
l = multiprocessing.Lock()
A= CircuitBreaker(failure_threshold=8, name="rogan-tset", expected_exception=ValueError, recovery_timeout=4,)
C = CircuitBreaker(failure_threshold=8, name="boooo-test", expected_exception=ValueError, recovery_timeout=4,)

@A
def test():
    raise ValueError("sorry rogan")

@C
def test1():
    print "hello"

class B(object):
    def __init__(self):
        self.val = multiprocessing.Value('i', 0)

    def inc(self):
        with self.val.get_lock():
            self.val.value += 1

from datetime import datetime

if os.fork():
    prefix = "parent"
    # b = B()
    for i in xrange(10):
        with A._state.get_lock():
            p(str(datetime.utcnow()) + " parent state of cb before:" + A.state + " failure count:" + str(A.failure_count) + " time remaining:" + str(A.open_remaining))
        try:
            test()
        except Exception as e :
            print("parent " + str(e))
            with A._state.get_lock():
                p(str(datetime.utcnow()) +" parent state of cb after:" + A.state + " failure count:" + str(A.failure_count) + " time remaining:" + str(A.open_remaining))
            time.sleep(1)


    os.wait()
    p("parent says value is: %s" % (A.state,))
    p(str(datetime.utcnow()) + " FINAL parent state of cb:" + C.state + " failure count:" + str(C.failure_count) + " time remaining:" + str(C.open_remaining))

else:
    prefix = "child"
    for i in xrange(10):
        with A._state.get_lock():
            p(str(datetime.utcnow()) +" child state of cb before:" + A.state + " failure count:" + str(A.failure_count) + " time remaining:" + str(A.open_remaining))
        try:
            test()
        except Exception as e:
            print("child " + str(e))
            with A._state.get_lock():
                p(str(datetime.utcnow()) + " child state of cb after:" + A.state + " failure count:" + str(A.failure_count) + " time remaining:" + str(A.open_remaining))
            time.sleep(.5)

    p(str(datetime.utcnow()) + " FINAL child state of cb:" + C.state + " failure count:" + str(C.failure_count) + " time remaining:" + str(C.open_remaining))
p(prefix + " program ending")
