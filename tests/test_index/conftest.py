import inspect
import logging
import shutil
import venv
from pathlib import Path
from typing import Optional

import pytest

logging.basicConfig()
logger = logging.getLogger("stores.test_index.conftest")
logger.setLevel(logging.INFO)

TEST_REPO_ID = "greentfrapp/tools-graph"
TEST_REPO_URL = f"http://github.com/{TEST_REPO_ID}.git"
VENV_NAME = ".venv"


@pytest.fixture()
def local_index_folder():
    return Path("./tests/mock_index")


@pytest.fixture(params=["tools.foo", "hello.world"])
def local_tools(request):
    yield request.params


# @pytest.fixture(scope="session")
# def remote_index_folder(tmpdir_factory: pytest.TempdirFactory):
#     index_folder = tmpdir_factory.mktemp("tmp") / TEST_REPO_ID
#     Repo.clone_from(TEST_REPO_URL, index_folder)
#     # Create venv and install deps
#     venv_folder = index_folder / VENV_NAME
#     venv.create(venv_folder, symlinks=True, with_pip=True)
#     subprocess.call(
#         [f"{VENV_NAME}/bin/pip", "install", "."],
#         cwd=index_folder,
#     )
#     return index_folder


@pytest.fixture(
    scope="session",
    params=[
        "./tests/mock_index_w_deps_pyproject",
        "./tests/mock_index_w_deps_req",
    ],
)
def remote_index_folder(request):
    index_folder = Path(request.param)
    # Create venv
    venv_folder = index_folder / VENV_NAME
    venv.create(venv_folder, symlinks=True, with_pip=True)
    yield index_folder
    # Clean up venv folder after tests
    shutil.rmtree(venv_folder)


def foo(bar: str):
    """
    Documentation of foo
    Args:
        bar (str): Sample text
    """
    return bar


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


def foo_w_optional(bar: Optional[str]):
    """
    Documentation of foo_w_optional
    Args:
        bar (Optional[str]): Sample text
    """
    bar = bar or "test"
    return bar


def foo_w_optional_and_default(bar: Optional[str] = "test"):
    """
    Documentation of foo_w_optional
    Args:
        bar (Optional[str]): Sample text
    """
    return bar


async def async_foo(bar: str):
    """
    Documentation of async_foo
    Args:
        bar (str): Sample text
    """
    return bar


@pytest.fixture(
    params=[
        {
            "function": foo,
            "signature": "(bar: str)",
        },
        {
            "function": async_foo,
            "signature": "(bar: str)",
        },
    ],
)
def sample_tool(request):
    function_metadata = {
        **request.param,
        "name": request.param["function"].__name__,
        "doc": inspect.getdoc(request.param["function"]),
    }
    yield function_metadata


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
            "function": foo_w_optional,
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
def buggy_index(request):
    yield request.param
