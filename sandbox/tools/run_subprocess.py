import asyncio

from pydantic import BaseModel


class RunSubprocessOutput(BaseModel):
    exit_code: int
    result: str
    error: str


async def run_subprocess(
    cmd: str,
    timeout: float | None = 5.0,  # seconds
):
    """
    Run a shell command asynchronously with a timeout
    Args:
    - cmd (str): Command to run (required)
    - timeout (float): Timeout defaults to 5.0 seconds
    """
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    timeout = timeout or 5.0

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return {
            "exit_code": process.returncode or 0,
            "result": stdout.decode(),
            "error": stderr.decode(),
        }
    except asyncio.TimeoutError as exc:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        raise TimeoutError(
            f"Command '{cmd}' timed out after {timeout} seconds"
        ) from exc
