import shutil

import pytest

import stores


async def test_index(local_index_folder):
    def foo():
        pass

    # Try loading Index with all types of inputs
    index = stores.Index(
        [
            "silanthro/send-gmail",
            local_index_folder,
            foo,
        ],
        env_var={
            "silanthro/send-gmail": {
                "GMAIL_ADDRESS": "not@real.email",
                "GMAIL_PASSWORD": "password",
            },
        },
    )

    assert [t.__name__ for t in index.tools] == [
        "tools.send_gmail",
        "tools.foo",
        "tools.foo_w_return_type",
        "tools.async_foo",
        "tools.enum_input",
        "tools.typed_dict_input",
        "hello.world",
        "foo",
    ]

    # Check that env_vars are set correctly
    # This should raise SMTPAuthenticationError
    # Otherwise it would raise KeyError
    with pytest.raises(RuntimeError, match="SMTPAuthenticationError"):
        index.tools[0](
            subject="Subject",
            body="Body",
            recipients=["no@such.email"],
        )

    # Clean up index
    shutil.rmtree(stores.indexes.remote_index.CACHE_DIR / "silanthro/send-gmail")


def test_invalid_index():
    with pytest.raises(ValueError, match="Unable to load index"):
        stores.Index(["./tests"])
