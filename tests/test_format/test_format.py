import inspect
import logging
import re
from typing import List, Optional, Union

import pytest

from stores.format import ProviderFormat, format_tools

logging.basicConfig()
logger = logging.getLogger("stores.test_format.test_format")
logger.setLevel(logging.INFO)


def sample_tool(
    str_param: str,
    int_param: int,
    bool_param: bool,
    float_param: float,
    default_param: str = "default",
    optional_param: Optional[str] = None,
    union_param: Union[str, int] = "default",
) -> str:
    """Sample tool with various parameter types.

    Args:
        str_param: A string parameter
        int_param: An integer parameter
        bool_param: A boolean parameter
        float_param: A float parameter
        default_param: A string parameter with a default value
        optional_param: An optional string parameter
        union_param: A parameter that can be string or integer
    """
    return "test"


sample_tool_min_args = {
    "str_param": {"type": "string"},
    "int_param": {
        "type": "integer",
    },
    "bool_param": {
        "type": "boolean",
    },
    "float_param": {
        "type": "number",
    },
}

sample_tool_union_types = {
    "default_param": ["string", "null"],
    "optional_param": ["string", "null"],
    "union_param": ["string", "integer", "null"],
}


def check_minimum_properties(input_dict: dict, model_dict: dict):
    for key, value in model_dict.items():
        if isinstance(value, dict):
            check_minimum_properties(input_dict[key], value)
        else:
            assert value == input_dict[key]


def check_union_mappings(params: dict, expected_types: dict):
    for param_name, expected_type in expected_types.items():
        assert params[param_name]["type"] == expected_type


def test_openai_chat_format():
    """Test OpenAI Chat format requirements."""
    formatted_tools = format_tools(
        [sample_tool],
        ProviderFormat.OPENAI_CHAT,
    )

    tool = formatted_tools[0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == sample_tool.__name__
    assert tool["function"]["description"] == inspect.getdoc(sample_tool)

    # Test type mappings
    params = tool["function"]["parameters"]
    check_minimum_properties(params["properties"], sample_tool_min_args)

    # Test optional and union
    check_union_mappings(params["properties"], sample_tool_union_types)

    # Test structure requirements
    assert tool["function"]["strict"] is True
    assert params["additionalProperties"] is False


def test_openai_responses_format():
    """Test OpenAI Responses format requirements."""
    formatted_tools = format_tools(
        [sample_tool],
        ProviderFormat.OPENAI_RESPONSES,
    )

    tool = formatted_tools[0]
    assert tool["type"] == "function"
    assert tool["name"] == sample_tool.__name__
    assert tool["description"] == inspect.getdoc(sample_tool)

    # Test type mappings
    params = tool["parameters"]
    check_minimum_properties(params["properties"], sample_tool_min_args)

    # Test optional and union
    check_union_mappings(params["properties"], sample_tool_union_types)

    # Test structure requirements
    assert params["additionalProperties"] is False


def test_anthropic_format():
    """Test Anthropic format requirements."""
    formatted_tools = format_tools(
        [sample_tool],
        ProviderFormat.ANTHROPIC,
    )

    tool = formatted_tools[0]
    assert tool["name"] == sample_tool.__name__
    assert tool["description"] == inspect.getdoc(sample_tool)

    params = tool["input_schema"]
    assert params["type"] == "object"

    # Test type mappings
    check_minimum_properties(params["properties"], sample_tool_min_args)

    # Test optional and union
    check_union_mappings(params["properties"], sample_tool_union_types)


def test_gemini_format():
    """Test Google Gemini format requirements."""
    formatted_tools = format_tools(
        [sample_tool],
        ProviderFormat.GOOGLE_GEMINI,
    )

    tool = formatted_tools[0]
    assert tool["name"] == sample_tool.__name__
    params = tool["parameters"]
    assert params["description"] == inspect.getdoc(sample_tool)
    assert params["type"] == "object"

    # Test standard type mappings
    check_minimum_properties(params["properties"], sample_tool_min_args)

    # Test nullable field for optional parameters
    assert params["properties"]["default_param"]["nullable"] is True
    assert (
        params["properties"]["optional_param"]["nullable"] is True
    )  # Has Optional type
    assert params["properties"]["union_param"]["nullable"] is True  # Has default value
    # Test non-nullable for required parameters
    assert params["properties"]["str_param"]["nullable"] is False


def test_list_type_formatting(provider):
    """Test list type handling across providers."""

    def tool_with_lists(
        str_list: List[str],
        int_list: List[int],
        bool_list: List[bool],
        float_list: List[float],
    ):
        """Tool with various list types."""
        pass

    tool_with_lists_min_args = {
        "str_list": {"type": "array", "items": {"type": "string"}},
        "int_list": {"type": "array", "items": {"type": "integer"}},
        "bool_list": {"type": "array", "items": {"type": "boolean"}},
        "float_list": {"type": "array", "items": {"type": "number"}},
    }

    provider_mappings = {
        ProviderFormat.OPENAI_CHAT: ["function", "parameters", "properties"],
        ProviderFormat.OPENAI_RESPONSES: ["parameters", "properties"],
        ProviderFormat.GOOGLE_GEMINI: ["parameters", "properties"],
        ProviderFormat.ANTHROPIC: ["input_schema", "properties"],
    }

    output_format = format_tools(
        [tool_with_lists],
        provider,
    )[0]
    for key in provider_mappings[provider]:
        output_format = output_format[key]
    check_minimum_properties(output_format, tool_with_lists_min_args)


def test_multiple_tools(many_tools):
    """Test formatting multiple tools in a single call."""

    formatted_tools = format_tools(
        many_tools,
        ProviderFormat.OPENAI_CHAT,
    )

    assert len(formatted_tools) == len(many_tools)
    for i, tool in enumerate(many_tools):
        assert formatted_tools[i]["function"]["name"] == tool.__name__
        assert formatted_tools[i]["function"]["description"] == inspect.getdoc(tool)


def test_duplicate_tool_names(a_tool):
    """Test that duplicate tool names raise ValueError."""

    with pytest.raises(
        ValueError, match=re.escape(f"Found duplicate(s): {[a_tool.__name__]}")
    ):
        format_tools(
            [a_tool, a_tool],
            ProviderFormat.OPENAI_CHAT,
        )


def test_complex_argtype_openai_chat(a_tool_with_complex_args):
    tool_fn = a_tool_with_complex_args["tool_fn"]
    provider = a_tool_with_complex_args["provider"]
    expected_schema = a_tool_with_complex_args["expected_schema"]
    output = format_tools([tool_fn], provider)
    assert output == [expected_schema]


def test_unsupported_type(provider, a_tool_with_invalid_args):
    """Test that unsupported types raise TypeError."""
    with pytest.raises(TypeError, match=a_tool_with_invalid_args["error_msg"]):
        format_tools([a_tool_with_invalid_args["tool_fn"]], provider)
