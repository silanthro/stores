from enum import Enum
from typing import Literal, TypedDict


def foo(bar: str):
    """
    Documentation of foo
    Args:
        bar (str): Sample text
    """
    return bar


def foo_w_return_type(bar: str) -> str:
    """
    Documentation of foo_w_return_type
    Args:
        bar (str): Sample text
    """
    return bar


async def async_foo(bar: str):
    """
    Documentation of async_foo
    Args:
        bar (str): Sample text
    """
    return bar


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


def enum_input(bar: Color):
    return bar


class Animal(TypedDict):
    name: str
    num_legs: int


def typed_dict_input(bar: Animal):
    return bar


def literal_input(bar: Literal["red", "green", "blue"]):
    return bar


def literal_nonstring_input(bar: Literal[1, 2, 3]):
    return bar


def default_input(bar: str = "foo"):
    return bar


def stream_input(bar: str):
    for _ in range(3):
        yield bar


async def astream_input(bar: str):
    for _ in range(3):
        yield bar
