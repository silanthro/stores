import inspect
import typing
from enum import Enum
from typing import GenericAlias, List, Type, Union


class ProviderFormat(str, Enum):
    OPENAI_CHAT = "openai-chat-completions"
    OPENAI_RESPONSES = "openai-responses"
    ANTHROPIC = "anthropic"
    GOOGLE_GEMINI = "google-gemini"


def get_type_info(param_type, param: inspect.Parameter, provider: ProviderFormat):
    """Helper method to get type information from a parameter type annotation."""
    origin = typing.get_origin(param_type)
    args = typing.get_args(param_type)
    # Check for default value first, as this applies regardless of type
    nullable = param.default is not inspect.Parameter.empty

    # Handle Union types
    if origin is Union:
        # Check if None is one of the types (Optional)
        nullable = nullable or type(None) in args
        # Filter out None types
        types = [t for t in args if t is not type(None)]
        if provider == ProviderFormat.GOOGLE_GEMINI:
            # For Gemini, we only use the first non-None type and track nullable
            param_type = types[0] if types else str
            args = typing.get_args(param_type)
        else:
            # For OpenAI and Anthropic, we keep all types
            return types, param_type, nullable

    # Return type information (args, and nullability)
    return args, param_type, nullable


def get_types(param: Type | GenericAlias, nullable: bool = False) -> List[str]:
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
    origin = typing.get_origin(param)
    args = typing.get_args(param)

    # If the parameter is a Union (like Union[int, str] or Optional[int])
    if origin is Union:
        types = []
        has_none = False
        for t in args:
            if t is type(None):
                has_none = True
                continue
            types.extend(get_types(t))
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
