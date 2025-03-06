def create_file(filepath: str) -> None:
    """
    Create a file at filepath
    Args:
    - filepath (str): Filepath of file to write (required)
    """
    with open(filepath, "w"):
        pass
