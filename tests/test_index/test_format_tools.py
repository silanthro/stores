from typing import List, Optional, Union

import pytest

from stores.index import ProviderFormat


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

sample_tool_description = """Sample tool with various parameter types.

Args:
    str_param: A string parameter
    int_param: An integer parameter
    bool_param: A boolean parameter
    float_param: A float parameter
    default_param: A string parameter with a default value
    optional_param: An optional string parameter
    union_param: A parameter that can be string or integer"""


def check_minimum_properties(input_dict: dict, model_dict: dict):
    for key, value in model_dict.items():
        if isinstance(value, dict):
            check_minimum_properties(input_dict[key], value)
        else:
            assert value == input_dict[key]


def check_union_mappings(params: dict, expected_types: dict):
    for param_name, expected_type in expected_types.items():
        assert params[param_name]["type"] == expected_type


def test_openai_chat_format(clean_index):
    """Test OpenAI Chat format requirements."""
    clean_index.tools = [sample_tool]
    formatted_tools = clean_index.format_tools(ProviderFormat.OPENAI_CHAT)

    tool = formatted_tools[0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "sample_tool"
    assert tool["function"]["description"] == sample_tool_description

    # Test type mappings
    params = tool["function"]["parameters"]
    check_minimum_properties(params["properties"], sample_tool_min_args)

    # Test optional and union
    check_union_mappings(params["properties"], sample_tool_union_types)

    # Test structure requirements
    assert tool["function"]["strict"] is True
    assert params["additionalProperties"] is False


def test_openai_responses_format(clean_index):
    """Test OpenAI Responses format requirements."""
    clean_index.tools = [sample_tool]
    formatted_tools = clean_index.format_tools(ProviderFormat.OPENAI_RESPONSES)

    tool = formatted_tools[0]
    assert tool["type"] == "function"
    assert tool["name"] == "sample_tool"
    assert tool["description"] == sample_tool_description

    # Test type mappings
    params = tool["parameters"]
    check_minimum_properties(params["properties"], sample_tool_min_args)

    # Test optional and union
    check_union_mappings(params["properties"], sample_tool_union_types)

    # Test structure requirements
    assert params["additionalProperties"] is False


def test_anthropic_format(clean_index):
    """Test Anthropic format requirements."""
    clean_index.tools = [sample_tool]
    formatted_tools = clean_index.format_tools(ProviderFormat.ANTHROPIC)

    tool = formatted_tools[0]
    assert tool["name"] == "sample_tool"
    assert tool["description"] == sample_tool_description

    params = tool["input_schema"]
    assert params["type"] == "object"

    # Test type mappings
    check_minimum_properties(params["properties"], sample_tool_min_args)

    # Test optional and union
    check_union_mappings(params["properties"], sample_tool_union_types)


def test_gemini_format(clean_index):
    """Test Google Gemini format requirements."""
    clean_index.tools = [sample_tool]
    formatted_tools = clean_index.format_tools(ProviderFormat.GOOGLE_GEMINI)

    tool = formatted_tools[0]
    assert tool["name"] == "sample_tool"
    params = tool["parameters"]
    assert params["description"] == sample_tool_description
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


def test_list_type_formatting(clean_index, provider):
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

    clean_index.tools = [tool_with_lists]
    provider_mappings = {
        ProviderFormat.OPENAI_CHAT: ["function", "parameters", "properties"],
        ProviderFormat.OPENAI_RESPONSES: ["parameters", "properties"],
        ProviderFormat.GOOGLE_GEMINI: ["parameters", "properties"],
        ProviderFormat.ANTHROPIC: ["input_schema", "properties"],
    }

    output_format = clean_index.format_tools(provider)[0]
    for key in provider_mappings[provider]:
        output_format = output_format[key]
    check_minimum_properties(output_format, tool_with_lists_min_args)


def test_tool_metadata(clean_index):
    """Test tool name and description formatting."""

    def my_tool():
        """Tool description."""
        pass

    my_tool.__name__ = "my.complex.tool"

    clean_index.tools = [my_tool]
    formatted_tools = clean_index.format_tools(ProviderFormat.OPENAI_CHAT)

    tool = formatted_tools[0]
    # Test period to hyphen conversion in name
    assert tool["function"]["name"] == "my-complex-tool"
    # Test description extraction
    assert tool["function"]["description"] == "Tool description."


def test_unsupported_type(clean_index, provider):
    """Test that unsupported types raise TypeError."""

    def tool_with_set(param: set):  # set type is not supported
        pass

    clean_index.tools = [tool_with_set]
    with pytest.raises(TypeError, match="Unsupported type: set"):
        clean_index.format_tools(provider)


def test_empty_tools_list(clean_index):
    """Test that empty tools list raises ValueError."""
    clean_index.tools = []
    with pytest.raises(ValueError, match="No tools provided to format"):
        clean_index.format_tools(ProviderFormat.OPENAI_CHAT)


def test_multiple_tools(clean_index):
    """Test formatting multiple tools in a single call."""

    def tool_one(param1: str):
        """First tool."""
        pass

    def tool_two(param2: int):
        """Second tool."""
        pass

    clean_index.tools = [tool_one, tool_two]
    formatted_tools = clean_index.format_tools(ProviderFormat.OPENAI_CHAT)

    assert len(formatted_tools) == 2
    assert formatted_tools[0]["function"]["name"] == "tool_one"
    assert formatted_tools[0]["function"]["description"] == "First tool."
    assert formatted_tools[1]["function"]["name"] == "tool_two"
    assert formatted_tools[1]["function"]["description"] == "Second tool."


def test_duplicate_tool_names(clean_index):
    """Test that duplicate tool names raise ValueError."""

    def first_tool(param1: str):
        """First tool."""
        pass

    clean_index.tools = [first_tool, first_tool]
    with pytest.raises(ValueError, match=r"Duplicate tool name\(s\): \['first_tool'\]"):
        clean_index.format_tools(ProviderFormat.OPENAI_CHAT)
