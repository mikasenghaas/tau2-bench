from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.helpdesk.data_model import HelpdeskDB
from tau2.domains.helpdesk.tools import HelpdeskTools
from tau2.domains.helpdesk.user_data_model import HelpdeskUserDB
from tau2.domains.helpdesk.user_tools import HelpdeskUserTools
from tau2.domains.helpdesk.utils import (
    HELPDESK_DB_PATH,
    HELPDESK_POLICY_PATH,
    HELPDESK_TASK_SET_PATH,
    HELPDESK_USER_DB_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


class HelpdeskEnvironment(Environment):
    tools: HelpdeskTools
    user_tools: HelpdeskUserTools

    def __init__(
        self,
        domain_name: str,
        policy: str,
        tools: HelpdeskTools,
        user_tools: HelpdeskUserTools,
    ):
        super().__init__(domain_name, policy, tools, user_tools)

    def sync_tools(self):
        """Sync agent-side state with user-side state.

        If the agent unlocks the account, reflect that on the user side.
        If the agent resets the password, clear the password_expired flag.
        """
        if self.user_tools.db.surroundings.employee_id is None:
            return
        emp_id = self.user_tools.db.surroundings.employee_id
        if emp_id not in self.tools.db.employees:
            return

        emp = self.tools.db.employees[emp_id]

        # Sync account lock status
        self.user_tools.db.surroundings.account_locked = emp.account_status == "locked"

        # If password was recently reset, clear the expired flag
        if emp.last_password_reset == "2025-10-15":
            self.user_tools.db.surroundings.password_expired = False


def get_environment(
    db: Optional[HelpdeskDB] = None,
    user_db: Optional[HelpdeskUserDB] = None,
    solo_mode: bool = False,
) -> HelpdeskEnvironment:
    if db is None:
        db = HelpdeskDB.load(HELPDESK_DB_PATH)
    tools = HelpdeskTools(db)
    if user_db is None:
        user_db = HelpdeskUserDB.load(HELPDESK_USER_DB_PATH)
    user_tools = HelpdeskUserTools(user_db)
    with open(HELPDESK_POLICY_PATH, "r") as fp:
        policy = fp.read()
    env = HelpdeskEnvironment(
        domain_name="helpdesk",
        policy=policy,
        tools=tools,
        user_tools=user_tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    tasks = load_file(HELPDESK_TASK_SET_PATH)
    tasks = [Task.model_validate(task) for task in tasks]
    if task_split_name is None:
        return tasks
    task_splits = get_tasks_split()
    if task_split_name not in task_splits:
        raise ValueError(
            f"Invalid task split name: {task_split_name}. "
            f"Valid splits are: {list(task_splits.keys())}"
        )
    return [task for task in tasks if task.id in task_splits[task_split_name]]


def get_tasks_split() -> dict[str, list[str]]:
    split_file = (
        Path(HELPDESK_TASK_SET_PATH).parent
        / f"split_{Path(HELPDESK_TASK_SET_PATH).stem}.json"
    )
    return load_file(split_file)
