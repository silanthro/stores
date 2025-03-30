import logging
import shutil

import pytest

import stores.indexes

logging.basicConfig()
logger = logging.getLogger("stores.test_indexes.test_remote_index")
logger.setLevel(logging.INFO)


def test_lookup_index():
    index_metadata = stores.indexes.remote_index.lookup_index(
        "silanthro/send-gmail", "0.1.0"
    )
    assert index_metadata == {
        "clone_url": "https://github.com/silanthro/send-gmail.git",
        "commit": "9cde5755e9ecd627a6f303421031d2a7fef9427d",
        "version": "0.1.0",
    }


async def test_remote_index():
    # Check that env_vars are set correctly
    index = stores.indexes.RemoteIndex(
        "silanthro/send-gmail:0.2.0",
        env_var={
            "GMAIL_ADDRESS": "not@real.email",
            "GMAIL_PASSWORD": "password",
        },
    )
    # If env_vars are set correctly, this should raise SMTPAuthenticationError
    # Otherwise it would raise KeyError
    with pytest.raises(RuntimeError, match="SMTPAuthenticationError"):
        index.tools[0](
            subject="Subject",
            body="Body",
            recipients=["no@such.email"],
        )
    # Clean up index
    shutil.rmtree(stores.indexes.remote_index.CACHE_DIR / "silanthro/send-gmail:0.2.0")
