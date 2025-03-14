import asyncio
import importlib
import inspect
import multiprocessing
import os
import sys
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Callable, Literal, Union

import yaml
from git import Repo
from pydantic import BaseModel

from stores.parsing import llm_parse_json
from stores.tools import DEFAULT_TOOLS, REPLY


def get_cache_dir():
    # TODO: Support venv and global
    return Path(".tools")


CACHE_DIR = get_cache_dir()
TOOLS_CONFIG_FILENAME = "TOOLS.yml"


def load_online_index(index_id: str):
    dst = CACHE_DIR / index_id
    if not dst.exists():
        # TODO: Update to use DB
        repo_url = f"https://github.com/{index_id}.git"
        # TODO: Use specific commit
        Repo.clone_from(repo_url, dst)
    return load_index_from_path(str(dst))


def load_index_from_path(index_path: str | Path):
    index_path = Path(index_path)
    if index_path.name == TOOLS_CONFIG_FILENAME:
        index_path = index_path.parent
    index_manifest = index_path / TOOLS_CONFIG_FILENAME
    with open(index_manifest) as file:
        manifest = yaml.safe_load(file)
    tools = []
    for tool_id in manifest.get("tools", []):
        module_name = ".".join(tool_id.split(".")[:-1])
        tool_name = tool_id.split(".")[-1]

        module_file = index_path / module_name.replace(".", "/")
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


def isolate_fn_env(
    tool_name: str,
    tool_index: str,
    local_tool: Callable,
    kwargs: dict,
    env_vars: dict | None = None,
    conn: Connection | None = None,
):
    os.environ.clear()
    os.environ.update(env_vars)

    if tool_index != "local":
        index = load_index_from_path(tool_index)
        index_dict = {t.__name__: t for t in index}
        fn = index_dict[tool_name]
    else:
        fn = local_tool
    if inspect.iscoroutinefunction(fn):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(fn(**kwargs))
    else:
        result = fn(**kwargs)
    if conn:
        conn.send(result)
        conn.close()


class Index(BaseModel):
    tools: list[Callable]
    tools_dict: dict[str, Callable]
    env_vars: dict

    def __init__(
        self,
        tools: list[Callable | str] | None = None,
        env_vars: dict | None = None,
    ):
        super().__init__(
            tools=[],
            tools_dict={},
            env_vars=env_vars or {},
        )
        self._tool_indexes = {}
        self._index_paths = {}
        if tools is None:
            tools = DEFAULT_TOOLS
        tools.append(REPLY)

        for tool in tools:
            if isinstance(tool, str):
                index_name = tool
                try:
                    loaded_index = load_online_index(index_name)
                    self._index_paths[index_name] = str(CACHE_DIR / index_name)
                except Exception:
                    loaded_index = load_index_from_path(index_name)
                    self._index_paths[index_name] = index_name
                for t in loaded_index:
                    self._add_tool(t, index_name)
            elif isinstance(tool, Callable):
                self._add_tool(tool, "local")

    def _add_tool(self, tool: Callable, index: str = "local"):
        if ":" in tool.__name__ and tool.__name__ in self.tools_dict:
            raise ValueError(f"Duplicate tool - {tool.__name__}")

        # tool.__name__ = f"{index}:{tool.__name__}"

        self.tools.append(tool)
        self.tools_dict[tool.__name__] = tool
        self._tool_indexes[tool.__name__] = index

    def format_tools(self, provider: Literal["openai-chat-completions", "openai-responses", "anthropic", "google-gemini"]):
        formatted_tools = []
        standard_type_mappings = {
            'str': 'string',
            'int': 'integer',
            'bool': 'boolean',
            'float': 'number',
            'list': 'array',
            'NoneType': 'null',
        }
        gemini_type_mappings = {
            'str': 'STRING',
            'int': 'NUMBER',
            'bool': 'BOOLEAN',
            'float': 'NUMBER',
            'list': 'ARRAY',
            'NoneType': 'null',
        }
        for tool in self.tools_dict.items():
            # Extract parameters and their types from the tool's function signature
            signature = inspect.signature(tool)
            parameters = {}
            required_params = []
            for param_name, param in signature.parameters.items():
                param_type = param.annotation
                if provider == "google-gemini":
                    # For google-gemini, handle Union types and simple types differently
                    nullable = False
                    if hasattr(param_type, '__origin__'):
                        if param_type.__origin__ is Union:
                            nullable = type(None) in param_type.__args__
                            types = [t for t in param_type.__args__ if t is not type(None)]  # Get non-None types
                            param_type = types[0] if types else str  # Use first non-None type or default to str
                        elif param_type.__origin__ is list:
                            type_name = "ARRAY"
                            item_type = param_type.__args__[0].__name__ if param_type.__args__ else 'STRING'
                            param_info = {
                                "type": type_name,
                                "items": {"type": gemini_type_mappings.get(item_type, item_type)},
                                "description": ""
                            }
                            if nullable:
                                param_info["nullable"] = True
                            parameters[param_name] = param_info
                            continue
                    elif param.default is not param.empty:
                        nullable = True

                    # Get the type name from the actual type object
                    type_name = param_type.__name__ if hasattr(param_type, '__name__') else 'STRING'
                    type_name = gemini_type_mappings.get(type_name, type_name)
                    param_info = {
                        "type": type_name,
                        "description": ""
                    }
                    if nullable:
                        param_info["nullable"] = True
                    parameters[param_name] = param_info
                else:
                    if hasattr(param_type, '__origin__') and param_type.__origin__ is list:
                        type_name = "array"
                        item_type = param_type.__args__[0].__name__ if param_type.__args__ else 'string'
                        parameters[param_name] = {
                            "type": type_name,
                            "items": {"type": standard_type_mappings.get(item_type, item_type)}
                        }
                    elif hasattr(param_type, '__args__'):
                        # Use array of types for union types
                        types = [standard_type_mappings.get(t.__name__, str(t)) if hasattr(t, '__name__') else str(t) for t in param_type.__args__]
                        parameters[param_name] = {"type": types}
                    else:
                        type_name = standard_type_mappings.get(param_type.__name__, str(param_type)) if hasattr(param_type, '__name__') else str(param_type)
                        # If parameter has a default value, include null type
                        if param.default is not param.empty:
                            parameters[param_name] = {"type": [type_name, "null"]}
                        else:
                            parameters[param_name] = {"type": type_name}
                required_params.append(param_name)

            # Replace periods in function name with hyphens
            formatted_tool_name = tool.__name__.replace('.', '-')

            # Create formatted tool structure based on provider
            if provider == "openai-chat-completions":
                formatted_tool = {
                    "type": "function",
                    "function": {
                        "name": formatted_tool_name,
                        "description": tool.__doc__ or "No description available.",
                        "parameters": {
                            "type": "object",
                            "properties": parameters,
                            "required": required_params,
                            "additionalProperties": False
                        },
                        "strict": True
                    }
                }
            elif provider == "openai-responses":
                formatted_tool = {
                    "type": "function",
                    "name": formatted_tool_name,
                    "description": tool.__doc__ or "No description available.",
                    "parameters": {
                        "type": "object",
                        "properties": parameters,
                        "required": required_params,
                        "additionalProperties": False
                    }
                }
            elif provider == "anthropic":
                formatted_tool = {
                    "name": formatted_tool_name,
                    "description": tool.__doc__ or "No description available.",
                    "input_schema": {
                        "type": "object",
                        "properties": parameters,
                        "required": required_params
                    }
                }
            elif provider == "google-gemini":
                formatted_tool = {
                    "name": formatted_tool_name,
                    "parameters": {
                        "type": "OBJECT",
                        "description": tool.__doc__ or "No description available.",
                        "properties": parameters,
                        "required": required_params
                    }
                }
            formatted_tools.append(formatted_tool)
        return formatted_tools

    def execute(self, toolname: str, kwargs: dict | None = None):
        if toolname == "REPLY":
            return kwargs.get("msg")
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
            raise ValueError("No tool matching '{toolname}'")

        tool = self.tools_dict[toolname]
        index = self._tool_indexes[toolname]
        if index == "local":
            env_vars = os.environ.copy()
        else:
            env_vars = self.env_vars.get(index, {})
        kwargs = kwargs or {}

        parent_conn, child_conn = multiprocessing.Pipe()
        p = multiprocessing.Process(
            target=isolate_fn_env,
            kwargs={
                "tool_name": tool.__name__,
                "tool_index": self._index_paths.get(index, index),
                "local_tool": tool if index == "local" else None,
                "kwargs": kwargs,
                "env_vars": env_vars,
                "conn": child_conn,
            },
        )
        p.start()
        p.join()

        output = parent_conn.recv()
        return output

    def parse_and_execute(self, msg: str):
        toolcall = llm_parse_json(msg, keys=["toolname", "kwargs"])
        return self.execute(toolcall.get("toolname"), toolcall.get("kwargs"))
