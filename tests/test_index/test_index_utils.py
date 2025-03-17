import logging

import stores.index_utils as utils

logging.basicConfig()
logger = logging.getLogger("stores.test_index.text_index_utils")
logger.setLevel(logging.INFO)


def test_get_index_signatures(local_index_folder):
    signatures = utils.get_index_signatures(local_index_folder)
    assert signatures == [
        {
            "name": "tools.foo",
            "signature": "foo(bar: str)",
            "doc": "Documentation of foo\nArgs:\n    bar (str): Sample text",
            "async": False,
        },
        {
            "name": "tools.async_foo",
            "signature": "async_foo(bar: str)",
            "doc": "Documentation of async_foo\nArgs:\n    bar (str): Sample text",
            "async": True,
        },
        {
            "name": "hello.world",
            "signature": "world(bar: str)",
            "doc": None,
            "async": False,
        },
    ]


def test_get_index_tools(local_index_folder):
    tools = utils.get_index_tools(local_index_folder)
    assert [t.__name__ for t in tools] == [
        "tools.foo",
        "tools.async_foo",
        "hello.world",
    ]


def test_run_remote_tool(local_index_folder):
    tools = utils.get_index_tools(local_index_folder)
    sample_string = "hello world"
    for tool in tools:
        result = utils.run_remote_tool(
            tool.__name__,
            index_folder=local_index_folder,
            kwargs={"bar": sample_string},
        )
        assert result == sample_string
