import importlib
import logging
import os
import sys
import venv
from pathlib import Path

from stores.constants import TOOLS_CONFIG_FILENAME, VENV_NAME
from stores.indexes.base_index import BaseIndex
from stores.indexes.venv_utils import init_venv_tools, install_venv_deps

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

logging.basicConfig()
logger = logging.getLogger("stores.indexes.local_index")
logger.setLevel(logging.INFO)


class LocalIndex(BaseIndex):
    def __init__(
        self,
        index_folder: os.PathLike,
        create_venv: bool = False,
        env_var: dict | None = None,
    ):
        self.index_folder = Path(index_folder)
        self.env_var = env_var or {}

        if not self.index_folder.exists():
            raise ValueError(
                f"Unable to load index - {self.index_folder} does not exist"
            )

        if create_venv:
            # Create venv and install deps
            self.venv = self.index_folder / VENV_NAME
            if not self.venv.exists():
                venv.create(self.venv, symlinks=True, with_pip=True, upgrade_deps=True)
            install_venv_deps(self.index_folder)
            # Initialize tools
            tools = init_venv_tools(self.index_folder, self.env_var)
        else:
            if self.env_var:
                raise ValueError(
                    "Environment variables will only be restricted if create_venv=True when initializing LocalIndex"
                )
            tools = self._init_tools()
        super().__init__(tools)

    def _init_tools(self):
        """
        Load local tools.toml file and import tool functions

        NOTE: Can we just add index_folder to sys.path and import the functions?
        """
        index_manifest = self.index_folder / TOOLS_CONFIG_FILENAME
        if not index_manifest.exists():
            raise ValueError(f"Unable to load index - {index_manifest} does not exist")

        with open(index_manifest, "rb") as file:
            manifest = tomllib.load(file)["index"]

        tools = []
        for tool_id in manifest.get("tools", []):
            module_name = ".".join(tool_id.split(".")[:-1])
            tool_name = tool_id.split(".")[-1]

            module_file = self.index_folder / module_name.replace(".", "/")
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
