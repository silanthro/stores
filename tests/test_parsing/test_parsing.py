import pytest

from stores.parsing import llm_parse_json


def test_llm_parse_json(str_object):
    assert llm_parse_json(str_object["string"]) == str_object["object"]


def test_llm_parse_json_handle_single_quotes(str_object):
    assert (
        llm_parse_json(str_object["string"].replace('"', "'")) == str_object["object"]
    )


def test_llm_parse_json_none_string(str_object):
    # Handles edge case where LLM produces "None" instead of "null"
    assert (
        llm_parse_json(str_object["string"].replace("null", "None"))
        == str_object["object"]
    )


def test_llm_parse_json_invalid():
    # Raises error for invalid string
    with pytest.raises(ValueError, match="Failed to parse JSON"):
        llm_parse_json("[invalid]")


def test_llm_parse_json_dirty_strings(dirty_string):
    assert (
        llm_parse_json(dirty_string["string"], keys=dirty_string["keys"])
        == dirty_string["object"]
    )
