import inspect
import logging
import types as T
from enum import Enum
from itertools import chain
from typing import (
    Callable,
    Dict,
    GenericAlias,
    List,
    Literal,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from stores.utils import check_duplicates

logging.basicConfig()
logger = logging.getLogger("stores.format")
logger.setLevel(logging.INFO)


class ProviderFormat(str, Enum):
    ANTHROPIC = "anthropic"
    GOOGLE_GEMINI = "google-gemini"
    OPENAI_CHAT = "openai-chat-completions"
    OPENAI_RESPONSES = "openai-responses"


def get_type_repr(typ: Type | GenericAlias) -> list[str]:
    origin = get_origin(typ)
    args = get_args(typ)

    if origin is Literal:
        return list(dict.fromkeys(chain(*[get_type_repr(type(arg)) for arg in args])))
    if inspect.isclass(typ) and issubclass(typ, Enum):
        return list(dict.fromkeys(chain(*[get_type_repr(type(v.value)) for v in typ])))
    if isinstance(typ, type) and typ.__class__.__name__ == "_TypedDictMeta":
        return ["object"]
    if origin in (list, List) or typ is list:
        return ["array"]
    if origin in (dict, Dict) or typ is dict:
        return ["object"]
    if origin in (tuple, Tuple) or typ is tuple:
        return ["array"]
    if origin is Union or origin is T.UnionType:
        return list(dict.fromkeys(chain(*[get_type_repr(arg) for arg in args])))

    type_mappings = {
        "str": "string",
        "int": "integer",
        "bool": "boolean",
        "float": "number",
        "NoneType": "null",
    }
    if typ.__name__ in type_mappings:
        return [type_mappings[typ.__name__]]


def get_type_schema(typ: Type | GenericAlias):
    origin = get_origin(typ)
    args = get_args(typ)

    schema = {
        "type": get_type_repr(typ),
        # TODO: Retrieve description from Annotation if available
        "description": "",
    }

    if origin is Literal:
        schema["enum"] = list(args)
    elif inspect.isclass(typ) and issubclass(typ, Enum):
        schema["enum"] = [v.value for v in typ]
    elif isinstance(typ, type) and typ.__class__.__name__ == "_TypedDictMeta":
        hints = get_type_hints(typ)
        schema["properties"] = {k: get_type_schema(v) for k, v in hints.items()}
        schema["additionalProperties"] = False
        schema["required"] = list(hints.keys())
    elif origin in (list, List) or typ is dict:
        if args:
            schema["items"] = get_type_schema(args[0])
        else:
            raise TypeError("Insufficient argument type information")
    elif origin in (dict, Dict) or typ is dict:
        raise TypeError("Insufficient argument type information")
    elif origin in (tuple, Tuple) or typ is tuple:
        if args:
            schema["items"] = get_type_schema(args[0])
        else:
            raise TypeError("Insufficient argument type information")
    elif origin is Union or origin is T.UnionType:
        for arg in args:
            subschema = get_type_schema(arg)
            del subschema["type"]
            schema = {
                **schema,
                **subschema,
            }

    # Un-nest single member type lists since Gemini does not accept list of types
    # Optional for OpenAI or Anthropic
    if schema["type"] and len(schema["type"]) == 1:
        schema["type"] = schema["type"][0]

    return schema


def get_param_schema(param: inspect.Parameter, provider: ProviderFormat):
    param_schema = get_type_schema(param.annotation)

    if param_schema["type"] is None:
        raise TypeError(f"Unsupported type: {param.annotation.__name__}")

    if (
        param.default is not inspect.Parameter.empty
        and "null" not in param_schema["type"]
    ):
        if type(param_schema["type"]) is list:
            param_schema["type"].append("null")
        else:
            param_schema["type"] = [param_schema["type"], "null"]

    if provider == ProviderFormat.GOOGLE_GEMINI:
        # Filter out "null" type
        if type(param_schema["type"]) is list:
            param_schema["type"] = [t for t in param_schema["type"] if t != "null"]
            if len(param_schema["type"]) == 1:
                param_schema["type"] = param_schema["type"][0]
        # Check if there are still multiple types are provided for a single argument
        if type(param_schema["type"]) is list:
            logger.warning(
                f"Gemini does not support a function argument with multiple types e.g. Union[str, int]; defaulting to first found non-null type: {param_schema['type'][0]}"
            )
            param_schema["type"] = param_schema["type"][0]
        # Add nullable property for Gemini
        param_schema["nullable"] = param.default is not inspect.Parameter.empty
        if param_schema["type"] == "object":
            logger.warning(
                f'Type of argument {param.name} is {param.annotation}, which is being formatted as an "object" type. However, Gemini does not seem to officially support an "object" parameter type yet and success rate might be spotty. Proceed with caution, or refactor {param.name} into one of the basic supported types: [string, integer, boolean, array].'
            )
    return param_schema


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
            parameters[param_name] = get_param_schema(param, provider)
            required_params.append(param_name)

        # Create formatted tool structure based on provider
        description = inspect.getdoc(tool) or "No description available."
        input_schema = {
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
                    "parameters": {**input_schema, "additionalProperties": False},
                    "strict": True,
                },
            }
        elif provider == ProviderFormat.OPENAI_RESPONSES:
            formatted_tool = {
                "type": "function",
                # OpenAI only supports ^[a-zA-Z0-9_-]{1,64}$
                "name": tool.__name__.replace(".", "-"),
                "description": description,
                "parameters": {**input_schema, "additionalProperties": False},
            }
        elif provider == ProviderFormat.ANTHROPIC:
            formatted_tool = {
                # Claude only supports ^[a-zA-Z0-9_-]{1,64}$
                "name": tool.__name__.replace(".", "-"),
                "description": description,
                "input_schema": input_schema,
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
