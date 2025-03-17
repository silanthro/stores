import logging
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
            "signature": "get_package()",
            "doc": None,
            "async": False,
        },
        {
            "name": "mock_index.async_get_package",
            "signature": "async_get_package()",
            "doc": None,
            "async": True,
        },
    ]

    # Tools should run successfully
    for tool_sig in signatures:
        tool_output = utils.run_mp_process(
            fn=utils.run_remote_tool,
            kwargs={
                "tool_id": tool_sig["name"],
                "index_folder": remote_index_folder,
            },
            venv_folder=venv_folder,
        )
        assert tool_output == "pip_install_test"
