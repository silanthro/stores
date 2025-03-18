import logging
from inspect import Parameter

import stores.index_utils as utils

logging.basicConfig()
logger = logging.getLogger("stores.test_index.text_index_utils")
logger.setLevel(logging.INFO)


def test_get_index_signatures(local_index_folder):
    signatures = utils.get_index_signatures(local_index_folder)
    assert signatures == [
        {
            "name": "tools.foo",
            "params": [
                {
                    "name": "bar",
                    "type": str,
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "default": Parameter.empty,
                }
            ],
            "doc": "Documentation of foo\nArgs:\n    bar (str): Sample text",
            "async": False,
        },
        {
            "name": "tools.async_foo",
            "params": [
                {
                    "name": "bar",
                    "type": str,
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "default": Parameter.empty,
                }
            ],
            "doc": "Documentation of async_foo\nArgs:\n    bar (str): Sample text",
            "async": True,
        },
        {
            "name": "tools.enum_input",
            "params": [
                {
                    "name": "bar",
                    "type": "enum",
                    "enum": {
                        "RED": "red",
                        "GREEN": "green",
                        "BLUE": "blue",
                    },
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "default": Parameter.empty,
                }
            ],
            "doc": None,
            "async": False,
        },
        {
            "name": "tools.typed_dict_input",
            "params": [
                {
                    "name": "bar",
                    "type": "object",
                    "properties": {
                        "name": str,
                        "num_legs": int,
                    },
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "default": Parameter.empty,
                }
            ],
            "doc": None,
            "async": False,
        },
        {
            "name": "hello.world",
            "params": [
                {
                    "name": "bar",
                    "type": str,
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                    "default": Parameter.empty,
                }
            ],
            "doc": None,
            "async": False,
        },
    ]


def test_get_index_tools(local_index_folder):
    tools = utils.get_index_tools(local_index_folder)
    assert [t.__name__ for t in tools] == [
        "tools.foo",
        "tools.async_foo",
        "tools.enum_input",
        "tools.typed_dict_input",
        "hello.world",
    ]


def test_run_remote_tool(local_index_folder):
    tools = utils.get_index_tools(local_index_folder)
    sample_inputs = {
        "tools.foo": "hello world",
        "tools.async_foo": "hello world",
        "tools.enum_input": "red",
        "tools.typed_dict_input": {"name": "Tiger", "num_legs": 4},
        "hello.world": "hello world",
    }
    for tool in tools:
        result = utils.run_remote_tool(
            tool.__name__,
            index_folder=local_index_folder,
            args=[sample_inputs[tool.__name__]],
        )
        assert result == sample_inputs[tool.__name__]
