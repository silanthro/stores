import json
import logging
import shutil
import subprocess
import venv
from os import PathLike
from pathlib import Path
from typing import Optional

import requests

from stores.constants import VENV_NAME
from stores.indexes.base_index import BaseIndex
from stores.indexes.venv_utils import init_venv_tools, install_venv_deps

logging.basicConfig()
logger = logging.getLogger("stores.indexes.remote_index")
logger.setLevel(logging.INFO)

try:
    from git import GitCommandError, Repo
except Exception:
    logger.warning("Failed to import git")

# TODO: CACHE_DIR might resolve differently
CACHE_DIR = Path(".tools")
INDEX_LOOKUP_URL = (
    "https://mnryl5tkkol3yitc3w2rupqbae0ovnej.lambda-url.us-east-1.on.aws/"
)


def clear_default_cache():
    shutil.rmtree(CACHE_DIR)


def lookup_index(index_id: str, index_version: str | None = None):
    response = requests.post(
        INDEX_LOOKUP_URL,
        headers={
            "content-type": "application/json",
        },
        data=json.dumps(
            {
                "index_id": index_id,
                "index_version": index_version,
            }
        ),
    )
    if response.ok:
        return response.json()
    else:
        raise ValueError(f"Index {index_id} not found in database")


class RemoteIndex(BaseIndex):
    def __init__(
        self,
        index_id: str,
        env_var: dict | None = None,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        cache_dir: Optional[PathLike] = None,
        reset_cache=False,
        sys_executable: str | None = None,
    ):
        self.index_id = index_id
        if cache_dir is None:
            cache_dir = CACHE_DIR
        else:
            cache_dir = Path(cache_dir)
        if reset_cache:
            shutil.rmtree(cache_dir)
        self.index_folder = cache_dir / self.index_id
        self.env_var = env_var or {}
        include = include or []
        exclude = exclude or []
        if not self.index_folder.exists():
            logger.info(f"Installing {index_id}...")
            commit_like = None
            if ":" in index_id:
                index_id, commit_like = index_id.split(":")
            # Lookup Stores DB
            repo_url = None
            try:
                index_metadata = lookup_index(index_id, commit_like)
                if index_metadata:
                    repo_url = index_metadata["clone_url"]
                    commit_like = index_metadata["commit"]
            except Exception:
                logger.warning(
                    f"Could not find {index_id} in stores, assuming index references a GitHub repo..."
                )
                pass
            if not repo_url:
                # Otherwise, assume index references a GitHub repo
                repo_url = f"https://github.com/{index_id}.git"
            try:
                repo = Repo.clone_from(repo_url, self.index_folder)
            except GitCommandError as e:
                raise ValueError(f"Index {index_id} not found") from e
            if commit_like:
                repo.git.checkout(commit_like)

        # Create venv and install deps
        self.venv = self.index_folder / VENV_NAME
        if not self.venv.exists():
            if sys_executable:
                subprocess.run(
                    [sys_executable, "-m", "venv", str(self.venv)], check=True
                )
            else:
                venv.create(self.venv, symlinks=True, with_pip=True, upgrade_deps=True)
        install_venv_deps(self.index_folder)
        # Initialize tools
        tools = init_venv_tools(
            self.index_folder, env_var=self.env_var, include=include, exclude=exclude
        )
        super().__init__(tools)
