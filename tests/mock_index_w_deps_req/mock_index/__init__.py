from typing import TypedDict

import pip_install_test


class Animal(TypedDict):
    name: str
    num_legs: int


def get_package():
    return pip_install_test.__name__


async def async_get_package():
    return pip_install_test.__name__


def tool_w_typed_dict(animal: Animal):
    return pip_install_test.__name__
