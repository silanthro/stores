from enum import Enum
from typing import TypedDict

import pytest

from stores.format import ProviderFormat


@pytest.fixture(params=ProviderFormat)
def provider(request):
    yield request.param


def tool_one():
    """First tool."""
    pass


def tool_two():
    """Second tool."""
    pass


@pytest.fixture()
def many_tools():
    return [tool_one, tool_two]


@pytest.fixture()
def a_tool():
    return tool_one


class Animal(TypedDict):
    name: str
    num_legs: int


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


def complex_foo(animal: Animal, color: Color):
    pass


@pytest.fixture()
def a_tool_with_complex_args(provider):
    tool = complex_foo
    description = "No description available."
    parameters = {
        "animal": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "",
                },
                "num_legs": {
                    "type": "integer",
                    "description": "",
                },
            },
            "description": "",
        },
        "color": {
            "type": "string",
            "enum": ["red", "green", "blue"],
            "description": "",
        },
    }
    required_params = ["animal", "color"]
    input_schema = {
        "type": "object",
        "properties": parameters,
        "required": required_params,
    }

    schema = {}
    if provider == ProviderFormat.OPENAI_CHAT:
        schema = {
            "type": "function",
            "function": {
                # OpenAI only supports ^[a-zA-Z0-9_-]{1,64}$
                "name": tool.__name__.replace(".", "-"),
                "description": description,
                "parameters": {**input_schema, "additionalProperties": False},
                "strict": True,
            },
        }
    elif provider == ProviderFormat.OPENAI_RESPONSES:
        schema = {
            "type": "function",
            # OpenAI only supports ^[a-zA-Z0-9_-]{1,64}$
            "name": tool.__name__.replace(".", "-"),
            "description": description,
            "parameters": {**input_schema, "additionalProperties": False},
        }
    elif provider == ProviderFormat.ANTHROPIC:
        schema = {
            # Claude only supports ^[a-zA-Z0-9_-]{1,64}$
            "name": tool.__name__.replace(".", "-"),
            "description": description,
            "input_schema": input_schema,
        }
    elif provider == ProviderFormat.GOOGLE_GEMINI:
        for k in parameters.keys():
            parameters[k]["nullable"] = False
        schema = {
            "name": tool.__name__,
            "parameters": {
                "type": "object",
                "description": description,
                "properties": parameters,
                "required": required_params,
            },
        }

    yield {
        "tool_fn": tool,
        "expected_schema": schema,
        "provider": provider,
    }
