import inspect
from typing import Callable

from stores.prompts.tool_template import TOOL_TEMPLATE


def get_tool_description(tool: Callable):
    input_schema = tool.__annotations__.copy()
    if "return" in input_schema:
        del input_schema["return"]
    return TOOL_TEMPLATE.format(
        name=tool.__name__,
        description=inspect.getdoc(tool),
        input_schema=input_schema,
        output_schema=tool.__annotations__.get("return"),
    )


def format_query(request: str, tools: list[Callable]):
    if len(tools) == 0:
        raise ValueError("No tools to format")

    descriptions = [get_tool_description(t) for t in tools]

    return (
        "Given the user request, respond with a JSON object containing two keys: "
        "'text' and 'tool_calls'. "
        "The 'text' key should contain your text response to the user. "
        "If a tool needs to be called, the 'tool_calls' key should be "
        "a list of objects with 'toolname' (string) and 'kwargs' (object)."
        "If no tool is needed, set 'tool_calls' to an empty list.\n"
        "Here are the tools available: "
        f"{descriptions}"
        f"User request: {request}"
    )
