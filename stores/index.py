import asyncio
import inspect
import logging
import venv
from collections import Counter
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
    lookup_index,
    run_mp_process,
    wrap_remote_tool,
    wrap_tool,
)
from stores.parsing import llm_parse_json
from stores.tools import REPLY
from stores.utils import ProviderFormat, get_type_info, get_types

logging.basicConfig()
logger = logging.getLogger("stores.index")


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
        tools = tools or []
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
                            f'Unable to load index "{index_name}"\nIf this is a local index, make sure it can be found as a directory and contains a tools.toml file.',
                            exc_info=True,
                        )
                if loaded_index is None:
                    raise ValueError(
                        f'Unable to load index "{index_name}"\nIf this is a local index, make sure it can be found as a directory and contains a tools.toml file.'
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

    def format_tools(
        self,
        provider: ProviderFormat,
    ):
        """Format tools based on the provider's requirements."""
        # Check for empty tools list first
        if not self.tools:
            raise ValueError("No tools provided to format")

        formatted_tools = []

        # Check for duplicate tool names
        tool_name_counts = Counter([tool.__name__ for tool in self.tools])
        duplicates = [name for name in tool_name_counts if tool_name_counts[name] > 1]
        if duplicates:
            raise ValueError(f"Duplicate tool name(s): {duplicates}")

        for tool in self.tools:
            # Extract parameters and their types from the tool's function signature
            signature = inspect.signature(tool)
            parameters = {}
            required_params = []
            for param_name, param in signature.parameters.items():
                param_type = param.annotation
                args, processed_type, nullable = get_type_info(
                    param_type, param, provider
                )

                types = get_types(processed_type, nullable)

                param_info = {
                    "type": types[0] if len(types) == 1 else types,
                    "description": "",
                }
                if provider == ProviderFormat.GOOGLE_GEMINI:
                    param_info["nullable"] = nullable

                if types[0] == "array":
                    item_type = get_types(args[0] if args else "str", nullable)[0]
                    param_info["items"] = {"type": item_type}

                parameters[param_name] = param_info

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
                        "type": "object",
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
