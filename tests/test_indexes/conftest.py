import inspect
import logging
import os
import shutil
import venv
from enum import Enum
from inspect import Parameter
from pathlib import Path
from typing import Optional, TypedDict, Union

import pytest

from stores.constants import VENV_NAME
from stores.format import ProviderFormat
from stores.indexes.venv_utils import HASH_FILE

logging.basicConfig()
logger = logging.getLogger("stores.test_indexes.conftest")
logger.setLevel(logging.INFO)

TEST_REPO_ID = "greentfrapp/tools-graph"
TEST_REPO_URL = f"http://github.com/{TEST_REPO_ID}.git"


@pytest.fixture()
def local_index_folder():
    return Path("./tests/mock_index")


@pytest.fixture(params=["tools.foo", "hello.world"])
def local_tools(request):
    yield request.params


config_files = [
    "pyproject.toml",
    "requirements.txt",
]


@pytest.fixture(
    scope="function",
    params=config_files,
)
def remote_index_folder(request):
    index_folder = Path("./tests/mock_index_w_deps")

    moved_files = []
    for file in config_files:
        if file != request.param:
            src = index_folder / file
            dst = index_folder / f".{file}"
            shutil.move(src, dst)
            moved_files.append([src, dst])

    # Create venv
    # venv_folder = index_folder / VENV_NAME
    # venv.create(venv_folder, symlinks=True, with_pip=True)
    yield index_folder
    # Clean up venv folder after tests
    shutil.rmtree(index_folder / VENV_NAME, ignore_errors=True)
    try:
        os.remove(index_folder / HASH_FILE)
    except FileNotFoundError:
        pass

    # Reinstate moved_files
    for src, dst in moved_files:
        shutil.move(dst, src)


def foo(bar: str):
    """
    Documentation of foo
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


async def union_tool(bar: Union[str, int]):
    """
    Documentation of union_tool
    Args:
        bar (str): Sample text
    """
    return bar


async def union_tool_w_none(bar: Union[None, str, int]):
    """
    Documentation of union_tool_w_none
    Args:
        bar (str): Sample text
    """
    return bar


@pytest.fixture(
    params=[
        {
            "function": foo,
            "signature": "(bar: str)",
            "params": [
                {
                    "name": "bar",
                    "type": str,
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "default": Parameter.empty,
                }
            ],
            "return_type": Parameter.empty,
        },
        {
            "function": async_foo,
            "signature": "(bar: str)",
            "params": [
                {
                    "name": "bar",
                    "type": str,
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "default": Parameter.empty,
                }
            ],
            "return_type": Parameter.empty,
        },
        {
            "function": union_tool,
            "signature": "(bar: str | int)",
            "params": [
                {
                    "name": "bar",
                    "type": str | int | None,
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "default": Parameter.empty,
                }
            ],
            "return_type": Parameter.empty,
        },
        {
            "function": union_tool_w_none,
            "signature": "(bar: str | int)",
            "params": [
                {
                    "name": "bar",
                    "type": str | int | None,
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "default": Parameter.empty,
                }
            ],
            "return_type": Parameter.empty,
        },
    ],
)
def sample_tool(request):
    yield request.param


def foo_w_default(bar: str = "test"):
    """
    Documentation of foo_w_default
    Args:
        bar (str): Sample text
    """
    return bar


def foo_w_default_notype(bar="test"):
    """
    Documentation of foo_w_default_notype
    Args:
        bar (str): Sample text
    """
    return bar


def foo_w_optional_and_default(bar: Optional[str] = "test"):
    """
    Documentation of foo_w_optional
    Args:
        bar (Optional[str]): Sample text
    """
    return bar


@pytest.fixture(
    params=[
        {
            "function": foo_w_default,
            "signature": "(bar: Optional[str] = None)",
        },
        {
            "function": foo_w_default_notype,
            "signature": "(bar: Optional[str] = None)",
        },
        {
            "function": foo_w_optional_and_default,
            "signature": "(bar: Optional[str] = None)",
        },
    ],
)
def sample_tool_w_defaults(request):
    function_metadata = {
        **request.param,
        "name": request.param["function"].__name__,
        "doc": inspect.getdoc(request.param["function"]),
    }
    yield function_metadata


def foo_w_optional_no_default(bar: Optional[str]):
    """
    Documentation of foo_w_optional
    Args:
        bar (Optional[str]): Sample text
    """
    bar = bar or "test"
    return bar


@pytest.fixture(
    params=[
        {
            "function": foo_w_optional_no_default,
            "signature": "(bar: str)",
        },
    ],
)
def sample_tool_optional_no_default(request):
    function_metadata = {
        **request.param,
        "name": request.param["function"].__name__,
        "doc": inspect.getdoc(request.param["function"]),
    }
    yield function_metadata


class Animal(TypedDict):
    name: str
    num_legs: int


def fn_with_typed_dict(animal: Animal) -> Animal:
    return animal


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


def fn_with_enum(color: Color) -> Color:
    return color


@pytest.fixture(
    params=[
        {
            "function": fn_with_typed_dict,
            "signature": "(animal: conftest.Animal) -> conftest.Animal",
            "remote_signature": "(animal: stores.index_utils.Animal) -> stores.index_utils.Animal",
            "sample_input": {"name": "Tiger", "num_legs": 4},
        },
        {
            "function": fn_with_enum,
            "signature": "(color: conftest.Color) -> conftest.Color",
            "remote_signature": "(color: stores.index_utils.Color) -> stores.index_utils.Color",
            "sample_input": 1,
        },
    ],
)
def complex_function(request):
    function_metadata = {
        **request.param,
        "name": request.param["function"].__name__,
        "doc": inspect.getdoc(request.param["function"]),
    }
    yield function_metadata


def divide_by_zero():
    return 1 / 0


@pytest.fixture(
    params=[
        {
            "function": divide_by_zero,
            "error": ZeroDivisionError,
        }
    ],
)
def buggy_tool(request):
    yield request.param


@pytest.fixture(
    params=[
        "non-existent/folder",  # Non-existent folder
        "tests",  # Folder exists but not an index
    ]
)
def buggy_index_folder(request):
    yield request.param


@pytest.fixture(
    params=[
        "./tests/mock_index_custom_class",
    ]
)
def index_folder_custom_class(request):
    # Create venv
    index_folder = Path(request.param)
    venv_folder = index_folder / VENV_NAME
    venv.create(venv_folder, symlinks=True, with_pip=True)
    yield index_folder
    # Clean up venv folder after tests
    shutil.rmtree(venv_folder)
    try:
        os.remove(index_folder / HASH_FILE)
    except FileNotFoundError:
        pass


@pytest.fixture(params=["./tests/mock_index_function_error"])
def index_folder_function_error(request):
    # Create venv
    index_folder = Path(request.param)
    venv_folder = index_folder / VENV_NAME
    venv.create(venv_folder, symlinks=True, with_pip=True)
    yield index_folder
    # Clean up venv folder after tests
    shutil.rmtree(venv_folder)
    try:
        os.remove(index_folder / HASH_FILE)
    except FileNotFoundError:
        pass


@pytest.fixture(params=ProviderFormat)
def provider(request):
    yield request.param


def cast_foo_int(bar: int):
    return bar


def cast_foo_float(bar: float):
    return bar


def cast_foo_str(bar: str):
    return bar


def cast_foo_bool(bar: bool):
    return bar


def cast_foo_list(bar: list[int]):
    return bar


def cast_foo_tuple(bar: tuple[int]):
    return bar


def cast_foo_typeddict(bar: Animal):
    return bar


def cast_foo_optional(bar: Optional[int] = None):
    return bar


def cast_foo_unhandled(bar: list[str, int]):
    return bar


@pytest.fixture(
    params=[
        {
            "tool_fn": cast_foo_int,
            "input": 1.0,
            "test": lambda x: x == 1 and isinstance(x, int),
        },
        {
            "tool_fn": cast_foo_float,
            "input": 1,
            "test": lambda x: x == 1.0 and isinstance(x, float),
        },
        {
            "tool_fn": cast_foo_str,
            "input": 1,
            "output_type": str,
            "test": lambda x: x == "1",
        },
        {
            "tool_fn": cast_foo_bool,
            "input": 1,
            "test": lambda x: x is True and isinstance(x, bool),
        },
        {
            "tool_fn": cast_foo_bool,
            "input": 0,
            "test": lambda x: x is False and isinstance(x, bool),
        },
        {
            "tool_fn": cast_foo_bool,
            "input": "false",
            "test": lambda x: x is False and isinstance(x, bool),
        },
        {
            "tool_fn": cast_foo_list,
            "input": [1.0],
            "test": lambda x: isinstance(x, list)
            and x[0] == 1
            and isinstance(x[0], int),
        },
        {
            "tool_fn": cast_foo_tuple,
            "input": [1.0],
            "test": lambda x: isinstance(x, tuple)
            and x[0] == 1
            and isinstance(x[0], int),
        },
        {
            "tool_fn": cast_foo_typeddict,
            "input": {
                "num_legs": 1.0,
                "name": 1,
            },
            "test": lambda x: x["num_legs"] == 1
            and isinstance(x["num_legs"], int)
            and x["name"] == "1",
        },
        {
            "tool_fn": cast_foo_optional,
            "input": 1.0,
            "test": lambda x: x == 1 and isinstance(x, int),
        },
        {
            "tool_fn": cast_foo_unhandled,
            "input": "unhandled",
            "test": lambda x: x == "unhandled",
        },
        {
            # Error case should also be unhandled
            "tool_fn": cast_foo_int,
            "input": "unhandled",
            "test": lambda x: x == "unhandled",
        },
    ]
)
def cast_tool(request):
    yield request.param
