import asyncio
import json
import logging
import re
from pathlib import Path
from uuid import uuid4

from markdownify import markdownify as md

from .paste_from_clipboard import paste_from_clipboard
from .utils import xdo

logging.basicConfig()
logger = logging.getLogger("get_web_source")
logger.setLevel(logging.INFO)


class PageNotLoadedError(ValueError):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)


def trim_html(source: str):
    title_tags_pattern = re.compile("<title(.*?)>(.*?)</title>", re.DOTALL)
    body_tags_pattern = re.compile("<body(.*?)>(.*?)</body>", re.DOTALL)
    script_tags_pattern = re.compile("<script ?.*?>.*?</script>", re.DOTALL)
    link_tags_pattern = re.compile("<link ?.*?>", re.DOTALL)
    style_tags_pattern = re.compile("<style>.*?</style>", re.DOTALL)
    comments_pattern = re.compile("<!--.*?-->", re.DOTALL)
    images_pattern = re.compile("<img .*?>", re.DOTALL)
    general_tag_pattern = re.compile("<(.*?)>", re.DOTALL)
    allowed_attr = ["href", "src"]
    allowed_attr_pattern = re.compile(f"( ({'|'.join(allowed_attr)})=(\"|').*?(\"|'))")

    # empty_tags_pattern = re.compile("<(div|span|path|svg)></(div|span|path|svg)>", re.DOTALL)

    # NOTE: This might remove important attributes like SVG properties
    def remove_attr(match: re.Match):
        groups = match.groups()
        content = groups[0]
        if " " not in content:
            return f"<{content}>"
        else:
            tag = content.split(" ")[0]
            attr_match = re.findall(allowed_attr_pattern, content)
            attr_match = "".join([a[0] for a in attr_match])
            if len(attr_match):
                return f"<{tag}{attr_match}>"
            else:
                return f"<{tag}>"

    title_match = re.search(title_tags_pattern, source)
    if title_match:
        title = title_match.groups()[1]
    else:
        title = ""

    # Get body
    body_match = re.search(body_tags_pattern, source)
    if body_match:
        source = body_match.group()
    else:
        return f"<body> not found in source: {source[:100]}..."
    source = re.sub(script_tags_pattern, "", source)
    source = re.sub(link_tags_pattern, "", source)
    source = re.sub(comments_pattern, "", source)
    source = re.sub(images_pattern, "", source)
    source = re.sub(general_tag_pattern, remove_attr, source)
    source = re.sub(style_tags_pattern, "", source)

    # length = len(source)
    # while True:
    #     source = re.sub(empty_tags_pattern, "", source)
    #     if len(source) == length:
    #         break
    #     length = len(source)
    # source = re.sub("\s", "", source)
    return f"<html><head><title>{title}</title></head>{source}</html>"


async def get_web_source_helper(
    markdown=True, trim_source=True, copy_string="document.documentElement.outerHTML"
):
    num_attempts = 5
    attempt = 0
    while attempt < num_attempts:
        attempt += 1
        try:
            # Make sure firefox is running
            firefox_check = await xdo(
                'search --onlyvisible --class "firefox-esr" windowactivate windowfocus'
            )
            if firefox_check["exit_code"] != 0:
                return "Firefox is not running - you might have to wait for the app to open"
            # _, app, _ = await xdo("getwindowfocus getwindowname")
            # if "Mozilla Firefox" not in app:
            #     return f"{app} - Firefox is not running"
            await xdo("key ctrl+shift+k")
            await asyncio.sleep(2)  # Wait for console to open
            # Get URL
            await xdo('type "copy(window.location.href);"')
            await xdo("key Return")
            await asyncio.sleep(2.5)  # Wait for copy
            url = await paste_from_clipboard()
            protocol = url.split("://")[0]
            base_url = url[len(protocol) + 3 :].split("/")[0]
            await xdo(f'type "copy({json.dumps(copy_string).strip('"')});"')
            await xdo("key Return")
            await asyncio.sleep(2.5)  # Wait for copy
            source = await paste_from_clipboard()

            if not source:
                raise PageNotLoadedError("Page not loaded")

            if trim_source:
                source = trim_html(source)

            if markdown:
                source = md(source)
                # Trim newlines
                newline_pattern = re.compile("\n(\n|\r)+", re.MULTILINE)
                source = re.sub(newline_pattern, "\n\n", source)
                # Replace double slash with https
                double_slash_pattern = re.compile("\\[(.*?)\\]\\((//.*?)\\)")

                def double_slash_to_https(match: re.Match):
                    groups = match.groups()
                    return f"[{groups[0]}](https:{groups[1]})"

                source = re.sub(double_slash_pattern, double_slash_to_https, source)
                # Convert relative links
                relative_link_pattern = re.compile(
                    "\\[(.*?)\\]\\((([a-zA-Z0-9_/]).*?)\\)"
                )

                def relative_to_absolute(match: re.Match):
                    groups = match.groups()
                    relative_link = groups[1]
                    if relative_link.startswith("https://"):
                        return match.group()
                    if relative_link.startswith("http://"):
                        return match.group()
                    if not relative_link.startswith("/"):
                        relative_link = "/" + relative_link
                    return f"[{groups[0]}]({protocol}://{base_url}{relative_link})"

                source = re.sub(relative_link_pattern, relative_to_absolute, source)
                # Convert bookmarks
                bookmark_link_pattern = re.compile("\\[(.*?)\\]\\((#.*?)\\)")

                def bookmark_to_absolute(match: re.Match):
                    groups = match.groups()
                    return f"[{groups[0]}]({url.split('#')[0]}{groups[1]})"

                source = re.sub(bookmark_link_pattern, bookmark_to_absolute, source)
            break
        except PageNotLoadedError:
            source = "Page not loaded"
            await asyncio.sleep(3)

    return source


async def get_web_source(markdown=True):
    """
    If Firefox is opened and in focus, saves the source of the current website to a temporary file and returns the file name
    Use markdown=True where possible unless specific html info is required.
    Args:
        markdown (bool): Converts the source to markdown, defaults to True
    """
    """
    1. Ctrl-Shift-K to open Console
    2. Run `copy(document.documentElement.outerHTML);`
    3. Return clipboard contents
    """
    source = await get_web_source_helper(markdown=markdown)

    tmp_filename = f"/tmp/outputs/{uuid4()}.txt"
    Path(tmp_filename).parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_filename, "w") as file:
        file.write(source)
    return {
        "output_file": tmp_filename,
    }
