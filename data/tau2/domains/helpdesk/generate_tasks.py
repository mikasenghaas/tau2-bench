#!/usr/bin/env python3
"""Procedurally generate ~200 IT helpdesk domain tasks from db.json.

Standalone script (stdlib only: json, random, pathlib).
Deterministic via random.seed(42).

Uses structured personas and variant generation:
- Easy (a) variants: full info, cooperative persona
- Hard (b) variants: vague info, challenging persona

Usage:
    python generate_tasks.py            # writes tasks.json + split_tasks.json
"""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

SEED = 42
TODAY = "2025-10-15"

DB_PATH = Path(__file__).parent / "db.json"
TASKS_PATH = Path(__file__).parent / "tasks.json"
SPLIT_TASKS_PATH = Path(__file__).parent / "split_tasks.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_db() -> dict:
    with open(DB_PATH) as f:
        return json.load(f)


def emp_name(db: dict, eid: str) -> str:
    return db["employees"][eid]["name"]


def emp_email(db: dict, eid: str) -> str:
    return db["employees"][eid]["email"]


def emp_dept(db: dict, eid: str) -> str:
    return db["employees"][eid]["department"]


def emp_role(db: dict, eid: str) -> str:
    return db["employees"][eid]["role"]


def device_model_name(db: dict, did: str) -> str:
    return db["devices"][did]["model"]


def sw_name_for_license(db: dict, lid: str) -> str:
    return db["software_licenses"][lid]["software_name"]


# ---------------------------------------------------------------------------
# Entity Indexes
# ---------------------------------------------------------------------------


@dataclass
class EntityIndexes:
    # Employees by status
    active_employees: list = field(default_factory=list)
    locked_employees: list = field(default_factory=list)
    disabled_employees: list = field(default_factory=list)

    # MFA states
    active_no_mfa: list = field(default_factory=list)
    active_with_mfa: list = field(default_factory=list)

    # VPN
    active_with_vpn: list = field(default_factory=list)
    active_without_vpn: list = field(default_factory=list)

    # Devices
    devices_valid_warranty: list = field(default_factory=list)
    devices_expired_warranty: list = field(default_factory=list)

    # Software
    standard_software: list = field(default_factory=list)
    non_standard_software: list = field(default_factory=list)
    restricted_software: list = field(default_factory=list)

    # Employees missing specific standard software
    employees_missing_standard_sw: dict = field(default_factory=dict)
    # Employees with specific software (for revoke scenarios)
    employees_with_sw: dict = field(default_factory=dict)

    # Access groups
    standard_groups: list = field(default_factory=list)
    restricted_groups: list = field(default_factory=list)

    # Employees not in specific standard groups
    employees_not_in_group: dict = field(default_factory=dict)
    # Employees in specific groups (for remove scenarios)
    employees_in_group: dict = field(default_factory=dict)

    # Tickets
    open_tickets: list = field(default_factory=list)
    in_progress_tickets: list = field(default_factory=list)

    # Departments
    employees_by_dept: dict = field(default_factory=dict)

    # Locked employees that were locked before (repeat lockout check)
    locked_with_vpn: list = field(default_factory=list)


def build_indexes(db: dict) -> EntityIndexes:
    ix = EntityIndexes()

    # Employees
    for eid, e in db["employees"].items():
        dept = e["department"]
        ix.employees_by_dept.setdefault(dept, []).append(eid)

        if e["account_status"] == "active":
            ix.active_employees.append(eid)
            if e["mfa_enabled"]:
                ix.active_with_mfa.append(eid)
            else:
                ix.active_no_mfa.append(eid)
            if e["vpn_access"]:
                ix.active_with_vpn.append(eid)
            else:
                ix.active_without_vpn.append(eid)
        elif e["account_status"] == "locked":
            ix.locked_employees.append(eid)
            if e["vpn_access"]:
                ix.locked_with_vpn.append(eid)
        elif e["account_status"] == "disabled":
            ix.disabled_employees.append(eid)

    # Devices
    for did, d in db["devices"].items():
        if d["status"] != "active":
            continue
        emp_id = d.get("employee_id")
        if not emp_id or emp_id not in db["employees"]:
            continue
        if db["employees"][emp_id]["account_status"] != "active":
            continue
        if d["warranty_expiry"] >= TODAY:
            ix.devices_valid_warranty.append(did)
        else:
            ix.devices_expired_warranty.append(did)

    # Software catalog
    for sw_key, cat in db["software_catalog"].items():
        if cat["category"] == "standard":
            ix.standard_software.append(sw_key)
        elif cat["category"] == "non_standard":
            ix.non_standard_software.append(sw_key)
        elif cat["category"] == "restricted":
            ix.restricted_software.append(sw_key)

    # For each standard software, find active employees who DON'T have it
    for sw_key in ix.standard_software:
        sw_name_lower = sw_key.lower()
        missing = []
        with_sw = []
        for eid in ix.active_employees:
            e = db["employees"][eid]
            has_it = any(
                db["software_licenses"].get(lid, {}).get("software_name", "").lower()
                == sw_name_lower
                and db["software_licenses"].get(lid, {}).get("status") == "active"
                for lid in e["software_licenses"]
            )
            if has_it:
                with_sw.append(eid)
            else:
                missing.append(eid)
        if missing:
            ix.employees_missing_standard_sw[sw_key] = missing
        if with_sw:
            ix.employees_with_sw[sw_key] = with_sw

    # Access groups
    for gid, g in db["access_groups"].items():
        if g["requires_approval"]:
            ix.restricted_groups.append(gid)
        else:
            ix.standard_groups.append(gid)
            # Employees not in this group
            not_in = [eid for eid in ix.active_employees if eid not in g["members"]]
            if not_in:
                ix.employees_not_in_group[gid] = not_in
            in_group = [eid for eid in ix.active_employees if eid in g["members"]]
            if in_group:
                ix.employees_in_group[gid] = in_group

    # Tickets
    for tid, t in db["tickets"].items():
        if t["status"] == "open":
            ix.open_tickets.append(tid)
        elif t["status"] == "in_progress":
            ix.in_progress_tickets.append(tid)

    # Filter out employees with duplicate names
    name_counts: dict[str, list[str]] = {}
    for eid, e in db["employees"].items():
        name_counts.setdefault(e["name"], []).append(eid)
    ambiguous: set[str] = set()
    for eids in name_counts.values():
        if len(eids) > 1:
            ambiguous.update(eids)

    def remove_ambiguous(ids: list) -> list:
        return [eid for eid in ids if eid not in ambiguous]

    ix.active_employees = remove_ambiguous(ix.active_employees)
    ix.locked_employees = remove_ambiguous(ix.locked_employees)
    ix.disabled_employees = remove_ambiguous(ix.disabled_employees)
    ix.active_no_mfa = remove_ambiguous(ix.active_no_mfa)
    ix.active_with_mfa = remove_ambiguous(ix.active_with_mfa)
    ix.active_with_vpn = remove_ambiguous(ix.active_with_vpn)
    ix.active_without_vpn = remove_ambiguous(ix.active_without_vpn)
    ix.locked_with_vpn = remove_ambiguous(ix.locked_with_vpn)

    for key in list(ix.employees_missing_standard_sw):
        ix.employees_missing_standard_sw[key] = remove_ambiguous(
            ix.employees_missing_standard_sw[key]
        )
    for key in list(ix.employees_with_sw):
        ix.employees_with_sw[key] = remove_ambiguous(ix.employees_with_sw[key])
    for key in list(ix.employees_not_in_group):
        ix.employees_not_in_group[key] = remove_ambiguous(
            ix.employees_not_in_group[key]
        )
    for key in list(ix.employees_in_group):
        ix.employees_in_group[key] = remove_ambiguous(ix.employees_in_group[key])

    return ix


# ---------------------------------------------------------------------------
# Persona System
# ---------------------------------------------------------------------------


@dataclass
class Persona:
    label: str
    instructions: str
    auth: str  # "name", "email", "id"
    difficulty: str  # "easy", "medium", "hard"


EASY_PERSONAS = [
    Persona(
        "Friendly and direct employee",
        "Provide all requested information promptly. Be cooperative and concise. "
        "If asked, give your employee ID and department right away.",
        "name",
        "easy",
    ),
    Persona(
        "Prepared employee with details ready",
        "You have your employee ID and department ready. Provide specifics clearly.",
        "email",
        "easy",
    ),
]

MEDIUM_PERSONAS = [
    Persona(
        "Busy professional, brief answers",
        "You have limited time. Give short answers. Omit details unless asked.",
        "name",
        "medium",
    ),
    Persona(
        "Casual, provides info gradually",
        "Don't volunteer all information at once. Wait for the agent to ask "
        "before providing details like your employee ID or department.",
        "name",
        "medium",
    ),
    Persona(
        "Slightly confused new hire",
        "You are relatively new and not sure about processes. You may not know "
        "exact terminology. Ask clarifying questions occasionally.",
        "email",
        "medium",
    ),
]

HARD_PERSONAS = [
    Persona(
        "Frustrated employee who can't work",
        "You are frustrated because you cannot do your job. Vent about the "
        "impact before giving details. Be curt. The agent may need to ask "
        "clarifying questions multiple times.",
        "name",
        "hard",
    ),
    Persona(
        "Vague and uncertain",
        "You don't remember exact details. Use approximate descriptions like "
        "'my laptop' instead of device IDs, 'that project tool' instead of "
        "'Jira'. You're not sure about your employee ID.",
        "name",
        "hard",
    ),
    Persona(
        "Non-technical manager",
        "You are not tech-savvy. You confuse terms (say 'password expired' "
        "when your account is locked, or 'the internet' when you mean VPN). "
        "You need patient guidance through each step.",
        "name",
        "hard",
    ),
    Persona(
        "Impatient executive",
        "You are a senior executive with very little patience. You expect "
        "immediate resolution and may push back on policies. You don't want "
        "to provide verification details and find the process frustrating.",
        "name",
        "hard",
    ),
    Persona(
        "Remote worker in a rush",
        "You are working remotely and have a deadline. You need this fixed "
        "NOW. You jump between describing symptoms without clearly stating "
        "the problem. You provide extra irrelevant details about your setup.",
        "email",
        "hard",
    ),
]

ALL_EASY_MEDIUM = EASY_PERSONAS + MEDIUM_PERSONAS


def pick_easy_persona() -> Persona:
    return random.choice(ALL_EASY_MEDIUM)


def pick_hard_persona() -> Persona:
    return random.choice(HARD_PERSONAS)


# ---------------------------------------------------------------------------
# Entity tracking & task builder
# ---------------------------------------------------------------------------

_entity_usage: dict[str, int] = {}


def track_use(entity_id: str) -> None:
    _entity_usage[entity_id] = _entity_usage.get(entity_id, 0) + 1


def sort_by_usage(ids: list[str]) -> list[str]:
    return sorted(ids, key=lambda x: _entity_usage.get(x, 0))


def sample_diverse(ids: list[str], n: int) -> list[str]:
    ordered = sort_by_usage(list(ids))
    chosen = ordered[:n]
    for c in chosen:
        track_use(c)
    return chosen


def make_task(
    task_id: str,
    purpose: str,
    relevant_policies: str,
    notes: str,
    persona: str,
    task_instructions: str,
    reason_for_call: str,
    known_info: str,
    unknown_info: str,
    ticket: str,
    actions: list,
    env_assertions: list | None = None,
    nl_assertions: list | None = None,
    reward_basis: list | None = None,
    user_setup: list | None = None,
    user_env_assertions: list | None = None,
    agent_init_data: dict | None = None,
) -> dict:
    if reward_basis is None:
        reward_basis = ["ACTION"]
    t = {
        "id": task_id,
        "description": {
            "purpose": purpose,
            "relevant_policies": relevant_policies,
            "notes": notes,
        },
        "user_scenario": {
            "persona": persona,
            "instructions": {
                "task_instructions": task_instructions,
                "domain": "helpdesk",
                "reason_for_call": reason_for_call,
                "known_info": known_info,
                "unknown_info": unknown_info,
            },
        },
        "ticket": ticket,
        "evaluation_criteria": {
            "actions": actions,
            "env_assertions": env_assertions,
            "nl_assertions": nl_assertions,
            "reward_basis": reward_basis,
        },
    }
    # Build initial_state from user_setup and/or agent_init_data
    if user_setup or agent_init_data:
        init_actions = None
        init_data = None
        if user_setup:
            init_actions = [
                {
                    "env_type": "user",
                    "func_name": a["func_name"],
                    "arguments": a["arguments"],
                }
                for a in user_setup
            ]
        if agent_init_data:
            init_data = {"agent_data": agent_init_data}
        t["initial_state"] = {
            "initialization_data": init_data,
            "initialization_actions": init_actions,
            "message_history": None,
        }
    # Merge user_env_assertions into env_assertions
    if user_env_assertions:
        if t["evaluation_criteria"]["env_assertions"] is None:
            t["evaluation_criteria"]["env_assertions"] = []
        t["evaluation_criteria"]["env_assertions"].extend(user_env_assertions)
    return t


def action(action_id, name, arguments, info, compare_args=None):
    d = {
        "action_id": action_id,
        "name": name,
        "arguments": arguments,
        "info": info,
    }
    if compare_args is not None:
        d["compare_args"] = compare_args
    return d


def env_assert(func_name, arguments):
    return {
        "env_type": "assistant",
        "func_name": func_name,
        "arguments": arguments,
    }


def user_env_assert(func_name, arguments):
    return {
        "env_type": "user",
        "func_name": func_name,
        "arguments": arguments,
    }


def user_setup_action(func_name, arguments):
    return {
        "func_name": func_name,
        "arguments": arguments,
    }


# ---------------------------------------------------------------------------
# Tier 1: Simple Single-Action Tasks
# ---------------------------------------------------------------------------


def gen_password_reset(db, ix, n=6):
    """Password reset for active employees. n bases -> 2n tasks."""
    tasks = []
    eligible = [eid for eid in ix.active_employees]
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        email = emp_email(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        acts = [
            action(
                "reset_1",
                "reset_password",
                {"employee_id": eid},
                f"Reset password for {name}",
                compare_args=["employee_id"],
            )
        ]
        asserts = [
            env_assert(
                "assert_password_reset_date",
                {"employee_id": eid, "expected_date": TODAY},
            )
        ]

        # Variant A: Easy - employee gives ID and department upfront
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"password_reset_{i + 1}a",
                "Test password reset with identity verification",
                "Identity verification (employee ID + department) required before password reset.",
                f"Employee {name} requests password reset.",
                pa.label,
                f"You are {name} from {dept}. You need your password reset. {pa.instructions}",
                "You need to reset your password because you forgot it.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}. Your email is {email}.",
                "You don't know what the temporary password will be.",
                f"Employee {name} ({eid}, {dept}): password reset. "
                f"Agent should verify identity then reset.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard - employee doesn't volunteer ID/dept
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"password_reset_{i + 1}b",
                "Test password reset with difficult persona",
                "Identity verification (employee ID + department) required before password reset.",
                f"Employee {name} requests password reset with limited info.",
                pb.label,
                f"You are {name}. You need your password reset. {pb.instructions}",
                "You can't log in and need a password reset.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know the process. Only give your ID and department if asked.",
                f"Employee {name}: password reset. Agent must extract identity info and verify.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_unlock_account(db, ix, n=5):
    """Unlock locked accounts. n bases -> 2n tasks."""
    tasks = []
    locked = list(ix.locked_employees)
    random.shuffle(locked)

    for i, eid in enumerate(locked[:n]):
        name = emp_name(db, eid)
        email = emp_email(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        acts = [
            action(
                "unlock_1",
                "unlock_account",
                {"employee_id": eid},
                f"Unlock account for {name}",
                compare_args=["employee_id"],
            )
        ]
        asserts = [
            env_assert(
                "assert_account_status",
                {"employee_id": eid, "expected_status": "active"},
            )
        ]
        user_asserts = [
            user_env_assert(
                "assert_account_locked",
                {"expected": False},
            )
        ]
        setup = [
            user_setup_action(
                "set_employee_info", {"name": name, "email": email, "employee_id": eid}
            ),
            user_setup_action("lock_account", {}),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"unlock_account_{i + 1}a",
                "Test account unlock with identity verification",
                "Verify identity before unlocking. If re-locked within 24h, escalate.",
                f"Employee {name}: account is locked after failed login attempts.",
                pa.label,
                f"You are {name} from {dept}. Your account is locked. {pa.instructions}",
                "You can't log in. You think you typed your password wrong too many times.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know if there's an underlying security issue.",
                f"Employee {name} ({eid}): locked account. Agent should verify and unlock.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
                user_env_assertions=user_asserts,
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"unlock_account_{i + 1}b",
                "Test account unlock with difficult persona",
                "Verify identity before unlocking. If re-locked within 24h, escalate.",
                f"Employee {name}: locked account, difficult interaction.",
                pb.label,
                f"You are {name}. You can't access anything. {pb.instructions}",
                "Your computer won't let you log in to anything.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't realize your account is locked. Only give ID and dept if asked.",
                f"Employee {name}: locked account. Agent must diagnose and unlock.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
                user_env_assertions=user_asserts,
            )
        )
    return tasks


def gen_enable_mfa(db, ix, n=5):
    """Enable MFA for active employees without it. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.active_no_mfa)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        acts = [
            action(
                "mfa_1",
                "enable_mfa",
                {"employee_id": eid},
                f"Enable MFA for {name}",
                compare_args=["employee_id"],
            )
        ]
        asserts = [
            env_assert(
                "assert_mfa_enabled",
                {"employee_id": eid, "expected": True},
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"enable_mfa_{i + 1}a",
                "Test enabling MFA for an employee",
                "MFA can be enabled for any active account.",
                f"Employee {name} requests MFA setup.",
                pa.label,
                f"You are {name} from {dept}. You want to enable MFA. {pa.instructions}",
                "You want to set up multi-factor authentication on your account.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You haven't set up MFA before.",
                f"Employee {name}: enable MFA. Agent should verify identity and enable.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"enable_mfa_{i + 1}b",
                "Test MFA enablement with unclear request",
                "MFA can be enabled for any active account.",
                f"Employee {name} wants extra security, doesn't say 'MFA'.",
                pb.label,
                f"You are {name}. You want more security on your account. {pb.instructions}",
                "You heard you should add extra security to your account but don't know the exact term.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know what MFA is or how it works. Only provide ID/dept if asked.",
                f"Employee {name}: wants MFA. Agent should identify this as MFA request and enable.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_grant_standard_software(db, ix, n=6):
    """Grant standard software license. n bases -> 2n tasks."""
    tasks = []
    combos = []
    for sw_key in ix.standard_software:
        missing = ix.employees_missing_standard_sw.get(sw_key, [])
        for eid in missing:
            combos.append((sw_key, eid))
    random.shuffle(combos)

    used_employees = set()
    selected = []
    for sw_key, eid in combos:
        if eid not in used_employees and len(selected) < n:
            selected.append((sw_key, eid))
            used_employees.add(eid)

    for i, (sw_key, eid) in enumerate(selected):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        acts = [
            action(
                "grant_1",
                "grant_software_license",
                {"employee_id": eid, "software_name": sw_key},
                f"Grant {sw_key} license to {name}",
                compare_args=["employee_id", "software_name"],
            )
        ]
        asserts = [
            env_assert(
                "assert_has_software_license",
                {"employee_id": eid, "software_name": sw_key, "expected": True},
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"grant_standard_sw_{i + 1}a",
                f"Test granting standard software ({sw_key})",
                "Standard software can be granted immediately without approval.",
                f"Employee {name} needs {sw_key} license.",
                pa.label,
                f"You are {name} from {dept}. You need access to {sw_key}. {pa.instructions}",
                f"You need a license for {sw_key} for your work.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know the software licensing process.",
                f"Employee {name}: grant {sw_key}. Standard software, grant immediately.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"grant_standard_sw_{i + 1}b",
                f"Test granting standard software with vague request",
                "Standard software can be granted immediately without approval.",
                f"Employee {name} vaguely asks for a tool that is {sw_key}.",
                pb.label,
                f"You are {name}. You need a tool for your work. {pb.instructions}",
                f"You need access to {sw_key} but may describe it vaguely.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You're not sure of the exact software name. Only give ID/dept if asked.",
                f"Employee {name}: wants {sw_key}. Agent should identify and grant.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Tier 2: Information & Lookup Tasks
# ---------------------------------------------------------------------------


def gen_check_ticket_status(db, ix, n=4):
    """Employee asks about their ticket status. Single variant."""
    tasks = []
    tickets = list(ix.open_tickets + ix.in_progress_tickets)
    random.shuffle(tickets)

    for i, tid in enumerate(tickets[:n]):
        ticket = db["tickets"][tid]
        eid = ticket["employee_id"]
        if eid not in db["employees"]:
            continue
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"check_ticket_{i + 1}",
                "Test ticket status inquiry",
                "Employees can inquire about their ticket status.",
                f"Employee {name} asks about ticket {tid}.",
                pa.label,
                f"You are {name} from {dept}. You want to check on a support ticket. {pa.instructions}",
                "You submitted a ticket earlier and want to know the status.",
                f"Your name is {name}. Your ticket number is {tid}. "
                f"Your department is {dept}.",
                "You don't know the current status.",
                f"Employee {name}: check ticket {tid}. Agent should look it up.",
                [],
                nl_assertions=[
                    f"The agent provided the status of ticket {tid}",
                    f"The agent mentioned the ticket status is '{ticket['status']}'",
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_list_software(db, ix, n=3):
    """Employee asks what software they have. Single variant."""
    tasks = []
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        e = db["employees"][eid]
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        sw_names = []
        for lid in e["software_licenses"]:
            if lid in db["software_licenses"]:
                lic = db["software_licenses"][lid]
                if lic["status"] == "active":
                    sw_names.append(lic["software_name"])
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"list_software_{i + 1}",
                "Test listing employee's software licenses",
                "Agents can look up employee software licenses.",
                f"Employee {name} asks about their installed software.",
                pa.label,
                f"You are {name} from {dept}. You want to know what software you have. {pa.instructions}",
                "You want to know what software licenses are assigned to you.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't remember which licenses you have.",
                f"Employee {name}: list software. Agent should look up and report.",
                [],
                nl_assertions=[
                    f"The agent listed or described the software licenses for {name}"
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_check_device_info(db, ix, n=3):
    """Employee asks about their device details. Single variant."""
    tasks = []
    eligible = [
        eid for eid in ix.active_employees if db["employees"][eid]["device_ids"]
    ]
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"check_device_{i + 1}",
                "Test device information lookup",
                "Agents can look up device details for employees.",
                f"Employee {name} asks about their device.",
                pa.label,
                f"You are {name} from {dept}. You want info about your device. {pa.instructions}",
                "You want to know details about your work laptop/device.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know your device ID or warranty status.",
                f"Employee {name}: device info. Agent should look up and provide details.",
                [],
                nl_assertions=[
                    f"The agent provided information about the employee's device"
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_check_access_groups(db, ix, n=3):
    """Employee asks what access groups they belong to. Single variant."""
    tasks = []
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"check_access_groups_{i + 1}",
                "Test listing employee's access groups",
                "Agents can look up employee access group memberships.",
                f"Employee {name} asks about their access groups.",
                pa.label,
                f"You are {name} from {dept}. You want to check your access groups. {pa.instructions}",
                "You want to know what access groups you belong to.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You're not sure which groups you're in.",
                f"Employee {name}: check access groups. Agent should list memberships.",
                [],
                nl_assertions=[f"The agent listed the access groups for {name}"],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Tier 3: Moderate Multi-Step Tasks
# ---------------------------------------------------------------------------


def gen_unlock_and_reset_password(db, ix, n=4):
    """Unlock account + reset password. n bases -> 2n tasks."""
    tasks = []
    locked = list(ix.locked_employees)
    random.shuffle(locked)

    for i, eid in enumerate(locked[:n]):
        name = emp_name(db, eid)
        email = emp_email(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        acts = [
            action(
                "unlock_1",
                "unlock_account",
                {"employee_id": eid},
                f"Unlock account for {name}",
                compare_args=["employee_id"],
            ),
            action(
                "reset_1",
                "reset_password",
                {"employee_id": eid},
                f"Reset password for {name}",
                compare_args=["employee_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_account_status",
                {"employee_id": eid, "expected_status": "active"},
            ),
            env_assert(
                "assert_password_reset_date",
                {"employee_id": eid, "expected_date": TODAY},
            ),
        ]
        user_asserts = [
            user_env_assert("assert_account_locked", {"expected": False}),
        ]
        setup = [
            user_setup_action(
                "set_employee_info", {"name": name, "email": email, "employee_id": eid}
            ),
            user_setup_action("lock_account", {}),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"unlock_reset_{i + 1}a",
                "Test unlock + password reset (multi-step)",
                "Verify identity. Unlock first, then reset password.",
                f"Employee {name}: locked account, also needs password reset.",
                pa.label,
                f"You are {name} from {dept}. Your account is locked and you "
                f"also need a password reset. {pa.instructions}",
                "Your account is locked and you've forgotten your password.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know the order of operations needed.",
                f"Employee {name}: unlock + reset. Agent should do both.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
                user_env_assertions=user_asserts,
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"unlock_reset_{i + 1}b",
                "Test unlock + reset with difficult persona",
                "Verify identity. Unlock first, then reset password.",
                f"Employee {name}: locked + forgot password, hard interaction.",
                pb.label,
                f"You are {name}. You can't get into any of your accounts. {pb.instructions}",
                "Nothing is working. You can't log in to anything.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't realize the account is locked vs password issue. "
                "Only provide ID/dept if asked.",
                f"Employee {name}: locked + reset. Agent must diagnose both issues.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
                user_env_assertions=user_asserts,
            )
        )
    return tasks


def gen_add_to_access_group(db, ix, n=5):
    """Add employee to standard access group. n bases -> 2n tasks."""
    tasks = []
    combos = []
    for gid in ix.standard_groups:
        not_in = ix.employees_not_in_group.get(gid, [])
        for eid in not_in:
            combos.append((gid, eid))
    random.shuffle(combos)

    used_employees = set()
    selected = []
    for gid, eid in combos:
        if eid not in used_employees and len(selected) < n:
            selected.append((gid, eid))
            used_employees.add(eid)

    for i, (gid, eid) in enumerate(selected):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        group = db["access_groups"][gid]
        group_name = group["name"]
        track_use(eid)

        acts = [
            action(
                "add_group_1",
                "add_to_access_group",
                {"employee_id": eid, "group_id": gid},
                f"Add {name} to {group_name}",
                compare_args=["employee_id", "group_id"],
            )
        ]
        asserts = [
            env_assert(
                "assert_in_access_group",
                {"employee_id": eid, "group_id": gid, "expected": True},
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"add_access_group_{i + 1}a",
                f"Test adding employee to {group_name}",
                "Standard access groups can be granted directly after verification.",
                f"Employee {name} needs access to {group_name}.",
                pa.label,
                f"You are {name} from {dept}. You need access to {group_name}. {pa.instructions}",
                f"You need to be added to the {group_name} group.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know which specific group ID to ask for.",
                f"Employee {name}: add to {group_name}. Standard group, grant directly.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"add_access_group_{i + 1}b",
                f"Test access group addition with vague request",
                "Standard access groups can be granted directly after verification.",
                f"Employee {name} vaguely requests tool access ({group_name}).",
                pb.label,
                f"You are {name}. You need access to something for work. {pb.instructions}",
                f"You need to use {group_name.split()[0]} but don't have access.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know the group name. Only provide ID/dept if asked.",
                f"Employee {name}: needs {group_name}. Agent should identify group and add.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_password_reset_with_mfa(db, ix, n=4):
    """Reset password and recommend/enable MFA. n bases -> 2n tasks."""
    tasks = []
    eligible = [eid for eid in ix.active_no_mfa]
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        acts = [
            action(
                "reset_1",
                "reset_password",
                {"employee_id": eid},
                f"Reset password for {name}",
                compare_args=["employee_id"],
            ),
            action(
                "mfa_1",
                "enable_mfa",
                {"employee_id": eid},
                f"Enable MFA for {name}",
                compare_args=["employee_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_password_reset_date",
                {"employee_id": eid, "expected_date": TODAY},
            ),
            env_assert(
                "assert_mfa_enabled",
                {"employee_id": eid, "expected": True},
            ),
        ]

        # Variant A: Easy - asks for both
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"reset_mfa_{i + 1}a",
                "Test password reset + MFA enable",
                "After reset, recommend MFA. Enable if employee agrees.",
                f"Employee {name} wants password reset and MFA.",
                pa.label,
                f"You are {name} from {dept}. You need a password reset and also "
                f"want to enable MFA. {pa.instructions}",
                "You need to reset your password and also set up two-factor authentication.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know the MFA setup process.",
                f"Employee {name}: reset password + enable MFA. Agent should do both.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard - only asks for reset, agent should recommend MFA
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"reset_mfa_{i + 1}b",
                "Test password reset where agent should recommend MFA",
                "After reset, recommend MFA if not enabled.",
                f"Employee {name} only asks for reset; agent should suggest MFA.",
                pb.label,
                f"You are {name}. You need a password reset. {pb.instructions} "
                "If the agent recommends enabling MFA, agree to it.",
                "You need to reset your password.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know what MFA is but will agree if recommended. "
                "Only provide ID/dept if asked.",
                f"Employee {name}: reset password. Agent should also recommend and enable MFA.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_device_replacement_valid_warranty(db, ix, n=4):
    """Device replacement with valid warranty. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.devices_valid_warranty)
    random.shuffle(eligible)

    for i, did in enumerate(eligible[:n]):
        device = db["devices"][did]
        eid = device["employee_id"]
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        model = device["model"]
        track_use(eid)

        acts = [
            action(
                "replace_1",
                "request_device_replacement",
                {"device_id": did, "reason": f"Device {model} is malfunctioning"},
                f"Replace device {did} for {name}",
                compare_args=["device_id"],
            )
        ]
        asserts = [
            env_assert(
                "assert_device_status",
                {"device_id": did, "expected_status": "repair"},
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"device_replace_{i + 1}a",
                "Test device replacement (valid warranty)",
                "Device replacement available if warranty active. Takes 3-5 business days.",
                f"Employee {name}: {model} is malfunctioning, warranty valid.",
                pa.label,
                f"You are {name} from {dept}. Your laptop is not working properly. {pa.instructions}",
                f"Your {model} keeps crashing and you need a replacement.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}. Your device is a {model}.",
                "You don't know your device ID or warranty status.",
                f"Employee {name}: replace {model} ({did}). Warranty valid, process replacement.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"device_replace_{i + 1}b",
                "Test device replacement with frustrated employee",
                "Device replacement available if warranty active. Takes 3-5 business days.",
                f"Employee {name}: device issues, frustrated.",
                pb.label,
                f"You are {name}. Your laptop is broken. {pb.instructions}",
                "Your laptop keeps crashing and freezing. You can't work.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know your device ID. Only provide ID/dept if asked.",
                f"Employee {name}: device replacement. Agent should find device and process.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_create_ticket(db, ix, n=4):
    """Create a support ticket for an issue. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    ticket_scenarios = [
        ("software", "medium", "Application crashes when opening large files"),
        ("network", "high", "Cannot connect to internal servers"),
        ("hardware", "low", "Keyboard keys are sticky"),
        ("account", "medium", "Need access to additional system"),
        ("software", "high", "Critical build tool not responding"),
        ("network", "medium", "Slow network performance"),
    ]

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)
        category, priority, desc = ticket_scenarios[i % len(ticket_scenarios)]

        acts = [
            action(
                "ticket_1",
                "create_ticket",
                {
                    "employee_id": eid,
                    "category": category,
                    "priority": priority,
                    "description": desc,
                },
                f"Create {priority} {category} ticket for {name}",
                compare_args=["employee_id", "category"],
            )
        ]
        asserts = [
            env_assert(
                "assert_ticket_exists_for_employee",
                {"employee_id": eid, "category": category},
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"create_ticket_{i + 1}a",
                f"Test creating a {category} ticket",
                "Create tickets for issues that can't be resolved directly.",
                f"Employee {name}: needs a {category} ticket.",
                pa.label,
                f"You are {name} from {dept}. You have an issue. {pa.instructions}",
                f"{desc}. Can you create a ticket for this?",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You're not sure what priority to assign.",
                f"Employee {name}: create {priority} {category} ticket. Agent should create ticket.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"create_ticket_{i + 1}b",
                f"Test ticket creation with vague complaint",
                "Create tickets for issues. Agent determines category and priority.",
                f"Employee {name}: vague complaint needing ticket.",
                pb.label,
                f"You are {name}. Something isn't working right. {pb.instructions}",
                f"Something is wrong. {desc.split('.')[0]}.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know what category or priority to use. Only provide ID/dept if asked.",
                f"Employee {name}: agent should diagnose and create {category} ticket.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Tier 4: Complex Multi-Step / User-Tool Tasks
# ---------------------------------------------------------------------------


def gen_vpn_troubleshooting(db, ix, n=4):
    """VPN troubleshooting with user tools. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.active_with_vpn)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        email = emp_email(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        # User should check internet, reconnect VPN
        user_asserts = [
            user_env_assert("assert_vpn_connected", {"expected": True}),
        ]
        info_setup = user_setup_action(
            "set_employee_info", {"name": name, "email": email, "employee_id": eid}
        )

        # Variant A: Easy - basic VPN reconnect
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"vpn_troubleshoot_{i + 1}a",
                "Test VPN troubleshooting workflow",
                "VPN troubleshooting: check internet, try reconnect, escalate if persistent.",
                f"Employee {name}: VPN disconnected, basic reconnect needed.",
                pa.label,
                f"You are {name} from {dept}. Your VPN isn't connecting. {pa.instructions} "
                "When asked, check your internet and try reconnecting.",
                "Your VPN stopped working and you can't access internal resources.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You haven't tried anything yet.",
                f"Employee {name}: VPN issue. Agent should walk through troubleshooting steps.",
                [],
                nl_assertions=[
                    "The agent asked the employee to check their internet connection",
                    "The agent asked the employee to try reconnecting the VPN",
                ],
                reward_basis=["NL_ASSERTION"],
                user_setup=[
                    info_setup,
                    user_setup_action("break_vpn", {"error": "Connection timed out"}),
                ],
                user_env_assertions=user_asserts,
            )
        )

        # Variant B: Hard - certificate error, needs escalation
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"vpn_troubleshoot_{i + 1}b",
                "Test VPN troubleshooting with certificate error (escalation needed)",
                "Certificate/firewall VPN errors require escalation to network team.",
                f"Employee {name}: VPN certificate error, requires escalation.",
                pb.label,
                f"You are {name}. Your VPN won't connect. {pb.instructions} "
                "When asked, check your internet and try reconnecting. "
                "Report any errors you see.",
                "Your VPN shows some error when you try to connect.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't understand the error message. Only provide ID/dept if asked.",
                f"Employee {name}: VPN cert error. Agent should troubleshoot then escalate.",
                [
                    action(
                        "ticket_1",
                        "create_ticket",
                        {
                            "employee_id": eid,
                            "category": "network",
                            "priority": "high",
                            "description": "VPN certificate error",
                        },
                        f"Create network ticket for {name} VPN cert error",
                        compare_args=["employee_id", "category"],
                    )
                ],
                env_assertions=[
                    env_assert(
                        "assert_ticket_exists_for_employee",
                        {"employee_id": eid, "category": "network"},
                    )
                ],
                nl_assertions=[
                    "The agent asked the employee to check their internet connection",
                    "The agent identified or communicated a certificate error",
                ],
                reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
                user_setup=[
                    info_setup,
                    user_setup_action(
                        "break_vpn", {"error": "VPN certificate has expired"}
                    ),
                ],
            )
        )
    return tasks


def gen_unlock_reset_mfa(db, ix, n=3):
    """Unlock + reset + enable MFA triple combo. n bases -> 2n tasks."""
    tasks = []
    locked_no_mfa = [
        eid for eid in ix.locked_employees if not db["employees"][eid]["mfa_enabled"]
    ]
    random.shuffle(locked_no_mfa)

    for i, eid in enumerate(locked_no_mfa[:n]):
        name = emp_name(db, eid)
        email = emp_email(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        acts = [
            action(
                "unlock_1",
                "unlock_account",
                {"employee_id": eid},
                f"Unlock account for {name}",
                compare_args=["employee_id"],
            ),
            action(
                "reset_1",
                "reset_password",
                {"employee_id": eid},
                f"Reset password for {name}",
                compare_args=["employee_id"],
            ),
            action(
                "mfa_1",
                "enable_mfa",
                {"employee_id": eid},
                f"Enable MFA for {name}",
                compare_args=["employee_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_account_status",
                {"employee_id": eid, "expected_status": "active"},
            ),
            env_assert(
                "assert_password_reset_date",
                {"employee_id": eid, "expected_date": TODAY},
            ),
            env_assert(
                "assert_mfa_enabled",
                {"employee_id": eid, "expected": True},
            ),
        ]
        user_asserts = [
            user_env_assert("assert_account_locked", {"expected": False}),
        ]
        setup = [
            user_setup_action(
                "set_employee_info", {"name": name, "email": email, "employee_id": eid}
            ),
            user_setup_action("lock_account", {}),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"unlock_reset_mfa_{i + 1}a",
                "Test unlock + reset + MFA triple action",
                "Unlock, reset password, enable MFA. All require identity verification.",
                f"Employee {name}: locked, forgot password, wants MFA.",
                pa.label,
                f"You are {name} from {dept}. Your account is locked, you forgot your "
                f"password, and you want to enable MFA. {pa.instructions}",
                "Your account is locked, you can't remember your password, and you "
                "want to set up two-factor authentication.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know what order these need to happen in.",
                f"Employee {name}: unlock + reset + MFA. Agent should do all three.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
                user_env_assertions=user_asserts,
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"unlock_reset_mfa_{i + 1}b",
                "Test triple action with difficult persona",
                "Unlock, reset password, enable MFA. All require identity verification.",
                f"Employee {name}: multiple issues, difficult interaction.",
                pb.label,
                f"You are {name}. Nothing works on your computer. {pb.instructions} "
                "If the agent recommends MFA, agree to it.",
                "You can't access anything. Your password doesn't work.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know your account is locked or that MFA exists. "
                "Only give ID/dept if asked.",
                f"Employee {name}: agent must diagnose all 3 issues and fix them.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
                user_env_assertions=user_asserts,
            )
        )
    return tasks


def gen_software_plus_access_group(db, ix, n=4):
    """Grant software + add to matching access group. n bases -> 2n tasks."""
    tasks = []
    # Find combos where employee needs both software and matching group
    sw_to_group = {
        "Jira": "jira_users",
        "Confluence": "confluence_users",
        "Slack Pro": "slack_users",
        "Zoom Business": "zoom_users",
    }
    combos = []
    for sw_key, gid in sw_to_group.items():
        missing_sw = ix.employees_missing_standard_sw.get(sw_key, [])
        not_in_group = set(ix.employees_not_in_group.get(gid, []))
        both = [eid for eid in missing_sw if eid in not_in_group]
        for eid in both:
            combos.append((sw_key, gid, eid))
    random.shuffle(combos)

    used = set()
    selected = []
    for sw_key, gid, eid in combos:
        if eid not in used and len(selected) < n:
            selected.append((sw_key, gid, eid))
            used.add(eid)

    for i, (sw_key, gid, eid) in enumerate(selected):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        group_name = db["access_groups"][gid]["name"]
        track_use(eid)

        acts = [
            action(
                "grant_1",
                "grant_software_license",
                {"employee_id": eid, "software_name": sw_key},
                f"Grant {sw_key} to {name}",
                compare_args=["employee_id", "software_name"],
            ),
            action(
                "add_group_1",
                "add_to_access_group",
                {"employee_id": eid, "group_id": gid},
                f"Add {name} to {group_name}",
                compare_args=["employee_id", "group_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_has_software_license",
                {"employee_id": eid, "software_name": sw_key, "expected": True},
            ),
            env_assert(
                "assert_in_access_group",
                {"employee_id": eid, "group_id": gid, "expected": True},
            ),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"sw_plus_group_{i + 1}a",
                f"Test granting {sw_key} + adding to {group_name}",
                "Standard software and groups can be granted directly.",
                f"Employee {name}: needs {sw_key} and {group_name}.",
                pa.label,
                f"You are {name} from {dept}. You need {sw_key} and the "
                f"corresponding access group. {pa.instructions}",
                f"You need both a {sw_key} license and access to the {group_name} group.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know the group ID.",
                f"Employee {name}: grant {sw_key} + add to {group_name}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"sw_plus_group_{i + 1}b",
                f"Test software + group with vague request",
                "Standard software and groups can be granted directly.",
                f"Employee {name}: vaguely wants to use {sw_key}.",
                pb.label,
                f"You are {name}. You need to start using {sw_key} for your work. {pb.instructions}",
                f"You need to use {sw_key} but can't access it.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know you need both a license and group membership. "
                "Only provide ID/dept if asked.",
                f"Employee {name}: agent should grant {sw_key} + add to {group_name}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_login_troubleshooting(db, ix, n=3):
    """Employee can't log in — agent must diagnose using user tools. n -> 2n."""
    tasks = []
    # Pick active employees whose accounts we'll lock via initialization
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        email = emp_email(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        acts = [
            action(
                "unlock_1",
                "unlock_account",
                {"employee_id": eid},
                f"Unlock account for {name}",
                compare_args=["employee_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_account_status",
                {"employee_id": eid, "expected_status": "active"},
            ),
        ]
        user_asserts = [
            user_env_assert("assert_account_locked", {"expected": False}),
            user_env_assert(
                "assert_service_accessible", {"service": "email", "expected": True}
            ),
        ]

        # Agent-side: lock the employee's account in the agent DB
        agent_data = {"employees": {eid: {"account_status": "locked"}}}
        # User-side: set employee identity + block email service
        setup = [
            user_setup_action(
                "set_employee_info", {"name": name, "email": email, "employee_id": eid}
            ),
            user_setup_action(
                "block_service", {"service": "email", "status": "account_locked"}
            ),
        ]

        # Variant A: Easy - tells agent their account is locked
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"login_troubleshoot_{i + 1}a",
                "Test login troubleshooting (account locked)",
                "Verify identity. Check account status. Unlock if locked.",
                f"Employee {name}: can't log in, account is locked.",
                pa.label,
                f"You are {name} from {dept}. You can't log in to email. {pa.instructions} "
                "If asked, try logging in and report the result.",
                "You can't log in to your email. You think your account might be locked.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know for sure if it's locked or something else.",
                f"Employee {name}: locked account causing login failure. Agent should unlock.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
                user_env_assertions=user_asserts,
                agent_init_data=agent_data,
            )
        )

        # Variant B: Hard - just says "nothing works"
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"login_troubleshoot_{i + 1}b",
                "Test login troubleshooting with vague symptoms",
                "Diagnose login issues. Check account status.",
                f"Employee {name}: vague 'nothing works' complaint.",
                pb.label,
                f"You are {name}. Nothing is working on your computer. {pb.instructions} "
                "If asked, try logging in and report the result.",
                "Nothing works. You can't access anything.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know what's wrong. Only provide ID/dept if specifically asked.",
                f"Employee {name}: locked account. Agent must diagnose from vague symptoms.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
                user_env_assertions=user_asserts,
                agent_init_data=agent_data,
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Tier 5: Edge Cases & Policy Enforcement
# ---------------------------------------------------------------------------


def gen_password_reset_disabled_account(db, ix, n=3):
    """Password reset for disabled account — should fail and direct to HR. Single variant."""
    tasks = []
    disabled = list(ix.disabled_employees)
    random.shuffle(disabled)

    for i, eid in enumerate(disabled[:n]):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"reset_disabled_{i + 1}",
                "Test password reset for disabled account",
                "Cannot reset password for disabled accounts — direct to HR.",
                f"Employee {name}: disabled account, requests password reset.",
                pa.label,
                f"You are {name} from {dept}. You need a password reset. {pa.instructions}",
                "You need to reset your password. You haven't used your account in a while.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know your account is disabled.",
                f"Employee {name}: disabled account. Agent should explain and direct to HR.",
                [],
                nl_assertions=[
                    "The agent informed the employee that their account is disabled",
                    "The agent directed the employee to contact HR",
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_non_standard_software_request(db, ix, n=3):
    """Non-standard software request — requires manager approval. n -> 2n tasks."""
    tasks = []
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        sw_key = ix.non_standard_software[i % len(ix.non_standard_software)]
        track_use(eid)

        # Agent should create a ticket and explain the approval process
        acts = [
            action(
                "ticket_1",
                "create_ticket",
                {
                    "employee_id": eid,
                    "category": "software",
                    "priority": "medium",
                    "description": f"Request for {sw_key} (non-standard, requires manager approval)",
                },
                f"Create ticket for {sw_key} request from {name}",
                compare_args=["employee_id", "category"],
            )
        ]
        asserts = [
            env_assert(
                "assert_ticket_exists_for_employee",
                {"employee_id": eid, "category": "software"},
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"non_standard_sw_{i + 1}a",
                f"Test non-standard software request ({sw_key})",
                "Non-standard software requires manager approval. Create ticket.",
                f"Employee {name} requests {sw_key} (non-standard).",
                pa.label,
                f"You are {name} from {dept}. You need {sw_key}. {pa.instructions}",
                f"You need a license for {sw_key} for a project.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know the approval process.",
                f"Employee {name}: wants {sw_key}. Agent should explain approval and create ticket.",
                acts,
                asserts,
                nl_assertions=[
                    f"The agent informed the employee that {sw_key} requires manager approval",
                ],
                reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"non_standard_sw_{i + 1}b",
                f"Test non-standard software with push-back",
                "Non-standard software requires manager approval. Cannot grant directly.",
                f"Employee {name} insists on getting {sw_key} immediately.",
                pb.label,
                f"You are {name}. You urgently need {sw_key}. {pb.instructions} "
                "If told it requires approval, express frustration but accept.",
                f"You need {sw_key} right now. A deadline is approaching.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know the approval process. Only provide ID/dept if asked.",
                f"Employee {name}: wants {sw_key}. Agent must enforce policy despite pressure.",
                acts,
                asserts,
                nl_assertions=[
                    f"The agent explained that {sw_key} requires manager approval",
                ],
                reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_restricted_software_request(db, ix, n=2):
    """Restricted software — must escalate. Single variant."""
    tasks = []
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        sw_key = ix.restricted_software[i % len(ix.restricted_software)]
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"restricted_sw_{i + 1}",
                f"Test restricted software request ({sw_key})",
                "Restricted software requires security team approval. Escalate.",
                f"Employee {name} requests {sw_key} (restricted).",
                pa.label,
                f"You are {name} from {dept}. You need {sw_key}. {pa.instructions}",
                f"You need access to {sw_key} for your work.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know it's restricted.",
                f"Employee {name}: wants {sw_key} (restricted). Agent should escalate.",
                [
                    action(
                        "transfer_1",
                        "transfer_to_human_agents",
                        {
                            "summary": f"Employee {name} requests restricted software: {sw_key}"
                        },
                        f"Transfer for restricted software {sw_key}",
                        compare_args=[],
                    )
                ],
                nl_assertions=[
                    f"The agent informed the employee that {sw_key} requires security team approval",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_restricted_group_request(db, ix, n=2):
    """Restricted access group — must escalate. Single variant."""
    tasks = []
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        gid = ix.restricted_groups[i % len(ix.restricted_groups)]
        group_name = db["access_groups"][gid]["name"]
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"restricted_group_{i + 1}",
                f"Test restricted group request ({group_name})",
                "Restricted groups require security team approval. Cannot grant directly.",
                f"Employee {name} requests {group_name} (restricted).",
                pa.label,
                f"You are {name} from {dept}. You need access to {group_name}. {pa.instructions}",
                f"You need to be added to the {group_name} access group.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know it requires security approval.",
                f"Employee {name}: wants {group_name} (restricted). Agent should escalate or create ticket.",
                [
                    action(
                        "transfer_1",
                        "transfer_to_human_agents",
                        {
                            "summary": f"Employee {name} requests restricted access group: {group_name}"
                        },
                        f"Transfer for restricted group {group_name}",
                        compare_args=[],
                    )
                ],
                nl_assertions=[
                    f"The agent informed the employee that {group_name} requires security team approval",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_device_replacement_expired_warranty(db, ix, n=3):
    """Device replacement with expired warranty — needs escalation. n -> 2n tasks."""
    tasks = []
    eligible = list(ix.devices_expired_warranty)
    random.shuffle(eligible)

    for i, did in enumerate(eligible[:n]):
        device = db["devices"][did]
        eid = device["employee_id"]
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        model = device["model"]
        track_use(eid)

        # Agent should try replacement, get error, then create ticket or transfer
        acts = [
            action(
                "ticket_1",
                "create_ticket",
                {
                    "employee_id": eid,
                    "category": "hardware",
                    "priority": "medium",
                    "description": f"Device replacement for {did} ({model}) - warranty expired",
                },
                f"Create ticket for expired warranty device replacement",
                compare_args=["employee_id", "category"],
            )
        ]
        asserts = [
            env_assert(
                "assert_ticket_exists_for_employee",
                {"employee_id": eid, "category": "hardware"},
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"device_expired_{i + 1}a",
                "Test device replacement with expired warranty",
                "Expired warranty requires IT manager approval. Create ticket or escalate.",
                f"Employee {name}: {model} broken, warranty expired.",
                pa.label,
                f"You are {name} from {dept}. Your {model} is broken. {pa.instructions}",
                f"Your {model} is not working and you need a replacement.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know the warranty status.",
                f"Employee {name}: device {did} warranty expired. Agent should explain and create ticket.",
                acts,
                asserts,
                nl_assertions=[
                    "The agent informed the employee that the device warranty has expired",
                    "The agent explained that IT manager approval is needed for replacement",
                ],
                reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"device_expired_{i + 1}b",
                "Test expired warranty device with frustrated employee",
                "Expired warranty requires IT manager approval. Do not make exceptions.",
                f"Employee {name}: broken device, frustrated about warranty.",
                pb.label,
                f"You are {name}. Your laptop is broken and you need it fixed NOW. {pb.instructions}",
                "Your laptop doesn't work. You can't do anything without it.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know the warranty is expired. Only provide ID/dept if asked.",
                f"Employee {name}: warranty expired. Agent must enforce policy despite pressure.",
                acts,
                asserts,
                nl_assertions=[
                    "The agent informed the employee about the warranty expiration",
                ],
                reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_mfa_on_locked_account(db, ix, n=2):
    """MFA cannot be enabled on locked account — must unlock first. n -> 2n tasks."""
    tasks = []
    locked_no_mfa = [
        eid for eid in ix.locked_employees if not db["employees"][eid]["mfa_enabled"]
    ]
    random.shuffle(locked_no_mfa)

    for i, eid in enumerate(locked_no_mfa[:n]):
        name = emp_name(db, eid)
        email = emp_email(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        acts = [
            action(
                "unlock_1",
                "unlock_account",
                {"employee_id": eid},
                f"Unlock account for {name}",
                compare_args=["employee_id"],
            ),
            action(
                "mfa_1",
                "enable_mfa",
                {"employee_id": eid},
                f"Enable MFA for {name}",
                compare_args=["employee_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_account_status",
                {"employee_id": eid, "expected_status": "active"},
            ),
            env_assert(
                "assert_mfa_enabled",
                {"employee_id": eid, "expected": True},
            ),
        ]
        setup = [
            user_setup_action(
                "set_employee_info", {"name": name, "email": email, "employee_id": eid}
            ),
            user_setup_action("lock_account", {}),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"mfa_locked_{i + 1}a",
                "Test MFA enable on locked account (must unlock first)",
                "MFA cannot be enabled on locked accounts. Unlock first.",
                f"Employee {name}: locked account, wants MFA.",
                pa.label,
                f"You are {name} from {dept}. You want MFA but your account is locked. {pa.instructions}",
                "You want to enable MFA on your account, but you also can't log in.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know you need to unlock first.",
                f"Employee {name}: locked + wants MFA. Agent must unlock then enable MFA.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"mfa_locked_{i + 1}b",
                "Test MFA on locked account with difficult persona",
                "MFA cannot be enabled on locked accounts.",
                f"Employee {name}: locked account, confused about MFA.",
                pb.label,
                f"You are {name}. You want to add extra security. {pb.instructions}",
                "You heard you need to set up something for security on your account.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know your account is locked. Only provide ID/dept if asked.",
                f"Employee {name}: locked + MFA. Agent must diagnose and handle both.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
            )
        )
    return tasks


def gen_new_hire_onboarding(db, ix, n=3):
    """New hire onboarding — set up standard software and access. n -> 2n tasks."""
    tasks = []
    # Find employees with minimal software and group setup
    eligible = []
    for eid in ix.active_employees:
        e = db["employees"][eid]
        # Count how many standard sw they're missing
        missing_sw = 0
        for sw_key in ix.standard_software:
            sw_lower = sw_key.lower()
            has = any(
                db["software_licenses"].get(lid, {}).get("software_name", "").lower()
                == sw_lower
                and db["software_licenses"].get(lid, {}).get("status") == "active"
                for lid in e["software_licenses"]
            )
            if not has:
                missing_sw += 1
        missing_groups = sum(
            1
            for gid in ix.standard_groups
            if eid not in db["access_groups"][gid]["members"]
        )
        if missing_sw >= 2 and missing_groups >= 1:
            eligible.append((eid, missing_sw, missing_groups))
    eligible.sort(key=lambda x: x[1] + x[2], reverse=True)

    for i, (eid, _, _) in enumerate(eligible[:n]):
        e = db["employees"][eid]
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        role = emp_role(db, eid)
        track_use(eid)

        # Determine what they need
        needed_sw = []
        for sw_key in ix.standard_software[:3]:  # grant up to 3
            sw_lower = sw_key.lower()
            has = any(
                db["software_licenses"].get(lid, {}).get("software_name", "").lower()
                == sw_lower
                and db["software_licenses"].get(lid, {}).get("status") == "active"
                for lid in e["software_licenses"]
            )
            if not has:
                needed_sw.append(sw_key)

        needed_groups = []
        for gid in ix.standard_groups[:3]:  # add to up to 3
            if eid not in db["access_groups"][gid]["members"]:
                needed_groups.append(gid)

        acts = []
        asserts = []
        for j, sw in enumerate(needed_sw[:2]):
            acts.append(
                action(
                    f"grant_{j + 1}",
                    "grant_software_license",
                    {"employee_id": eid, "software_name": sw},
                    f"Grant {sw} to {name}",
                    compare_args=["employee_id", "software_name"],
                )
            )
            asserts.append(
                env_assert(
                    "assert_has_software_license",
                    {"employee_id": eid, "software_name": sw, "expected": True},
                )
            )
        for j, gid in enumerate(needed_groups[:2]):
            gname = db["access_groups"][gid]["name"]
            acts.append(
                action(
                    f"add_group_{j + 1}",
                    "add_to_access_group",
                    {"employee_id": eid, "group_id": gid},
                    f"Add {name} to {gname}",
                    compare_args=["employee_id", "group_id"],
                )
            )
            asserts.append(
                env_assert(
                    "assert_in_access_group",
                    {"employee_id": eid, "group_id": gid, "expected": True},
                )
            )

        # Check MFA — if not enabled, enable it
        if not e["mfa_enabled"]:
            acts.append(
                action(
                    "mfa_1",
                    "enable_mfa",
                    {"employee_id": eid},
                    f"Enable MFA for {name}",
                    compare_args=["employee_id"],
                )
            )
            asserts.append(
                env_assert(
                    "assert_mfa_enabled",
                    {"employee_id": eid, "expected": True},
                )
            )

        sw_desc = ", ".join(needed_sw[:2])
        group_desc = ", ".join(
            db["access_groups"][gid]["name"] for gid in needed_groups[:2]
        )

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"onboarding_{i + 1}a",
                "Test new hire onboarding (multi-step setup)",
                "Help new hires set up standard software and access groups. Enable MFA.",
                f"New hire {name} ({dept}, {role}): set up software and access.",
                pa.label,
                f"You are {name}, a new {role} in {dept}. You just started and "
                f"need your accounts set up. {pa.instructions}",
                "You just started and need your work tools set up.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}. Your role is {role}.",
                "You don't know exactly what software or groups you need.",
                f"New hire {name}: set up {sw_desc} and {group_desc}. Enable MFA if needed.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"onboarding_{i + 1}b",
                "Test new hire onboarding with inexperienced employee",
                "Help new hires set up all standard tools for their role.",
                f"New hire {name}: confused about what they need.",
                pb.label,
                f"You are {name}, a new {role} in {dept}. It's your first day. {pb.instructions}",
                "You just started and were told to call IT to get set up. "
                "You're not sure what you need.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You have no idea what software or tools are available. "
                "Only provide ID/dept if asked.",
                f"New hire {name}: agent should determine needs and set up everything.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_transfer_scenarios(db, ix, n=4):
    """Transfer to human agent scenarios. Single variant."""
    tasks = []
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    scenarios = [
        {
            "suffix": "salary_system",
            "reason": "You need access to the salary management system.",
            "known": "Your name is {name}. You need salary system access.",
            "unknown": "You're not sure who to ask.",
            "ticket": "Employee {name} requests salary system access. Agent should transfer.",
            "nl": ["The agent transferred the employee to a human agent"],
        },
        {
            "suffix": "security_incident",
            "reason": "You think someone accessed your account without authorization.",
            "known": "Your name is {name}. You noticed suspicious activity.",
            "unknown": "You don't know the security incident process.",
            "ticket": "Employee {name} reports security incident. Agent should transfer.",
            "nl": [
                "The agent transferred the employee to a human agent or security team"
            ],
        },
        {
            "suffix": "bulk_licenses",
            "reason": "You need 20 licenses of Jira for your entire team.",
            "known": "Your name is {name}. You manage a team of 20.",
            "unknown": "You assume IT can do bulk operations.",
            "ticket": "Employee {name} requests bulk licensing. Agent should transfer.",
            "nl": [
                "The agent transferred the employee to a human agent for bulk processing"
            ],
        },
        {
            "suffix": "data_recovery",
            "reason": "You accidentally deleted important files from your laptop.",
            "known": "Your name is {name}. You deleted files yesterday.",
            "unknown": "You don't know if files can be recovered.",
            "ticket": "Employee {name} needs data recovery. Agent should transfer.",
            "nl": [
                "The agent transferred the employee to a human agent for data recovery"
            ],
        },
    ]

    for i, scenario in enumerate(scenarios[:n]):
        if i >= len(eligible):
            break
        eid = eligible[i]
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"transfer_{scenario['suffix']}",
                f"Test transfer to human agent ({scenario['suffix']})",
                "Transfer to human when issue cannot be resolved with available tools.",
                f"Employee {name}: {scenario['suffix']} scenario.",
                pa.label,
                f"You are {name} from {dept}. {scenario['reason']} {pa.instructions}",
                scenario["reason"],
                scenario["known"].format(name=name),
                scenario["unknown"],
                scenario["ticket"].format(name=name),
                [
                    action(
                        "transfer_1",
                        "transfer_to_human_agents",
                        {"summary": f"Employee {name}: {scenario['suffix']}"},
                        "Transfer to human agent",
                        compare_args=[],
                    )
                ],
                nl_assertions=scenario["nl"],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_vpn_no_internet(db, ix, n=2):
    """VPN issue caused by no internet — user tools reveal root cause. Single variant."""
    tasks = []
    eligible = list(ix.active_with_vpn)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        email = emp_email(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"vpn_no_internet_{i + 1}",
                "Test VPN troubleshooting when internet is down",
                "Check internet first. If down, VPN can't connect. Create network ticket.",
                f"Employee {name}: VPN issue, root cause is no internet.",
                pa.label,
                f"You are {name} from {dept}. Your VPN won't connect. {pa.instructions} "
                "When asked, check your internet connection and report the result.",
                "Your VPN stopped working and you can't access internal resources.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You haven't checked your internet connection.",
                f"Employee {name}: VPN issue, internet is down. Agent should identify root cause.",
                [
                    action(
                        "ticket_1",
                        "create_ticket",
                        {
                            "employee_id": eid,
                            "category": "network",
                            "priority": "high",
                            "description": "No internet connection affecting VPN",
                        },
                        f"Create network ticket for internet outage",
                        compare_args=["employee_id", "category"],
                    )
                ],
                env_assertions=[
                    env_assert(
                        "assert_ticket_exists_for_employee",
                        {"employee_id": eid, "category": "network"},
                    )
                ],
                nl_assertions=[
                    "The agent identified that the internet connection is down",
                    "The agent explained that VPN requires internet connectivity",
                ],
                reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
                user_setup=[
                    user_setup_action(
                        "set_employee_info",
                        {"name": name, "email": email, "employee_id": eid},
                    ),
                    user_setup_action("break_internet", {}),
                ],
            )
        )
    return tasks


def gen_revoke_software_license(db, ix, n=3):
    """Revoke software from an active employee (manager request). Single variant."""
    tasks = []
    # Find active employees with at least 2 software licenses (so revoking one is realistic)
    combos = []
    for eid in ix.active_employees:
        e = db["employees"][eid]
        active_lics = [
            lid
            for lid in e["software_licenses"]
            if lid in db["software_licenses"]
            and db["software_licenses"][lid]["status"] == "active"
        ]
        if len(active_lics) >= 2:
            combos.append((eid, active_lics))
    random.shuffle(combos)

    for i, (eid, active_lics) in enumerate(combos[:n]):
        lid = active_lics[-1]  # pick last license
        sw = db["software_licenses"][lid]["software_name"]
        name = emp_name(db, eid)
        track_use(eid)
        pa = pick_easy_persona()

        # The caller is a manager
        e = db["employees"][eid]
        manager_id = e.get("manager_id")
        if manager_id and manager_id in db["employees"]:
            caller = manager_id
        else:
            caller = [c for c in ix.active_employees if c != eid][0]
        caller_name = emp_name(db, caller)
        caller_dept = emp_dept(db, caller)

        tasks.append(
            make_task(
                f"revoke_license_{i + 1}",
                f"Test revoking {sw} license from employee",
                "Licenses can be revoked. Manager may request license removal.",
                f"Manager {caller_name}: revoke {sw} from {name}.",
                pa.label,
                f"You are {caller_name} from {caller_dept}. You need to remove "
                f"a software license from one of your team members. {pa.instructions}",
                f"Employee {name} no longer needs {sw}. Please revoke their license.",
                f"Your name is {caller_name}. The employee is {name} ({eid}). "
                f"The software is {sw}.",
                "You don't know the license ID.",
                f"Manager requests {sw} revoke from {name}. Agent should find and revoke.",
                [
                    action(
                        "revoke_1",
                        "revoke_software_license",
                        {"license_id": lid},
                        f"Revoke {sw} license {lid} from {name}",
                        compare_args=["license_id"],
                    )
                ],
                env_assertions=[
                    env_assert(
                        "assert_license_status",
                        {"license_id": lid, "expected_status": "revoked"},
                    )
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_critical_ticket_escalation(db, ix, n=2):
    """Critical issue that needs immediate escalation. Single variant."""
    tasks = []
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    scenarios = [
        {
            "issue": "Production system is completely down, entire engineering team is blocked",
            "category": "software",
            "priority": "critical",
        },
        {
            "issue": "Suspected security breach - unauthorized access to multiple accounts",
            "category": "account",
            "priority": "critical",
        },
    ]

    for i, scenario in enumerate(scenarios[:n]):
        if i >= len(eligible):
            break
        eid = eligible[i]
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)
        pa = pick_easy_persona()

        acts = [
            action(
                "ticket_1",
                "create_ticket",
                {
                    "employee_id": eid,
                    "category": scenario["category"],
                    "priority": "critical",
                    "description": scenario["issue"],
                },
                f"Create critical ticket for {name}",
                compare_args=["employee_id", "priority"],
            ),
            action(
                "transfer_1",
                "transfer_to_human_agents",
                {"summary": f"CRITICAL: {scenario['issue']}"},
                "Transfer critical issue to human agent",
                compare_args=[],
            ),
        ]

        tasks.append(
            make_task(
                f"critical_escalation_{i + 1}",
                "Test critical issue handling and escalation",
                "Critical tickets bypass normal queue. Escalate immediately. Transfer to human.",
                f"Employee {name}: critical issue - {scenario['issue'][:50]}.",
                pa.label,
                f"You are {name} from {dept}. This is urgent. {pa.instructions}",
                scenario["issue"],
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You need this resolved immediately.",
                f"CRITICAL: {name} reports {scenario['issue'][:50]}. "
                "Agent should create critical ticket and transfer.",
                acts,
                nl_assertions=[
                    "The agent acknowledged the severity of the issue",
                    "The agent created a critical-priority ticket or escalated",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_browser_cache_troubleshooting(db, ix, n=2):
    """Web app issues resolved by clearing browser cache. Single variant."""
    tasks = []
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"browser_cache_{i + 1}",
                "Test browser cache troubleshooting",
                "For web app issues, try clearing browser cache first.",
                f"Employee {name}: web app loading incorrectly.",
                pa.label,
                f"You are {name} from {dept}. A web application isn't loading correctly. "
                f"{pa.instructions} When asked, clear your browser cache and report.",
                "Jira is showing me an old version of a page. It won't load correctly.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You haven't tried clearing your cache.",
                f"Employee {name}: web app issue. Agent should suggest clearing browser cache.",
                [],
                nl_assertions=[
                    "The agent suggested clearing the browser cache",
                ],
                reward_basis=["NL_ASSERTION"],
                user_env_assertions=[
                    user_env_assert("assert_browser_cache_cleared", {}),
                ],
            )
        )
    return tasks


def gen_password_expired_troubleshoot(db, ix, n=3):
    """Employee's password has expired — they can't login, need reset. n -> 2n tasks."""
    tasks = []
    eligible = list(ix.active_employees)
    random.shuffle(eligible)

    for i, eid in enumerate(eligible[:n]):
        name = emp_name(db, eid)
        email = emp_email(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)

        acts = [
            action(
                "reset_1",
                "reset_password",
                {"employee_id": eid},
                f"Reset password for {name}",
                compare_args=["employee_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_password_reset_date",
                {"employee_id": eid, "expected_date": TODAY},
            ),
        ]
        setup = [
            user_setup_action(
                "set_employee_info", {"name": name, "email": email, "employee_id": eid}
            ),
            user_setup_action("expire_password", {}),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"password_expired_{i + 1}a",
                "Test expired password troubleshooting",
                "Password expired means reset is needed. Verify identity first.",
                f"Employee {name}: password expired, can't log in.",
                pa.label,
                f"You are {name} from {dept}. You can't log in. {pa.instructions} "
                "When asked, try logging in and report what happens.",
                "You can't log in to anything. It says your password has expired.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You need to know what to do about the expired password.",
                f"Employee {name}: password expired. Agent should verify identity and reset.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"password_expired_{i + 1}b",
                "Test expired password with vague symptoms",
                "Password expired means reset is needed.",
                f"Employee {name}: can't login, doesn't know password expired.",
                pb.label,
                f"You are {name}. You can't access your work tools. {pb.instructions} "
                "When asked, try logging in and report what happens.",
                "Nothing is working today. You can't get into any of your tools.",
                f"Your name is {name}. Your employee ID is {eid}. "
                f"Your department is {dept}.",
                "You don't know your password expired. Only provide ID/dept if asked.",
                f"Employee {name}: password expired. Agent must diagnose from symptoms.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
                user_setup=setup,
            )
        )
    return tasks


def gen_remove_from_group(db, ix, n=3):
    """Remove employee from a group. Single variant."""
    tasks = []
    combos = []
    for gid in ix.standard_groups:
        in_group = ix.employees_in_group.get(gid, [])
        for eid in in_group:
            combos.append((gid, eid))
    random.shuffle(combos)

    used = set()
    selected = []
    for gid, eid in combos:
        if eid not in used and len(selected) < n:
            selected.append((gid, eid))
            used.add(eid)

    for i, (gid, eid) in enumerate(selected):
        name = emp_name(db, eid)
        group_name = db["access_groups"][gid]["name"]
        track_use(eid)
        pa = pick_easy_persona()

        # Caller is a manager requesting removal
        e = db["employees"][eid]
        manager_id = e.get("manager_id")
        if manager_id and manager_id in db["employees"]:
            caller = manager_id
        else:
            caller = ix.active_employees[0]
        caller_name = emp_name(db, caller)
        caller_dept = emp_dept(db, caller)

        tasks.append(
            make_task(
                f"remove_group_{i + 1}",
                f"Test removing employee from {group_name}",
                "Employees can be removed from access groups.",
                f"Manager requests removing {name} from {group_name}.",
                pa.label,
                f"You are {caller_name} from {caller_dept}. You need to remove "
                f"an employee from an access group. {pa.instructions}",
                f"Employee {name} no longer needs access to {group_name}. "
                "Please remove them from the group.",
                f"Your name is {caller_name}. The employee is {name} ({eid}). "
                f"The group is {group_name}.",
                "You don't know the group ID.",
                f"Remove {name} from {group_name}. Agent should find group and remove.",
                [
                    action(
                        "remove_1",
                        "remove_from_access_group",
                        {"employee_id": eid, "group_id": gid},
                        f"Remove {name} from {group_name}",
                        compare_args=["employee_id", "group_id"],
                    )
                ],
                env_assertions=[
                    env_assert(
                        "assert_in_access_group",
                        {"employee_id": eid, "group_id": gid, "expected": False},
                    )
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_update_ticket_status(db, ix, n=3):
    """Update an existing ticket status. Single variant."""
    tasks = []
    tickets = list(ix.open_tickets)
    random.shuffle(tickets)

    for i, tid in enumerate(tickets[:n]):
        ticket = db["tickets"][tid]
        eid = ticket["employee_id"]
        if eid not in db["employees"]:
            continue
        name = emp_name(db, eid)
        dept = emp_dept(db, eid)
        track_use(eid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"update_ticket_{i + 1}",
                "Test updating ticket status",
                "Tickets can be updated with new status and resolution.",
                f"Employee {name}: wants to close/resolve ticket {tid}.",
                pa.label,
                f"You are {name} from {dept}. Your issue from ticket {tid} has been "
                f"resolved. {pa.instructions}",
                f"My issue from ticket {tid} has been resolved. Can you update it?",
                f"Your name is {name}. Your ticket is {tid}. "
                f"Your department is {dept}.",
                "You don't know the exact status to use.",
                f"Employee {name}: resolve ticket {tid}. Agent should update status.",
                [
                    action(
                        "update_1",
                        "update_ticket",
                        {
                            "ticket_id": tid,
                            "status": "resolved",
                            "resolution": "Issue resolved per employee report",
                        },
                        f"Resolve ticket {tid}",
                        compare_args=["ticket_id", "status"],
                    )
                ],
                env_assertions=[
                    env_assert(
                        "assert_ticket_status",
                        {"ticket_id": tid, "expected_status": "resolved"},
                    )
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    random.seed(SEED)
    db = load_db()
    ix = build_indexes(db)

    all_tasks = []
    stats = {}

    generators_t1 = [
        ("password_reset", gen_password_reset, 7),
        ("unlock_account", gen_unlock_account, 5),
        ("enable_mfa", gen_enable_mfa, 6),
        ("grant_standard_sw", gen_grant_standard_software, 7),
    ]

    generators_t2 = [
        ("check_ticket", gen_check_ticket_status, 4),
        ("list_software", gen_list_software, 3),
        ("check_device", gen_check_device_info, 3),
        ("check_access_groups", gen_check_access_groups, 3),
    ]

    generators_t3 = [
        ("unlock_reset", gen_unlock_and_reset_password, 4),
        ("add_access_group", gen_add_to_access_group, 5),
        ("reset_mfa", gen_password_reset_with_mfa, 4),
        ("device_replace", gen_device_replacement_valid_warranty, 4),
        ("create_ticket", gen_create_ticket, 5),
    ]

    generators_t4 = [
        ("vpn_troubleshoot", gen_vpn_troubleshooting, 4),
        ("unlock_reset_mfa", gen_unlock_reset_mfa, 3),
        ("sw_plus_group", gen_software_plus_access_group, 4),
        ("login_troubleshoot", gen_login_troubleshooting, 3),
        ("onboarding", gen_new_hire_onboarding, 3),
        ("password_expired", gen_password_expired_troubleshoot, 3),
    ]

    generators_t5 = [
        ("reset_disabled", gen_password_reset_disabled_account, 3),
        ("non_standard_sw", gen_non_standard_software_request, 3),
        ("restricted_sw", gen_restricted_software_request, 2),
        ("restricted_group", gen_restricted_group_request, 2),
        ("device_expired", gen_device_replacement_expired_warranty, 3),
        ("mfa_locked", gen_mfa_on_locked_account, 2),
        ("critical_escalation", gen_critical_ticket_escalation, 2),
        ("transfer", gen_transfer_scenarios, 4),
        ("vpn_no_internet", gen_vpn_no_internet, 2),
        ("revoke_license", gen_revoke_software_license, 3),
        ("browser_cache", gen_browser_cache_troubleshooting, 2),
        ("remove_group", gen_remove_from_group, 3),
        ("update_ticket", gen_update_ticket_status, 3),
    ]

    tier_names = [
        ("Tier 1: Simple Single-Action", generators_t1),
        ("Tier 2: Information & Lookup", generators_t2),
        ("Tier 3: Moderate Multi-Step", generators_t3),
        ("Tier 4: Complex Multi-Step", generators_t4),
        ("Tier 5: Edge Cases & Policy", generators_t5),
    ]

    for tier_name, generators in tier_names:
        for gname, gen_fn, base_n in generators:
            tasks = gen_fn(db, ix, n=base_n)
            stats[gname] = {"base": base_n, "actual": len(tasks)}
            all_tasks.extend(tasks)

    # Validate unique IDs
    ids = [t["id"] for t in all_tasks]
    dupes = [tid for tid in ids if ids.count(tid) > 1]
    if dupes:
        print(f"WARNING: Duplicate task IDs: {set(dupes)}")

    # Print stats
    print(f"\n{'=' * 60}")
    print(f"Generated {len(all_tasks)} tasks")
    print(f"{'=' * 60}")
    for tier_name, generators in tier_names:
        tier_total = sum(stats[n]["actual"] for n, _, _ in generators)
        print(f"\n{tier_name}: {tier_total} tasks")
        for gname, _, base_n in generators:
            s = stats[gname]
            print(f"  {gname:35s} {s['actual']:3d}  (base={s['base']})")

    # Difficulty distribution
    easy_count = sum(1 for t in all_tasks if t["id"].endswith("a"))
    hard_count = sum(1 for t in all_tasks if t["id"].endswith("b"))
    single_count = len(all_tasks) - easy_count - hard_count
    print(f"\nDifficulty distribution:")
    print(f"  Easy (a variants):    {easy_count}")
    print(f"  Hard (b variants):    {hard_count}")
    print(f"  Single variant:       {single_count}")

    # Reward basis distribution
    rb_counts: dict[str, int] = {}
    for t in all_tasks:
        for rb in t["evaluation_criteria"]["reward_basis"]:
            rb_counts[rb] = rb_counts.get(rb, 0) + 1
    print(f"\nReward basis distribution:")
    for rb, count in sorted(rb_counts.items()):
        print(f"  {rb}: {count}")

    # Write tasks.json
    with open(TASKS_PATH, "w") as f:
        json.dump(all_tasks, f, indent=2)
    print(f"\nWritten to {TASKS_PATH}")

    # Write split_tasks.json
    easy_ids = [t["id"] for t in all_tasks if t["id"].endswith("a")]
    hard_ids = [t["id"] for t in all_tasks if t["id"].endswith("b")]
    single_ids = [
        t["id"]
        for t in all_tasks
        if not t["id"].endswith("a") and not t["id"].endswith("b")
    ]
    split = {
        "base": [t["id"] for t in all_tasks],
        "easy": easy_ids + single_ids,
        "hard": hard_ids,
    }
    with open(SPLIT_TASKS_PATH, "w") as f:
        json.dump(split, f, indent=2)
    print(f"Written to {SPLIT_TASKS_PATH}")


if __name__ == "__main__":
    main()
