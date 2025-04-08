import asyncio
import inspect
import logging
import re
from inspect import Parameter
from types import NoneType, UnionType
from typing import (
    Any,
    Callable,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from makefun import create_function

from stores.format import ProviderFormat, format_tools
from stores.parse import llm_parse_json
from stores.utils import check_duplicates

logging.basicConfig()
logger = logging.getLogger("stores.indexes.base_index")
logger.setLevel(logging.INFO)


def _cast_arg(value: Any, typ: type | tuple[type]):
    try:
        if isinstance(typ, tuple) and len(typ) == 1:
            typ = typ[0]
        typ_origin = get_origin(typ)
        if typ in [float, int, str]:
            return typ(value)
        if typ is bool:
            if isinstance(value, str) and value.lower() == "false":
                return False
            else:
                return typ(value)
        if typ_origin in (list, List) and isinstance(value, (list, tuple)):
            return [_cast_arg(v, get_args(typ)) for v in value]
        if typ_origin in (tuple, Tuple) and isinstance(value, (list, tuple)):
            return tuple(_cast_arg(v, get_args(typ)) for v in value)
        if isinstance(typ, type) and typ.__class__.__name__ == "_TypedDictMeta":
            hints = get_type_hints(typ)
            for k, v in value.items():
                value[k] = _cast_arg(v, hints[k])
            return value
        if typ_origin in [Union, UnionType]:
            if NoneType in get_args(typ) and value is None:
                return value
            valid_types = [a for a in get_args(typ) if a is not NoneType]
            if len(valid_types) == 1:
                return _cast_arg(value, valid_types[0])
    except Exception:
        pass
    # If not in one of the cases above, we return value unchanged
    return value


def _cast_bound_args(bound_args: inspect.BoundArguments):
    """
    In some packages, passed argument types are incorrect
    e.g. LangChain returns float even when argtype is int
    This only casts basic argtypes
    """
    for arg, argparam in bound_args.signature.parameters.items():
        argtype = argparam.annotation
        value = bound_args.arguments[arg]
        new_value = _cast_arg(value, argtype)
        if new_value != value:
            # Warn that we are modifying value since this might not be expected
            logger.warning(
                f'Argument "{arg}" is type {argtype} but passed value is {value} of type {type(value)} - modifying value to {value} instead.'
            )
        bound_args.arguments[arg] = new_value

    return bound_args


# TODO: Support more nested types
def _handle_non_string_literal(annotation: type):
    origin = get_origin(annotation)
    if origin is Literal:
        if any([not isinstance(a, str) for a in get_args(annotation)]):
            # TODO: Handle duplicates
            literal_map = {str(a): a for a in get_args(annotation)}
            new_annotation = Literal.__getitem__(tuple(literal_map.keys()))
            return new_annotation, literal_map
        else:
            return annotation, {}
    if origin in (list, List):
        args = get_args(annotation)
        new_annotation, literal_map = _handle_non_string_literal(args[0])
        return list[new_annotation], {"item": literal_map}
    if origin is Union or origin is UnionType:
        union_literal_maps = {}
        argtype_args = [a for a in get_args(annotation) if a != NoneType]
        new_union, literal_map = _handle_non_string_literal(argtype_args[0])
        union_literal_maps[new_union.__name__] = literal_map
        for child_argtype in argtype_args[1:]:
            new_annotation, literal_map = _handle_non_string_literal(child_argtype)
            new_union = new_union | new_annotation
            union_literal_maps[new_annotation.__name__] = literal_map
        return new_union, union_literal_maps
    return annotation, {}


# TODO: Support more nested types
def _undo_non_string_literal(annotation: type, value: Any, literal_map: dict):
    origin = get_origin(annotation)
    if origin is Literal:
        return literal_map.get(value, value)
    if origin in (list, List) and isinstance(value, (list, tuple)):
        args = get_args(annotation)
        return [
            _undo_non_string_literal(args[0], v, literal_map["item"]) for v in value
        ]
    if origin is Union or origin is UnionType:
        for arg in get_args(annotation):
            try:
                return _undo_non_string_literal(arg, value, literal_map[arg.__name__])
            except Exception:
                pass
    return value


def wrap_tool(tool: Callable):
    """
    Wrap tool to make it compatible with LLM libraries
    - Gemini does not accept non-None default values
        If there are any default args, we set default value to None
        and inject the correct default value at runtime.
    - Gemini does not accept non-string Literals
        We convert non-string Literals to strings and reset this at runtime
    """
    if hasattr(tool, "_wrapped") and tool._wrapped:
        return tool

    # Retrieve default arguments
    original_signature = inspect.signature(tool)
    new_args = []
    literal_maps = {}
    for arg in original_signature.parameters.values():
        new_arg = arg

        # Handle non-string Literals
        argtype = new_arg.annotation
        new_annotation, literal_map = _handle_non_string_literal(argtype)
        literal_maps[arg.name] = literal_map
        new_arg = new_arg.replace(
            kind=Parameter.POSITIONAL_OR_KEYWORD,
            annotation=new_annotation,
        )

        # Handle defaults
        argtype = new_arg.annotation
        if new_arg.default is Parameter.empty:
            # If it's annotated with Optional or Union[None, X]
            # remove the Optional tag since no default value is supplied
            origin = get_origin(argtype)
            if (origin in [Union, UnionType]) and NoneType in get_args(argtype):
                argtype_args = [a for a in get_args(argtype) if a != NoneType]
                new_annotation = argtype_args[0]
                for child_argtype in argtype_args[1:]:
                    new_annotation = new_annotation | child_argtype
                new_arg = new_arg.replace(
                    kind=Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=new_annotation,
                )
        else:
            # Process args with default values: make sure type includes None
            new_annotation = argtype
            if new_annotation is Parameter.empty:
                new_annotation = Optional[type(new_arg.default)]
            origin = get_origin(new_annotation)
            if origin not in [Union, UnionType] or NoneType not in get_args(
                new_annotation
            ):
                new_annotation = Optional[new_annotation]
            new_arg = new_arg.replace(
                default=None,
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                annotation=new_annotation,
            )
        new_args.append(new_arg)
    new_sig = original_signature.replace(parameters=new_args)

    if inspect.iscoroutinefunction(tool):

        async def wrapper(*args, **kwargs):
            # Inject default values within wrapper
            bound_args = original_signature.bind(*args, **kwargs)
            bound_args.apply_defaults()
            _cast_bound_args(bound_args)
            # Inject correct Literals
            for k, v in bound_args.arguments.items():
                if k in literal_maps:
                    param = original_signature.parameters[k]
                    bound_args.arguments[k] = _undo_non_string_literal(
                        param.annotation, v, literal_maps[k]
                    )
            return await tool(*bound_args.args, **bound_args.kwargs)
    else:

        def wrapper(*args, **kwargs):
            # Inject default values within wrapper
            bound_args = original_signature.bind(*args, **kwargs)
            bound_args.apply_defaults()
            # Inject correct Literals
            for k, v in bound_args.arguments.items():
                if (
                    v is None
                    and original_signature.parameters[k].default is not Parameter.empty
                ):
                    bound_args.arguments[k] = original_signature.parameters[k].default

            _cast_bound_args(bound_args)
            for k, v in bound_args.arguments.items():
                if k in literal_maps:
                    param = original_signature.parameters[k]
                    bound_args.arguments[k] = _undo_non_string_literal(
                        param.annotation, v, literal_maps[k]
                    )
            return tool(*bound_args.args, **bound_args.kwargs)

    wrapped = create_function(
        new_sig,
        wrapper,
        qualname=tool.__name__,
        doc=inspect.getdoc(tool),
    )

    wrapped.__name__ = tool.__name__
    wrapped._wrapped = True

    return wrapped


class BaseIndex:
    def __init__(self, tools: list[Callable]):
        check_duplicates([t.__name__ for t in tools])
        self.tools = [wrap_tool(t) for t in tools]

    @property
    def tools_dict(self):
        return {tool.__name__: tool for tool in self.tools}

    def execute(self, toolname: str, kwargs: dict | None = None):
        kwargs = kwargs or {}

        # Use regex since we need to match cases where we perform
        # substitutions such as replace(".", "-")
        pattern = re.compile(":?" + re.sub("-|\\.", "(-|\\.)", toolname) + "$")

        matching_tools = []
        for key in self.tools_dict.keys():
            if pattern.match(key):
                matching_tools.append(key)
        if len(matching_tools) == 0:
            raise ValueError(f"No tool matching '{toolname}'")
        elif len(matching_tools) > 1:
            raise ValueError(f"'{toolname}' matches multiple tools - {matching_tools}")
        else:
            toolname = matching_tools[0]

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
