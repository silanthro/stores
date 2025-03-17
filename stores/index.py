import logging
import venv
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
                loaded_index = None
                # Load local index
                if index_name.startswith(".") or index_name.startswith("/"):
                    try:
                        loaded_index = load_local_index(index_name)
                        self._index_paths[index_name] = index_name
                    except Exception:
                        logger.warning(
                            f'Unable to load index "{index_name}"', exc_info=True
                        )
                # Load remote index
                else:
                    try:
                        branch_or_commit = None
                        if ":" in index_name:
                            index_name, branch_or_commit = index_name.split(":")
                        loaded_index = load_remote_index(index_name, branch_or_commit)
                        self._index_paths[index_name] = str(CACHE_DIR / index_name)
                    except Exception:
                        logger.warning(
                            f'Unable to load index "{index_name}"\nIf this is a local index, index string should start with "." or "/"',
                            exc_info=True,
                        )
                if loaded_index:
                    for t in loaded_index:
                        self._add_tool(t, index_name)
            elif isinstance(tool, Callable):
                self._add_tool(wrap_tool(tool), "local")

    def _add_tool(self, tool: Callable, index: str = "local"):
        if ":" in tool.__name__ and tool.__name__ in self.tools_dict:
            raise ValueError(f"Duplicate tool - {tool.__name__}")

        # tool.__name__ = f"{index}:{tool.__name__}"

        self.tools.append(tool)
        self.tools_dict[tool.__name__] = tool
        self._tool_indexes[tool.__name__] = index

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
        return tool(**kwargs)

    def parse_and_execute(self, msg: str):
        toolcall = llm_parse_json(msg, keys=["toolname", "kwargs"])
        return self.execute(toolcall.get("toolname"), toolcall.get("kwargs"))
