from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.festival.data_model import FestivalDB
from tau2.domains.festival.tools import FestivalTools
from tau2.domains.festival.utils import (
    FESTIVAL_DB_PATH,
    FESTIVAL_POLICY_PATH,
    FESTIVAL_TASK_SET_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


def get_environment(
    db: Optional[FestivalDB] = None, solo_mode: bool = False
) -> Environment:
    if db is None:
        db = FestivalDB.load(FESTIVAL_DB_PATH)
    tools = FestivalTools(db)
    with open(FESTIVAL_POLICY_PATH, "r") as fp:
        policy = fp.read()
    env = Environment(
        domain_name="festival",
        policy=policy,
        tools=tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    tasks = load_file(FESTIVAL_TASK_SET_PATH)
    tasks = [Task.model_validate(task) for task in tasks]
    if task_split_name is None:
        return tasks
    task_splits = get_tasks_split()
    if task_split_name not in task_splits:
        raise ValueError(
            f"Invalid task split name: {task_split_name}. "
            f"Valid splits are: {task_splits.keys()}"
        )
    return [task for task in tasks if task.id in task_splits[task_split_name]]


def get_tasks_split() -> dict[str, list[str]]:
    split_file = (
        Path(FESTIVAL_TASK_SET_PATH).parent
        / f"split_{Path(FESTIVAL_TASK_SET_PATH).stem}.json"
    )
    return load_file(split_file)
