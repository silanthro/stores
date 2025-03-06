import argparse
import asyncio
import json
from typing import Dict

from .get_google_results import get_google_results

TOOLS = [get_google_results]

TOOLS_DICT = {t.__name__: t for t in TOOLS}


def call_tool(
    tool_name: str,
    kwargs: Dict,
):
    print(f"Calling {tool_name} with kwargs {kwargs}")

    tool = TOOLS_DICT[tool_name]

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(tool(**kwargs))
    print(f"<RESULT>{json.dumps(result)}</RESULT>")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--tool_name", type=str, required=True)
    parser.add_argument("-a", "--kwargs", type=str, required=True)

    args = parser.parse_args()

    call_tool(args.tool_name, json.loads(args.kwargs))
