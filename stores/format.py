import inspect
import types as T
from enum import Enum
from typing import (
    Callable,
    GenericAlias,
    Type,
    Union,
    get_args,
    get_origin,
)

from stores.utils import check_duplicates


class ProviderFormat(str, Enum):
    OPENAI_CHAT = "openai-chat-completions"
    OPENAI_RESPONSES = "openai-responses"
    ANTHROPIC = "anthropic"
    GOOGLE_GEMINI = "google-gemini"


def get_type_info(param_type, param: inspect.Parameter, provider: ProviderFormat):
    """Helper method to get type information from a parameter type annotation."""
    origin = get_origin(param_type)
    args = get_args(param_type)
    # Check for default value first, as this applies regardless of type
    nullable = param.default is not inspect.Parameter.empty

    # Handle Union types
    if origin is Union or origin == T.UnionType:
        # Check if None is one of the types (Optional)
        nullable = nullable or type(None) in args
        # Filter out None types
        types = [t for t in args if t is not type(None)]
        if provider == ProviderFormat.GOOGLE_GEMINI:
            # For Gemini, we only use the first non-None type and track nullable
            param_type = types[0] if types else str
            args = get_args(param_type)
        else:
            # For OpenAI and Anthropic, we keep all types
            return types, param_type, nullable

    # Return type information (args, and nullability)
    return args, param_type, nullable


def get_types(param: Type | GenericAlias, nullable: bool = False) -> list[str]:
    """Helper method to get all the types."""
    type_mappings = {
        "str": "string",
        "int": "integer",
        "bool": "boolean",
        "float": "number",
        "list": "array",
        "NoneType": "null",
    }

    # Handle Union and Optional (since Optional is essentially Union[T, None])
    origin = get_origin(param)
    args = get_args(param)

    # If the parameter is a Union (like Union[int, str] or Optional[int])
    if origin is Union or origin == T.UnionType:
        types = []
        has_none = False
        for argtype in args:
            if argtype is type(None):
                has_none = True
                continue
            types.extend(get_types(argtype))
        if has_none or nullable:
            types.append("null")
        return types

    # If the param is a simple type (not Union, not Optional)
    try:
        type_name = param.__name__.lower()
        if type_name not in type_mappings:
            raise TypeError(f"Unsupported type: {param.__name__}")
        types = [type_mappings[type_name]]
        # Handle simple type with a default value
        if nullable:
            types.append("null")
        return types
    except (AttributeError, KeyError):
        types = ["string"]
        if nullable:
            types.append("null")
        return types


def format_tools(
    tools: list[Callable],
    provider: ProviderFormat,
):
    """Format tools based on the provider's requirements."""

    # Check for duplicate tool names
    check_duplicates([t.__name__ for t in tools])

    formatted_tools = []
    for tool in tools:
        # Extract parameters and their types from the tool's function signature
        signature = inspect.signature(tool)
        parameters = {}
        required_params = []
        for param_name, param in signature.parameters.items():
            param_type = param.annotation
            args, processed_type, nullable = get_type_info(param_type, param, provider)

            types = get_types(processed_type, nullable)

            param_info = {
                "type": types[0] if len(types) == 1 else types,
                "description": "",
            }
            if provider == ProviderFormat.GOOGLE_GEMINI:
                param_info["nullable"] = nullable

            if types[0] == "array":
                item_type = get_types(args[0] if args else "str", nullable)[0]
                param_info["items"] = {"type": item_type}

            parameters[param_name] = param_info

            required_params.append(param_name)

        # Create formatted tool structure based on provider
        description = inspect.getdoc(tool) or "No description available."
        base_params = {
            "type": "object",
            "properties": parameters,
            "required": required_params,
        }

        # Format tool based on provider
        if provider == ProviderFormat.OPENAI_CHAT:
            formatted_tool = {
                "type": "function",
                "function": {
                    # OpenAI only supports ^[a-zA-Z0-9_-]{1,64}$
                    "name": tool.__name__.replace(".", "-"),
                    "description": description,
                    "parameters": {**base_params, "additionalProperties": False},
                    "strict": True,
                },
            }
        elif provider == ProviderFormat.OPENAI_RESPONSES:
            formatted_tool = {
                "type": "function",
                # OpenAI only supports ^[a-zA-Z0-9_-]{1,64}$
                "name": tool.__name__.replace(".", "-"),
                "description": description,
                "parameters": {**base_params, "additionalProperties": False},
            }
        elif provider == ProviderFormat.ANTHROPIC:
            formatted_tool = {
                "name": tool.__name__,
                "description": description,
                "input_schema": base_params,
            }
        elif provider == ProviderFormat.GOOGLE_GEMINI:
            formatted_tool = {
                "name": tool.__name__,
                "parameters": {
                    "type": "object",
                    "description": description,
                    "properties": parameters,
                    "required": required_params,
                },
            }

        formatted_tools.append(formatted_tool)
    return formatted_tools
