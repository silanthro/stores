import asyncio
import inspect
import logging
import typing
import venv
from enum import Enum
from pathlib import Path
from typing import Callable, GenericAlias, Type, Union

from git import Repo
from pydantic import BaseModel

from stores.index_utils import (
    CACHE_DIR,
    VENV_NAME,
    get_index_signatures,
    get_index_tools,
    install_venv_deps,
    lookup_index,
    run_mp_process,
    wrap_remote_tool,
    wrap_tool,
)
from stores.parsing import llm_parse_json
from stores.tools import DEFAULT_TOOLS, REPLY

logging.basicConfig()
logger = logging.getLogger("stores.index")


class ProviderFormat(str, Enum):
    OPENAI_CHAT = "openai-chat-completions"
    OPENAI_RESPONSES = "openai-responses"
    ANTHROPIC = "anthropic"
    GOOGLE_GEMINI = "google-gemini"


def load_remote_index(
    index_id: str, commit_like: str | None = None, env_vars: dict | None = None
):
    index_folder = CACHE_DIR / index_id
    if not index_folder.exists():
        # Lookup Stores DB
        index_metadata = lookup_index(index_id, commit_like)
        if index_metadata:
            repo_url = index_metadata["clone_url"]
            commit_like = index_metadata["commit"]
        else:
            # Otherwise, assume index references a GitHub repo
            repo_url = f"https://github.com/{index_id}.git"
        repo = Repo.clone_from(repo_url, index_folder)
        if commit_like:
            repo.git.checkout(commit_like)
    # Create venv and install deps
    venv_folder = index_folder / VENV_NAME
    if not venv_folder.exists():
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
            env_vars=env_vars or {},
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
        env_vars = env_vars or {}
        super().__init__(
            tools=[],
            tools_dict={},
            env_vars=env_vars,
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
                        index_env_vars = env_vars.get(index_name)
                        commit_like = None  # Version or branch or commit
                        if ":" in index_name:
                            index_name, commit_like = index_name.split(":")
                        loaded_index = load_remote_index(
                            index_name, commit_like, index_env_vars
                        )
                        self._index_paths[index_name] = str(CACHE_DIR / index_name)
                    except Exception:
                        logger.warning(
                            f'Unable to load index "{index_name}"\nIf this is a local index, make sure it can be found as a directory and contains a TOOLS.yml file.',
                            exc_info=True,
                        )
                if loaded_index is None:
                    raise ValueError(
                        f'Unable to load index "{index_name}"\nIf this is a local index, make sure it can be found as a directory and contains a TOOLS.yml file.'
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

    def _get_name(self, param: Type | GenericAlias, default: str = "STRING") -> str:
        """Helper method to get the name of a type."""
        try:
            return param.__name__
        except AttributeError:
            return default

    def _get_type_info(self, param_type, param, provider=None):
        """Helper method to get type information from a parameter type annotation."""
        origin = typing.get_origin(param_type)
        args = typing.get_args(param_type)
        # Check for default value first, as this applies regardless of type
        nullable = param.default is not inspect.Parameter.empty

        if origin is Union:
            # For Union types, also check if None is one of the types
            nullable = nullable or type(None) in args
            types = [t for t in args if t is not type(None)]
            if provider == ProviderFormat.GOOGLE_GEMINI:
                # For Gemini, we only use the first type and track nullable
                param_type = types[0] if types else str
                origin = typing.get_origin(param_type)
                args = typing.get_args(param_type)
            else:
                # For OpenAI and Anthropic, we keep all types
                return origin, types, param_type, nullable

        return origin, args, param_type, nullable

    def format_tools(
        self,
        provider: ProviderFormat,
    ):
        """Format tools based on the provider's requirements."""
        # Check for empty tools list first
        if not self.tools:
            raise ValueError("No tools provided to format")

        formatted_tools = []

        # Check for duplicate tool names early
        tool_names = [tool.__name__ for tool in self.tools]
        seen_names = set()
        for name in tool_names:
            formatted_name = name.replace(".", "-")
            if formatted_name in seen_names:
                raise ValueError(f"Duplicate tool name: {formatted_name}")
            seen_names.add(formatted_name)

        standard_type_mappings = {
            "str": "string",
            "int": "integer",
            "bool": "boolean",
            "float": "number",
            "list": "array",
            "NoneType": "null",
        }
        for tool in self.tools:
            # Extract parameters and their types from the tool's function signature
            signature = inspect.signature(tool)
            parameters = {}
            required_params = []
            for param_name, param in signature.parameters.items():
                param_type = param.annotation
                origin, args, param_type, nullable = self._get_type_info(
                    param_type, param, provider
                )

                if provider == ProviderFormat.GOOGLE_GEMINI:
                    if origin is list:
                        type_name = "array"
                        item_type = self._get_name(args[0]) if args else "string"
                        if item_type not in standard_type_mappings:
                            raise TypeError(
                                f"Unsupported type for array items: {item_type}"
                            )
                        param_info = {
                            "type": type_name,
                            "items": {"type": standard_type_mappings[item_type]},
                            "description": "",
                            "nullable": nullable,
                        }
                    else:
                        type_name = self._get_name(param_type)
                        if type_name not in standard_type_mappings:
                            raise TypeError(f"Unsupported type: {type_name}")
                        param_info = {
                            "type": standard_type_mappings[type_name],
                            "description": "",
                            "nullable": nullable,
                        }
                    parameters[param_name] = param_info
                else:
                    if origin is list:
                        type_name = "array"
                        item_type = (
                            self._get_name(args[0], "string") if args else "string"
                        )
                        if item_type not in standard_type_mappings:
                            raise TypeError(
                                f"Unsupported type for array items: {item_type}"
                            )
                        parameters[param_name] = {
                            "type": type_name,
                            "items": {"type": standard_type_mappings[item_type]},
                        }
                    else:
                        # Handle both Union types and simple types
                        types = []
                        # Validate all types in the Union
                        for t in args if args else [param_type]:
                            type_name = self._get_name(t, str(t))
                            if type_name not in standard_type_mappings:
                                raise TypeError(f"Unsupported type: {type_name}")
                            types.append(standard_type_mappings[type_name])
                        parameters[param_name] = {
                            "type": types[0] if len(types) == 1 else types
                        }

                required_params.append(param_name)

            # Replace periods in function name with hyphens
            # TODO: Move ./- replacement to tool wrapper
            formatted_tool_name = tool.__name__.replace(".", "-")

            # Create formatted tool structure based on provider
            description = inspect.getdoc(tool) or "No description available."
            base_params = {
                "type": "object",
                "properties": parameters,
                "required": required_params,
            }

            # Format tool based on provider
            if provider == ProviderFormat.OPENAI_CHAT:
                formatted_tool = {
                    "type": "function",
                    "function": {
                        "name": formatted_tool_name,
                        "description": description,
                        "parameters": {**base_params, "additionalProperties": False},
                        "strict": True,
                    },
                }
            elif provider == ProviderFormat.OPENAI_RESPONSES:
                formatted_tool = {
                    "type": "function",
                    "name": formatted_tool_name,
                    "description": description,
                    "parameters": {**base_params, "additionalProperties": False},
                }
            elif provider == ProviderFormat.ANTHROPIC:
                formatted_tool = {
                    "name": formatted_tool_name,
                    "description": description,
                    "input_schema": base_params,
                }
            elif provider == ProviderFormat.GOOGLE_GEMINI:
                formatted_tool = {
                    "name": formatted_tool_name,
                    "parameters": {
                        "type": "OBJECT",
                        "description": description,
                        "properties": parameters,
                        "required": required_params,
                    },
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
