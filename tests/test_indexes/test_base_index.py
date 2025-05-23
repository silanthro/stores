import asyncio
import inspect
import json
import logging

import pytest

from stores.format import ProviderFormat
from stores.indexes.base_index import BaseIndex, wrap_tool

logging.basicConfig()
logger = logging.getLogger("stores.test_indexes.test_base_index")
logger.setLevel(logging.INFO)


async def test_wrap_tool(sample_tool):
    tool_fn = sample_tool["function"]
    wrapped_tool = wrap_tool(tool_fn)
    assert str(inspect.signature(wrapped_tool)) == sample_tool["signature"]
    assert wrapped_tool.__name__ == tool_fn.__name__
    assert inspect.getdoc(wrapped_tool) == inspect.getdoc(tool_fn)
    # Check that tool runs
    sample_string = "hello world"
    if inspect.iscoroutinefunction(tool_fn):
        assert await wrapped_tool(sample_string) == await tool_fn(sample_string)
    else:
        assert wrapped_tool(sample_string) == tool_fn(sample_string)


# Test default value injection
async def test_wrap_tool_w_defaults(sample_tool_w_defaults):
    tool_fn = sample_tool_w_defaults["function"]
    wrapped_tool = wrap_tool(tool_fn)
    assert str(inspect.signature(wrapped_tool)) == sample_tool_w_defaults["signature"]
    assert wrapped_tool.__name__ == sample_tool_w_defaults["name"]
    assert inspect.getdoc(wrapped_tool) == sample_tool_w_defaults["doc"]
    # Check that tool runs
    # Note: In some cases we need to supply an argument to the original function
    # even though arg annotation is Optional
    if inspect.iscoroutinefunction(tool_fn):
        try:
            original_result = await tool_fn()
        except TypeError:
            original_result = await tool_fn("test")
        assert await wrapped_tool() == original_result
    else:
        try:
            original_result = tool_fn()
        except TypeError:
            original_result = tool_fn("test")
        assert wrapped_tool() == original_result


def test_cast_bound_args(cast_tool):
    wrapped_fn = wrap_tool(cast_tool["tool_fn"])
    assert cast_tool["test"](wrapped_fn(cast_tool["input"]))


# If tool has Optional parameter without default, it should remove the Optional
async def test_wrap_tool_option_no_default(sample_tool_optional_no_default):
    tool_fn = sample_tool_optional_no_default["function"]
    wrapped_tool = wrap_tool(tool_fn)
    assert (
        str(inspect.signature(wrapped_tool))
        == sample_tool_optional_no_default["signature"]
    )
    assert wrapped_tool.__name__ == sample_tool_optional_no_default["name"]
    assert inspect.getdoc(wrapped_tool) == sample_tool_optional_no_default["doc"]
    # Check that error is raised when wrapped_tool is run without arguments
    with pytest.raises(TypeError):
        if inspect.iscoroutinefunction(tool_fn):
            await wrapped_tool()
        else:
            wrapped_tool()
    # Check that tool runs
    if inspect.iscoroutinefunction(tool_fn):
        assert await wrapped_tool("test") == await tool_fn("test")
    else:
        assert wrapped_tool("test") == tool_fn("test")


def test_base_index_from_functions(sample_tool):
    index = BaseIndex(
        [
            sample_tool["function"],
        ]
    )
    assert [t.__name__ for t in index.tools] == [
        sample_tool["function"].__name__,
    ]


def test_base_index_with_duplicates(sample_tool):
    tool_fn = sample_tool["function"]
    with pytest.raises(ValueError, match="Found duplicate"):
        BaseIndex(
            [tool_fn, tool_fn],
        )


def test_base_index_invalid_tool(sample_tool):
    index = BaseIndex([sample_tool["function"]])
    # Non-existent tool should raise an error
    with pytest.raises(ValueError, match="No tool matching"):
        index.execute("not_a_tool")


def test_base_index_match_multiple():
    # Artificial example with overwritten tool name
    # This should not happen in actual usage
    def foo():
        pass

    def alt_foo():
        pass

    alt_foo.__name__ = ":foo"

    index = BaseIndex([foo, alt_foo])
    # Non-existent tool should raise an error
    with pytest.raises(ValueError, match="matches multiple"):
        index.execute("foo")


def test_base_index_format_tools(sample_tool, provider):
    tool_fn = sample_tool["function"]
    index = BaseIndex([tool_fn])
    tools_format = index.format_tools(provider)

    param_types = {
        "foo": "string",
        "async_foo": "string",
        "union_tool": ["string", "integer"],
        "union_tool_w_none": ["string", "integer"],
    }
    tool_name = tool_fn.__name__
    param_type = param_types[tool_name]

    if provider == ProviderFormat.OPENAI_CHAT:
        assert tools_format == [
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": inspect.getdoc(tool_fn),
                    "parameters": {
                        "type": "object",
                        "properties": {"bar": {"type": param_type, "description": ""}},
                        "required": ["bar"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            }
        ]
    elif provider == ProviderFormat.OPENAI_RESPONSES:
        assert tools_format == [
            {
                "type": "function",
                "name": tool_name,
                "description": inspect.getdoc(tool_fn),
                "parameters": {
                    "type": "object",
                    "properties": {"bar": {"type": param_type, "description": ""}},
                    "required": ["bar"],
                    "additionalProperties": False,
                },
            }
        ]
    elif provider == ProviderFormat.ANTHROPIC:
        assert tools_format == [
            {
                "name": tool_name,
                "description": inspect.getdoc(tool_fn),
                "input_schema": {
                    "type": "object",
                    "properties": {"bar": {"type": param_type, "description": ""}},
                    "required": ["bar"],
                },
            }
        ]
    elif provider == ProviderFormat.GOOGLE_GEMINI:
        assert tools_format == [
            {
                "name": tool_name,
                "parameters": {
                    "type": "object",
                    "description": inspect.getdoc(tool_fn),
                    "properties": {
                        "bar": {
                            "type": param_type
                            if isinstance(param_type, str)
                            else param_type[0],
                            "description": "",
                            "nullable": False,
                        }
                    },
                    "required": ["bar"],
                },
            }
        ]


def handle_various_run_type(tool_fn, kwargs: dict, collect_results=False):
    if inspect.isasyncgenfunction(tool_fn):
        # Handle async generator

        async def collect():
            results = []
            async for value in tool_fn(**kwargs):
                results.append(value)
            if collect_results:
                return results
            else:
                return results[-1]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(collect())
    elif inspect.isgeneratorfunction(tool_fn):
        # Handle sync generator
        results = []
        for value in tool_fn(**kwargs):
            results.append(value)
        if collect_results:
            return results
        else:
            return results[-1]
    elif inspect.iscoroutinefunction(tool_fn):
        # Handle async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(tool_fn(**kwargs))
    else:
        # Handle sync
        return tool_fn(**kwargs)


async def ahandle_various_run_type(tool_fn, kwargs: dict, collect_results=False):
    kwargs = kwargs or {}
    if inspect.isasyncgenfunction(tool_fn):
        # Handle async generator
        results = []
        async for value in tool_fn(**kwargs):
            results.append(value)
        if collect_results:
            return results
        else:
            return results[-1]
    elif inspect.isgeneratorfunction(tool_fn):
        # Handle sync generator
        results = []
        for value in tool_fn(**kwargs):
            results.append(value)
        if collect_results:
            return results
        else:
            return results[-1]
    elif inspect.iscoroutinefunction(tool_fn):
        # Handle async
        return await tool_fn(**kwargs)
    else:
        # Handle sync
        return tool_fn(**kwargs)


def test_base_index_execute(various_runtype_tool):
    index = BaseIndex([various_runtype_tool])

    assert index.parse_and_execute(
        json.dumps(
            {
                "toolname": various_runtype_tool.__name__,
                "kwargs": {"bar": "hello"},
            }
        )
    ) == handle_various_run_type(various_runtype_tool, {"bar": "hello"})


async def test_base_index_aexecute(various_runtype_tool):
    index = BaseIndex([various_runtype_tool])

    assert await index.aparse_and_execute(
        json.dumps(
            {
                "toolname": various_runtype_tool.__name__,
                "kwargs": {"bar": "hello"},
            }
        )
    ) == await ahandle_various_run_type(various_runtype_tool, {"bar": "hello"})


def test_base_index_execute_collect(various_runtype_tool):
    index = BaseIndex([various_runtype_tool])

    assert index.execute(
        various_runtype_tool.__name__, {"bar": "hello"}, collect_results=True
    ) == handle_various_run_type(
        various_runtype_tool, {"bar": "hello"}, collect_results=True
    )


async def test_base_index_aexecute_collect(various_runtype_tool):
    index = BaseIndex([various_runtype_tool])

    assert await index.aexecute(
        various_runtype_tool.__name__, {"bar": "hello"}, collect_results=True
    ) == await ahandle_various_run_type(
        various_runtype_tool, {"bar": "hello"}, collect_results=True
    )


def test_base_index_stream_execute(various_runtype_tool):
    index = BaseIndex([various_runtype_tool])

    results = []
    for result in index.stream_parse_and_execute(
        json.dumps(
            {
                "toolname": various_runtype_tool.__name__,
                "kwargs": {"bar": "hello"},
            }
        )
    ):
        results.append(result)
    if not inspect.isgeneratorfunction(
        various_runtype_tool
    ) and not inspect.isasyncgenfunction(various_runtype_tool):
        results = results[0]

    answer = handle_various_run_type(
        various_runtype_tool, {"bar": "hello"}, collect_results=True
    )

    assert results == answer


async def test_base_index_astream_execute(various_runtype_tool):
    index = BaseIndex([various_runtype_tool])

    results = []
    async for result in index.astream_parse_and_execute(
        json.dumps(
            {
                "toolname": various_runtype_tool.__name__,
                "kwargs": {"bar": "hello"},
            }
        )
    ):
        results.append(result)
    if not inspect.isgeneratorfunction(
        various_runtype_tool
    ) and not inspect.isasyncgenfunction(various_runtype_tool):
        results = results[0]

    answer = await ahandle_various_run_type(
        various_runtype_tool, {"bar": "hello"}, collect_results=True
    )

    assert results == answer
