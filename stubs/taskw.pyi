class TaskWarrior:
    def __init__(self, marshal: bool = True, **kw): ...

    def filter_tasks(self, filter: dict): ...

    def get_task(self, id: int): ...
