import asyncio
import importlib
import inspect
import multiprocessing
import os
import sys
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Callable

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
    for tool in manifest.get("tools", []):
        module_name = ".".join(tool.split(".")[:-1])
        tool_name = tool.split(".")[-1]

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
        tools.append(tool)
    return tools


def isolate_fn_env(
    fn: Callable,
    kwargs: dict,
    env_vars: dict | None = None,
    conn: Connection | None = None,
):
    os.environ.clear()
    os.environ.update(env_vars)

    if inspect.iscoroutinefunction(fn):
        loop = asyncio.get_event_loop()
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
        if tools is None:
            tools = DEFAULT_TOOLS
        tools.append(REPLY)

        for tool in tools:
            if isinstance(tool, str):
                index_name = tool
                try:
                    loaded_index = load_online_index(index_name)
                except Exception:
                    loaded_index = load_index_from_path(index_name)
                for t in loaded_index:
                    self._add_tool(t, index_name)
            elif isinstance(tool, Callable):
                self._add_tool(tool, "local")

    def _add_tool(self, tool: Callable, index: str = "local"):
        if ":" in tool.__name__ and tool.__name__ in self.tools_dict:
            raise ValueError(f"Duplicate tool - {tool.__name__}")

        tool.__name__ = f"{index}:{tool.__name__}"

        self.tools.append(tool)
        self.tools_dict[tool.__name__] = tool
        self._tool_indexes[tool.__name__] = index

    def execute(self, toolname: str, kwargs: dict | None = None):
        if ":" not in toolname:
            matching_tools = []
            for key in self.tools_dict.keys():
                if key.endswith(f":{toolname}"):
                    matching_tools.append(key)
            if len(matching_tools) == 0:
                raise ValueError("No tool matching '{toolname}'")
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
                "fn": tool,
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
        toolcall = llm_parse_json(msg)
        return self.execute(toolcall.get("toolname"), toolcall.get("kwargs"))
