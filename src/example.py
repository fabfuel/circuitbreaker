from time import sleep
from src.circuitbreaker import CircuitBreaker


@CircuitBreaker(failure_threshold=2, recover_timeout=3)
def external_call(call_id):
    if call_id in (2, 3, 6, 7, 10, 12, 15):
        raise ConnectionError('Connection refused')
    return 'SUCCESS'

for i in range(0, 20):
    try:
        print('CALL: %d' % i)
        print(' ## %s ' % external_call(i))
    except Exception as e:
        print('  \__ %s ' % e)

    sleep(0.5)
