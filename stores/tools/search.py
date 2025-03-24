import re
from typing import TypedDict

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from litellm import acompletion
from markdownify import markdownify as md

from stores.parsing import llm_parse_json

from .run_subprocess import run_subprocess

load_dotenv()

PARSE_TEXT_PROMPT = """
Instructions:
Retrieve all the Google search results from the text below.
Ignore results that seem like obvious advertisements.
Return your response as a JSON array where each item has keys 'title', 'url', 'description'

Text:
{text}
"""


def parse_google_search(source: str, num_results: int | None = None):
    soup = BeautifulSoup(source, "html.parser")

    result_els = soup.find_all("div", class_="g")

    results = []
    for result_el in result_els[:num_results]:
        imgless_result_el = re.sub(r"<img.*?>", "", str(result_el))
        md_content = md(imgless_result_el).replace("\xa0", " ").strip()
        cleaned_md_content = re.sub(r"\n(\s|\n)*\n", " ", md_content)
        results.append(cleaned_md_content)
    return "\n\n".join(results)


def parse_google_news(source: str, num_results: int = None):
    soup = BeautifulSoup(source, "html.parser")

    result_els = soup.find_all(lambda tag: "data-news-cluster-id" in tag.attrs)

    results = []
    for result_el in result_els[:num_results]:
        imgless_result_el = re.sub(r"<img.*?>", "", str(result_el))
        md_content = md(imgless_result_el).replace("\xa0", " ").strip()
        cleaned_md_content = re.sub(r"\n(\s|\n)*\n", " ", md_content)
        results.append(cleaned_md_content)
    return "\n\n".join(results)


class GoogleResult(TypedDict):
    title: str
    url: str
    description: str


async def google_search(
    query: str, num_results: int = 10, news: bool = False
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
    # batchsize = num_results
    # max_attempts = 5

    source = await run_subprocess(
        f"""docker run \
            --rm \
            greentfrapp/sandbox-2:v0.1.2 '{url}'
        """,
        timeout=120,
    )
    try:
        source = parse_fn(source, num_results=num_results)
    except Exception:
        try:
            source = md(source)
        except Exception:
            pass

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
    return response_results
