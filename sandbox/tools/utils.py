from .run_subprocess import run_subprocess


async def xdo(command: str):
    xdotool = "DISPLAY=:1 xdotool"
    return await run_subprocess(f"{xdotool} {command}")
