from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.library.data_model import LibraryDB
from tau2.domains.library.tools import LibraryTools
from tau2.domains.library.utils import (
    LIBRARY_DB_PATH,
    LIBRARY_POLICY_PATH,
    LIBRARY_TASK_SET_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


def get_environment(
    db: Optional[LibraryDB] = None, solo_mode: bool = False
) -> Environment:
    if db is None:
        db = LibraryDB.load(LIBRARY_DB_PATH)
    tools = LibraryTools(db)
    policy_path = LIBRARY_POLICY_PATH
    with open(policy_path, "r") as fp:
        policy = fp.read()
    env = Environment(
        domain_name="library",
        policy=policy,
        tools=tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    tasks = load_file(LIBRARY_TASK_SET_PATH)
    tasks = [Task.model_validate(task) for task in tasks]
    if task_split_name is None:
        return tasks
    task_splits = get_tasks_split()
    if task_split_name not in task_splits:
        raise ValueError(
            f"Invalid task split name: {task_split_name}. Valid splits are: {task_splits.keys()}"
        )
    return [task for task in tasks if task.id in task_splits[task_split_name]]


def get_tasks_split() -> dict[str, list[str]]:
    split_file = (
        Path(LIBRARY_TASK_SET_PATH).parent / f"split_{Path(LIBRARY_TASK_SET_PATH).stem}.json"
    )
    return load_file(split_file)
