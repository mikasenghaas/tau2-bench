#!/usr/bin/env python3
"""Procedurally generate ~200 clinic domain tasks from db.json.

Standalone script (stdlib only: json, random, pathlib).
Deterministic via random.seed(42).

Uses retail-inspired structured personas and variant generation:
- Easy (a) variants: full info, direct persona
- Hard (b) variants: vague info, challenging persona

Usage:
    python generate_tasks.py            # writes tasks.json + split_tasks.json
    python generate_tasks.py --stats    # print stats only, don't write
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


def patient_name(db: dict, pid: str) -> str:
    return db["patients"][pid]["name"]


def doctor_name(db: dict, did: str) -> str:
    return db["doctors"][did]["name"]


def clinic_name(db: dict, cid: str) -> str:
    return db["clinics"][cid]["name"]


def patient_has_recent_visit(db: dict, pid: str) -> bool:
    """Check if patient has been seen in the last 12 months."""
    from datetime import datetime, timedelta

    cutoff = (datetime.strptime(TODAY, "%Y-%m-%d") - timedelta(days=365)).strftime(
        "%Y-%m-%d"
    )
    patient = db["patients"][pid]
    return any(
        db["appointments"].get(aid, {}).get("status") == "completed"
        and db["appointments"].get(aid, {}).get("date", "") >= cutoff
        for aid in patient["appointment_ids"]
    )


def patient_has_active_insurance(db: dict, pid: str) -> bool:
    iid = db["patients"][pid].get("insurance_id")
    if not iid or iid not in db["insurance"]:
        return False
    return db["insurance"][iid]["status"] == "active"


def patient_has_primary_doctor(db: dict, pid: str) -> bool:
    return db["patients"][pid].get("primary_doctor_id") is not None


def patient_has_valid_referral(db: dict, pid: str, specialty: str) -> bool:
    return any(
        r["patient_id"] == pid
        and r["specialty"] == specialty
        and r["status"] in ("pending", "scheduled")
        and r["expiry_date"] >= TODAY
        for r in db["referrals"].values()
    )


# ---------------------------------------------------------------------------
# Entity Indexes
# ---------------------------------------------------------------------------


@dataclass
class EntityIndexes:
    # Patients
    active_patients: list = field(default_factory=list)
    patients_with_primary: list = field(default_factory=list)
    patients_without_primary: list = field(default_factory=list)
    patients_with_balance: list = field(default_factory=list)
    patients_high_balance: list = field(default_factory=list)
    patients_with_active_insurance: list = field(default_factory=list)
    patients_with_expired_insurance: list = field(default_factory=list)
    patients_uninsured: list = field(default_factory=list)
    patients_with_recent_visit: list = field(default_factory=list)
    patients_without_recent_visit: list = field(default_factory=list)

    # Appointments
    future_scheduled: list = field(default_factory=list)
    future_cancellable_soon: list = field(default_factory=list)  # within 24h
    future_reschedulable: list = field(default_factory=list)  # > 24h away

    # Prescriptions
    refillable_prescriptions: list = field(default_factory=list)
    no_refills_prescriptions: list = field(default_factory=list)
    controlled_prescriptions: list = field(default_factory=list)
    needs_visit_prescriptions: list = field(default_factory=list)

    # Referrals
    pending_referrals: list = field(default_factory=list)
    expired_referrals: list = field(default_factory=list)

    # Invoices
    pending_invoices: list = field(default_factory=list)
    overdue_invoices: list = field(default_factory=list)
    large_invoices: list = field(default_factory=list)  # > $500

    # Lab results
    pending_labs: list = field(default_factory=list)
    completed_labs: list = field(default_factory=list)

    # Doctors
    accepting_general: list = field(default_factory=list)
    specialist_doctors: dict = field(default_factory=dict)

    # Availability helpers
    available_slots_by_doctor: dict = field(default_factory=dict)


def build_indexes(db: dict) -> EntityIndexes:
    ix = EntityIndexes()

    # Filter out patients with ambiguous (duplicate) names
    _name_counts: dict[str, list[str]] = {}
    for pid, p in db["patients"].items():
        _name_counts.setdefault(p["name"], []).append(pid)
    _ambiguous: set[str] = set()
    for _pids in _name_counts.values():
        if len(_pids) > 1:
            _ambiguous.update(_pids)

    for pid, p in db["patients"].items():
        if pid in _ambiguous:
            continue
        ix.active_patients.append(pid)
        if p.get("primary_doctor_id"):
            ix.patients_with_primary.append(pid)
        else:
            ix.patients_without_primary.append(pid)

        if p["balance_due"] > 0:
            ix.patients_with_balance.append(pid)
        if p["balance_due"] > 500:
            ix.patients_high_balance.append(pid)

        iid = p.get("insurance_id")
        if iid and iid in db["insurance"]:
            ins = db["insurance"][iid]
            if ins["status"] == "active":
                ix.patients_with_active_insurance.append(pid)
            elif ins["status"] == "expired":
                ix.patients_with_expired_insurance.append(pid)
        else:
            ix.patients_uninsured.append(pid)

        if patient_has_recent_visit(db, pid):
            ix.patients_with_recent_visit.append(pid)
        else:
            ix.patients_without_recent_visit.append(pid)

    from datetime import datetime, timedelta

    ref_date = datetime.strptime(TODAY, "%Y-%m-%d")
    for aid, a in db["appointments"].items():
        if a["status"] not in ("scheduled", "confirmed"):
            continue
        adate = datetime.strptime(f"{a['date']} {a['time']}", "%Y-%m-%d %H:%M")
        if adate <= ref_date:
            continue
        patient_pid = a["patient_id"]
        if patient_pid in _ambiguous:
            continue
        ix.future_scheduled.append(aid)
        hours_until = (adate - ref_date).total_seconds() / 3600
        if hours_until < 24:
            ix.future_cancellable_soon.append(aid)
        else:
            ix.future_reschedulable.append(aid)

    for rxid, rx in db["prescriptions"].items():
        if rx["patient_id"] in _ambiguous:
            continue
        pid = rx["patient_id"]
        if rx["controlled_substance"]:
            ix.controlled_prescriptions.append(rxid)
            continue
        if rx["refills_remaining"] <= 0:
            ix.no_refills_prescriptions.append(rxid)
            continue
        if not patient_has_recent_visit(db, pid):
            ix.needs_visit_prescriptions.append(rxid)
            continue
        ix.refillable_prescriptions.append(rxid)

    for rid, r in db["referrals"].items():
        if r["patient_id"] in _ambiguous:
            continue
        if r["status"] == "pending" and r["expiry_date"] >= TODAY:
            ix.pending_referrals.append(rid)
        elif r["status"] == "expired" or r["expiry_date"] < TODAY:
            ix.expired_referrals.append(rid)

    for iid, inv in db["invoices"].items():
        if inv["patient_id"] in _ambiguous:
            continue
        if inv["status"] == "pending":
            ix.pending_invoices.append(iid)
        elif inv["status"] == "overdue":
            ix.overdue_invoices.append(iid)
        if inv["patient_responsibility"] > 500 and inv["status"] in (
            "pending",
            "overdue",
        ):
            ix.large_invoices.append(iid)

    for lid, lr in db["lab_results"].items():
        if lr["patient_id"] in _ambiguous:
            continue
        if lr["status"] == "pending":
            ix.pending_labs.append(lid)
        elif lr["status"] in ("completed", "reviewed"):
            ix.completed_labs.append(lid)

    for did, d in db["doctors"].items():
        if d["specialty"] == "general" and d["accepting_new_patients"]:
            ix.accepting_general.append(did)
        ix.specialist_doctors.setdefault(d["specialty"], []).append(did)

    return ix


# ---------------------------------------------------------------------------
# Persona System
# ---------------------------------------------------------------------------


@dataclass
class Persona:
    label: str
    instructions: str
    auth: str  # "name_dob" always for clinic
    difficulty: str


EASY_PERSONAS = [
    Persona(
        "Friendly and direct patient",
        "Provide all requested information promptly and clearly. Be cooperative and concise.",
        "name_dob",
        "easy",
    ),
    Persona(
        "Organized, knows their medical info",
        "You know your medical history well. Provide information concisely and politely.",
        "name_dob",
        "easy",
    ),
]

MEDIUM_PERSONAS = [
    Persona(
        "Busy professional, terse answers",
        "You have limited time. Be terse and direct. Give short answers. Omit details you assume the agent can figure out.",
        "name_dob",
        "medium",
    ),
    Persona(
        "Provides info gradually",
        "Don't volunteer all information at once. Wait for the agent to ask for specific details before providing them. Answer one question at a time.",
        "name_dob",
        "medium",
    ),
    Persona(
        "Distracted parent",
        "You are scheduling for your child or while managing kids. Your responses may be slightly scattered. You might answer a question, then go back to add something you forgot.",
        "name_dob",
        "medium",
    ),
]

HARD_PERSONAS = [
    Persona(
        "Anxious patient",
        "You are worried about your health. Ask many questions about what's going to happen. Express anxiety frequently. You might need reassurance before providing details.",
        "name_dob",
        "hard",
    ),
    Persona(
        "Confused elderly patient",
        "You are not very familiar with medical terminology or clinic procedures. You might confuse terms (say 'refill' when you mean 'appointment'). You need patient guidance.",
        "name_dob",
        "hard",
    ),
    Persona(
        "Frustrated patient",
        "You are frustrated about a billing issue or long wait times. Vent before giving details. Your responses are curt. The agent may need to ask clarifying questions multiple times.",
        "name_dob",
        "hard",
    ),
    Persona(
        "Vague about medical details",
        "You don't remember exact medication names or doctor names. Describe things approximately: 'my heart medicine' instead of 'lisinopril', 'the doctor I usually see' instead of a specific name.",
        "name_dob",
        "hard",
    ),
    Persona(
        "Nervous first-time patient",
        "You are a new patient unfamiliar with the clinic system. You're unsure about procedures and ask the agent to walk you through each step.",
        "name_dob",
        "hard",
    ),
]

ALL_EASY_MEDIUM = EASY_PERSONAS + MEDIUM_PERSONAS


def pick_easy_persona() -> Persona:
    return random.choice(ALL_EASY_MEDIUM)


def pick_hard_persona() -> Persona:
    return random.choice(HARD_PERSONAS)


# ---------------------------------------------------------------------------
# Task builder helpers
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
    actions: list[dict],
    env_assertions: list[dict] | None = None,
    nl_assertions: list[str] | None = None,
    reward_basis: list[str] | None = None,
) -> dict:
    if reward_basis is None:
        reward_basis = ["ACTION"]
    return {
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
                "domain": "clinic",
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


def action(action_id: str, name: str, arguments: dict, info: str, compare_args=None):
    d = {
        "action_id": action_id,
        "name": name,
        "arguments": arguments,
        "info": info,
    }
    if compare_args is not None:
        d["compare_args"] = compare_args
    return d


def env_assert(func_name: str, arguments: dict):
    return {
        "env_type": "assistant",
        "func_name": func_name,
        "arguments": arguments,
    }


# ---------------------------------------------------------------------------
# Tier 1: Simple Single-Action Generators
# ---------------------------------------------------------------------------


def gen_book_appointment(db, ix, n=8):
    """Book a general checkup. n bases -> 2n tasks."""
    tasks = []
    eligible = [
        pid
        for pid in ix.patients_with_primary
        if patient_has_active_insurance(db, pid)
    ]
    random.shuffle(eligible)

    general_docs = ix.accepting_general[:]
    random.shuffle(general_docs)

    count = 0
    for pid in eligible:
        if count >= n or not general_docs:
            break
        patient = db["patients"][pid]
        did = patient["primary_doctor_id"]
        if did not in db["doctors"]:
            continue
        doctor = db["doctors"][did]
        cid = doctor["clinic_id"]
        cn = clinic_name(db, cid)
        name = patient["name"]
        dob = patient["dob"]
        dname = doctor["name"]
        track_use(pid)

        # Pick a future date
        from datetime import datetime, timedelta

        ref = datetime.strptime(TODAY, "%Y-%m-%d")
        date = (ref + timedelta(days=random.randint(3, 30))).strftime("%Y-%m-%d")
        time_str = f"{random.randint(9, 15):02d}:00"

        acts = [
            action(
                "book_1",
                "book_appointment",
                {
                    "patient_id": pid,
                    "doctor_id": did,
                    "clinic_id": cid,
                    "date": date,
                    "time": time_str,
                    "appointment_type": "checkup",
                },
                f"Book checkup for {name} with {dname}",
                compare_args=["patient_id", "doctor_id", "clinic_id", "appointment_type"],
            )
        ]
        asserts = [
            env_assert(
                "assert_appointment_exists_for_patient",
                {"patient_id": pid, "doctor_id": did},
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"book_checkup_{count + 1}a",
                "Test booking a general checkup appointment",
                "Appointments need patient, doctor, clinic, date, time, type. Insurance must be active for non-urgent.",
                f"{name} books checkup with {dname} at {cn}.",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to book a routine checkup. {pa.instructions}",
                f"I'd like to schedule a checkup with {dname} at {cn}.",
                f"Your name is {name}, DOB {dob}. You want a checkup with {dname}. You're flexible on date.",
                "You don't know specific available slots.",
                f"{name} wants checkup with {dname} at {cn}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"book_checkup_{count + 1}b",
                "Test booking checkup with vague patient request",
                "Appointments need patient, doctor, clinic, date, time, type. Insurance must be active for non-urgent.",
                f"{name} vaguely requests a doctor visit.",
                pb.label,
                f"You are {name} (DOB: {dob}). You want to see your doctor. {pb.instructions}",
                "I need to see my doctor for a regular visit... it's been a while.",
                f"Your name is {name}, DOB {dob}. Your doctor is {dname}. You want a general checkup.",
                "You don't know available times or the clinic details.",
                f"{name} vaguely wants a doctor visit. Agent should identify doctor and book checkup.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
        count += 1
    return tasks


def gen_cancel_appointment(db, ix, n=6):
    """Cancel a future appointment. n bases -> 2n tasks."""
    tasks = []
    cancellable = list(ix.future_reschedulable)
    random.shuffle(cancellable)

    for i, aid in enumerate(cancellable[:n]):
        appt = db["appointments"][aid]
        pid = appt["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        did = appt["doctor_id"]
        dname = doctor_name(db, did)
        date = appt["date"]
        time_str = appt["time"]
        track_use(pid)

        acts = [
            action(
                "cancel_1",
                "cancel_appointment",
                {"appointment_id": aid, "reason": "patient request"},
                f"Cancel appointment {aid}",
                compare_args=["appointment_id"],
            )
        ]
        asserts = [
            env_assert(
                "assert_appointment_status",
                {"appointment_id": aid, "expected_status": "cancelled"},
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"cancel_appt_{i + 1}a",
                "Test cancelling a future appointment",
                "Cancellations <24h incur $50 fee; <4h incur $100. These are >24h away.",
                f"{name} cancels appointment on {date} with {dname}.",
                pa.label,
                f"You are {name} (DOB: {dob}). You need to cancel an appointment. {pa.instructions}",
                f"I need to cancel my appointment on {date} at {time_str} with {dname}.",
                f"Your name is {name}, DOB {dob}. Appointment on {date} at {time_str} with {dname}.",
                "You don't know the appointment ID.",
                f"{name} cancels {date} appointment with {dname}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"cancel_appt_{i + 1}b",
                "Test cancelling appointment with vague info",
                "Cancellations <24h incur $50 fee; <4h incur $100. These are >24h away.",
                f"{name} vaguely describes appointment to cancel.",
                pb.label,
                f"You are {name} (DOB: {dob}). You need to cancel a doctor appointment. {pb.instructions}",
                "I need to cancel my upcoming doctor appointment... I'm not going to be able to make it.",
                f"Your name is {name}, DOB {dob}. You have an appointment on {date} but only know it's 'coming up soon'.",
                "You don't remember the exact date or doctor name off the top of your head. If asked, you can provide your DOB and name.",
                f"{name} vaguely wants to cancel. Agent should look up and cancel.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_reschedule_appointment(db, ix, n=5):
    """Reschedule a future appointment. n bases -> 2n tasks."""
    tasks = []
    reschedulable = list(ix.future_reschedulable)
    random.shuffle(reschedulable)

    from datetime import datetime, timedelta

    ref = datetime.strptime(TODAY, "%Y-%m-%d")

    for i, aid in enumerate(reschedulable[:n]):
        appt = db["appointments"][aid]
        pid = appt["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        did = appt["doctor_id"]
        dname = doctor_name(db, did)
        old_date = appt["date"]
        new_date = (ref + timedelta(days=random.randint(7, 45))).strftime("%Y-%m-%d")
        new_time = f"{random.randint(9, 15):02d}:00"
        track_use(pid)

        acts = [
            action(
                "reschedule_1",
                "reschedule_appointment",
                {"appointment_id": aid, "date": new_date, "time": new_time},
                f"Reschedule {aid} to {new_date}",
                compare_args=["appointment_id"],
            )
        ]

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"reschedule_appt_{i + 1}a",
                "Test rescheduling an appointment",
                "Rescheduling moves the appointment without a cancellation fee.",
                f"{name} reschedules from {old_date} to {new_date}.",
                pa.label,
                f"You are {name} (DOB: {dob}). You need to reschedule your appointment. {pa.instructions}",
                f"I need to move my appointment on {old_date} with {dname} to a different day.",
                f"Your name is {name}, DOB {dob}. Current appointment is {old_date} with {dname}.",
                "You don't know the appointment ID. You're flexible on the new date.",
                f"{name} reschedules from {old_date}.",
                acts,
                reward_basis=["ACTION"],
            )
        )

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"reschedule_appt_{i + 1}b",
                "Test rescheduling with vague info",
                "Rescheduling moves the appointment without a cancellation fee.",
                f"{name} vaguely asks to move appointment.",
                pb.label,
                f"You are {name} (DOB: {dob}). You need to change your upcoming appointment. {pb.instructions}",
                "I need to change when I'm seeing the doctor... the current time doesn't work anymore.",
                f"Your name is {name}, DOB {dob}. You have an appointment coming up but can't remember exactly when.",
                "You don't remember the date, time, or doctor name initially.",
                f"{name} vaguely wants to reschedule. Agent should look up and reschedule.",
                acts,
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_refill_prescription(db, ix, n=6):
    """Refill eligible prescription. n bases -> 2n tasks."""
    tasks = []
    refillable = list(ix.refillable_prescriptions)
    random.shuffle(refillable)

    for i, rxid in enumerate(refillable[:n]):
        rx = db["prescriptions"][rxid]
        pid = rx["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        med = rx["medication"]
        dosage = rx["dosage"]
        refills = rx["refills_remaining"]
        track_use(pid)

        acts = [
            action(
                "refill_1",
                "refill_prescription",
                {"prescription_id": rxid},
                f"Refill {med} for {name}",
            )
        ]
        asserts = [
            env_assert(
                "assert_prescription_refills",
                {"prescription_id": rxid, "expected_refills": refills - 1},
            )
        ]

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"refill_rx_{i + 1}a",
                "Test prescription refill for eligible patient",
                "Refills require visit in last 12 months, remaining refills, and non-controlled substance.",
                f"{name} refills {med} {dosage} ({refills} refills left).",
                pa.label,
                f"You are {name} (DOB: {dob}). You need a prescription refill. {pa.instructions}",
                f"I need to refill my {med} prescription.",
                f"Your name is {name}, DOB {dob}. You take {med} {dosage}.",
                "You don't know the prescription ID or how many refills are left.",
                f"{name} refills {med}. Eligible ({refills} refills, recent visit).",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        pb = pick_hard_persona()
        vague_med = med.split()[0][:4] + "..." if len(med) > 4 else med
        tasks.append(
            make_task(
                f"refill_rx_{i + 1}b",
                "Test prescription refill with vague medication description",
                "Refills require visit in last 12 months, remaining refills, and non-controlled substance.",
                f"{name} vaguely describes {med} for refill.",
                pb.label,
                f"You are {name} (DOB: {dob}). You need more of your medication. {pb.instructions}",
                f"I'm running low on my medication... I think it starts with '{vague_med}'.",
                f"Your name is {name}, DOB {dob}. Your medication is {med} but you only vaguely remember it as '{vague_med}'.",
                "You don't remember the exact medication name or prescription details.",
                f"{name} vaguely describes {med}. Agent should identify and refill.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_make_payment(db, ix, n=5):
    """Make payment on invoice. n bases -> 2n tasks."""
    tasks = []
    payable = list(ix.pending_invoices + ix.overdue_invoices)
    # Filter to invoices where patient has a payment method
    payable = [
        iid
        for iid in payable
        if db["patients"][db["invoices"][iid]["patient_id"]].get("payment_method_ids")
    ]
    random.shuffle(payable)

    for i, iid in enumerate(payable[:n]):
        inv = db["invoices"][iid]
        pid = inv["patient_id"]
        patient = db["patients"][pid]
        name = patient["name"]
        dob = patient["dob"]
        amount = inv["patient_responsibility"]
        pmid = patient["payment_method_ids"][0]
        track_use(pid)

        acts = [
            action(
                "pay_1",
                "make_payment",
                {"invoice_id": iid, "amount": amount, "payment_method_id": pmid},
                f"Pay ${amount:.2f} on {iid}",
                compare_args=["invoice_id"],
            )
        ]
        asserts = [
            env_assert(
                "assert_invoice_status",
                {"invoice_id": iid, "expected_status": "paid"},
            )
        ]

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"make_payment_{i + 1}a",
                "Test making a payment on an invoice",
                "Payments reduce patient_responsibility. Full payment marks invoice as paid.",
                f"{name} pays ${amount:.2f} on invoice {iid}.",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to pay a medical bill. {pa.instructions}",
                f"I'd like to pay my outstanding balance.",
                f"Your name is {name}, DOB {dob}. You want to pay your bill in full.",
                "You don't know the exact amount or invoice ID. Use the card on file.",
                f"{name} pays invoice {iid} in full.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"make_payment_{i + 1}b",
                "Test payment with frustrated patient",
                "Payments reduce patient_responsibility. Full payment marks invoice as paid.",
                f"{name} pays bill after difficult interaction.",
                pb.label,
                f"You are {name} (DOB: {dob}). You received a bill and want to deal with it. {pb.instructions}",
                "I got some bill from the clinic... I need to take care of it.",
                f"Your name is {name}, DOB {dob}. You have an outstanding balance.",
                "You're not sure what it's for or how much. When told the amount, agree to pay in full.",
                f"{name} vaguely asks about a bill. Agent should look up and process payment.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_request_referral(db, ix, n=5):
    """Request specialist referral. Single variant tasks."""
    tasks = []
    eligible = [
        pid
        for pid in ix.patients_with_primary
        if pid not in set()  # no filter needed
    ]
    random.shuffle(eligible)
    specialties = ["dermatology", "cardiology", "orthopedics"]

    for i, pid in enumerate(eligible[:n]):
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        spec = specialties[i % len(specialties)]
        reasons = {
            "dermatology": "persistent skin rash on arms",
            "cardiology": "occasional chest discomfort during exercise",
            "orthopedics": "chronic lower back pain",
        }
        reason = reasons[spec]
        track_use(pid)

        acts = [
            action(
                "referral_1",
                "request_referral",
                {"patient_id": pid, "specialty": spec, "reason": reason},
                f"Request {spec} referral for {name}",
                compare_args=["patient_id", "specialty"],
            )
        ]
        asserts = [
            env_assert(
                "assert_referral_exists",
                {"patient_id": pid, "specialty": spec},
            )
        ]

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"request_referral_{i + 1}a",
                f"Test requesting a {spec} referral",
                "Referrals require primary doctor on file. Expire after 90 days.",
                f"{name} requests {spec} referral for {reason}.",
                pa.label,
                f"You are {name} (DOB: {dob}). You need a specialist referral. {pa.instructions}",
                f"My doctor suggested I see a {spec} specialist for {reason}.",
                f"Your name is {name}, DOB {dob}. You need a {spec} referral.",
                "You don't know the referral process details.",
                f"{name} needs {spec} referral. Has primary doctor on file.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"request_referral_{i + 1}b",
                f"Test requesting {spec} referral with vague symptoms",
                "Referrals require primary doctor on file. Expire after 90 days.",
                f"{name} vaguely describes need for {spec}.",
                pb.label,
                f"You are {name} (DOB: {dob}). You have a health concern you'd like addressed. {pb.instructions}",
                f"I've been having some issues... {reason}. I think I need to see a specialist.",
                f"Your name is {name}, DOB {dob}. You have {reason}.",
                "You don't know what type of specialist you need or the referral process.",
                f"{name} describes {reason}. Agent should identify need for {spec} referral.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Tier 2: Information & Search Generators
# ---------------------------------------------------------------------------


def gen_list_appointments(db, ix, n=4):
    """List patient's appointments. n bases -> 2n tasks."""
    tasks = []
    with_appts = [
        pid
        for pid in ix.active_patients
        if db["patients"][pid]["appointment_ids"]
    ]
    random.shuffle(with_appts)

    for i, pid in enumerate(with_appts[:n]):
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        track_use(pid)
        future_count = sum(
            1
            for aid in db["patients"][pid]["appointment_ids"]
            if db["appointments"].get(aid, {}).get("date", "") >= TODAY
            and db["appointments"].get(aid, {}).get("status") in ("scheduled", "confirmed")
        )

        acts = [
            action(
                "find_1",
                "find_patient_by_name_dob",
                {"name": name, "dob": dob},
                f"Find patient {name}",
                compare_args=[],
            ),
        ]

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"list_appts_{i + 1}a",
                "Test listing patient's appointments",
                "Find patient then list appointments.",
                f"{name} asks about upcoming appointments.",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to check your upcoming appointments. {pa.instructions}",
                "I'd like to see what appointments I have coming up.",
                f"Your name is {name}, DOB {dob}.",
                "You don't remember exactly what's scheduled.",
                f"{name} wants to see upcoming appointments.",
                acts,
                nl_assertions=[
                    f"The agent provided information about the patient's upcoming appointment(s)"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"list_appts_{i + 1}b",
                "Test listing appointments with vague request",
                "Find patient then list appointments.",
                f"{name} vaguely asks about scheduled visits.",
                pb.label,
                f"You are {name} (DOB: {dob}). {pb.instructions}",
                "I think I have something coming up at the clinic... can you check?",
                f"Your name is {name}, DOB {dob}.",
                "You're not sure what appointments you have or when.",
                f"{name} vaguely asks about schedule.",
                acts,
                nl_assertions=[
                    f"The agent provided information about the patient's upcoming appointment(s)"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_check_lab_results(db, ix, n=4):
    """Check if lab results are ready. n bases -> 2n tasks."""
    tasks = []
    labs = ix.completed_labs + ix.pending_labs
    random.shuffle(labs)

    for i, lid in enumerate(labs[:n]):
        lr = db["lab_results"][lid]
        pid = lr["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        test_name = lr["test_name"]
        status = lr["status"]
        track_use(pid)

        acts = [
            action(
                "find_1",
                "find_patient_by_name_dob",
                {"name": name, "dob": dob},
                f"Find patient {name}",
                compare_args=[],
            ),
        ]

        ready_str = "ready" if status != "pending" else "not yet ready"

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"check_lab_{i + 1}a",
                "Test checking lab result status",
                "Agent can confirm if results are ready but cannot share details. Patient must access portal or speak with doctor.",
                f"{name} asks about {test_name} results ({status}).",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to check on lab results. {pa.instructions}",
                f"I had a {test_name} done recently. Are my results back?",
                f"Your name is {name}, DOB {dob}. You had a {test_name}.",
                "You don't know if results are ready.",
                f"{name} asks about {test_name} results. Status: {status}.",
                acts,
                nl_assertions=[
                    f"The agent informed the patient that their {test_name} results are {ready_str}",
                    "The agent did NOT share detailed lab results and directed the patient to the portal or their doctor",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"check_lab_{i + 1}b",
                "Test checking lab results with anxious patient",
                "Agent can confirm if results are ready but cannot share details.",
                f"{name} anxiously asks about test results.",
                pb.label,
                f"You are {name} (DOB: {dob}). You are worried about lab results. {pb.instructions}",
                "I had some blood work done and I'm really worried... are my results in yet?",
                f"Your name is {name}, DOB {dob}. You had a {test_name} but describe it vaguely as 'blood work' or 'tests'.",
                "You don't remember exactly what test it was called.",
                f"{name} anxiously asks about lab results.",
                acts,
                nl_assertions=[
                    f"The agent informed the patient about the status of their lab results",
                    "The agent did NOT share detailed lab results and directed the patient to the portal or their doctor",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_check_insurance(db, ix, n=3):
    """Check insurance details. Single variant."""
    tasks = []
    with_ins = [
        pid for pid in ix.patients_with_active_insurance
        if db["patients"][pid].get("insurance_id")
    ]
    random.shuffle(with_ins)

    for i, pid in enumerate(with_ins[:n]):
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        iid = db["patients"][pid]["insurance_id"]
        ins = db["insurance"][iid]
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"check_insurance_{i + 1}",
                "Test checking patient's insurance details",
                "Agent can look up insurance information for verified patients.",
                f"{name} asks about their insurance coverage.",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to check your insurance info. {pa.instructions}",
                "Can you tell me what insurance you have on file for me?",
                f"Your name is {name}, DOB {dob}.",
                "You don't remember your plan details.",
                f"{name} asks about insurance on file.",
                [
                    action(
                        "find_1",
                        "find_patient_by_name_dob",
                        {"name": name, "dob": dob},
                        f"Find patient {name}",
                        compare_args=[],
                    ),
                ],
                nl_assertions=[
                    f"The agent provided insurance information including the provider name ({ins['provider']})"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_list_prescriptions(db, ix, n=3):
    """List patient's prescriptions. n bases -> 2n tasks."""
    tasks = []
    with_rx = [
        pid
        for pid in ix.active_patients
        if any(rx["patient_id"] == pid for rx in db["prescriptions"].values())
    ]
    random.shuffle(with_rx)

    for i, pid in enumerate(with_rx[:n]):
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        track_use(pid)

        acts = [
            action(
                "find_1",
                "find_patient_by_name_dob",
                {"name": name, "dob": dob},
                f"Find patient {name}",
                compare_args=[],
            ),
        ]

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"list_rx_{i + 1}a",
                "Test listing patient's prescriptions",
                "Find patient then list active prescriptions.",
                f"{name} asks about current medications.",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to see your prescriptions. {pa.instructions}",
                "Can you tell me what prescriptions I have on file?",
                f"Your name is {name}, DOB {dob}.",
                "You don't remember all your prescriptions.",
                f"{name} wants to see active prescriptions.",
                acts,
                nl_assertions=[
                    "The agent provided information about the patient's active prescriptions"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"list_rx_{i + 1}b",
                "Test listing prescriptions with confused patient",
                "Find patient then list active prescriptions.",
                f"{name} asks about 'my medicines'.",
                pb.label,
                f"You are {name} (DOB: {dob}). You want to check on your medications. {pb.instructions}",
                "I need to know what medicines I'm supposed to be taking... can you look it up?",
                f"Your name is {name}, DOB {dob}.",
                "You're not sure what you're currently prescribed.",
                f"{name} vaguely asks about medications.",
                acts,
                nl_assertions=[
                    "The agent provided information about the patient's active prescriptions"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_check_invoices(db, ix, n=3):
    """Check outstanding invoices. Single variant."""
    tasks = []
    with_balance = list(ix.patients_with_balance)
    random.shuffle(with_balance)

    for i, pid in enumerate(with_balance[:n]):
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        balance = db["patients"][pid]["balance_due"]
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"check_invoices_{i + 1}",
                "Test checking patient's outstanding invoices",
                "Agent can look up and explain invoice details.",
                f"{name} (balance ${balance:.2f}) asks about bills.",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to check your balance. {pa.instructions}",
                "Do I have any outstanding bills with the clinic?",
                f"Your name is {name}, DOB {dob}.",
                "You don't know your exact balance.",
                f"{name} asks about outstanding bills. Balance: ${balance:.2f}.",
                [
                    action(
                        "find_1",
                        "find_patient_by_name_dob",
                        {"name": name, "dob": dob},
                        f"Find patient {name}",
                        compare_args=[],
                    ),
                ],
                nl_assertions=[
                    f"The agent informed the patient about their outstanding balance"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Tier 3: Moderate Multi-Step Generators
# ---------------------------------------------------------------------------


def gen_referral_then_book(db, ix, n=5):
    """Request referral then book specialist. n bases -> 2n tasks."""
    tasks = []
    eligible = [
        pid
        for pid in ix.patients_with_primary
        if not patient_has_valid_referral(db, pid, "dermatology")
        and patient_has_active_insurance(db, pid)
    ]
    random.shuffle(eligible)
    specialties_cycle = ["dermatology", "cardiology", "orthopedics"]

    for i, pid in enumerate(eligible[:n]):
        spec = specialties_cycle[i % len(specialties_cycle)]
        # Skip if already has valid referral for this specialty
        if patient_has_valid_referral(db, pid, spec):
            continue
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        track_use(pid)

        reasons = {
            "dermatology": "persistent skin rash",
            "cardiology": "chest discomfort during exercise",
            "orthopedics": "chronic knee pain",
        }
        reason = reasons[spec]

        acts = [
            action(
                "referral_1",
                "request_referral",
                {"patient_id": pid, "specialty": spec, "reason": reason},
                f"Request {spec} referral",
                compare_args=["patient_id", "specialty"],
            ),
            action(
                "book_1",
                "book_appointment",
                {
                    "patient_id": pid,
                    "doctor_id": "placeholder",
                    "clinic_id": "placeholder",
                    "date": "placeholder",
                    "time": "placeholder",
                    "appointment_type": "consultation",
                },
                f"Book {spec} appointment",
                compare_args=["patient_id", "appointment_type"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_referral_exists",
                {"patient_id": pid, "specialty": spec},
            )
        ]

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"referral_book_{i + 1}a",
                f"Test referral request then specialist booking ({spec})",
                "Specialist visits require a referral. Agent should request referral first, then book.",
                f"{name} needs {spec} referral + appointment.",
                pa.label,
                f"You are {name} (DOB: {dob}). You need to see a {spec} specialist. {pa.instructions}",
                f"I'd like to see a {spec} specialist for {reason}. Can you help me get an appointment?",
                f"Your name is {name}, DOB {dob}. You need a {spec} for {reason}.",
                "You don't know if you need a referral or which specialist to see.",
                f"{name} needs {spec} for {reason}. No existing referral.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"referral_book_{i + 1}b",
                f"Test referral + booking with vague symptoms ({spec})",
                "Specialist visits require a referral. Agent should request referral first, then book.",
                f"{name} vaguely describes need for specialist.",
                pb.label,
                f"You are {name} (DOB: {dob}). You have a health issue. {pb.instructions}",
                f"I've been dealing with {reason} for a while now... I think I need to see someone about it.",
                f"Your name is {name}, DOB {dob}. Your issue is {reason}.",
                "You don't know what type of specialist you need.",
                f"{name} describes {reason}. Agent should identify specialty, request referral, and book.",
                [acts[0]],  # only require referral action for hard variant
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_pay_then_book(db, ix, n=4):
    """Pay outstanding balance then book appointment. n bases -> tasks."""
    tasks = []
    eligible = [
        pid
        for pid in ix.patients_with_balance
        if db["patients"][pid]["balance_due"] <= 300
        and db["patients"][pid].get("payment_method_ids")
        and db["patients"][pid].get("primary_doctor_id")
    ]
    random.shuffle(eligible)

    for i, pid in enumerate(eligible[:n]):
        patient = db["patients"][pid]
        name = patient["name"]
        dob = patient["dob"]
        balance = patient["balance_due"]
        pmid = patient["payment_method_ids"][0]
        did = patient["primary_doctor_id"]
        dname = doctor_name(db, did)

        # Find a pending invoice
        patient_invoices = [
            inv
            for inv in db["invoices"].values()
            if inv["patient_id"] == pid and inv["status"] in ("pending", "overdue")
        ]
        if not patient_invoices:
            continue
        inv = patient_invoices[0]
        iid = inv["invoice_id"]
        amount = inv["patient_responsibility"]
        track_use(pid)

        from datetime import datetime, timedelta

        ref = datetime.strptime(TODAY, "%Y-%m-%d")
        date = (ref + timedelta(days=random.randint(5, 30))).strftime("%Y-%m-%d")
        time_str = f"{random.randint(9, 15):02d}:00"

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"pay_book_{i + 1}",
                "Test paying balance then booking appointment",
                "Patient wants to clear balance and schedule a visit.",
                f"{name} pays ${amount:.2f} and books checkup.",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to pay your bill and book an appointment. {pa.instructions}",
                f"I'd like to pay my outstanding bill and also schedule a checkup with {dname}.",
                f"Your name is {name}, DOB {dob}. You want to pay your bill and book with {dname}.",
                "You don't know the exact balance or available appointment slots.",
                f"{name} pays and books. Balance ${amount:.2f}, wants checkup with {dname}.",
                [
                    action(
                        "pay_1",
                        "make_payment",
                        {"invoice_id": iid, "amount": amount, "payment_method_id": pmid},
                        f"Pay ${amount:.2f}",
                        compare_args=["invoice_id"],
                    ),
                    action(
                        "book_1",
                        "book_appointment",
                        {
                            "patient_id": pid,
                            "doctor_id": did,
                            "clinic_id": db["doctors"][did]["clinic_id"],
                            "date": date,
                            "time": time_str,
                            "appointment_type": "checkup",
                        },
                        f"Book checkup",
                        compare_args=["patient_id", "doctor_id", "appointment_type"],
                    ),
                ],
                [
                    env_assert(
                        "assert_invoice_status",
                        {"invoice_id": iid, "expected_status": "paid"},
                    )
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_update_insurance_then_book(db, ix, n=4):
    """Update expired insurance then book. n bases -> tasks."""
    tasks = []
    eligible = list(ix.patients_with_expired_insurance)
    random.shuffle(eligible)

    for i, pid in enumerate(eligible[:n]):
        patient = db["patients"][pid]
        name = patient["name"]
        dob = patient["dob"]
        track_use(pid)

        new_provider = random.choice(["Blue Cross Blue Shield", "Aetna", "UnitedHealthcare"])
        new_plan = random.choice(["Gold PPO", "Silver HMO"])
        new_group = f"GRP{random.randint(10000, 99999)}"
        new_member = f"MEM{random.randint(100000, 999999)}"

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"update_ins_book_{i + 1}",
                "Test updating expired insurance then booking",
                "Insurance must be active for non-urgent appointments. Updated insurance goes to pending_verification.",
                f"{name} updates insurance (was expired).",
                pa.label,
                f"You are {name} (DOB: {dob}). Your insurance changed and you need to update it. {pa.instructions}",
                f"I have new insurance — {new_provider}, {new_plan}. My group number is {new_group} and member ID is {new_member}. I'd also like to schedule a checkup.",
                f"Your name is {name}, DOB {dob}. New insurance: {new_provider}, {new_plan}, group {new_group}, member {new_member}.",
                "You don't know if the old insurance is still on file.",
                f"{name} updates insurance and wants to book. Note: updated insurance goes to pending_verification.",
                [
                    action(
                        "update_ins_1",
                        "update_insurance",
                        {
                            "patient_id": pid,
                            "provider": new_provider,
                            "plan_name": new_plan,
                            "group_number": new_group,
                            "member_id": new_member,
                        },
                        f"Update insurance for {name}",
                        compare_args=["patient_id"],
                    ),
                ],
                nl_assertions=[
                    "The agent informed the patient that updated insurance needs verification before booking non-urgent appointments"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_cancel_reschedule(db, ix, n=4):
    """Cancel one appointment and reschedule to different date. n bases -> tasks."""
    tasks = []
    reschedulable = list(ix.future_reschedulable)
    random.shuffle(reschedulable)

    from datetime import datetime, timedelta

    ref = datetime.strptime(TODAY, "%Y-%m-%d")

    for i, aid in enumerate(reschedulable[:n]):
        appt = db["appointments"][aid]
        pid = appt["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        dname = doctor_name(db, appt["doctor_id"])
        old_date = appt["date"]
        new_date = (ref + timedelta(days=random.randint(14, 45))).strftime("%Y-%m-%d")
        new_time = f"{random.randint(9, 15):02d}:00"
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"cancel_reschedule_{i + 1}",
                "Test rescheduling an appointment to new date",
                "Rescheduling updates date/time without cancellation fee.",
                f"{name} moves appointment from {old_date} to {new_date}.",
                pa.label,
                f"You are {name} (DOB: {dob}). You need to move your appointment. {pa.instructions}",
                f"I need to reschedule my appointment on {old_date} with {dname}. Can we move it to sometime around {new_date}?",
                f"Your name is {name}, DOB {dob}. Current appointment: {old_date} with {dname}.",
                "You don't know the appointment ID.",
                f"{name} reschedules from {old_date} to around {new_date}.",
                [
                    action(
                        "reschedule_1",
                        "reschedule_appointment",
                        {"appointment_id": aid, "date": new_date, "time": new_time},
                        f"Reschedule to {new_date}",
                        compare_args=["appointment_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Tier 4: Complex Multi-Step Generators
# ---------------------------------------------------------------------------


def gen_setup_payment_plan(db, ix, n=3):
    """Set up payment plan for large invoice. Single variant."""
    tasks = []
    large = list(ix.large_invoices)
    random.shuffle(large)

    for i, iid in enumerate(large[:n]):
        inv = db["invoices"][iid]
        pid = inv["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        amount = inv["patient_responsibility"]
        installments = random.choice([3, 4, 6])
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"payment_plan_{i + 1}a",
                "Test setting up a payment plan",
                "Payment plans for balances >$500, max 6 installments.",
                f"{name} sets up {installments}-installment plan for ${amount:.2f}.",
                pa.label,
                f"You are {name} (DOB: {dob}). You received a large bill and want a payment plan. {pa.instructions}",
                f"I got a bill for ${amount:.2f} and I can't pay it all at once. Can I set up a payment plan?",
                f"Your name is {name}, DOB {dob}. Bill is ${amount:.2f}. You want {installments} installments.",
                "You don't know the invoice ID.",
                f"{name} needs payment plan for ${amount:.2f}.",
                [
                    action(
                        "plan_1",
                        "setup_payment_plan",
                        {"invoice_id": iid, "installments": installments},
                        f"Set up {installments}-installment plan",
                        compare_args=["invoice_id"],
                    ),
                ],
                [
                    env_assert(
                        "assert_invoice_status",
                        {"invoice_id": iid, "expected_status": "payment_plan"},
                    )
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"payment_plan_{i + 1}b",
                "Test payment plan setup with frustrated patient",
                "Payment plans for balances >$500, max 6 installments.",
                f"{name} is frustrated about large bill.",
                pb.label,
                f"You are {name} (DOB: {dob}). You got a large unexpected bill. {pb.instructions}",
                f"I just got this huge bill and there's no way I can pay it all right now. What are my options?",
                f"Your name is {name}, DOB {dob}. You want to split payments.",
                "You don't know the exact amount or options. When told about payment plans, choose {installments} installments.",
                f"{name} needs payment plan. Agent should find invoice and set up plan.",
                [
                    action(
                        "plan_1",
                        "setup_payment_plan",
                        {"invoice_id": iid, "installments": installments},
                        f"Set up payment plan",
                        compare_args=["invoice_id"],
                    ),
                ],
                [
                    env_assert(
                        "assert_invoice_status",
                        {"invoice_id": iid, "expected_status": "payment_plan"},
                    )
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_new_patient_flow(db, ix, n=3):
    """New patient wants to establish care. Find accepting doctor, book."""
    tasks = []
    no_primary = list(ix.patients_without_primary)
    random.shuffle(no_primary)

    for i, pid in enumerate(no_primary[:n]):
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        track_use(pid)

        from datetime import datetime, timedelta

        ref = datetime.strptime(TODAY, "%Y-%m-%d")
        date = (ref + timedelta(days=random.randint(5, 30))).strftime("%Y-%m-%d")

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"new_patient_{i + 1}a",
                "Test new patient establishing care",
                "New patients need a primary doctor who accepts new patients.",
                f"{name} wants to find a primary doctor and book first appointment.",
                pa.label,
                f"You are {name} (DOB: {dob}). You're a new patient looking for a primary care doctor. {pa.instructions}",
                "I just moved to the area and need to find a primary care doctor. Can you help me get set up?",
                f"Your name is {name}, DOB {dob}. You need a primary care doctor.",
                "You don't know which doctors are available or accepting new patients.",
                f"{name} needs primary care. Agent should find accepting doctor and book.",
                [
                    action(
                        "search_docs_1",
                        "search_doctors",
                        {"specialty": "general", "accepting_new": True},
                        "Search for accepting general doctors",
                        compare_args=[],
                    ),
                    action(
                        "book_1",
                        "book_appointment",
                        {
                            "patient_id": pid,
                            "doctor_id": "placeholder",
                            "clinic_id": "placeholder",
                            "date": date,
                            "time": "placeholder",
                            "appointment_type": "checkup",
                        },
                        "Book new patient appointment",
                        compare_args=["patient_id", "appointment_type"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"new_patient_{i + 1}b",
                "Test new patient with nervous persona",
                "New patients need a primary doctor who accepts new patients.",
                f"{name} is nervous new patient.",
                pb.label,
                f"You are {name} (DOB: {dob}). You're looking for a new doctor. {pb.instructions}",
                "I need to find a doctor... I haven't been to one in a while and I'm not sure how this works.",
                f"Your name is {name}, DOB {dob}. You need a primary care doctor.",
                "You don't know what to ask for or how the process works.",
                f"{name} is a nervous new patient. Agent should guide through finding a doctor.",
                [
                    action(
                        "search_docs_1",
                        "search_doctors",
                        {"specialty": "general", "accepting_new": True},
                        "Search for accepting doctors",
                        compare_args=[],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_update_info_and_book(db, ix, n=3):
    """Update patient contact info then book. Single variant."""
    tasks = []
    eligible = list(ix.patients_with_primary)
    random.shuffle(eligible)

    for i, pid in enumerate(eligible[:n]):
        patient = db["patients"][pid]
        name = patient["name"]
        dob = patient["dob"]
        new_phone = f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}"
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"update_info_{i + 1}",
                "Test updating patient info",
                "Patient contact info can be updated by verified patients.",
                f"{name} updates phone number.",
                pa.label,
                f"You are {name} (DOB: {dob}). You have a new phone number. {pa.instructions}",
                f"I need to update my phone number to {new_phone}.",
                f"Your name is {name}, DOB {dob}. New phone: {new_phone}.",
                "You don't know your patient ID.",
                f"{name} updates phone to {new_phone}.",
                [
                    action(
                        "update_1",
                        "update_patient_info",
                        {"patient_id": pid, "phone": new_phone},
                        f"Update phone for {name}",
                        compare_args=["patient_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Tier 5: Edge Cases & Policy Violations
# ---------------------------------------------------------------------------


def gen_controlled_refill_denied(db, ix, n=3):
    """Attempt to refill controlled substance by phone. Should be denied."""
    tasks = []
    controlled = list(ix.controlled_prescriptions)
    random.shuffle(controlled)

    for i, rxid in enumerate(controlled[:n]):
        rx = db["prescriptions"][rxid]
        pid = rx["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        med = rx["medication"]
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"controlled_deny_{i + 1}",
                "Test denying controlled substance phone refill",
                "Controlled substances cannot be refilled by phone. Patient must see doctor.",
                f"{name} tries to refill controlled substance {med}.",
                pa.label,
                f"You are {name} (DOB: {dob}). You need a refill on your medication. {pa.instructions}",
                f"I need to refill my {med} prescription.",
                f"Your name is {name}, DOB {dob}. You take {med}.",
                "You don't know this is a controlled substance that requires an in-person visit.",
                f"{name} requests {med} refill. Should be denied — controlled substance.",
                [],
                nl_assertions=[
                    f"The agent explained that {med} is a controlled substance and cannot be refilled by phone",
                    "The agent recommended the patient schedule an appointment with their doctor",
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_no_refills_remaining(db, ix, n=3):
    """Attempt refill with 0 refills. Should be denied."""
    tasks = []
    no_refills = list(ix.no_refills_prescriptions)
    random.shuffle(no_refills)

    for i, rxid in enumerate(no_refills[:n]):
        rx = db["prescriptions"][rxid]
        pid = rx["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        med = rx["medication"]
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"no_refills_{i + 1}",
                "Test denying refill with no refills remaining",
                "No refills remaining requires a new prescription from the doctor.",
                f"{name} tries to refill {med} (0 refills left).",
                pa.label,
                f"You are {name} (DOB: {dob}). You need more of your medication. {pa.instructions}",
                f"I need a refill on {med}.",
                f"Your name is {name}, DOB {dob}. You take {med}.",
                "You don't know how many refills are left.",
                f"{name} requests {med} refill. 0 refills remaining.",
                [],
                nl_assertions=[
                    f"The agent explained that no refills remain on the {med} prescription",
                    "The agent recommended scheduling an appointment for a new prescription",
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_needs_visit_for_refill(db, ix, n=3):
    """Refill denied because patient hasn't been seen in 12 months."""
    tasks = []
    needs_visit = list(ix.needs_visit_prescriptions)
    random.shuffle(needs_visit)

    for i, rxid in enumerate(needs_visit[:n]):
        rx = db["prescriptions"][rxid]
        pid = rx["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        med = rx["medication"]
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"needs_visit_refill_{i + 1}",
                "Test denying refill due to no recent visit",
                "Refills require a visit within the last 12 months.",
                f"{name} tries to refill {med} but hasn't been seen recently.",
                pa.label,
                f"You are {name} (DOB: {dob}). You need a prescription refill. {pa.instructions}",
                f"I need to refill my {med}.",
                f"Your name is {name}, DOB {dob}. You take {med}.",
                "You don't know that a recent visit is required for refills.",
                f"{name} requests {med} refill. No visit in 12 months.",
                [],
                nl_assertions=[
                    "The agent explained that a visit within the last 12 months is required for refills",
                    "The agent offered to help schedule a follow-up appointment",
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_specialist_no_referral(db, ix, n=4):
    """Try to book specialist without referral. Should explain requirement."""
    tasks = []
    eligible = [
        pid
        for pid in ix.patients_with_primary
        if patient_has_active_insurance(db, pid)
    ]
    random.shuffle(eligible)
    specialties = ["dermatology", "cardiology", "orthopedics", "dental"]

    count = 0
    for pid in eligible:
        if count >= n:
            break
        spec = specialties[count % len(specialties)]
        if patient_has_valid_referral(db, pid, spec):
            continue
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        track_use(pid)

        spec_doctors = ix.specialist_doctors.get(spec, [])
        if not spec_doctors:
            continue

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"no_referral_{count + 1}",
                f"Test explaining referral requirement for {spec}",
                "Specialist visits require a referral. Agent should explain and offer to request one.",
                f"{name} wants {spec} appointment without referral.",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to book a specialist appointment. {pa.instructions}",
                f"I'd like to book an appointment with a {spec} specialist.",
                f"Your name is {name}, DOB {dob}. You want a {spec} appointment.",
                "You don't know that you need a referral first.",
                f"{name} wants {spec} without referral. Agent should explain referral requirement.",
                [
                    action(
                        "referral_1",
                        "request_referral",
                        {"patient_id": pid, "specialty": spec, "reason": f"{spec} consultation"},
                        f"Request {spec} referral",
                        compare_args=["patient_id", "specialty"],
                    ),
                ],
                nl_assertions=[
                    f"The agent explained that a referral is required for {spec} specialist visits"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
        count += 1
    return tasks


def gen_medical_advice_transfer(db, ix, n=3):
    """Patient asks for medical advice. Agent should transfer to clinical staff."""
    tasks = []
    patients = list(ix.active_patients)
    random.shuffle(patients)

    symptoms = [
        ("severe headache and blurred vision", "neurological symptoms"),
        ("chest pain that comes and goes", "cardiac symptoms"),
        ("a rash that won't go away and is spreading", "dermatological symptoms"),
    ]

    for i, pid in enumerate(patients[:n]):
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        symptom_desc, symptom_type = symptoms[i % len(symptoms)]
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"medical_advice_{i + 1}",
                "Test transferring to clinical staff for medical questions",
                "Agent cannot provide medical advice, interpret symptoms, or discuss diagnoses. Must transfer to clinical staff.",
                f"{name} asks about {symptom_type}.",
                pa.label,
                f"You are {name} (DOB: {dob}). You have a medical question. {pa.instructions}",
                f"I've been experiencing {symptom_desc}. What do you think it could be? Should I be worried?",
                f"Your name is {name}, DOB {dob}. You are experiencing {symptom_desc}.",
                "You want medical advice about your symptoms.",
                f"{name} asks for medical advice about {symptom_type}. Agent should transfer.",
                [
                    action(
                        "transfer_1",
                        "transfer_to_human_agents",
                        {"summary": f"Patient {name} reporting {symptom_type}"},
                        "Transfer to clinical staff",
                        compare_args=[],
                    ),
                ],
                nl_assertions=[
                    "The agent explained that they cannot provide medical advice",
                    "The agent offered to transfer the patient to clinical staff or their doctor",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_lab_results_no_share(db, ix, n=3):
    """Patient wants detailed lab results. Agent should say they can't share details."""
    tasks = []
    completed = list(ix.completed_labs)
    random.shuffle(completed)

    for i, lid in enumerate(completed[:n]):
        lr = db["lab_results"][lid]
        pid = lr["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        test = lr["test_name"]
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"lab_no_share_{i + 1}",
                "Test refusing to share detailed lab results",
                "Agent can confirm results status but cannot share details. Patient must use portal or speak with doctor.",
                f"{name} wants detailed {test} results.",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to know your lab results. {pa.instructions}",
                f"My {test} results should be in by now. Can you tell me what the numbers are?",
                f"Your name is {name}, DOB {dob}. You had a {test}.",
                "You want the actual test values and numbers.",
                f"{name} wants detailed {test} results. Agent should confirm status but not share details.",
                [],
                nl_assertions=[
                    f"The agent confirmed the status of the {test} results",
                    "The agent explained they cannot share detailed lab results",
                    "The agent directed the patient to the patient portal or their doctor for detailed results",
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_late_cancel_fee(db, ix, n=2):
    """Cancel appointment within 24 hours. Fee should be assessed."""
    tasks = []
    soon = list(ix.future_cancellable_soon)
    random.shuffle(soon)

    for i, aid in enumerate(soon[:n]):
        appt = db["appointments"][aid]
        pid = appt["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        dname = doctor_name(db, appt["doctor_id"])
        date = appt["date"]
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"late_cancel_{i + 1}",
                "Test late cancellation with fee",
                "Cancellations <24h incur $50 fee; <4h incur $100.",
                f"{name} cancels within 24 hours. Fee applies.",
                pa.label,
                f"You are {name} (DOB: {dob}). You need to cancel a very soon appointment. {pa.instructions}",
                f"I need to cancel my appointment with {dname} today — something came up.",
                f"Your name is {name}, DOB {dob}. Appointment on {date} with {dname}.",
                "You don't know there's a cancellation fee for late cancellations.",
                f"{name} cancels within 24h. Fee of $50 or $100 applies.",
                [
                    action(
                        "cancel_1",
                        "cancel_appointment",
                        {"appointment_id": aid, "reason": "patient request"},
                        f"Cancel appointment {aid}",
                        compare_args=["appointment_id"],
                    ),
                ],
                [
                    env_assert(
                        "assert_appointment_status",
                        {"appointment_id": aid, "expected_status": "cancelled"},
                    )
                ],
                nl_assertions=[
                    "The agent informed the patient about the late cancellation fee"
                ],
                reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_payment_plan_too_small(db, ix, n=2):
    """Try to set up payment plan for invoice under $500."""
    tasks = []
    small_invoices = [
        iid
        for iid in ix.pending_invoices + ix.overdue_invoices
        if 0 < db["invoices"][iid]["patient_responsibility"] < 500
    ]
    random.shuffle(small_invoices)

    for i, iid in enumerate(small_invoices[:n]):
        inv = db["invoices"][iid]
        pid = inv["patient_id"]
        name = patient_name(db, pid)
        dob = db["patients"][pid]["dob"]
        amount = inv["patient_responsibility"]
        track_use(pid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"plan_too_small_{i + 1}",
                "Test denying payment plan for small balance",
                "Payment plans only for balances >$500.",
                f"{name} requests payment plan for ${amount:.2f} (<$500).",
                pa.label,
                f"You are {name} (DOB: {dob}). You want to set up a payment plan. {pa.instructions}",
                f"Can I set up a payment plan for my bill?",
                f"Your name is {name}, DOB {dob}. Balance is ${amount:.2f}.",
                "You don't know the minimum for payment plans.",
                f"{name} wants payment plan for ${amount:.2f}. Under $500 minimum.",
                [],
                nl_assertions=[
                    "The agent explained that payment plans are only available for balances over $500",
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Main Generator
# ---------------------------------------------------------------------------


def generate_all(db: dict) -> list[dict]:
    ix = build_indexes(db)
    all_tasks = []

    # Tier 1: Simple single-action (~70 tasks)
    all_tasks.extend(gen_book_appointment(db, ix, n=10))
    all_tasks.extend(gen_cancel_appointment(db, ix, n=8))
    all_tasks.extend(gen_reschedule_appointment(db, ix, n=6))
    all_tasks.extend(gen_refill_prescription(db, ix, n=8))
    all_tasks.extend(gen_make_payment(db, ix, n=6))
    all_tasks.extend(gen_request_referral(db, ix, n=6))

    # Tier 2: Information & search (~35 tasks)
    all_tasks.extend(gen_list_appointments(db, ix, n=5))
    all_tasks.extend(gen_check_lab_results(db, ix, n=5))
    all_tasks.extend(gen_check_insurance(db, ix, n=4))
    all_tasks.extend(gen_list_prescriptions(db, ix, n=4))
    all_tasks.extend(gen_check_invoices(db, ix, n=4))

    # Tier 3: Moderate multi-step (~45 tasks)
    all_tasks.extend(gen_referral_then_book(db, ix, n=6))
    all_tasks.extend(gen_pay_then_book(db, ix, n=5))
    all_tasks.extend(gen_update_insurance_then_book(db, ix, n=5))
    all_tasks.extend(gen_cancel_reschedule(db, ix, n=5))

    # Tier 4: Complex multi-step (~25 tasks)
    all_tasks.extend(gen_setup_payment_plan(db, ix, n=4))
    all_tasks.extend(gen_new_patient_flow(db, ix, n=4))
    all_tasks.extend(gen_update_info_and_book(db, ix, n=4))

    # Tier 5: Edge cases & policy violations (~35 tasks)
    all_tasks.extend(gen_controlled_refill_denied(db, ix, n=4))
    all_tasks.extend(gen_no_refills_remaining(db, ix, n=4))
    all_tasks.extend(gen_needs_visit_for_refill(db, ix, n=4))
    all_tasks.extend(gen_specialist_no_referral(db, ix, n=5))
    all_tasks.extend(gen_medical_advice_transfer(db, ix, n=3))
    all_tasks.extend(gen_lab_results_no_share(db, ix, n=4))
    all_tasks.extend(gen_late_cancel_fee(db, ix, n=2))
    all_tasks.extend(gen_payment_plan_too_small(db, ix, n=3))

    return all_tasks


def build_splits(tasks: list[dict]) -> dict[str, list[str]]:
    all_ids = [t["id"] for t in tasks]
    easy_ids = [tid for tid in all_ids if tid.endswith("a") or not any(tid.endswith(c) for c in "ab")]
    hard_ids = [tid for tid in all_ids if tid.endswith("b")]

    return {
        "base": all_ids,
        "easy": easy_ids,
        "hard": hard_ids,
    }


def print_stats(tasks):
    print(f"Total tasks: {len(tasks)}")
    # Count by tier
    tier_names = {
        "book_checkup": "T1", "cancel_appt": "T1", "reschedule_appt": "T1",
        "refill_rx": "T1", "make_payment": "T1", "request_referral": "T1",
        "list_appts": "T2", "check_lab": "T2", "check_insurance": "T2",
        "list_rx": "T2", "check_invoices": "T2",
        "referral_book": "T3", "pay_book": "T3", "update_ins_book": "T3",
        "cancel_reschedule": "T3",
        "payment_plan": "T4", "new_patient": "T4", "update_info": "T4",
        "controlled_deny": "T5", "no_refills": "T5", "needs_visit_refill": "T5",
        "no_referral": "T5", "medical_advice": "T5", "lab_no_share": "T5",
        "late_cancel": "T5", "plan_too_small": "T5",
    }
    tier_counts: dict[str, int] = {}
    for t in tasks:
        tid = t["id"]
        # Extract base name (remove trailing number and variant letter)
        base = "_".join(tid.rsplit("_", 1)[0].split("_"))
        tier = "??"
        for prefix, tn in tier_names.items():
            if tid.startswith(prefix):
                tier = tn
                break
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    print("\nTier distribution:")
    for tier in sorted(tier_counts):
        print(f"  {tier}: {tier_counts[tier]}")

    easy = sum(1 for t in tasks if t["id"].endswith("a") or not any(t["id"].endswith(c) for c in "ab"))
    hard = sum(1 for t in tasks if t["id"].endswith("b"))
    print(f"\nEasy variants: {easy}")
    print(f"Hard variants: {hard}")

    # Reward basis distribution
    rb_counts: dict[str, int] = {}
    for t in tasks:
        rb = tuple(sorted(t["evaluation_criteria"]["reward_basis"]))
        rb_key = "+".join(rb)
        rb_counts[rb_key] = rb_counts.get(rb_key, 0) + 1
    print("\nReward basis distribution:")
    for rb, c in sorted(rb_counts.items()):
        print(f"  {rb}: {c}")


if __name__ == "__main__":
    import sys

    random.seed(SEED)
    db = load_db()
    tasks = generate_all(db)

    if "--stats" in sys.argv:
        print_stats(tasks)
        sys.exit(0)

    with open(TASKS_PATH, "w") as f:
        json.dump(tasks, f, indent=2)

    splits = build_splits(tasks)
    with open(SPLIT_TASKS_PATH, "w") as f:
        json.dump(splits, f, indent=2)

    print_stats(tasks)
    print(f"\nWrote {len(tasks)} tasks to {TASKS_PATH}")
    print(f"Wrote splits to {SPLIT_TASKS_PATH}")
