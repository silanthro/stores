import asyncio
import functools
import importlib.util
import inspect
import logging
import multiprocessing
import os
import subprocess
import sys
import sysconfig
from enum import Enum
from inspect import Parameter
from multiprocessing.connection import Connection
from pathlib import Path
from types import NoneType
from typing import (
    Awaitable,
    Callable,
    Optional,
    TypedDict,
    Union,
    get_args,
    get_origin,
)

import yaml
from makefun import create_function

logging.basicConfig()
logger = logging.getLogger("stores.index_utils")
logger.setLevel(logging.INFO)

# TODO: CACHE_DIR might resolve differently
CACHE_DIR = Path(".tools")
VENV_NAME = ".venv"
TOOLS_CONFIG_FILENAME = "TOOLS.yml"


class ToolMetadata(TypedDict):
    name: str
    signature: str
    docs: str


def get_param_signature(param: inspect.Parameter):
    param_type = param.annotation
    param_sig = {
        "name": param.name,
        "kind": param.kind,
        "default": param.default,
    }
    if inspect.isclass(param_type) and issubclass(param_type, Enum):
        # Enum
        enum_values = list(map(lambda c: c.value, param_type))
        return {
            **param_sig,
            "type": type(enum_values[0]),
            "enum": {c.name: c.value for c in param_type},
        }
    if (
        inspect.isclass(param_type)
        and issubclass(param_type, dict)
        and hasattr(param_type, "__annotations__")
    ):
        # TypedDict
        return {
            **param_sig,
            "type": "object",
            "properties": {
                # TODO: Recursively examine proptype
                propname: proptype
                for propname, proptype in param_type.__annotations__.items()
            },
        }
    return {
        **param_sig,
        "type": param_type,
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
    with open(index_manifest) as file:
        manifest = yaml.safe_load(file)

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
    return [
        {
            "name": t.__name__,
            "params": [
                get_param_signature(arg)
                for arg in inspect.signature(t).parameters.values()
            ],
            "doc": inspect.getdoc(t),
            "async": inspect.iscoroutinefunction(t),
        }
        for t in tools
    ]


def get_index_tools(index_folder: str | Path) -> list[Callable]:
    index_folder = Path(index_folder)

    index_manifest = index_folder / TOOLS_CONFIG_FILENAME
    with open(index_manifest) as file:
        manifest = yaml.safe_load(file)

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


def install_venv_deps(index_folder: str | Path, lib_paths: list[str] | None = None):
    lib_paths = lib_paths or [
        sysconfig.get_path("platlib"),
        sysconfig.get_path("purelib"),
    ]
    # Either `pip install .`
    # Or `pip install -r requirements.txt`
    index_folder = Path(index_folder)
    setup_files = [
        "setup.py",
        "pyproject.toml",
    ]
    if any((index_folder / f).exists() for f in setup_files):
        # Check if module has already been installed
        for pkg in importlib.metadata.distributions():
            if pkg.locate_file("").as_posix() in lib_paths and pkg.name != "pip":
                # `pip install .` has already been run
                # since there exists packages installed in this venv
                return
        subprocess.call(
            [f"{VENV_NAME}/bin/pip", "install", "."],
            cwd=index_folder,
        )
    elif (index_folder / "requirements.txt").exists():
        subprocess.call(
            [f"{VENV_NAME}/bin/pip", "install", "-r", "requirements.txt"],
            cwd=index_folder,
        )


def run_mp_process_helper(
    fn: Callable,
    kwargs: dict | None = None,
    env_vars: dict | None = None,
    conn: Connection | None = None,
):
    error = None
    result = None
    try:
        # Add venv packages to sys.path
        # https://www.rossgray.co.uk/posts/python-multiprocessing-using-a-different-python-executable/
        lib_paths = [
            sysconfig.get_path("platlib"),
            sysconfig.get_path("purelib"),
        ]
        for path in lib_paths:
            if path not in sys.path:
                sys.path.append(path)

        os.environ.clear()
        os.environ.update(env_vars or {})

        kwargs = kwargs or {}
        if inspect.iscoroutinefunction(fn):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(fn(**kwargs))
        else:
            result = fn(**kwargs)
    except Exception as e:
        # Handle exception in parent
        error = e
        if conn:
            conn.send(error)
            conn.close()
    if conn and not error:
        conn.send(result)
        conn.close()
    return result


def run_mp_process(
    fn: Callable,
    kwargs: dict | None = None,
    env_vars: dict | None = None,
    venv_folder: str | Path | None = None,
):
    start_method = None
    if venv_folder:
        venv_folder = Path(venv_folder)
        # Set appropriate executable
        start_method = multiprocessing.get_start_method()
        multiprocessing.set_start_method("spawn", force=True)
        multiprocessing.set_executable(venv_folder / "bin/python")

    parent_conn, child_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(
        target=run_mp_process_helper,
        kwargs={
            "fn": fn,
            "kwargs": kwargs,
            "env_vars": env_vars,
            "conn": child_conn,
        },
    )
    p.start()
    p.join()
    output = parent_conn.recv()
    if venv_folder:
        # Reset executable
        if start_method:
            multiprocessing.set_start_method(start_method, force=True)
        multiprocessing.set_executable(sys.executable)
    if isinstance(output, Exception):
        raise output
    return output


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
        result = loop.run_until_complete(fn(**kwargs))
    else:
        result = fn(**kwargs)
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
        # Run tool with run_mp_process
        return run_mp_process(
            fn=run_remote_tool,
            kwargs={
                "tool_id": tool_metadata["name"],
                "index_folder": index_folder,
                "args": args,
                "kwargs": kwargs,
            },
            env_vars=env_vars,
            venv_folder=venv_folder,
        )

    async def async_func_handler(*args, **kwargs):
        # Run tool with run_mp_process
        return run_mp_process(
            fn=run_remote_tool,
            kwargs={
                "tool_id": tool_metadata["name"],
                "index_folder": index_folder,
                "args": args,
                "kwargs": kwargs,
            },
            env_vars=env_vars,
            venv_folder=venv_folder,
        )

    # Reconstruct signature from list of args
    params = []
    for param in tool_metadata["params"]:
        name = param["name"]
        if param["type"] == "object":
            argtype = TypedDict(name, param["properties"])
        elif param["type"] == "enum":
            argtype = Enum(name, param["enum"])
        else:
            argtype = param["type"]
        params.append(
            inspect.Parameter(
                name=name,
                kind=param["kind"],
                default=param["default"],
                annotation=argtype,
            )
        )
    signature = inspect.Signature(params)
    func = create_function(
        signature,
        async_func_handler if tool_metadata.get("async") else func_handler,
        doc=tool_metadata.get("doc"),
    )
    func = wrap_tool(func)
    func.__name__ = tool_metadata["name"]
    return func


def wrap_tool(tool: Callable | Awaitable):
    """
    Wrap tool to make it compatible with LLM libraries
    e.g. Gemini does not accept non-None default values
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
            # Check if it's annotated with Optional or Union[None, X]
            # TODO: We might want to remove the Optional tag instead since no
            # default value is supplied
            if get_origin(argtype) == Union and NoneType in get_args(argtype):
                default_args[argname] = None
                new_args.append(
                    arg.replace(
                        default=None,
                        kind=Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=argtype,
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
