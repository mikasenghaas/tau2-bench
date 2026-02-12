#!/usr/bin/env python3
"""Verify referential integrity and consistency of the library domain database.

Usage:
    uv run python environments/service_agent/tau2/data/tau2/domains/library/verify_db.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "db.json"
TASKS_PATH = DATA_DIR / "tasks.json"

EXPECTED_BORROWING_LIMITS = {
    "standard": 10,
    "student": 15,
    "senior": 10,
    "child": 10,  # policy.md says 10
}


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


class Violation:
    def __init__(self, check: str, entity_id: str, message: str):
        self.check = check
        self.entity_id = entity_id
        self.message = message

    def __repr__(self):
        return f"  [{self.entity_id}] {self.message}"


def verify_db(db: dict) -> list[Violation]:
    patrons = db["patrons"]
    books = db["books"]
    copies = db["copies"]
    branches = db["branches"]
    loans = db["loans"]
    holds = db["holds"]
    fines = db["fines"]
    events = db["events"]

    violations: list[Violation] = []

    def v(check, eid, msg):
        violations.append(Violation(check, eid, msg))

    # ── Foreign key checks ──────────────────────────────────────────────

    for copy_id, copy in copies.items():
        if copy["book_id"] not in books:
            v("fk", copy_id, f"book_id '{copy['book_id']}' not in books")
        if copy["branch_id"] not in branches:
            v("fk", copy_id, f"branch_id '{copy['branch_id']}' not in branches")
        if copy.get("borrower_id") and copy["borrower_id"] not in patrons:
            v("fk", copy_id, f"borrower_id '{copy['borrower_id']}' not in patrons")

    for book_id, book in books.items():
        for cid in book.get("copies", []):
            if cid not in copies:
                v("fk", book_id, f"copy '{cid}' not in copies")

    for loan_id, loan in loans.items():
        if loan["patron_id"] not in patrons:
            v("fk", loan_id, f"patron_id '{loan['patron_id']}' not in patrons")
        if loan["copy_id"] not in copies:
            v("fk", loan_id, f"copy_id '{loan['copy_id']}' not in copies")

    for hold_id, hold in holds.items():
        if hold["patron_id"] not in patrons:
            v("fk", hold_id, f"patron_id '{hold['patron_id']}' not in patrons")
        if hold["book_id"] not in books:
            v("fk", hold_id, f"book_id '{hold['book_id']}' not in books")
        if hold["branch_id"] not in branches:
            v("fk", hold_id, f"branch_id '{hold['branch_id']}' not in branches")

    for fine_id, fine in fines.items():
        if fine["patron_id"] not in patrons:
            v("fk", fine_id, f"patron_id '{fine['patron_id']}' not in patrons")
        if fine["loan_id"] not in loans:
            v("fk", fine_id, f"loan_id '{fine['loan_id']}' not in loans")

    for event_id, event in events.items():
        if event["branch_id"] not in branches:
            v("fk", event_id, f"branch_id '{event['branch_id']}' not in branches")
        for pid in event.get("registered_patrons", []):
            if pid not in patrons:
                v("fk", event_id, f"registered patron '{pid}' not in patrons")

    # ── Patron list consistency ─────────────────────────────────────────

    for patron_id, patron in patrons.items():
        for lid in patron.get("active_loans", []):
            if lid not in loans:
                v("patron_loans", patron_id, f"active_loan '{lid}' not in loans")
            elif loans[lid].get("return_date") is not None:
                v("patron_loans", patron_id, f"active_loan '{lid}' already returned")
        for hid in patron.get("holds", []):
            if hid not in holds:
                v("patron_holds", patron_id, f"hold '{hid}' not in holds")

    # ── Fines owed consistency ──────────────────────────────────────────

    outstanding_by_patron: dict[str, float] = defaultdict(float)
    for fine in fines.values():
        if fine["status"] == "outstanding":
            outstanding_by_patron[fine["patron_id"]] += fine["amount"]

    for patron_id, patron in patrons.items():
        expected = outstanding_by_patron.get(patron_id, 0.0)
        actual = patron["fines_owed"]
        if abs(expected - actual) > 0.01:
            v(
                "fines_owed",
                patron_id,
                f"fines_owed={actual:.2f} but sum of outstanding fines={expected:.2f}",
            )

    # ── Copy ↔ loan state consistency ───────────────────────────────────

    # Build map: copy_id → active loan (return_date is None)
    active_loan_by_copy: dict[str, str] = {}
    for loan_id, loan in loans.items():
        if loan.get("return_date") is None and loan["copy_id"] in copies:
            active_loan_by_copy[loan["copy_id"]] = loan_id

    for copy_id, copy in copies.items():
        if copy["status"] == "checked_out":
            if not copy.get("borrower_id"):
                v("copy_loan", copy_id, "status=checked_out but no borrower_id")
            if not copy.get("due_date"):
                v("copy_loan", copy_id, "status=checked_out but no due_date")
            if copy_id not in active_loan_by_copy:
                v("copy_loan", copy_id, "status=checked_out but no active loan found")
        elif copy["status"] == "available":
            if copy.get("borrower_id"):
                v("copy_loan", copy_id, "status=available but has borrower_id")
            if copy.get("due_date"):
                v("copy_loan", copy_id, "status=available but has due_date")

    # ── Borrowing limit consistency with policy ─────────────────────────

    for patron_id, patron in patrons.items():
        mtype = patron["membership_type"]
        expected_limit = EXPECTED_BORROWING_LIMITS.get(mtype)
        if expected_limit and patron["borrowing_limit"] != expected_limit:
            v(
                "policy",
                patron_id,
                f"borrowing_limit={patron['borrowing_limit']} but policy says {expected_limit} for {mtype}",
            )

    # ── Active loans don't exceed borrowing limit ───────────────────────

    for patron_id, patron in patrons.items():
        n_loans = len(patron.get("active_loans", []))
        if n_loans > patron["borrowing_limit"]:
            v(
                "policy",
                patron_id,
                f"has {n_loans} active loans but limit is {patron['borrowing_limit']}",
            )

    # ── Event capacity ──────────────────────────────────────────────────

    for event_id, event in events.items():
        n_reg = len(event.get("registered_patrons", []))
        if n_reg > event["capacity"]:
            v("event_cap", event_id, f"{n_reg} registered but capacity is {event['capacity']}")
        if n_reg >= event["capacity"] and event["status"] not in ("full", "completed", "cancelled"):
            v("event_cap", event_id, f"at capacity ({n_reg}/{event['capacity']}) but status='{event['status']}'")

    return violations


def verify_tasks(db: dict, tasks: list) -> list[Violation]:
    """Verify that task evaluation criteria reference entities that exist in the DB."""
    violations: list[Violation] = []

    def v(task_id, msg):
        violations.append(Violation("task", task_id, msg))

    for task in tasks:
        task_id = task["id"]
        criteria = task.get("evaluation_criteria", {})

        for action in criteria.get("actions", []):
            args = action.get("arguments", {})
            name = action.get("name", "")

            # Check referenced patron_ids
            if "patron_id" in args and args["patron_id"] not in db["patrons"]:
                v(task_id, f"action '{name}' references patron '{args['patron_id']}' not in DB")

            # Check referenced copy_ids
            if "copy_id" in args and args["copy_id"] not in db["copies"]:
                v(task_id, f"action '{name}' references copy '{args['copy_id']}' not in DB")

            # Check referenced fine_ids
            if "fine_id" in args and args["fine_id"] not in db["fines"]:
                v(task_id, f"action '{name}' references fine '{args['fine_id']}' not in DB")

            # Check referenced loan_ids
            if "loan_id" in args and args["loan_id"] not in db["loans"]:
                v(task_id, f"action '{name}' references loan '{args['loan_id']}' not in DB")

            # Check referenced hold_ids
            if "hold_id" in args and args["hold_id"] not in db["holds"]:
                v(task_id, f"action '{name}' references hold '{args['hold_id']}' not in DB")

            # Check referenced event_ids
            if "event_id" in args and args["event_id"] not in db["events"]:
                v(task_id, f"action '{name}' references event '{args['event_id']}' not in DB")

        for assertion in criteria.get("env_assertions", []):
            args = assertion.get("arguments", {})
            func = assertion.get("func_name", "")

            if "patron_id" in args and args["patron_id"] not in db["patrons"]:
                v(task_id, f"assertion '{func}' references patron '{args['patron_id']}' not in DB")
            if "copy_id" in args and args["copy_id"] not in db["copies"]:
                v(task_id, f"assertion '{func}' references copy '{args['copy_id']}' not in DB")
            if "fine_id" in args and args["fine_id"] not in db["fines"]:
                v(task_id, f"assertion '{func}' references fine '{args['fine_id']}' not in DB")

    return violations


def print_stats(db: dict):
    copies = db["copies"]
    status_counts: dict[str, int] = defaultdict(int)
    for copy in copies.values():
        status_counts[copy["status"]] += 1

    membership_counts: dict[str, int] = defaultdict(int)
    for patron in db["patrons"].values():
        membership_counts[patron["membership_type"]] += 1

    hold_status_counts: dict[str, int] = defaultdict(int)
    for hold in db["holds"].values():
        hold_status_counts[hold["status"]] += 1

    fine_status_counts: dict[str, int] = defaultdict(int)
    for fine in db["fines"].values():
        fine_status_counts[fine["status"]] += 1

    active_loans = sum(1 for l in db["loans"].values() if l.get("return_date") is None)

    print("=== Database Statistics ===")
    print(f"  Patrons:  {len(db['patrons'])}")
    print(f"  Books:    {len(db['books'])}")
    print(f"  Copies:   {len(db['copies'])}")
    print(f"  Branches: {len(db['branches'])}")
    print(f"  Loans:    {len(db['loans'])} ({active_loans} active)")
    print(f"  Holds:    {len(db['holds'])}")
    print(f"  Fines:    {len(db['fines'])}")
    print(f"  Events:   {len(db['events'])}")

    print("\n=== Copy Statuses ===")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

    print("\n=== Membership Types ===")
    for mtype, count in sorted(membership_counts.items()):
        print(f"  {mtype}: {count}")

    print("\n=== Hold Statuses ===")
    for status, count in sorted(hold_status_counts.items()):
        print(f"  {status}: {count}")

    print("\n=== Fine Statuses ===")
    for status, count in sorted(fine_status_counts.items()):
        print(f"  {status}: {count}")


def main():
    db = load_json(DB_PATH)

    print_stats(db)

    print("\n=== Verifying DB Integrity ===")
    db_violations = verify_db(db)

    task_violations = []
    if TASKS_PATH.exists():
        print("\n=== Verifying Tasks Against DB ===")
        tasks = load_json(TASKS_PATH)
        task_violations = verify_tasks(db, tasks)

    all_violations = db_violations + task_violations

    if all_violations:
        print(f"\nFOUND {len(all_violations)} VIOLATION(S):\n")
        by_check: dict[str, list[Violation]] = defaultdict(list)
        for viol in all_violations:
            by_check[viol.check].append(viol)
        for check, viols in by_check.items():
            print(f"[{check}] ({len(viols)} issues)")
            for viol in viols[:20]:
                print(repr(viol))
            if len(viols) > 20:
                print(f"  ... and {len(viols) - 20} more")
            print()
        sys.exit(1)
    else:
        print("\nAll checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
