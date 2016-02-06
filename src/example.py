from time import sleep

from src.circuitbreaker import CircuitBreaker

breaker = CircuitBreaker(failure_threshold=1, retry_timeout=5)

@breaker
def callx(i):
    if i in (2, 3, 6, 7, 10, 12, 15):
        raise ConnectionError('Connection refused')
    print('## SUCCESS')

if __name__ == '__main__':

    for i in range(0, 20):
        try:
            print('CALL: %s' % i)
            callx(i)
        except Exception as e:
            print('  \__ ' + str(e))

        sleep(1)
