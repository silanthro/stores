import inspect
import logging

import stores.index_utils as utils

logging.basicConfig()
logger = logging.getLogger("stores.test_index.test_tool_wrappers")
logger.setLevel(logging.INFO)


# Check that wrapped tool has same metadata as original tool
def test_wrap_remote_tool(sample_tool):
    tool_fn = sample_tool["function"]
    tool_metadata = {
        "name": sample_tool["name"],
        "params": sample_tool["params"],
        "doc": sample_tool["doc"],
        "async": inspect.iscoroutinefunction(tool_fn),
    }
    wrapped_tool = utils.wrap_remote_tool(
        tool_metadata,
        "./",
        "./.venv",
    )
    assert str(inspect.signature(wrapped_tool)) == sample_tool["signature"]
    assert wrapped_tool.__name__ == sample_tool["name"]
    assert inspect.getdoc(wrapped_tool) == sample_tool["doc"]
    assert inspect.iscoroutinefunction(wrapped_tool) == inspect.iscoroutinefunction(
        tool_fn
    )


# Check that wrapped tool has same metadata as original tool
async def test_wrap_tool(sample_tool):
    tool_fn = sample_tool["function"]
    wrapped_tool = utils.wrap_tool(tool_fn)
    assert str(inspect.signature(wrapped_tool)) == sample_tool["signature"]
    assert wrapped_tool.__name__ == sample_tool["name"]
    assert inspect.getdoc(wrapped_tool) == sample_tool["doc"]
    # Check that tool runs
    sample_string = "hello world"
    if inspect.iscoroutinefunction(tool_fn):
        assert await wrapped_tool(sample_string) == await tool_fn(sample_string)
    else:
        assert wrapped_tool(sample_string) == tool_fn(sample_string)


# Test default value injection
async def test_wrap_tool_w_defaults(sample_tool_w_defaults):
    tool_fn = sample_tool_w_defaults["function"]
    wrapped_tool = utils.wrap_tool(tool_fn)
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


# Test complex args
async def test_wrap_tool_w_complex_args(complex_function):
    tool_fn = complex_function["function"]
    sample_input = complex_function["sample_input"]
    wrapped_tool = utils.wrap_tool(tool_fn)
    assert str(inspect.signature(wrapped_tool)) == complex_function["signature"]
    # Check that tool runs
    # Note: In some cases we need to supply an argument to the original function
    # even though arg annotation is Optional
    if inspect.iscoroutinefunction(tool_fn):
        assert await wrapped_tool(sample_input) == await tool_fn(sample_input)
    else:
        assert wrapped_tool(sample_input) == tool_fn(sample_input)
