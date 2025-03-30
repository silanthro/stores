import json

import pytest


@pytest.fixture(
    params=[
        {
            "foo": "bar",
            "answer": 42,
            "hello world": [1, 2, 3.14],
            "empty": None,
        },
        ["foo", 1, [3.14], {"hello": "world"}, None],
    ],
)
def str_object(request):
    yield {
        "string": json.dumps(request.param),
        "object": request.param,
    }


@pytest.fixture(
    params=[
        # Unescaped quotes
        {
            "string": """{
                "foo": ""This is a quote"",
            }""",
            "object": {
                "foo": '"This is a quote"',
            },
            "keys": ["foo"],
        },
        # Mispelled keys
        {
            "string": """{
                "foo": "bar",
                "hell": "world",
            }""",
            "object": {
                "foo": "bar",
                "hello": "world",
            },
            "keys": ["foo", "hello"],
        },
        # Get larger json with given keys
        {
            "string": """{
                "foo": ""bar"",
                "hello": ""world"",
            }""",
            "object": {"foo": '"bar"",\n                "hello": ""world"'},
            "keys": ["foo"],
        },
    ],
)
def dirty_string(request):
    yield request.param
