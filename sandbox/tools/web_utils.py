import re

from bs4 import BeautifulSoup
from markdownify import markdownify as md


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
