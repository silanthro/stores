import asyncio
import importlib.util
import inspect
import logging
import multiprocessing
import os
import subprocess
import sys
import sysconfig
from inspect import Parameter
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Awaitable, Callable, TypedDict

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


def get_index_signatures(index_folder: str | Path) -> list[ToolMetadata]:
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
            # TODO: Handle custom types
            "signature": t.__name__.split(".")[-1] + str(inspect.signature(t)),
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

    func = create_function(
        tool_metadata["signature"],
        async_func_handler if tool_metadata.get("async") else func_handler,
        doc=tool_metadata.get("doc"),
    )
    func = wrap_tool(func)
    func.__name__ = tool_metadata["name"]
    return func


# Wrap tool to make it compatible with LLM libraries
def wrap_tool(tool: Callable | Awaitable):
    # Retrieve default arguments
    sig = inspect.signature(tool)
    new_args = []
    default_args = {}
    for argname, arg in sig.parameters.items():
        if arg.default is Parameter.empty:
            new_args.append(arg)
        else:
            # Process args with default values
            # - Store default value
            # - Change type to include None
            default_args[argname] = arg.default
            new_annotation = arg.annotation
            if new_annotation is Parameter.empty:
                new_annotation = type(arg.default)
            new_annotation = None | new_annotation
            new_args.append(
                arg.replace(
                    # Set to None instead of empty because
                    # Gemini accepts a None default value but
                    # raises an error with other default
                    # values. And we still want to be able to
                    # call the tool without supplying this arg
                    # default=Parameter.empty,
                    default=None,
                    annotation=new_annotation,
                )
            )
    new_signature = sig.replace(parameters=new_args)

    def wrapper(*args, **kwargs):
        # Inject default values within wrapper
        for kw, kwarg in kwargs.items():
            if kwarg is None:
                kwargs[kw] = default_args.get(kw)
        return tool(*args, **kwargs)

    async def async_wrapper(*args, **kwargs):
        # Inject default values within wrapper
        for kw, kwarg in kwargs.items():
            if kwarg is None:
                kwargs[kw] = default_args.get(kw)
        return await tool(*args, **kwargs)

    wrapped_tool = create_function(
        tool.__name__.split(".")[-1] + str(new_signature),
        async_wrapper if inspect.iscoroutinefunction(tool) else wrapper,
        doc=inspect.getdoc(tool),
    )
    wrapped_tool.__name__ = tool.__name__
    return wrapped_tool
