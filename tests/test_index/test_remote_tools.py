import logging
from inspect import Parameter
from pathlib import Path

import pytest

import stores.index_utils as utils

logging.basicConfig()
logger = logging.getLogger("stores.test_index.test_remote_tools")
logger.setLevel(logging.INFO)


def test_remote_tool(remote_index_folder):
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
            "name": "mock_index.tool_w_typed_dict",
            "params": [
                {
                    "name": "animal",
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
    for sig in signatures:
        utils.wrap_remote_tool(
            sig,
            venv_folder,
            remote_index_folder,
        )

    # Tools should run successfully
    for tool_sig in signatures:
        tool_output = utils.run_mp_process(
            fn=utils.run_remote_tool,
            kwargs={
                "tool_id": tool_sig["name"],
                "kwargs": {"animal": {"name": "Tiger", "num_legs": 4}}
                if tool_sig["name"] == "mock_index.tool_w_typed_dict"
                else None,
                "index_folder": remote_index_folder,
            },
            venv_folder=venv_folder,
        )
        assert tool_output == "pip_install_test"
