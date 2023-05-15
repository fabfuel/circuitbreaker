import asyncio
import time
from enum import Enum

import pytest

from circuitbreaker import CircuitBreakerMonitor


class FunctionType(str, Enum):
    sync_function = "sync-function"
    sync_generator = "sync-generator"
    async_function = "async-function"
    async_generator = "async-generator"


@pytest.fixture(autouse=True)
def clean_circuit_breaker_monitor():
    CircuitBreakerMonitor.circuit_breakers = {}


@pytest.fixture(params=FunctionType, ids=[e.value for e in FunctionType])
def function_type(request):
    return request.param


@pytest.fixture
def is_async(function_type):
    return function_type.startswith("async-")


@pytest.fixture
def is_generator(function_type):
    return function_type.endswith("-generator")


@pytest.fixture
def function_factory(function_type):
    def factory(inner_call):
        def _sync(*a, **kwa):
            return inner_call(*a, **kwa)

        def _sync_gen(*a, **kwa):
            yield inner_call(*a, **kwa)

        async def _async(*a, **kwa):
            return inner_call(*a, **kwa)

        async def _async_gen(*a, **kwa):
            yield inner_call(*a, **kwa)

        mapping = {
            FunctionType.sync_function: _sync,
            FunctionType.sync_generator: _sync_gen,
            FunctionType.async_function: _async,
            FunctionType.async_generator: _async_gen,
        }
        return mapping[function_type]

    return factory


@pytest.fixture
def resolve_call(function_type):
    """
    This fixture helps abstract calls from other fixtures that have sync and
    async, function and generator versions.

    For example, this:
        if is_async:
            if is_generator:
                result = [el async for el in function()]
            else:
                result = await function()
        else:
            if is_generator:
                result = list(function())
            else:
                result = function()

    Can be replaced with:
        result = await resolve_call(function())

    """
    async def _sync(value):
        return value

    async def _sync_gen(generator):
        return list(generator)

    async def _async(coroutine):
        return await coroutine

    async def _async_gen(async_generator):
        return [el async for el in async_generator]

    mapping = {
        FunctionType.sync_function: _sync,
        FunctionType.sync_generator: _sync_gen,
        FunctionType.async_function: _async,
        FunctionType.async_generator: _async_gen,
    }
    return mapping[function_type]


@pytest.fixture
def sleep(is_async):
    async def _sleep(secs):
        if is_async:
            await asyncio.sleep(secs)
        else:
            time.sleep(secs)

    return _sleep


@pytest.fixture
def mock_function_call(mocker):
    return mocker.Mock(return_value=object())


@pytest.fixture
def mock_fallback_call(mocker):
    return mocker.Mock(return_value=object())


@pytest.fixture
def function_call_return_value(is_generator, mock_function_call):
    value = mock_function_call.return_value
    return [value] if is_generator else value


@pytest.fixture
def fallback_call_return_value(is_generator, mock_fallback_call):
    value = mock_fallback_call.return_value
    return [value] if is_generator else value


@pytest.fixture
def function_call_error(mock_function_call):
    error = IOError
    mock_function_call.side_effect = error
    return error


@pytest.fixture
def function(function_factory, mock_function_call):
    return function_factory(mock_function_call)


@pytest.fixture
def fallback_function(function_factory, mock_fallback_call):
    return function_factory(mock_fallback_call)
