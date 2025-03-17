import asyncio
import inspect
import logging
import venv
from pathlib import Path
from typing import Callable

from git import Repo
from pydantic import BaseModel

from stores.index_utils import (
    CACHE_DIR,
    VENV_NAME,
    get_index_signatures,
    get_index_tools,
    install_venv_deps,
    run_mp_process,
    wrap_remote_tool,
    wrap_tool,
)
from stores.parsing import llm_parse_json
from stores.tools import DEFAULT_TOOLS, REPLY

logging.basicConfig()
logger = logging.getLogger("stores.index")


def load_remote_index(index_id: str, branch_or_commit: str | None = None):
    index_folder = CACHE_DIR / index_id
    if not index_folder.exists():
        # TODO: Update to use DB
        repo_url = f"https://github.com/{index_id}.git"
        repo = Repo.clone_from(repo_url, index_folder)
        if branch_or_commit:
            repo.git.checkout(branch_or_commit)
    # Create venv and install deps
    venv_folder = index_folder / VENV_NAME
    venv.create(venv_folder, symlinks=True, with_pip=True)

    run_mp_process(
        fn=install_venv_deps,
        kwargs={"index_folder": index_folder},
        venv_folder=venv_folder,
    )

    tools = []
    index_signatures = run_mp_process(
        fn=get_index_signatures,
        kwargs={"index_folder": index_folder},
        venv_folder=venv_folder,
    )
    tools = [
        wrap_remote_tool(
            s,
            venv_folder,
            index_folder,
        )
        for s in index_signatures
    ]
    return tools


def load_local_index(index_path: str):
    tools = get_index_tools(index_path)
    return [wrap_tool(t) for t in tools]


class Index(BaseModel):
    tools: list[Callable]
    tools_dict: dict[str, Callable]
    env_vars: dict

    def __init__(
        self,
        tools: list[Callable | str | Path] | None = None,
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
            if isinstance(tool, (str, Path)):
                index_name = tool
                loaded_index = None
                # Load local index
                if Path(index_name).exists():
                    try:
                        loaded_index = load_local_index(index_name)
                        self._index_paths[index_name] = index_name
                    except Exception:
                        logger.warning(
                            f'Unable to load index "{index_name}"', exc_info=True
                        )
                if loaded_index is None and isinstance(index_name, str):
                    # Load remote index
                    try:
                        branch_or_commit = None
                        if ":" in index_name:
                            index_name, branch_or_commit = index_name.split(":")
                        loaded_index = load_remote_index(index_name, branch_or_commit)
                        self._index_paths[index_name] = str(CACHE_DIR / index_name)
                    except Exception:
                        logger.warning(
                            f'Unable to load index "{index_name}"\nIf this is a local index, make sure it can be found as a directory',
                            exc_info=True,
                        )
                if loaded_index is None:
                    raise ValueError(
                        f'Unable to load index "{index_name}"\nIf this is a local index, make sure it can be found as a directory'
                    )
                else:
                    for t in loaded_index:
                        self._add_tool(t, index_name)
            elif isinstance(tool, Callable):
                self._add_tool(wrap_tool(tool), "local")

    def _add_tool(self, tool: Callable, index: str = "local"):
        # if ":" in tool.__name__ and tool.__name__ in self.tools_dict:
        if tool.__name__ in self.tools_dict:
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
