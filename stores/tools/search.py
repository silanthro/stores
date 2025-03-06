import json
import logging
import os
import re
from typing import TypedDict

from dotenv import load_dotenv

from stores.parsing import llm_parse_json

from .run_subprocess import run_subprocess

load_dotenv()

logging.basicConfig()
logger = logging.getLogger("get_google_results")
logger.setLevel(logging.INFO)


class GoogleResult(TypedDict):
    title: str
    url: str
    description: str


async def google_search(
    query: str, num_results: int = 10, news=False
) -> list[GoogleResult]:
    """
    Retrieves Google or Google News search results for a query.
    Returns a list with dict of keys 'title', 'url', 'description'
    Args:
        query (str): Query string
        num_results (int): Number of results to return, defaults to 10
        news (bool): If True, searches Google News, defaults to False
    """
    task = {
        "tool_name": "get_google_results",
        "kwargs": json.dumps(
            json.dumps(
                {
                    "query": query,
                    "num_results": num_results,
                    "news": news,
                }
            )
        ),
    }
    result = await run_subprocess(
        f"""docker run \
            -e GEMINI_API_KEY={os.environ["GEMINI_API_KEY"]} \
            --rm \
            greentfrapp/sandbox -t {task["tool_name"]} -a {task["kwargs"]}""",
        timeout=120,
    )
    # logger.info(result["result"])
    pattern = re.compile("<RESULT>(.*?)</RESULT>", flags=re.DOTALL)
    task_result = re.search(pattern, result["result"])
    try:
        parsed_result = llm_parse_json(task_result.group(1))
        return {"results": parsed_result}
    except Exception:
        logger.info(result["result"])
        logger.info(result["error"])
