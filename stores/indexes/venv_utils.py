import asyncio
import hashlib
import inspect
import json
import logging
import os
import pickle
import queue
import socket
import subprocess
import sys
import threading
from enum import Enum
from pathlib import Path
from typing import Dict, Literal, Tuple, TypedDict, Union

from makefun import create_function

from stores.constants import TOOLS_CONFIG_FILENAME, VENV_NAME

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

logging.basicConfig()
logger = logging.getLogger("stores.indexes.venv_utils")
logger.setLevel(logging.INFO)

HASH_FILE = ".deps_hash"


SUPPORTED_CONFIGS = [
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
]


def get_pip_command(venv_path: os.PathLike, config_file: str) -> list[str]:
    venv_path = Path(venv_path).resolve()
    if os.name == "nt":
        pip_path = venv_path / "Scripts" / "pip.exe"
    else:
        pip_path = venv_path / "bin" / "pip"

    if config_file in {"pyproject.toml", "setup.py"}:
        return [str(pip_path), "install", "."]
    elif config_file == "requirements.txt":
        return [str(pip_path), "install", "-r", "requirements.txt"]
    else:
        raise ValueError(f"Unsupported config file: {config_file}")


def get_python_command(venv_path: os.PathLike) -> list[str]:
    venv_path = Path(venv_path).resolve()
    if os.name == "nt":
        executable = venv_path / "Scripts" / "python.exe"
    else:
        executable = venv_path / "bin" / "python"
    return str(executable)


def has_installed(config_path: os.PathLike):
    """
    Read hash file to check if dependencies have been installed
    """
    with open(config_path, "rb") as f:
        config_hash = hashlib.sha256(f.read()).hexdigest()
    hash_path = config_path.parent / HASH_FILE
    if hash_path.exists():
        with open(hash_path) as f:
            return config_hash == f.read().strip()
    else:
        return False


def write_hash(config_path: os.PathLike):
    """
    Write hash file once dependencies have been installed
    """
    with open(config_path, "rb") as f:
        config_hash = hashlib.sha256(f.read()).hexdigest()
    hash_path = config_path.parent / HASH_FILE
    with open(hash_path, "w") as f:
        f.write(config_hash)


def install_venv_deps(index_folder: os.PathLike):
    index_folder = Path(index_folder)

    for config_file in SUPPORTED_CONFIGS:
        config_path = index_folder / config_file
        if config_path.exists():
            # Check if already installed
            if has_installed(config_path):
                return "Already installed"
            pip_command = get_pip_command(index_folder / VENV_NAME, config_file)
            subprocess.check_call(
                pip_command,
                cwd=index_folder,
            )
            write_hash(config_path)
            message = f'Installed with "{" ".join(pip_command)}"'
            logger.info(message)
            return message


def init_venv_tools(
    index_folder: os.PathLike,
    env_var: dict | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
):
    index_folder = Path(index_folder)
    env_var = env_var or {}
    include = include or []
    exclude = exclude or []

    index_manifest = index_folder / TOOLS_CONFIG_FILENAME
    with open(index_manifest, "rb") as file:
        manifest = tomllib.load(file)["index"]

    tools = []
    for tool_id in include or manifest.get("tools", []):
        if tool_id in exclude:
            continue
        tool_sig = get_tool_signature(
            tool_id=tool_id,
            index_folder=index_folder,
            venv=VENV_NAME,
            env_var=env_var,
        )
        tool = parse_tool_signature(
            signature_dict=tool_sig,
            index_folder=index_folder,
            venv=VENV_NAME,
            env_var=env_var,
        )
        tools.append(tool)
    return tools


# TODO: Sanitize tool_id, args, and kwargs
def get_tool_signature(
    tool_id: str,
    index_folder: os.PathLike,
    venv: str = VENV_NAME,
    env_var: dict | None = None,
):
    module_name = ".".join(tool_id.split(".")[:-1])
    tool_name = tool_id.split(".")[-1]
    env_var = env_var or {}

    # We use sockets to pass pass function metadata
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("localhost", 0))
    listener.listen(1)
    _, port = listener.getsockname()

    runner = f"""
import pickle, sys, traceback, inspect, enum, socket
from typing import Any, Dict, List, Literal, Tuple, Union, get_args, get_origin, get_type_hints
import types as T


def extract_type_info(typ, custom_types: list[str] | None = None):
    custom_types = custom_types or []
    if hasattr(typ, "__name__") and typ.__name__ in custom_types:
        return typ.__name__
    origin = get_origin(typ)
    args = list(get_args(typ))
    if origin is Literal:
        return {{"type": "Literal", "values": args}}
    elif inspect.isclass(typ) and issubclass(typ, enum.Enum):
        custom_types.append(typ.__name__)
        return {{
            "type": "Enum",
            "type_name": typ.__name__,
            "values": {{v.name: v.value for v in typ}},
        }}
    elif isinstance(typ, type) and typ.__class__.__name__ == "_TypedDictMeta":
        custom_types.append(typ.__name__)
        hints = get_type_hints(typ)
        return {{
            "type": "TypedDict",
            "type_name": typ.__name__,
            "fields": {{k: extract_type_info(v, custom_types) for k, v in hints.items()}}
        }}
    elif origin in (list, List) or typ is list:
        return {{
            "type": "List",
            "item_type": extract_type_info(args[0], custom_types) if args else {{"type": Any}}
        }}
    elif origin in (dict, Dict) or typ is dict:
        return {{
            "type": "Dict",
            "key_type": extract_type_info(args[0], custom_types) if args else {{"type": Any}},
            "value_type": extract_type_info(args[1], custom_types) if len(args) > 1 else {{"type": Any}}
        }}
    elif origin in (tuple, Tuple) or typ is tuple:
        return {{
            "type": "Tuple",
            "item_types": [extract_type_info(arg, custom_types) for arg in args] if args else [{{"type": Any}}]
        }}
    elif origin is Union or origin is T.UnionType:
        return {{
            "type": "Union",
            "options": [extract_type_info(arg, custom_types) for arg in args]
        }}
    else:
        return {{"type": typ}}

try:
    from {module_name} import {tool_name}
    func = {tool_name}
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    params = {{}}
    for name, param in sig.parameters.items():
        hint = hints.get(name, param.annotation)
        param_info = extract_type_info(hint)
        param_info["kind"] = param.kind
        param_info["default"] = param.default
        params[name] = param_info
    return_type = hints.get('return', sig.return_annotation)
    return_info = extract_type_info(return_type)

    payload = {{
        "ok": True,
        "result": {{
            "tool_id": "{tool_id}",
            "params": params,
            "return": return_info,
            "iscoroutinefunction": inspect.iscoroutinefunction(func),
            "isgeneratorfunction": inspect.isgeneratorfunction(func),
            "isasyncgenfunction": inspect.isasyncgenfunction(func),
            "doc": inspect.getdoc(func),
        }},
    }}
except Exception as e:
    payload = {{"ok": False, "error": traceback.format_exc()}}

with socket.create_connection(("localhost", {port})) as s:
    s.sendall(pickle.dumps(payload))
"""
    proc = subprocess.Popen(
        [get_python_command(Path(index_folder) / venv), "-c", runner],
        cwd=index_folder,
        env=env_var or None,
    )

    conn, _ = listener.accept()
    with conn:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk

    listener.close()
    proc.wait()

    try:
        response = pickle.loads(data)
    except ModuleNotFoundError as e:
        raise RuntimeError(
            f"Error loading tool {tool_id}:\nThe tool most likely has a parameter of a custom type that cannot be exported"
        ) from e
    if response.get("ok"):
        return response["result"]
    else:
        raise RuntimeError(f"Error loading tool {tool_id}:\n{response['error']}")


def parse_param_type(param_info: dict, custom_types: list[str] | None = None):
    custom_types = custom_types or []
    # Support ForwardRef
    param_type = param_info["type"]
    if param_type in custom_types:
        return param_type
    if not isinstance(param_type, str):
        return param_type
    if param_type == "Literal":
        return Literal.__getitem__(tuple(param_info["values"]))
    elif param_type == "Enum":
        custom_types.append(param_info["type_name"])
        return Enum(param_info["type_name"], param_info["values"])
    elif param_type == "TypedDict":
        custom_types.append(param_info["type_name"])
        properties = {}
        for k, v in param_info["fields"].items():
            properties[k] = parse_param_type(v, custom_types)
        return TypedDict(param_info["type_name"], properties)
    elif param_type == "List":
        return list[parse_param_type(param_info["item_type"], custom_types)]
    elif param_type == "Dict":
        return Dict[
            parse_param_type(param_info["key_type"], custom_types),
            parse_param_type(param_info["value_type"], custom_types),
        ]
    elif param_type == "Tuple":
        return Tuple.__getitem__(
            tuple([parse_param_type(i, custom_types) for i in param_info["item_types"]])
        )
    elif param_type == "Union":
        return Union.__getitem__(
            tuple([parse_param_type(i, custom_types) for i in param_info["options"]])
        )
    else:
        raise TypeError(f"Invalid param type {param_type} in param info {param_info}")


def parse_tool_signature(
    signature_dict: dict,
    index_folder: os.PathLike,
    venv: str = VENV_NAME,
    env_var: dict | None = None,
):
    """
    Create a wrapper function that replicates the remote tool
    given its signature
    """
    env_var = env_var or {}

    if signature_dict.get("isasyncgenfunction"):

        async def func_handler(*args, **kwargs):
            async for value in run_remote_tool_async(
                tool_id=signature_dict["tool_id"],
                index_folder=index_folder,
                args=args,
                kwargs=kwargs,
                venv=venv,
                env_var=env_var,
                stream=True,
            ):
                yield value

    elif signature_dict.get("isgeneratorfunction"):

        def func_handler(*args, **kwargs):
            q = queue.Queue()
            sentinel = object()

            def run():
                async def runner():
                    try:
                        async for item in run_remote_tool_async(
                            tool_id=signature_dict["tool_id"],
                            index_folder=index_folder,
                            args=args,
                            kwargs=kwargs,
                            venv=venv,
                            env_var=env_var,
                            stream=True,
                        ):
                            q.put(item)
                    except Exception as e:
                        q.put(e)
                    finally:
                        q.put(sentinel)

                asyncio.run(runner())

            t = threading.Thread(target=run)
            t.start()

            while True:
                item = q.get()
                if item is sentinel:
                    break
                elif isinstance(item, Exception):
                    raise item
                else:
                    yield item

            t.join()

    elif signature_dict.get("iscoroutinefunction"):

        async def func_handler(*args, **kwargs):
            result = []
            async for item in run_remote_tool_async(
                tool_id=signature_dict["tool_id"],
                index_folder=index_folder,
                args=args,
                kwargs=kwargs,
                venv=venv,
                env_var=env_var,
                stream=True,
            ):
                result.append(item)
            return result[-1] if result else None
    else:

        async def func_handler_async_fallback(*args, **kwargs):
            result = []
            async for item in run_remote_tool_async(
                tool_id=signature_dict["tool_id"],
                index_folder=index_folder,
                args=args,
                kwargs=kwargs,
                venv=venv,
                env_var=env_var,
                stream=True,
            ):
                result.append(item)
            return result[-1] if result else None

        def func_handler(*args, **kwargs):
            coro = func_handler_async_fallback(*args, **kwargs)
            try:
                # Check if we're in an async context
                asyncio.get_running_loop()
                in_async = True
            except RuntimeError:
                in_async = False

            if not in_async:
                # Safe to run directly
                return asyncio.run(coro)

            q = queue.Queue()

            def runner():
                try:
                    result = asyncio.run(coro)
                    q.put(result)
                except Exception as e:
                    q.put(e)

            t = threading.Thread(target=runner)
            t.start()
            result = q.get()
            t.join()
            if isinstance(result, Exception):
                raise result
            return result

    # Reconstruct signature from list of args
    params = []
    for param_name, param_info in signature_dict["params"].items():
        params.append(
            inspect.Parameter(
                name=param_name,
                kind=param_info["kind"],
                default=param_info["default"],
                annotation=parse_param_type(param_info),
            )
        )
    # Reconstruct return type
    return_type = parse_param_type(signature_dict["return"])
    signature = inspect.Signature(params, return_annotation=return_type)
    func = create_function(
        signature,
        func_handler,
        qualname=signature_dict["tool_id"],
        doc=signature_dict.get("doc"),
    )
    func.__name__ = signature_dict["tool_id"]
    return func


tool_runner = """
import asyncio, inspect, json, socket, sys, traceback
sys.path.insert(0, "{index_folder}")

def send(sock, payload):
    sock.sendall((json.dumps(payload) + "\\n").encode("utf-8"))

sock = socket.create_connection(("localhost", {port}))

try:
    from {module_name} import {tool_name}
    params = json.load(sys.stdin)
    args = params.get("args", [])
    kwargs = params.get("kwargs", {{}})

    func = {tool_name}

    if inspect.isasyncgenfunction(func):
        async def run():
            async for value in func(*args, **kwargs):
                send(sock, {{"ok": True, "stream": value}})
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run())
    elif inspect.isgeneratorfunction(func):
        for value in func(*args, **kwargs):
            send(sock, {{"ok": True, "stream": value}})
    elif inspect.iscoroutinefunction(func):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(func(*args, **kwargs))
        send(sock, {{"ok": True, "result": result}})
    else:
        result = func(*args, **kwargs)
        send(sock, {{"ok": True, "result": result}})
    send(sock, {{"done": True}})
except Exception as e:
    err = traceback.format_exc()
    try:
        send(sock, {{"ok": False, "error": err}})
    except:
        pass
finally:
    try:
        sock.close()
    except:
        pass
"""


# TODO: Sanitize tool_id, args, and kwargs
async def run_remote_tool_async(
    tool_id: str,
    index_folder: os.PathLike,
    args: list | None = None,
    kwargs: dict | None = None,
    venv: str = VENV_NAME,
    env_var: dict | None = None,
    stream: bool = True,
):
    args = args or []
    kwargs = kwargs or {}
    env_var = env_var or {}

    module_name = ".".join(tool_id.split(".")[:-1])
    tool_name = tool_id.split(".")[-1]
    payload = json.dumps({"args": args, "kwargs": kwargs}).encode("utf-8")

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("localhost", 0))
    listener.listen(1)
    listener.setblocking(False)
    _, port = listener.getsockname()

    loop = asyncio.get_running_loop()
    conn_task = loop.create_task(loop.sock_accept(listener))

    runner = tool_runner.format(
        index_folder=index_folder,
        port=port,
        module_name=module_name,
        tool_name=tool_name,
    )

    proc = await asyncio.create_subprocess_exec(
        get_python_command(Path(index_folder) / venv),
        "-c",
        runner,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        env=env_var or None,
    )

    try:
        proc.stdin.write(payload)
        await proc.stdin.drain()
        proc.stdin.close()

        conn, _ = await conn_task
        conn.setblocking(False)

        buffer = ""
        result = None
        while True:
            chunk = await loop.sock_recv(conn, 4096)
            if not chunk:
                break
            buffer += chunk.decode("utf-8")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue
                msg = json.loads(line)

                if msg.get("ok") and "stream" in msg:
                    if stream:
                        yield msg["stream"]
                    else:
                        result = msg["stream"]
                elif msg.get("ok") and "result" in msg:
                    result = msg["result"]
                elif "error" in msg:
                    raise RuntimeError(f"Subprocess error:\n{msg['error']}")
                elif "done" in msg and result is not None:
                    yield result
                    return

    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            listener.close()
        except Exception:
            pass
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
