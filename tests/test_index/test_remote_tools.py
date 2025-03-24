import inspect
import logging
from inspect import Parameter
from pathlib import Path

import pytest

import stores.index_utils as utils

logging.basicConfig()
logger = logging.getLogger("stores.test_index.test_remote_tools")
logger.setLevel(logging.INFO)


async def test_remote_tool(remote_index_folder):
    venv_folder = Path(remote_index_folder) / utils.VENV_NAME
    # Check that tool retrieval fails initially
    with pytest.raises(ModuleNotFoundError):
        utils.run_mp_process(
            fn=utils.get_index_signatures,
            kwargs={"index_folder": remote_index_folder},
            venv_folder=venv_folder,
        )
    # Install dependencies
    # Since we are running install_venv_deps outside of run_mp_process
    # we have to specify lib_paths
    utils.install_venv_deps(
        index_folder=remote_index_folder,
        lib_paths=[
            remote_index_folder / utils.VENV_NAME / "lib/python3.12/site-packages"
        ],
    )

    # Check that tool retrieval succeeds after installation
    signatures = utils.run_mp_process(
        fn=utils.get_index_signatures,
        kwargs={"index_folder": remote_index_folder},
        venv_folder=venv_folder,
    )
    assert signatures == [
        {
            "name": "mock_index.get_package",
            "params": [],
            "doc": None,
            "is_async": False,
            "return_type": Parameter.empty,
        },
        {
            "name": "mock_index.async_get_package",
            "params": [],
            "doc": None,
            "is_async": True,
            "return_type": Parameter.empty,
        },
        {
            "name": "mock_index.typed_function",
            "params": [
                {
                    "name": "bar",
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "type": str,
                    "default": Parameter.empty,
                },
            ],
            "doc": None,
            "is_async": False,
            "return_type": {
                "type": str,
            },
        },
        {
            "name": "mock_index.enum_input",
            "params": [
                {
                    "name": "bar",
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "type": "enum",
                    "type_name": "Color",
                    "enum": {
                        "RED": "red",
                        "GREEN": "green",
                        "BLUE": "blue",
                    },
                    "default": Parameter.empty,
                },
            ],
            "doc": None,
            "is_async": False,
            "return_type": {
                "type": "enum",
                "type_name": "Color",
                "enum": {
                    "RED": "red",
                    "GREEN": "green",
                    "BLUE": "blue",
                },
            },
        },
        {
            "name": "mock_index.typed_dict_input",
            "params": [
                {
                    "name": "bar",
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "type": "object",
                    "type_name": "Animal",
                    "properties": {
                        "name": str,
                        "num_legs": int,
                    },
                    "default": Parameter.empty,
                },
            ],
            "doc": None,
            "is_async": False,
            "return_type": {
                "type": "object",
                "type_name": "Animal",
                "properties": {
                    "name": str,
                    "num_legs": int,
                },
            },
        },
    ]
    # Test wrap_remote_tool
    tools = [
        utils.wrap_remote_tool(
            sig,
            venv_folder,
            remote_index_folder,
        )
        for sig in signatures
    ]

    # Tools should run successfully
    for tool in tools:
        if tool.__name__ == "mock_index-typed_function":
            kwargs = {"bar": "red"}
            output = kwargs["bar"]
        elif tool.__name__ == "mock_index-enum_input":
            kwargs = {"bar": "red"}
            output = kwargs["bar"]
        elif tool.__name__ == "mock_index-typed_dict_input":
            kwargs = {"bar": {"name": "Tiger", "num_legs": 4}}
            output = kwargs["bar"]
        else:
            kwargs = {}
            output = "pip_install_test"
        if inspect.iscoroutinefunction(tool):
            assert await tool(**kwargs) == output
        else:
            assert tool(**kwargs) == output
