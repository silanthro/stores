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
            "async": False,
        },
        {
            "name": "mock_index.async_get_package",
            "params": [],
            "doc": None,
            "async": True,
        },
        {
            "name": "mock_index.enum_input",
            "params": [
                {
                    "name": "bar",
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "type": "enum",
                    "enum": {
                        "RED": "red",
                        "GREEN": "green",
                        "BLUE": "blue",
                    },
                    "default": Parameter.empty,
                },
            ],
            "doc": None,
            "async": False,
        },
        {
            "name": "mock_index.typed_dict_input",
            "params": [
                {
                    "name": "bar",
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "type": "object",
                    "properties": {
                        "name": str,
                        "num_legs": int,
                    },
                    "default": Parameter.empty,
                },
            ],
            "doc": None,
            "async": False,
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
        if tool.__name__ == "mock_index.enum_input":
            kwargs = {"bar": "red"}
        elif tool.__name__ == "mock_index.typed_dict_input":
            kwargs = {"bar": {"name": "Tiger", "num_legs": 4}}
        else:
            kwargs = {}
        if inspect.iscoroutinefunction(tool):
            assert await tool(**kwargs) == "pip_install_test"
        else:
            assert tool(**kwargs) == "pip_install_test"

    # for tool_sig in signatures:
    #     tool_output = utils.run_mp_process(
    #         fn=utils.run_remote_tool,
    #         kwargs={
    #             "tool_id": tool_sig["name"],
    #             "kwargs": {"animal": {"name": "Tiger", "num_legs": 4}}
    #             if tool_sig["name"] == "mock_index.tool_w_typed_dict"
    #             else None,
    #             "index_folder": remote_index_folder,
    #         },
    #         venv_folder=venv_folder,
    #     )
    #     assert tool_output == "pip_install_test"
