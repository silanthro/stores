import inspect
import logging
import venv

import pytest

import stores.indexes.venv_utils as venv_utils
from stores.constants import VENV_NAME

logging.basicConfig()
logger = logging.getLogger("tests.test_indexes.test_venv_utils")
logger.setLevel(logging.INFO)


def test_init_venv_tools_without_venv(remote_index_folder):
    # Tools should not load without venv
    with pytest.raises(FileNotFoundError):
        venv_utils.init_venv_tools(remote_index_folder)


def test_init_venv_tools_without_install(remote_index_folder):
    # Create venv
    venv_folder = remote_index_folder / VENV_NAME
    venv.create(venv_folder, symlinks=True, with_pip=True)
    # Tools should not load without dependencies
    with pytest.raises(RuntimeError):
        venv_utils.init_venv_tools(remote_index_folder)


async def test_install_venv_deps(remote_index_folder):
    # Create venv
    venv_folder = remote_index_folder / VENV_NAME
    venv.create(venv_folder, symlinks=True, with_pip=True)
    # Test installation
    result = venv_utils.install_venv_deps(remote_index_folder)
    assert (remote_index_folder / venv_utils.HASH_FILE).exists()

    for config_file, cmd in venv_utils.SUPPORTED_DEP_CONFIGS.items():
        if (remote_index_folder / config_file).exists():
            assert result.endswith(cmd)
            assert venv_utils.has_installed(remote_index_folder / config_file)
            break

    # Running install again should show "Already installed"
    reinstall_result = venv_utils.install_venv_deps(remote_index_folder)
    assert reinstall_result == "Already installed"

    # Tools should load and be runnable
    tools = venv_utils.init_venv_tools(remote_index_folder)

    # Tools should run successfully
    sample_string = "red"
    sample_color = "red"
    sample_animal = {"name": "Tiger", "num_legs": 4}
    for tool in tools:
        if tool.__name__ == "mock_index.typed_function":
            kwargs = {"bar": sample_string}
        elif tool.__name__ == "mock_index.literal_input":
            kwargs = {"bar": sample_color}
        elif tool.__name__ == "mock_index.enum_input":
            kwargs = {"bar": sample_color}
        elif tool.__name__ == "mock_index.typed_dict_input":
            kwargs = {"bar": sample_animal}
        elif tool.__name__ == "mock_index.list_input":
            kwargs = {"bar": [sample_animal]}
        elif tool.__name__ == "mock_index.dict_input":
            kwargs = {"bar": {"animal": sample_animal}}
        elif tool.__name__ == "mock_index.tuple_input":
            # NOTE: Tuple gets transformed into list in run_remote_tool
            # due to json transformation
            kwargs = {"bar": [sample_animal, sample_animal]}
        elif tool.__name__ == "mock_index.union_input":
            kwargs = {"bar": sample_animal}
        else:
            kwargs = {}
        output = kwargs.get("bar", "pip_install_test")
        if inspect.iscoroutinefunction(tool):
            assert await tool(**kwargs) == output
        else:
            assert tool(**kwargs) == output


def test_index_with_invalid_tool(index_folder_custom_class):
    with pytest.raises(RuntimeError, match="Error loading tool"):
        venv_utils.init_venv_tools(index_folder_custom_class)


def test_index_with_tool_error(index_folder_function_error):
    tools = venv_utils.init_venv_tools(index_folder_function_error)
    with pytest.raises(RuntimeError, match="Subprocess failed with error"):
        tools[0]()


def test_parse_param_type_with_invalid_type():
    with pytest.raises(TypeError, match="Invalid param type"):
        venv_utils.parse_param_type({"type": "not a type"})
