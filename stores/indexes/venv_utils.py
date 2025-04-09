import hashlib
import inspect
import json
import logging
import os
import pickle
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


SUPPORTED_DEP_CONFIGS = {
    "pyproject.toml": f"{VENV_NAME}/bin/pip install .",
    "setup.py": f"{VENV_NAME}/bin/pip install .",
    "requirements.txt": f"{VENV_NAME}/bin/pip install -r requirements.txt",
}


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

    for config_file, install_cmd in SUPPORTED_DEP_CONFIGS.items():
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
            message = f"Installed with {index_folder}/{install_cmd}"
            logger.info(message)
            return message


def init_venv_tools(index_folder: os.PathLike, env_var: dict | None = None):
    index_folder = Path(index_folder)
    env_var = env_var or {}

    index_manifest = index_folder / TOOLS_CONFIG_FILENAME
    with open(index_manifest, "rb") as file:
        manifest = tomllib.load(file)["index"]

    tools = []
    for tool_id in manifest.get("tools", []):
        tool_sig = get_tool_signature(
            tool_id=tool_id,
            index_folder=index_folder,
            venv=VENV_NAME,
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
def get_tool_signature(tool_id: str, index_folder: os.PathLike, venv: str = VENV_NAME):
    module_name = ".".join(tool_id.split(".")[:-1])
    tool_name = tool_id.split(".")[-1]

    runner = f"""
import pickle, sys, traceback, inspect, enum
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
    sig = inspect.signature({tool_name})
    hints = get_type_hints({tool_name})
    params = {{}}
    for name, param in sig.parameters.items():
        hint = hints.get(name, param.annotation)
        param_info = extract_type_info(hint)
        param_info["kind"] = param.kind
        param_info["default"] = param.default
        params[name] = param_info
    return_type = hints.get('return', sig.return_annotation)
    return_info = extract_type_info(return_type)

    pickle.dump(
        {{
            "ok": True,
            "result": {{
                "tool_id": "{tool_id}",
                "params": params,
                "return": return_info,
                "is_async": inspect.iscoroutinefunction({tool_name}),
                "doc": inspect.getdoc({tool_name}),
            }},
        }},
        sys.stdout.buffer,
    )
except Exception as e:
    err = traceback.format_exc()
    pickle.dump({{"ok": False, "error": err}}, sys.stdout.buffer)
"""
    result = subprocess.run(
        [f"{venv}/bin/python", "-c", runner],
        capture_output=True,
        cwd=index_folder,
    )
    try:
        response = pickle.loads(result.stdout)
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

    def func_handler(*args, **kwargs):
        return run_remote_tool(
            tool_id=signature_dict["tool_id"],
            index_folder=index_folder,
            args=args,
            kwargs=kwargs,
            venv=venv,
            env_var=env_var,
        )

    async def async_func_handler(*args, **kwargs):
        return run_remote_tool(
            tool_id=signature_dict["tool_id"],
            index_folder=index_folder,
            args=args,
            kwargs=kwargs,
            venv=venv,
            env_var=env_var,
        )

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
        async_func_handler if signature_dict.get("is_async") else func_handler,
        qualname=signature_dict["tool_id"],
        doc=signature_dict.get("doc"),
    )
    func.__name__ = signature_dict["tool_id"]
    return func


# TODO: Sanitize tool_id, args, and kwargs
def run_remote_tool(
    tool_id: str,
    index_folder: os.PathLike,
    args: list | None = None,
    kwargs: dict | None = None,
    venv: str = VENV_NAME,
    env_var: dict | None = None,
):
    args = args or []
    kwargs = kwargs or {}
    env_var = env_var or {}

    module_name = ".".join(tool_id.split(".")[:-1])
    tool_name = tool_id.split(".")[-1]
    payload = json.dumps(
        {
            "args": args,
            "kwargs": kwargs,
        }
    ).encode("utf-8")

    # We use sockets to pass function output
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("localhost", 0))
    listener.listen(1)
    _, port = listener.getsockname()

    def handle_connection():
        conn, _ = listener.accept()
        with conn:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            listener.close()
            return data

    result_data = {}
    t = threading.Thread(
        target=lambda: result_data.setdefault("data", handle_connection())
    )
    t.start()

    runner = f"""
import asyncio, inspect, json, socket, sys, traceback
sys.path.insert(0, "{index_folder}")
try:
    from {module_name} import {tool_name}
    params = json.load(sys.stdin)
    args = params.get("args", [])
    kwargs = params.get("kwargs", {{}})
    if inspect.iscoroutinefunction({tool_name}):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete({tool_name}(*args, **kwargs))
    else:
        result = {tool_name}(*args, **kwargs)
    response = json.dumps({{"ok": True, "result": result}})
except Exception as e:
    err = traceback.format_exc()
    response = json.dumps({{"ok": False, "error": err}})
sock = socket.create_connection(("localhost", {port}))
sock.sendall(response.encode("utf-8"))
sock.close()
"""
    subprocess.run(
        [f"{index_folder}/{venv}/bin/python", "-c", runner],
        input=payload,
        capture_output=True,
        env=env_var,
    )

    t.join()
    response = json.loads(result_data["data"].decode("utf-8"))
    if response.get("ok"):
        return response["result"]
    else:
        raise RuntimeError(f"Subprocess failed with error:\n{response['error']}")
