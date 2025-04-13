import logging
import os
from pathlib import Path
from typing import Callable, Optional

from stores.indexes.base_index import BaseIndex
from stores.indexes.local_index import LocalIndex
from stores.indexes.remote_index import RemoteIndex

logging.basicConfig()
logger = logging.getLogger("stores.index")
logger.setLevel(logging.INFO)


class Index(BaseIndex):
    def __init__(
        self,
        tools: list[Callable, os.PathLike] | None = None,
        env_var: dict[str, dict] | None = None,
        cache_dir: Optional[os.PathLike] = None,
        reset_cache=False,
    ):
        self.env_var = env_var or {}
        tools = tools or []

        _tools = []
        for tool in tools:
            if isinstance(tool, (str, Path)):
                index_name = tool
                loaded_index = None
                if Path(index_name).exists():
                    # Load LocalIndex
                    try:
                        loaded_index = LocalIndex(index_name)
                    except Exception:
                        logger.warning(
                            f'Unable to load index "{index_name}"', exc_info=True
                        )
                if loaded_index is None and isinstance(index_name, str):
                    # Load RemoteIndex
                    try:
                        loaded_index = RemoteIndex(
                            index_name,
                            env_var=self.env_var.get(index_name),
                            cache_dir=cache_dir,
                            reset_cache=reset_cache,
                        )
                    except Exception:
                        logger.warning(
                            f'Unable to load index "{index_name}"\nIf this is a local index, make sure it can be found as a directory and contains a tools.toml file.',
                            exc_info=True,
                        )
                if loaded_index is None:
                    raise ValueError(
                        f'Unable to load index "{index_name}"\nIf this is a local index, make sure it can be found as a directory and contains a tools.toml file.'
                    )
                _tools += loaded_index.tools
            elif isinstance(tool, Callable):
                _tools.append(tool)

        super().__init__(_tools)
