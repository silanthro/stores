import pytest

from stores.format import ProviderFormat


@pytest.fixture(params=ProviderFormat)
def provider(request):
    yield request.param


def tool_one():
    """First tool."""
    pass


def tool_two():
    """Second tool."""
    pass


@pytest.fixture()
def many_tools():
    return [tool_one, tool_two]


@pytest.fixture()
def a_tool():
    return tool_one
