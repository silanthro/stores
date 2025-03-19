import logging
import shutil
from smtplib import SMTPAuthenticationError

import pytest

import stores

logging.basicConfig()
logger = logging.getLogger("stores.test_index.test_remote_index")
logger.setLevel(logging.INFO)


async def test_remote_index():
    # Check that env_vars are set correctly
    index = stores.Index(
        ["silanthro/send-gmail"],
        env_vars={
            "silanthro/send-gmail": {
                "GMAIL_ADDRESS": "not@real.email",
                "GMAIL_PASSWORD": "password",
            },
        },
    )
    # If env_vars are set correctly, this should raise SMTPAuthenticationError
    # Otherwise it would raise KeyError
    with pytest.raises(SMTPAuthenticationError):
        index.tools[0](
            subject="Subject",
            body="Body",
            recipients=["no@such.email"],
        )
    # Clean up index
    shutil.rmtree(stores.index_utils.CACHE_DIR / "silanthro/send-gmail")
