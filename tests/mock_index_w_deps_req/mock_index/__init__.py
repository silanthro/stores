from enum import Enum
from typing import TypedDict

import pip_install_test


def get_package():
    return pip_install_test.__name__


async def async_get_package():
    return pip_install_test.__name__


def typed_function(bar: str) -> str:
    return bar


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


def enum_input(bar: Color) -> Color:
    return bar


class Animal(TypedDict):
    name: str
    num_legs: int


def typed_dict_input(bar: Animal) -> Animal:
    return bar
