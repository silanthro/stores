from typing import List, Optional, Union

import pytest
from stores.index import Index, ProviderFormat


@pytest.fixture
def clean_index():
    """Create a clean Index instance without default tools."""
    index = Index(tools=[])
    return index


def sample_tool(
    str_param: str,
    int_param: int,
    bool_param: bool,
    float_param: float,
    list_param: List[str],
    optional_param: Optional[str] = None,
    union_param: Union[str, int] = "default",
) -> str:
    """Sample tool with various parameter types.

    Args:
        str_param: A string parameter
        int_param: An integer parameter
        bool_param: A boolean parameter
        float_param: A float parameter
        list_param: A list of strings
        optional_param: An optional string parameter
        union_param: A parameter that can be string or integer
    """
    return "test"


def test_openai_chat_format(clean_index):
    """Test OpenAI Chat format requirements."""
    clean_index.tools = [sample_tool]
    formatted_tools = clean_index.format_tools(ProviderFormat.OPENAI_CHAT)

    tool = formatted_tools[0]
    assert tool["type"] == "function"
    params = tool["function"]["parameters"]

    # Test type mappings
    assert params["properties"]["str_param"]["type"] == "string"
    assert params["properties"]["int_param"]["type"] == "integer"
    assert params["properties"]["bool_param"]["type"] == "boolean"
    assert params["properties"]["float_param"]["type"] == "number"
    assert params["properties"]["list_param"]["type"] == "array"
    assert params["properties"]["list_param"]["items"]["type"] == "string"

    # Test structure requirements
    assert tool["function"]["strict"] is True
    assert params["additionalProperties"] is False


def test_openai_responses_format(clean_index):
    """Test OpenAI Responses format requirements."""
    clean_index.tools = [sample_tool]
    formatted_tools = clean_index.format_tools(ProviderFormat.OPENAI_RESPONSES)

    tool = formatted_tools[0]
    assert tool["type"] == "function"
    params = tool["parameters"]

    # Test type mappings
    assert params["properties"]["str_param"]["type"] == "string"
    assert params["properties"]["int_param"]["type"] == "integer"
    assert params["properties"]["bool_param"]["type"] == "boolean"
    assert params["properties"]["float_param"]["type"] == "number"
    assert params["properties"]["list_param"]["type"] == "array"
    assert params["properties"]["list_param"]["items"]["type"] == "string"

    # Test structure requirements
    assert params["additionalProperties"] is False


def test_anthropic_format(clean_index):
    """Test Anthropic format requirements."""
    clean_index.tools = [sample_tool]
    formatted_tools = clean_index.format_tools(ProviderFormat.ANTHROPIC)

    tool = formatted_tools[0]
    params = tool["input_schema"]

    # Test type mappings
    assert params["properties"]["str_param"]["type"] == "string"
    assert params["properties"]["int_param"]["type"] == "integer"
    assert params["properties"]["bool_param"]["type"] == "boolean"
    assert params["properties"]["float_param"]["type"] == "number"
    assert params["properties"]["list_param"]["type"] == "array"
    assert params["properties"]["list_param"]["items"]["type"] == "string"


def test_gemini_format(clean_index):
    """Test Google Gemini format requirements."""
    clean_index.tools = [sample_tool]
    formatted_tools = clean_index.format_tools(ProviderFormat.GOOGLE_GEMINI)

    tool = formatted_tools[0]
    params = tool["parameters"]

    # Test standard type mappings
    assert params["properties"]["str_param"]["type"] == "string"
    assert params["properties"]["int_param"]["type"] == "integer"
    assert params["properties"]["bool_param"]["type"] == "boolean"
    assert params["properties"]["float_param"]["type"] == "number"
    assert params["properties"]["list_param"]["type"] == "array"
    assert params["properties"]["list_param"]["items"]["type"] == "string"

    # Test nullable field for optional parameters
    assert (
        params["properties"]["optional_param"]["nullable"] is True
    )  # Has Optional type
    assert params["properties"]["union_param"]["nullable"] is True  # Has default value
    # Test non-nullable for required parameters
    assert params["properties"]["str_param"]["nullable"] is False


def test_list_type_formatting(clean_index):
    """Test list type handling across providers."""

    def tool_with_lists(
        str_list: List[str],
        int_list: List[int],
        bool_list: List[bool],
        float_list: List[float],
    ):
        """Tool with various list types."""
        pass

    clean_index.tools = [tool_with_lists]

    # Test OpenAI format
    openai_tool = clean_index.format_tools(ProviderFormat.OPENAI_CHAT)[0]
    params = openai_tool["function"]["parameters"]["properties"]
    assert params["str_list"]["type"] == "array"
    assert params["str_list"]["items"]["type"] == "string"
    assert params["int_list"]["type"] == "array"
    assert params["int_list"]["items"]["type"] == "integer"
    assert params["bool_list"]["type"] == "array"
    assert params["bool_list"]["items"]["type"] == "boolean"
    assert params["float_list"]["type"] == "array"
    assert params["float_list"]["items"]["type"] == "number"

    # Test Gemini format
    gemini_tool = clean_index.format_tools(ProviderFormat.GOOGLE_GEMINI)[0]
    params = gemini_tool["parameters"]["properties"]
    assert params["str_list"]["type"] == "array"
    assert params["str_list"]["items"]["type"] == "string"
    assert params["int_list"]["type"] == "array"
    assert params["int_list"]["items"]["type"] == "integer"
    assert params["bool_list"]["type"] == "array"
    assert params["bool_list"]["items"]["type"] == "boolean"
    assert params["float_list"]["type"] == "array"
    assert params["float_list"]["items"]["type"] == "number"

    # Test Anthropic format
    anthropic_tool = clean_index.format_tools(ProviderFormat.ANTHROPIC)[0]
    params = anthropic_tool["input_schema"]["properties"]
    assert params["str_list"]["type"] == "array"
    assert params["str_list"]["items"]["type"] == "string"
    assert params["int_list"]["type"] == "array"
    assert params["int_list"]["items"]["type"] == "integer"
    assert params["bool_list"]["type"] == "array"
    assert params["bool_list"]["items"]["type"] == "boolean"
    assert params["float_list"]["type"] == "array"
    assert params["float_list"]["items"]["type"] == "number"


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


def test_unsupported_type(clean_index):
    """Test that unsupported types raise TypeError."""

    def tool_with_set(param: set):  # set type is not supported
        pass

    clean_index.tools = [tool_with_set]
    with pytest.raises(TypeError, match="Unsupported type: set"):
        clean_index.format_tools(ProviderFormat.OPENAI_CHAT)

    # Test Gemini format - uses same error message
    with pytest.raises(TypeError, match="Unsupported type: set"):
        clean_index.format_tools(ProviderFormat.GOOGLE_GEMINI)


def test_unsupported_array_type(clean_index):
    """Test that unsupported array item types raise TypeError."""

    def tool_with_set_array(param: List[set]):  # array of sets is not supported
        pass

    clean_index.tools = [tool_with_set_array]
    with pytest.raises(TypeError, match="Unsupported type for array items: set"):
        clean_index.format_tools(ProviderFormat.OPENAI_CHAT)

    # Test Gemini format - uses same error message
    with pytest.raises(TypeError, match="Unsupported type for array items: set"):
        clean_index.format_tools(ProviderFormat.GOOGLE_GEMINI)


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

    first_tool.__name__ = "tool_one"  # Set same name

    def second_tool(param2: int):
        """Second tool with same name."""
        pass

    second_tool.__name__ = "tool_one"  # Set same name

    clean_index.tools = [first_tool, second_tool]  # Both tools have name "tool_one"
    with pytest.raises(ValueError, match="Duplicate tool name: tool_one"):
        clean_index.format_tools(ProviderFormat.OPENAI_CHAT)
