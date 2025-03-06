import asyncio
import logging
from typing import TypedDict

from litellm import acompletion
from markdownify import markdownify as md

from .get_web_source import get_web_source_helper
from .parse_utils import llm_parse_json
from .run_subprocess import run_subprocess
from .utils import xdo
from .web_utils import parse_google_news, parse_google_search

logging.basicConfig()
logger = logging.getLogger("subcontainer_get_google_results")
logger.setLevel(logging.INFO)


class GoogleResult(TypedDict):
    title: str
    url: str
    description: str


PARSE_TEXT_PROMPT = """
Instructions:
Retrieve all the Google search results from the text below.
Ignore results that seem like obvious advertisements.
Return your response as a JSON array where each item has keys 'title', 'url', 'description'

Text:
{text}
"""


async def get_google_results(
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

    url = f"https://google.com/search?q={query}"
    parse_fn = parse_google_search
    if news:
        url += "&tbm=nws"
        parse_fn = parse_google_news
    url += f"&num={num_results}"
    batchsize = num_results
    max_attempts = 5

    await run_subprocess(f"DISPLAY=:1 firefox-esr '{url}' > /dev/null 2>&1 &")

    results = []
    for attempt in range(max_attempts):
        # Wait for Firefox and page to load
        await asyncio.sleep(5)
        source = await get_web_source_helper(markdown=False, trim_source=False)
        try:
            source = parse_fn(source, num_results=num_results)
        except Exception:
            source = md(source)

        response = await acompletion(
            model="gemini/gemini-2.0-flash-001",
            messages=[
                {
                    "role": "user",
                    "content": PARSE_TEXT_PROMPT.format(
                        text=source,
                    ),
                }
            ],
            num_retries=3,
            timeout=60,
        )
        response_results = llm_parse_json(response.choices[0].message.content)
        for result in response_results:
            if result not in results:
                results.append(result)
        if len(results) < num_results:
            # Paginate search results
            new_url = url + f"&start={batchsize * (attempt + 1)}"
            await xdo("key ctrl+l")
            await xdo(f'type "{new_url}"')
            await xdo("key Return")
        else:
            break
    return results[:num_results]
