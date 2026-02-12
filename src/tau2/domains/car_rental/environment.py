from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.car_rental.data_model import CarRentalDB
from tau2.domains.car_rental.tools import CarRentalTools
from tau2.domains.car_rental.utils import (
    CAR_RENTAL_DB_PATH,
    CAR_RENTAL_POLICY_PATH,
    CAR_RENTAL_TASK_SET_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


def get_environment(
    db: Optional[CarRentalDB] = None, solo_mode: bool = False
) -> Environment:
    if db is None:
        db = CarRentalDB.load(CAR_RENTAL_DB_PATH)
    tools = CarRentalTools(db)
    with open(CAR_RENTAL_POLICY_PATH, "r") as fp:
        policy = fp.read()
    env = Environment(
        domain_name="car_rental",
        policy=policy,
        tools=tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    tasks = load_file(CAR_RENTAL_TASK_SET_PATH)
    tasks = [Task.model_validate(task) for task in tasks]
    if task_split_name is None:
        return tasks
    task_splits = get_tasks_split()
    if task_split_name not in task_splits:
        raise ValueError(
            f"Invalid task split: {task_split_name}. Valid: {list(task_splits.keys())}"
        )
    return [task for task in tasks if task.id in task_splits[task_split_name]]


def get_tasks_split() -> dict[str, list[str]]:
    split_file = (
        Path(CAR_RENTAL_TASK_SET_PATH).parent
        / f"split_{Path(CAR_RENTAL_TASK_SET_PATH).stem}.json"
    )
    return load_file(split_file)
