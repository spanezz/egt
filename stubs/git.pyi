from pathlib import Path
from typing import Generator, Optional

class Author:
    def __init__(self) -> None:
        self.email: str

class Commit:
    def __init__(self) -> None:
        self.authored_date: float
        self.hexsha: str
        self.summary: str
        self.author: Author

class GitConfigParser:
    def get_value(self, section: str, option: str, default: Optional[str] = None) -> str: ...

class Repo:
    def __init__(self, path: str | Path) -> None: ...
    def config_reader(self) -> GitConfigParser: ...
    def iter_commits(self) -> Generator[Commit, None, None]: ...
