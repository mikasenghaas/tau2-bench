from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.clinic.data_model import ClinicDB
from tau2.domains.clinic.tools import ClinicTools
from tau2.domains.clinic.utils import (
    CLINIC_DB_PATH,
    CLINIC_POLICY_PATH,
    CLINIC_TASK_SET_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


def get_environment(
    db: Optional[ClinicDB] = None, solo_mode: bool = False
) -> Environment:
    if db is None:
        db = ClinicDB.load(CLINIC_DB_PATH)
    tools = ClinicTools(db)
    with open(CLINIC_POLICY_PATH, "r") as fp:
        policy = fp.read()
    env = Environment(
        domain_name="clinic",
        policy=policy,
        tools=tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    tasks = load_file(CLINIC_TASK_SET_PATH)
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
        Path(CLINIC_TASK_SET_PATH).parent
        / f"split_{Path(CLINIC_TASK_SET_PATH).stem}.json"
    )
    return load_file(split_file)
