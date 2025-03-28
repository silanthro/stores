import json
import logging
import re
from itertools import combinations
from typing import Any

import dirtyjson
from dirtyjson.attributed_containers import AttributedDict, AttributedList
from fuzzywuzzy import process

logging.basicConfig()
logger = logging.getLogger("stores.parse")
logger.setLevel(logging.INFO)


def find_json(rgx: str, text: str):
    match = re.search(rgx, text)
    if match is None:
        return text
    else:
        return match.groupdict().get("json")


def convert_attributed_container(
    container: Any | AttributedDict | AttributedList | float | int,
):
    if isinstance(container, AttributedList):
        return [convert_attributed_container(i) for i in container]
    elif isinstance(container, AttributedDict):
        dict_container = {**container}
        for k, v in dict_container.items():
            dict_container[k] = convert_attributed_container(v)
        return dict_container
    else:
        return container


def llm_parse_json(text: str, keys: list[str] = None, autoescape=True):
    """Read LLM output and extract JSON data from it."""

    keys = keys or []

    # First check for ```json
    code_snippet_pattern = r"```json(?P<json>(.|\s|\n)*?)```"
    code_snippet_result = find_json(code_snippet_pattern, text)
    # Then try to find the longer match between [.*?] and {.*?}
    array_pattern = re.compile("(?P<json>\\[.*\\])", re.DOTALL)
    array_result = find_json(array_pattern, text)
    dict_pattern = re.compile("(?P<json>{.*})", re.DOTALL)
    dict_result = find_json(dict_pattern, text)

    if array_result and dict_result and len(dict_result) > len(array_result):
        results = [
            code_snippet_result,
            dict_result,
            array_result,
        ]
    else:
        results = [
            code_snippet_result,
            array_result,
            dict_result,
        ]

    # Try each result in order
    result_json = None
    for result in results:
        if result is not None:
            try:
                result_json = dirtyjson.loads(result)
                break
            except dirtyjson.error.Error as e:
                if autoescape and e.msg.startswith("Expecting ',' delimiter"):
                    # Possibly due to non-escaped quotes
                    corrected_json_str = escape_quotes(result, keys)
                    if corrected_json_str:
                        result_json = dirtyjson.loads(corrected_json_str)
                        break

            try:
                result = (
                    result.replace("None", "null")
                    .replace("True", "true")
                    .replace("False", "false")
                )
                result_json = dirtyjson.loads(result)
                break
            except dirtyjson.error.Error:
                continue

    if result_json:
        result_json = fuzzy_match_keys(result_json, keys)
        return convert_attributed_container(result_json)

    error_message = f"Failed to parse JSON from text {text}"
    raise ValueError(error_message)


# Brute force escape chars
def escape_quotes(json_str: str, keys: list[str] = None):
    keys = keys or []
    quote_pos = [i for i, c in enumerate(json_str) if c in "\"'"]
    # At minimum there should be 2*len(keys) quotes, any quotes
    # more than this is a candidate for escape
    # In addition, as long as there is an escaped quote, we need
    # at least two none-escaped quotes
    # TODO: Stricter conditions
    max_escapes = len(quote_pos) - 2 * len(keys) - 2
    candidate_json_str = None
    for n in range(1, max_escapes + 1):
        candidates = list(combinations(quote_pos, n))
        for candidate in candidates:
            new_json_str = ""
            for start, end in zip(
                [0, *candidate], [*candidate, len(json_str)], strict=True
            ):
                new_json_str += json_str[start:end] + "\\"
            new_json_str = new_json_str[:-1]
            try:
                parsed = llm_parse_json(new_json_str, keys, autoescape=False)
                if all(key in parsed for key in keys):
                    new_candidate = json.dumps(parsed)
                    if candidate_json_str is None:
                        candidate_json_str = new_candidate
                    # Get the largest valid JSON
                    elif len(new_candidate) > len(candidate_json_str):
                        candidate_json_str = new_candidate
            except Exception:
                pass
    return candidate_json_str


def fuzzy_match_keys(json_dict: dict, gold_keys: list[str] = None, min_score=80):
    if not gold_keys:
        return json_dict
    keys = list(json_dict.keys())
    for key in keys:
        closest_key, score = process.extractOne(key, gold_keys)
        if score == 100:
            continue
        elif score >= min_score:
            json_dict[closest_key] = json_dict[key]
            del json_dict[key]
    return json_dict
