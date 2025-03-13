from typing import TypedDict

import requests
from bs4 import BeautifulSoup
from litellm import acompletion
from markdownify import markdownify as md

from stores.parsing import llm_parse_json

PARSE_TEXT_PROMPT = """
Instructions:
Retrieve all the Reddit search results from the text below.
Ignore results that seem like obvious advertisements.
Also retrieve the URL to the next page in the results if any.
Return your response as in the following format:
{{
    "results": A list where each item has keys 'title', 'comments_url', 'article_url', 'description', 'num_comments', 'num_points'. For 'comments_url', use reddit.com instead of old.reddit.com where relevant.
    "next_page": A string representing the URL to the next page, or null
}}

Text:
{text}
"""


class RedditResult(TypedDict):
    title: str
    comments_url: str
    article_url: str
    description: str
    num_comments: int
    num_points: int


def parse_subreddit(source: str, num_results: int | None = None):
    soup = BeautifulSoup(source, "html.parser")

    post_els = soup.find_all("div", class_="thing")

    posts = []
    for post_el in post_els[:num_results]:
        score_el = post_el.find("div", class_="score unvoted")
        title_el = post_el.find("a", class_="title")
        tagline_el = post_el.find("p", class_="tagline")
        comments_el = post_el.find("a", class_="comments")
        # Ignore promoted posts
        if "promoted by" in str(tagline_el):
            continue
        posts.append(
            md(f"{title_el}{tagline_el}{comments_el}<br/>{score_el} points").replace(
                "\n\n", "\n"
            )
        )
    return "\n\n".join(posts)


def parse_reddit_search(source: str, num_results: int | None = None):
    soup = BeautifulSoup(source, "html.parser")

    container_els = soup.find_all("div", class_="listing")
    container_el = container_els[-1]

    result_els = container_el.find_all("div", class_="search-result")
    posts = []
    for result_el in result_els[:num_results]:
        title_el = result_el.find("a", class_="search-title")
        meta_el = result_el.find("div", class_="search-result-meta")
        link_el = result_el.find("a", class_="search-link")
        posts.append(md(f"{title_el}<br/>{meta_el}<br/>{link_el}"))

    footer = container_el.find("footer")
    posts.append(md(str(footer)))

    return "\n\n".join(posts)


async def search_reddit(
    query: str, subreddit: None | str = None, num_results: int = 10, latest: bool = False
) -> list[RedditResult]:
    """
    Retrieves Reddit search results for a query.
    Returns a list with dict of keys 'title', 'comments_url', 'article_url', 'description', 'num_comments', 'num_points'
    Args:
        query (str): Query string
        subreddit (None|str): Name of subreddit to search, if None, searches entire Reddit, defaults to None
        num_results (int): Number of results to return, defaults to 10
        latest (bool): If True, sorts results by date instead of relevance, defaults to False
    """

    if not query:
        if subreddit is None:
            url = "https://old.reddit.com"
        else:
            url = f"https://old.reddit.com/r/{subreddit.split('/')[-1]}"
        if latest:
            url += "/new"
        parse_fn = parse_subreddit
    else:
        if subreddit is None:
            url = f"https://old.reddit.com/search/?q={query}"
        else:
            url = f"https://old.reddit.com/r/{subreddit.split('/')[-1]}/search/?q={query}&restrict_sr=on"
        if latest:
            url += "&sort=new"
        parse_fn = parse_reddit_search

    # TODO: Rotate user agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    source = parse_fn(response.text, num_results=num_results)
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
        num_retries=1,
        timeout=60,
    )

    response_json = llm_parse_json(response.choices[0].message.content)
    return response_json["results"][:num_results]
