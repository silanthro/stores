import logging
from pathlib import Path

import pytest

from stores import Index

logging.basicConfig()
logger = logging.getLogger("stores.test_index.test_load_utils")
logger.setLevel(logging.INFO)


def test_load_index_from_functions(sample_tool):
    index = Index(
        [
            sample_tool["function"],
        ]
    )
    assert [t.__name__ for t in index.tools] == [
        sample_tool["name"],
        "REPLY",
    ]


def test_load_index_with_duplicates(sample_tool):
    tool_fn = sample_tool["function"]
    with pytest.raises(ValueError, match="Duplicate tool"):
        Index(
            [tool_fn, tool_fn],
        )


def test_load_index(local_index_folder):
    index = Index([local_index_folder])
    assert [t.__name__ for t in index.tools] == [
        "tools.foo",
        "tools.async_foo",
        "tools.enum_input",
        "tools.typed_dict_input",
        "hello.world",
        "REPLY",
    ]
    # Test tool execution
    sample_inputs = {
        "tools.foo": "hello world",
        "tools.async_foo": "hello world",
        "tools.enum_input": "red",
        "tools.typed_dict_input": {"name": "Tiger", "num_legs": 4},
        "hello.world": "hello world",
    }
    for tool in index.tools[:-1]:
        result = index.execute(
            tool.__name__,
            kwargs={
                "bar": sample_inputs[tool.__name__],
            },
        )
        assert result == sample_inputs[tool.__name__]
    sample_string = "hello world"
    assert index.execute("REPLY", {"msg": sample_string}) == sample_string
    # Test parse_and_execute
    message = f"""{{"toolname": "REPLY", "kwargs": {{"msg": "{sample_string}"}}}}"""
    assert index.parse_and_execute(message) == sample_string

    # Non-existent tool should raise an error
    with pytest.raises(ValueError, match="No tool matching"):
        index.execute("not_a_tool")


def test_load_index_error(buggy_index):
    with pytest.raises(ValueError, match="Unable to load index"):
        Index([Path(buggy_index)])
