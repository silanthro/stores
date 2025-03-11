from typing import Callable

from stores.prompts.tool_template import TOOL_TEMPLATE


def get_tool_description(tool: Callable):
    input_schema = tool.__annotations__.copy()
    if "return" in input_schema:
        del input_schema["return"]
    return TOOL_TEMPLATE.format(
        name=tool.__name__,
        description=tool.__doc__,
        input_schema=input_schema,
        output_schema=tool.__annotations__.get("return"),
    )


def format_query(request: str, tools: list[Callable]):
    if len(tools) == 0:
        raise ValueError("No tools to format")

    descriptions = [get_tool_description(t) for t in tools]

    return (
        "Given the user request, return a JSON with keys `toolname` and `kwargs`. "
        "Where `toolname` is a string representing the tool to call and `kwargs` is an "
        "object corresponding to the required tool function inputs.\n"
        "Here are the tools available: "
        f"{descriptions}"
        f"User request: {request}"
    )
