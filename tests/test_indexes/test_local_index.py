import json

import pytest

from stores.indexes import LocalIndex


def test_local_index_basic(local_index_folder):
    index = LocalIndex(local_index_folder)
    assert [t.__name__ for t in index.tools] == [
        "tools.foo",
        "tools.foo_w_return_type",
        "tools.async_foo",
        "tools.enum_input",
        "tools.typed_dict_input",
        "hello.world",
    ]
    # Test tool execution
    sample_inputs = {
        "tools.foo": "hello world",
        "tools.foo_w_return_type": "hello world",
        "tools.async_foo": "hello world",
        "tools.enum_input": "red",
        "tools.typed_dict_input": {"name": "Tiger", "num_legs": 4},
        "hello.world": "hello world",
    }
    for tool in index.tools[:-1]:
        # Test execute
        result = index.execute(
            tool.__name__,
            kwargs={
                "bar": sample_inputs[tool.__name__],
            },
        )
        assert result == sample_inputs[tool.__name__]
        # Test parse_and_execute
        message = f"""{{"toolname": "{tool.__name__}", "kwargs": {{"bar": {json.dumps(sample_inputs[tool.__name__])}}}}}"""
        assert index.parse_and_execute(message) == sample_inputs[tool.__name__]


def test_local_index_invalid_tool(local_index_folder):
    index = LocalIndex(local_index_folder)
    # Non-existent tool should raise an error
    with pytest.raises(ValueError, match="No tool matching"):
        index.execute("not_a_tool")


def test_local_index_invalid_folder(buggy_index_folder):
    with pytest.raises(ValueError, match="Unable to load index"):
        LocalIndex(buggy_index_folder)


def test_local_index_with_deps(remote_index_folder):
    # Regular LocalIndex should not load index folder with deps since deps are not installed
    with pytest.raises(ModuleNotFoundError):
        LocalIndex(remote_index_folder)
    # LocalIndex can load index folder with deps if create_venv=True
    LocalIndex(remote_index_folder, create_venv=True)


def test_local_index_with_env_var():
    with pytest.raises(
        ValueError,
        match="Environment variables will only be restricted if create_venv=True when initializing LocalIndex",
    ):
        LocalIndex("", create_venv=False, env_var={"foo": "bar"})
