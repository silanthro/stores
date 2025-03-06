import asyncio
import importlib
import inspect
from pathlib import Path
from typing import Callable

import yaml
from pydantic import BaseModel

from stores.tools import DEFAULT_TOOLS


def load_index_from_path(index_path: str):
    index_folder = Path(index_path)
    index_manifest = index_folder / "TOOLS.yml"
    with open(index_manifest) as file:
        manifest = yaml.safe_load(file)

    tools = []
    package = "/".join(index_path.split("/")[:-1])
    module_parent = index_path.split("/")[-1]
    for tool in manifest.get("tools"):
        module_name = ".".join(tool.split(".")[:-1])
        tool_name = tool.split(".")[-1]
        module = importlib.import_module(
            f"{module_parent}.{module_name}",
            package=package,
        )
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
