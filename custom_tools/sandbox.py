from llm_sandbox import SandboxSession


def run_python_code(code: str) -> str:
    """
    Creates a sandbox to run Python code
    Returns stdout as string
    Args:
    - code (str): Code to run
    """
    with SandboxSession(
        image="python:3.9.21-alpine3.21",
        keep_template=True,
        lang="python",
    ) as session:
        result = session.run(code)
        return result
