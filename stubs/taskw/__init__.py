from typing import Any, List, Optional, Tuple

class TaskWarrior:
    _marshal: bool
    def __init__(self, marshal: bool = True, **kw: Any) -> None: ...
    def filter_tasks(self, filter: dict): ...
    def get_task(self, **kw: Any) -> Tuple[int, dict[str, Any]]: ...
    def task_add(self, description: str, tags: Optional[List[str]] = None, **kw): ...
    def task_done(self, **kw: Any) -> None: ...
