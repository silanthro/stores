import asyncio
import importlib
import inspect
import sys
from pathlib import Path
from typing import Callable

import yaml
from git import Repo
from pydantic import BaseModel

from stores.tools import DEFAULT_TOOLS


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


class Index(BaseModel):
    tools: list[Callable]

    def __init__(self, tools: list[Callable | str] | None = None):
        if tools is None:
            tools = DEFAULT_TOOLS
        else:
            loaded_tools = []
            for tool in tools:
                if isinstance(tool, str):
                    try:
                        loaded_tools += load_online_index(tool)
                    except Exception:
                        loaded_tools += load_index_from_path(tool)
                elif isinstance(tool, Callable):
                    loaded_tools.append(tool)
            tools = loaded_tools
        super().__init__(
            tools=tools,
        )

    @property
    def tools_dict(self):
        return {t.__name__: t for t in self.tools}

    def execute(self, toolname: str, kwargs: dict):
        tool = self.tools_dict[toolname]
        if inspect.iscoroutinefunction(tool):
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(tool(**kwargs))
        else:
            result = tool(**kwargs)
        return result
