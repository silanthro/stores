import os
import sys
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def new_env_context(venv_path: os.PathLike, env_vars: dict | None = None):
    old_env = os.environ.copy()
    os.environ.clear()
    os.environ.update(env_vars or {})

    original_sys_path = list(sys.path)

    venv_path = Path(venv_path)
    site_packages_candidates = list(venv_path.glob("lib/**/*/site-packages"))
    if len(site_packages_candidates) == 0:
        raise RuntimeError(f"No site-packages found in venv {venv_path}")

    sys.path.insert(0, str(site_packages_candidates[0]))

    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        sys.path = original_sys_path
