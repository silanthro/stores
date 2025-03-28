import asyncio
import functools
import inspect
from inspect import Parameter
from types import NoneType
from typing import Callable, Optional, Union, get_args, get_origin

from stores.format import ProviderFormat, format_tools
from stores.parse import llm_parse_json
from stores.utils import check_duplicates


def wrap_tool(tool: Callable):
    """
    Wrap tool to make it compatible with LLM libraries
    - Gemini does not accept non-None default values
    If there are any default args, we set default value to None
    and inject the correct default value at runtime.
    """
    # Retrieve default arguments
    sig = inspect.signature(tool)
    new_args = []
    default_args = {}
    for argname, arg in sig.parameters.items():
        argtype = arg.annotation
        if arg.default is Parameter.empty:
            # If it's annotated with Optional or Union[None, X]
            # remove the Optional tag since no default value is supplied
            if get_origin(argtype) == Union and NoneType in get_args(argtype):
                argtype_args = [a for a in get_args(argtype) if a != NoneType]
                if len(argtype_args) == 0:
                    raise TypeError(
                        f"Parameter {argname} of tool {tool.__name__} has an invalid type of {argtype}"
                    )
                new_annotation = argtype_args[0]
                for arg in argtype_args[1:]:
                    new_annotation = new_annotation | arg
                new_args.append(
                    arg.replace(
                        kind=Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=new_annotation,
                    )
                )
            else:
                new_args.append(arg)
        else:
            # Process args with default values
            # - Store default value
            # - Change type to include None
            default_args[argname] = arg.default
            new_annotation = argtype
            if new_annotation is Parameter.empty:
                new_annotation = Optional[type(arg.default)]
            if get_origin(new_annotation) != Union or NoneType not in get_args(
                new_annotation
            ):
                new_annotation = Optional[new_annotation]
            new_args.append(
                arg.replace(
                    default=None,
                    kind=Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=new_annotation,
                )
            )
    new_sig = sig.replace(parameters=new_args)

    if inspect.iscoroutinefunction(tool):

        async def wrapper(*args, **kwargs):
            # Inject default values within wrapper
            for kw, kwarg in kwargs.items():
                if kwarg is None:
                    kwargs[kw] = default_args.get(kw)
            return await tool(*args, **kwargs)
    else:

        def wrapper(*args, **kwargs):
            # Inject default values within wrapper
            for kw, kwarg in kwargs.items():
                if kwarg is None:
                    kwargs[kw] = default_args.get(kw)
            for default_kw, default_kwarg in default_args.items():
                if default_kw not in kwargs:
                    kwargs[default_kw] = default_kwarg
            return tool(*args, **kwargs)

    functools.update_wrapper(wrapper, tool)
    wrapper.__signature__ = new_sig

    return wrapper


class BaseIndex:
    def __init__(self, tools: list[Callable]):
        check_duplicates([t.__name__ for t in tools])
        self.tools = [wrap_tool(t) for t in tools]

    @property
    def tools_dict(self):
        return {tool.__name__: tool for tool in self.tools}

    def execute(self, toolname: str, kwargs: dict | None = None):
        kwargs = kwargs or {}

        if ":" not in toolname:
            matching_tools = []
            for key in self.tools_dict.keys():
                if key == toolname or key.endswith(f":{toolname}"):
                    matching_tools.append(key)
            if len(matching_tools) == 0:
                raise ValueError(f"No tool matching '{toolname}'")
            elif len(matching_tools) > 1:
                raise ValueError(
                    f"'{toolname}' matches multiple tools - {matching_tools}"
                )
            else:
                toolname = matching_tools[0]

        if self.tools_dict.get(toolname) is None:
            raise ValueError(f"No tool matching '{toolname}'")

        tool = self.tools_dict[toolname]
        if inspect.iscoroutinefunction(tool):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(tool(**kwargs))
        else:
            return tool(**kwargs)

    def parse_and_execute(self, msg: str):
        toolcall = llm_parse_json(msg, keys=["toolname", "kwargs"])
        return self.execute(toolcall.get("toolname"), toolcall.get("kwargs"))

    def format_tools(self, provider: ProviderFormat):
        return format_tools(self.tools, provider)
