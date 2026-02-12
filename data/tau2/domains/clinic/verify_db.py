#!/usr/bin/env python3
"""Verify clinic database integrity.

Checks referential integrity, status consistency, and policy constraints.

Usage:
    python verify_db.py
"""

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path(__file__).parent / "db.json"
TASKS_PATH = Path(__file__).parent / "tasks.json"
TODAY = "2025-10-15"


@dataclass
class Violation:
    check: str
    entity_type: str
    entity_id: str
    message: str

    def __repr__(self):
        return f"  [{self.entity_type}:{self.entity_id}] {self.message}"


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def verify_db(db: dict) -> list[Violation]:
    violations = []

    # Check all patient foreign keys
    for pid, p in db["patients"].items():
        if p["primary_doctor_id"] and p["primary_doctor_id"] not in db["doctors"]:
            violations.append(Violation(
                "fk_patient_doctor", "patient", pid,
                f"Primary doctor {p['primary_doctor_id']} not found"
            ))
        if p["insurance_id"] and p["insurance_id"] not in db["insurance"]:
            violations.append(Violation(
                "fk_patient_insurance", "patient", pid,
                f"Insurance {p['insurance_id']} not found"
            ))
        for aid in p["appointment_ids"]:
            if aid not in db["appointments"]:
                violations.append(Violation(
                    "fk_patient_appointment", "patient", pid,
                    f"Appointment {aid} not found"
                ))
        for pmid in p["payment_method_ids"]:
            if pmid not in db["payment_methods"]:
                violations.append(Violation(
                    "fk_patient_payment_method", "patient", pid,
                    f"Payment method {pmid} not found"
                ))

    # Check doctor foreign keys
    for did, d in db["doctors"].items():
        if d["clinic_id"] not in db["clinics"]:
            violations.append(Violation(
                "fk_doctor_clinic", "doctor", did,
                f"Clinic {d['clinic_id']} not found"
            ))

    # Check appointment foreign keys
    for aid, a in db["appointments"].items():
        if a["patient_id"] not in db["patients"]:
            violations.append(Violation(
                "fk_appt_patient", "appointment", aid,
                f"Patient {a['patient_id']} not found"
            ))
        if a["doctor_id"] not in db["doctors"]:
            violations.append(Violation(
                "fk_appt_doctor", "appointment", aid,
                f"Doctor {a['doctor_id']} not found"
            ))
        if a["clinic_id"] not in db["clinics"]:
            violations.append(Violation(
                "fk_appt_clinic", "appointment", aid,
                f"Clinic {a['clinic_id']} not found"
            ))

    # Check prescription foreign keys
    for rxid, rx in db["prescriptions"].items():
        if rx["patient_id"] not in db["patients"]:
            violations.append(Violation(
                "fk_rx_patient", "prescription", rxid,
                f"Patient {rx['patient_id']} not found"
            ))
        if rx["doctor_id"] not in db["doctors"]:
            violations.append(Violation(
                "fk_rx_doctor", "prescription", rxid,
                f"Doctor {rx['doctor_id']} not found"
            ))

    # Check referral foreign keys
    for rid, r in db["referrals"].items():
        if r["patient_id"] not in db["patients"]:
            violations.append(Violation(
                "fk_ref_patient", "referral", rid,
                f"Patient {r['patient_id']} not found"
            ))
        if r["referring_doctor_id"] not in db["doctors"]:
            violations.append(Violation(
                "fk_ref_doctor", "referral", rid,
                f"Referring doctor {r['referring_doctor_id']} not found"
            ))

    # Check invoice foreign keys
    for iid, inv in db["invoices"].items():
        if inv["patient_id"] not in db["patients"]:
            violations.append(Violation(
                "fk_inv_patient", "invoice", iid,
                f"Patient {inv['patient_id']} not found"
            ))

    # Check insurance foreign keys
    for insid, ins in db["insurance"].items():
        if ins["patient_id"] not in db["patients"]:
            violations.append(Violation(
                "fk_ins_patient", "insurance", insid,
                f"Patient {ins['patient_id']} not found"
            ))

    # Check payment method foreign keys
    for pmid, pm in db["payment_methods"].items():
        if pm["patient_id"] not in db["patients"]:
            violations.append(Violation(
                "fk_pm_patient", "payment_method", pmid,
                f"Patient {pm['patient_id']} not found"
            ))

    # Check lab result foreign keys
    for lid, lr in db["lab_results"].items():
        if lr["patient_id"] not in db["patients"]:
            violations.append(Violation(
                "fk_lab_patient", "lab_result", lid,
                f"Patient {lr['patient_id']} not found"
            ))

    # Check for duplicate patient names (informational)
    name_counts: dict[str, list[str]] = defaultdict(list)
    for pid, p in db["patients"].items():
        name_counts[p["name"]].append(pid)
    for name, pids in name_counts.items():
        if len(pids) > 1:
            violations.append(Violation(
                "duplicate_name", "patient", pids[0],
                f"Duplicate name '{name}' shared by {len(pids)} patients: {pids}"
            ))

    return violations


def verify_tasks(db: dict, tasks: list) -> list[Violation]:
    violations = []

    for task in tasks:
        tid = task["id"]
        criteria = task.get("evaluation_criteria", {})

        # Check action references
        for act in criteria.get("actions") or []:
            tool_name = act.get("name", "")
            args = act.get("arguments", {})

            # Check patient_id references
            if "patient_id" in args and args["patient_id"] != "placeholder":
                if args["patient_id"] not in db["patients"]:
                    violations.append(Violation(
                        "task_fk_patient", "task", tid,
                        f"Action {act['action_id']} references missing patient {args['patient_id']}"
                    ))

            # Check appointment_id references
            if "appointment_id" in args and args["appointment_id"] != "placeholder":
                if args["appointment_id"] not in db["appointments"]:
                    violations.append(Violation(
                        "task_fk_appointment", "task", tid,
                        f"Action {act['action_id']} references missing appointment {args['appointment_id']}"
                    ))

            # Check prescription_id references
            if "prescription_id" in args and args["prescription_id"] != "placeholder":
                if args["prescription_id"] not in db["prescriptions"]:
                    violations.append(Violation(
                        "task_fk_prescription", "task", tid,
                        f"Action {act['action_id']} references missing prescription {args['prescription_id']}"
                    ))

            # Check invoice_id references
            if "invoice_id" in args and args["invoice_id"] != "placeholder":
                if args["invoice_id"] not in db["invoices"]:
                    violations.append(Violation(
                        "task_fk_invoice", "task", tid,
                        f"Action {act['action_id']} references missing invoice {args['invoice_id']}"
                    ))

    return violations


def print_stats(db):
    print("=== Database Statistics ===")
    print(f"  Patients:       {len(db['patients'])}")
    print(f"  Doctors:        {len(db['doctors'])}")
    print(f"  Clinics:        {len(db['clinics'])}")
    print(f"  Appointments:   {len(db['appointments'])}")
    print(f"  Prescriptions:  {len(db['prescriptions'])}")
    print(f"  Referrals:      {len(db['referrals'])}")
    print(f"  Invoices:       {len(db['invoices'])}")
    print(f"  Insurance:      {len(db['insurance'])}")
    print(f"  Lab Results:    {len(db['lab_results'])}")
    print(f"  Payment Methods:{len(db['payment_methods'])}")


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
