from .run_subprocess import run_subprocess


async def paste_from_clipboard():
    """
    Return contents from current clipboard
    """
    paste_command = await run_subprocess("DISPLAY=:1 xclip -selection clipboard -o")
    return paste_command["result"][:-1]
