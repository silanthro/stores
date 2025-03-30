from enum import Enum
from typing import Literal, TypedDict, Union

import pip_install_test


def get_package():
    return pip_install_test.__name__


async def async_get_package():
    return pip_install_test.__name__


def typed_function(bar: str) -> str:
    return bar


def literal_input(
    bar: Literal["red", "green", "blue"],
) -> Literal["red", "green", "blue"]:
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


def list_input(bar: list[Animal]) -> list[Animal]:
    return bar


def dict_input(bar: dict[str, Animal]) -> dict[str, Animal]:
    return bar


def tuple_input(bar: tuple[Animal]) -> tuple[Animal]:
    return bar


def union_input(bar: Union[Color, Animal]) -> Union[Color, Animal]:
    return bar
