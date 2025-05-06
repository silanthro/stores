import inspect
import logging
import venv
from typing import get_args, get_origin, get_type_hints

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

    for config_file in venv_utils.SUPPORTED_CONFIGS:
        if (remote_index_folder / config_file).exists():
            assert result.endswith(
                f'"{" ".join(venv_utils.get_pip_command(venv_folder, config_file))}"'
            )
            assert venv_utils.has_installed(remote_index_folder / config_file)
            break

    # Running install again should show "Already installed"
    reinstall_result = venv_utils.install_venv_deps(remote_index_folder)
    assert reinstall_result == "Already installed"

    # Tools should load and be runnable
    tools = venv_utils.init_venv_tools(
        remote_index_folder,
        # Test exclude
        exclude=["mock_index.not_a_function"],
    )

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
        elif tool.__name__ in ["mock_index.stream_input", "mock_index.astream_input"]:
            kwargs = {"bar": sample_string}
        else:
            kwargs = {}
        output = kwargs.get("bar", "pip_install_test")
        if inspect.isasyncgenfunction(tool):
            async for value in tool(**kwargs):
                assert value == output
        elif inspect.isgeneratorfunction(tool):
            for value in tool(**kwargs):
                assert value == output
        elif inspect.iscoroutinefunction(tool):
            assert await tool(**kwargs) == output
        else:
            assert tool(**kwargs) == output


async def test_install_venv_deps_with_include(remote_index_folder):
    # Create venv
    venv_folder = remote_index_folder / VENV_NAME
    venv.create(venv_folder, symlinks=True, with_pip=True)
    # Test installation
    result = venv_utils.install_venv_deps(remote_index_folder)
    assert (remote_index_folder / venv_utils.HASH_FILE).exists()

    for config_file in venv_utils.SUPPORTED_CONFIGS:
        if (remote_index_folder / config_file).exists():
            assert result.endswith(
                f'"{" ".join(venv_utils.get_pip_command(venv_folder, config_file))}"'
            )
            assert venv_utils.has_installed(remote_index_folder / config_file)
            break

    # Running install again should show "Already installed"
    reinstall_result = venv_utils.install_venv_deps(remote_index_folder)
    assert reinstall_result == "Already installed"

    # Tools should load and be runnable
    tools = venv_utils.init_venv_tools(
        remote_index_folder,
        # Test include
        include=["mock_index.typed_function"],
    )

    assert len(tools) == 1
    tool = tools[0]
    assert tool.__name__ == "mock_index.typed_function"


def test_index_with_invalid_tool(index_folder_custom_class):
    with pytest.raises(RuntimeError, match="Error loading tool"):
        venv_utils.init_venv_tools(index_folder_custom_class)


def test_index_with_tool_error(index_folder_function_error):
    tools = venv_utils.init_venv_tools(index_folder_function_error)
    with pytest.raises(RuntimeError, match="ZeroDivisionError"):
        tools[0]()


def test_parse_param_type_with_forward_ref():
    param_info = {
        "type": "TypedDict",
        "type_name": "Person",
        "fields": {
            "name": {"type": str},
            "friends": {
                "type": "List",
                "item_type": {
                    "type": "Person",
                },
            },
        },
    }
    typ = venv_utils.parse_param_type(param_info)
    assert typ.__class__.__name__ == "_TypedDictMeta"
    assert typ.__name__ == "Person"
    hints = get_type_hints(typ)
    for k, v in hints.items():
        if k == "name":
            assert v is str
        elif k == "friends":
            origin = get_origin(v)
            assert origin is list
            args = list(get_args(v))
            assert len(args) == 1
            assert args[0] == "Person"
        else:
            raise AssertionError("Invalid attribute")


def test_parse_param_type_with_invalid_type():
    with pytest.raises(TypeError, match="Invalid param type"):
        venv_utils.parse_param_type({"type": "not a type"})
