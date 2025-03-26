import asyncio
import functools
import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import logging
import os
import subprocess
import sys
from enum import Enum
from inspect import Parameter
from pathlib import Path
from types import NoneType
from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    TypedDict,
    Union,
    get_args,
    get_origin,
)

import requests
from makefun import create_function

from stores.context import new_env_context

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


logging.basicConfig()
logger = logging.getLogger("stores.index_utils")
logger.setLevel(logging.INFO)

# TODO: CACHE_DIR might resolve differently
CACHE_DIR = Path(".tools")
VENV_NAME = ".venv"
TOOLS_CONFIG_FILENAME = "tools.toml"


class ToolMetadata(TypedDict):
    name: str
    params: list[Any]
    doc: str
    is_async: bool
    return_type: Any


def get_param_type(param_type: type):
    if get_origin(param_type) is list:
        # List
        return {
            "type": "array",
            "items": [get_param_type(a) for a in get_args(param_type)],
        }
    if get_origin(param_type) is Union:
        # Union
        return {
            "type": "union",
            "items": [get_param_type(a) for a in get_args(param_type)],
        }
    if inspect.isclass(param_type) and issubclass(param_type, Enum):
        # Enum
        return {
            "type": "enum",
            "type_name": param_type.__name__,
            "enum": {c.name: c.value for c in param_type},
        }
    if (
        inspect.isclass(param_type)
        and issubclass(param_type, dict)
        and hasattr(param_type, "__annotations__")
    ):
        # TypedDict
        return {
            "type": "object",
            "type_name": param_type.__name__,
            "properties": {
                propname: get_param_type(proptype)
                for propname, proptype in param_type.__annotations__.items()
            },
        }
    return {
        "type": param_type,
    }


def parse_param_type(param_dict: dict) -> type:
    if param_dict["type"] == "array":
        child_types = [parse_param_type(a) for a in param_dict["items"]]
        child_union = child_types[0]
        for child_type in child_types[1:]:
            child_union = child_union | child_type
        return list[child_union]
    if param_dict["type"] == "union":
        child_types = [parse_param_type(a) for a in param_dict["items"]]
        union_type = child_types[0]
        for child_type in child_types[1:]:
            union_type = union_type | child_type
        return union_type
    if param_dict["type"] == "enum":
        return Enum(param_dict["type_name"], param_dict["enum"])
    if param_dict["type"] == "object":
        properties = {}
        for k, v in param_dict["properties"].items():
            properties[k] = parse_param_type(v)
        return TypedDict(param_dict["type_name"], properties)
    return param_dict["type"]


def get_param_signature(param: Parameter):
    param_type = get_param_type(param.annotation)
    return {
        "name": param.name,
        "kind": param.kind,
        "default": param.default,
        **param_type,
    }


def get_index_signatures(index_folder: str | Path) -> list[ToolMetadata]:
    """
    This is used to retrieve tool signatures from tool indexes that are
    isolated in their own venv.
    In practice, this function will be run from within the venv.
    Since we might not be able to export the tools outside of the venv,
    retrieving signatures allows us to reconstruct tool wrappers that act
    as proxies that will call the actual tools.
    We also need to export metadata for custom arg types defined within the venv.
    Only the following custom arg type parents are supported for now.
    - TypedDict
    - Enum
    """
    index_folder = Path(index_folder)

    index_manifest = index_folder / TOOLS_CONFIG_FILENAME
    with open(index_manifest, "rb") as file:
        manifest = tomllib.load(file)["index"]

    tools = []
    for tool_id in manifest.get("tools", []):
        module_name = ".".join(tool_id.split(".")[:-1])
        tool_name = tool_id.split(".")[-1]

        module_file = index_folder / module_name.replace(".", "/")
        if (module_file / "__init__.py").exists():
            module_file = module_file / "__init__.py"
        else:
            module_file = Path(str(module_file) + ".py")

        spec = importlib.util.spec_from_file_location(module_name, module_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        tool = getattr(module, tool_name)
        tool.__name__ = tool_id
        tools.append(tool)

    index_signatures = []
    for tool in tools:
        sig = inspect.signature(tool)
        params = [get_param_signature(arg) for arg in sig.parameters.values()]
        return_type = inspect.signature(tool).return_annotation
        if return_type != Parameter.empty:
            return_type = get_param_type(return_type)
        index_signatures.append(
            {
                "name": tool.__name__,
                "params": params,
                "doc": inspect.getdoc(tool),
                "is_async": inspect.iscoroutinefunction(tool),
                "return_type": return_type,
            }
        )
    return index_signatures


def get_index_tools(index_folder: str | Path) -> list[Callable]:
    index_folder = Path(index_folder)

    index_manifest = index_folder / TOOLS_CONFIG_FILENAME
    with open(index_manifest, "rb") as file:
        manifest = tomllib.load(file)["index"]

    tools = []
    for tool_id in manifest.get("tools", []):
        module_name = ".".join(tool_id.split(".")[:-1])
        tool_name = tool_id.split(".")[-1]

        module_file = index_folder / module_name.replace(".", "/")
        if (module_file / "__init__.py").exists():
            module_file = module_file / "__init__.py"
        else:
            module_file = Path(str(module_file) + ".py")

        spec = importlib.util.spec_from_file_location(module_name, module_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        tool = getattr(module, tool_name)
        tool.__name__ = tool_id
        tools.append(tool)
    return tools


def install_venv_deps(index_folder: os.PathLike):
    index_folder = Path(index_folder)

    supported_deps_configs = {
        "pyproject.toml": f"{VENV_NAME}/bin/pip install .",
        "setup.py": f"{VENV_NAME}/bin/pip install .",
        "requirements.txt": f"{VENV_NAME}/bin/pip install -r requirements.txt",
    }
    hash_file = ".deps_hash"

    def has_installed(config_path: os.PathLike):
        """
        Use a hash file to check if dependencies have been installed
        """
        with open(config_path, "rb") as f:
            config_hash = hashlib.sha256(f.read()).hexdigest()
        hash_path = config_path.parent / hash_file
        if hash_path.exists():
            with open(hash_path) as f:
                return config_hash == f.read().strip()
        else:
            return False

    def write_hash(config_path: os.PathLike):
        with open(config_path, "rb") as f:
            config_hash = hashlib.sha256(f.read()).hexdigest()
        hash_path = config_path.parent / hash_file
        with open(hash_path, "w") as f:
            f.write(config_hash)

    for config_file, install_cmd in supported_deps_configs.items():
        config_path = index_folder / config_file
        if config_path.exists():
            # Check if already installed
            if has_installed(config_path):
                return "Already installed"
            subprocess.check_call(
                install_cmd.split(),
                cwd=index_folder,
            )
            write_hash(config_path)
            return logger.info(f"Installed with {index_folder}/{install_cmd}")


def run_remote_tool(
    tool_id: str,
    index_folder: str | Path = None,
    args: list | None = None,
    kwargs: dict | None = None,
):
    args = args or []
    kwargs = kwargs or {}

    module_name = ".".join(tool_id.split(".")[:-1])
    tool_name = tool_id.split(".")[-1]

    index_folder = Path(index_folder)
    module_file = index_folder / module_name.replace(".", "/")
    if (module_file / "__init__.py").exists():
        module_file = module_file / "__init__.py"
    else:
        module_file = Path(str(module_file) + ".py")

    spec = importlib.util.spec_from_file_location(module_name, module_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fn = getattr(module, tool_name)

    if inspect.iscoroutinefunction(fn):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(fn(*args, **kwargs))
    else:
        result = fn(*args, **kwargs)
    return result


def wrap_remote_tool(
    tool_metadata: dict,
    venv_folder: str | Path,
    index_folder: str | Path,
    env_vars: dict | None = None,
):
    """
    Wrap remote tool since we cannot actually define these tools
    outside of their venv
    """
    # Explicitly import some typing Types to prevent create_function
    # from running into NameError

    # TODO: Handle misc issues
    # - . in function name
    def func_handler(*args, **kwargs):
        # Run tool with new_env_context
        with new_env_context(
            Path(index_folder) / VENV_NAME,
            env_vars=env_vars,
        ):
            result = run_remote_tool(
                tool_metadata["name"],
                index_folder,
                args,
                kwargs,
            )
        return result

    async def async_func_handler(*args, **kwargs):
        # Run tool with new_env_context
        with new_env_context(
            Path(index_folder) / VENV_NAME,
            env_vars=env_vars,
        ):
            result = run_remote_tool(
                tool_metadata["name"],
                index_folder,
                args,
                kwargs,
            )
        return result

    # Reconstruct signature from list of args
    params = []
    for param in tool_metadata["params"]:
        name = param["name"]
        params.append(
            inspect.Parameter(
                name=name,
                kind=param["kind"],
                default=param["default"],
                annotation=parse_param_type(param),
            )
        )
    # Reconstruct return type
    return_type_metadata = tool_metadata.get("return_type", Parameter.empty)
    if return_type_metadata == Parameter.empty:
        return_type = Parameter.empty
    else:
        return_type = parse_param_type(return_type_metadata)
    signature = inspect.Signature(params, return_annotation=return_type)
    func = create_function(
        signature,
        async_func_handler if tool_metadata.get("is_async") else func_handler,
        qualname=tool_metadata["name"],
        doc=tool_metadata.get("doc"),
    )
    func.__name__ = tool_metadata["name"]
    func = wrap_tool(func)
    return func


def wrap_tool(tool: Callable | Awaitable):
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


def lookup_index(index_id: str, index_version: str | None = None):
    response = requests.post(
        "https://mnryl5tkkol3yitc3w2rupqbae0ovnej.lambda-url.us-east-1.on.aws/",
        headers={
            "content-type": "application/json",
        },
        data=json.dumps(
            {
                "index_id": index_id,
                "index_version": index_version,
            }
        ),
    )
    if response.ok:
        return response.json()
