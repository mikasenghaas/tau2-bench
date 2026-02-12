#!/usr/bin/env python3
"""Generate clinic database.

Standalone script (stdlib only). Deterministic via random.seed(42).

Usage:
    python generate_db.py
"""

import json
import random
from pathlib import Path

random.seed(42)
HERE = Path(__file__).parent

TODAY = "2025-10-15"

# ── Name pools ────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Alice", "Bob", "Carol", "David", "Elena", "Frank", "Grace", "Henry",
    "Irene", "Jack", "Karen", "Liam", "Mia", "Noah", "Olivia", "Peter",
    "Quinn", "Rachel", "Samuel", "Tina", "Uma", "Victor", "Wendy", "Xavier",
    "Yolanda", "Zachary", "Angela", "Brian", "Chloe", "Daniel", "Emily",
    "Felix", "Gina", "Harold", "Isabel", "James", "Kylie", "Lucas",
    "Monica", "Nathan", "Paige", "Raymond", "Sarah", "Thomas", "Ursula",
    "Vincent", "Whitney", "Yasmin", "Zoe", "Adrian", "Beatrice", "Calvin",
    "Diana", "Edward", "Fiona", "George", "Hannah", "Ian", "Julia",
    "Kenneth", "Laura", "Marcus", "Nina", "Oscar", "Patricia", "Quincy",
    "Rebecca", "Steven", "Teresa", "Ulrich", "Valerie", "Walter", "Ximena",
    "Yusuf", "Zara", "Arthur", "Bridget", "Craig", "Donna", "Ethan",
    "Florence", "Grant", "Holly", "Ivan", "Janet", "Keith", "Linda",
    "Martin", "Natalie", "Owen", "Penelope", "Ruben", "Sophia", "Travis",
    "Uma", "Vince", "Willa", "Xander", "Yvette", "Zelda",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Clark", "Lewis",
    "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Hill",
    "Scott", "Adams", "Baker", "Nelson", "Carter", "Mitchell", "Roberts",
    "Turner", "Phillips", "Campbell", "Parker", "Evans", "Edwards",
    "Collins", "Stewart", "Morris", "Reed", "Cook", "Morgan", "Bell",
    "Murphy", "Bailey", "Rivera", "Cooper", "Richardson", "Cox", "Howard",
    "Ward", "Torres", "Peterson", "Gray", "Ramirez", "James", "Watson",
    "Brooks", "Kelly", "Sanders", "Price", "Bennett", "Wood", "Barnes",
    "Ross", "Henderson", "Coleman", "Jenkins", "Perry", "Powell", "Long",
    "Patterson", "Hughes", "Flores", "Washington", "Butler", "Simmons",
    "Foster", "Bryant", "Alexander", "Russell", "Griffin", "Hayes",
    "Myers", "Ford", "Hamilton", "Graham", "Sullivan", "Wallace",
]

DOCTOR_FIRST = [
    "Sarah", "Michael", "Jennifer", "David", "Lisa", "James", "Emily",
    "Robert", "Amanda", "William", "Maria", "John", "Anna", "Richard",
    "Karen", "Joseph", "Linda", "Thomas", "Patricia", "Daniel",
    "Christine", "Mark", "Susan", "Paul", "Nancy",
]

DOCTOR_LAST = [
    "Chen", "Patel", "Nakamura", "Kim", "Okafor", "Johansson", "Singh",
    "Alvarez", "Schmidt", "Kowalski", "Nguyen", "Hansen", "Muller",
    "Tanaka", "Rossi", "Park", "Gupta", "Sato", "Becker", "Larsen",
    "Dubois", "Ferreira", "Cohen", "Andersen", "Novak",
]

STREETS = [
    "Main St", "Oak Ave", "Elm St", "Park Blvd", "Maple Dr", "Cedar Ln",
    "Washington Ave", "Lincoln Rd", "Spring St", "River Rd", "Forest Ave",
    "Highland Dr", "Valley Rd", "Sunset Blvd", "Lake Dr",
]

CITIES = [
    "Springfield", "Riverside", "Lakewood", "Fairview", "Greenville",
    "Meadowbrook", "Westfield",
]

ALLERGIES = [
    "penicillin", "sulfa drugs", "aspirin", "ibuprofen", "latex",
    "codeine", "amoxicillin", "tetracycline", "erythromycin", "none",
]

MEDICATIONS = [
    "lisinopril 10mg", "metformin 500mg", "atorvastatin 20mg",
    "levothyroxine 50mcg", "amlodipine 5mg", "omeprazole 20mg",
    "metoprolol 25mg", "sertraline 50mg", "gabapentin 300mg",
    "albuterol inhaler", "fluoxetine 20mg", "losartan 50mg",
    "prednisone 10mg", "montelukast 10mg", "amoxicillin 500mg",
]

INSURANCE_PROVIDERS = [
    "Blue Cross Blue Shield", "Aetna", "UnitedHealthcare", "Cigna",
    "Humana", "Kaiser Permanente",
]

PLAN_NAMES = [
    "Gold PPO", "Silver HMO", "Bronze EPO", "Platinum PPO", "Standard HMO",
    "Premier PPO",
]

SPECIALTIES = ["general", "dental", "dermatology", "orthopedics", "pediatrics", "cardiology"]

APPOINTMENT_TYPES = ["checkup", "follow_up", "consultation", "procedure", "urgent", "vaccination"]

LAB_TESTS = [
    "Complete Blood Count", "Basic Metabolic Panel", "Lipid Panel",
    "Thyroid Panel", "Hemoglobin A1C", "Urinalysis", "Liver Function Panel",
    "Vitamin D Level", "Iron Studies", "PSA Test",
]


# ── Helpers ───────────────────────────────────────────────────────────────

def make_id(prefix, name):
    """Create a slug ID from a prefix and name."""
    slug = name.lower().replace(" ", "_").replace(".", "").replace("'", "")
    return f"{prefix}_{slug}"


def rand_phone():
    return f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}"


def rand_date(start, end):
    """Random date string between start and end (inclusive)."""
    from datetime import datetime, timedelta
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    delta = (e - s).days
    d = s + timedelta(days=random.randint(0, max(0, delta)))
    return d.strftime("%Y-%m-%d")


def rand_future_date(min_days=1, max_days=60):
    from datetime import datetime, timedelta
    base = datetime.strptime(TODAY, "%Y-%m-%d")
    d = base + timedelta(days=random.randint(min_days, max_days))
    return d.strftime("%Y-%m-%d")


def rand_past_date(min_days=1, max_days=365):
    from datetime import datetime, timedelta
    base = datetime.strptime(TODAY, "%Y-%m-%d")
    d = base - timedelta(days=random.randint(min_days, max_days))
    return d.strftime("%Y-%m-%d")


# ── Generators ────────────────────────────────────────────────────────────

def generate_clinics():
    clinics = {}
    clinic_defs = [
        ("carewell_downtown", "CareWell Downtown", "100 Main St, Springfield", "(555) 100-1000",
         "Mon-Fri 8:00-18:00", ["general", "cardiology", "dermatology"]),
        ("carewell_riverside", "CareWell Riverside", "200 River Rd, Riverside", "(555) 200-2000",
         "Mon-Sat 7:00-19:00", ["general", "orthopedics", "pediatrics"]),
        ("carewell_lakewood", "CareWell Lakewood", "300 Lake Dr, Lakewood", "(555) 300-3000",
         "Mon-Fri 8:00-17:00", ["general", "dental", "dermatology"]),
        ("carewell_fairview", "CareWell Fairview", "400 Oak Ave, Fairview", "(555) 400-4000",
         "Mon-Fri 9:00-18:00, Sat 9:00-13:00", ["general", "pediatrics", "cardiology"]),
    ]
    for cid, name, addr, phone, hours, depts in clinic_defs:
        clinics[cid] = {
            "clinic_id": cid,
            "name": name,
            "address": addr,
            "phone": phone,
            "hours": hours,
            "departments": depts,
        }
    return clinics


def generate_doctors(clinics):
    doctors = {}
    # Assign doctors to clinics with specific specialties
    assignments = []
    for cid, clinic in clinics.items():
        for dept in clinic["departments"]:
            # 2-3 doctors per specialty per clinic
            n = random.choice([2, 3])
            for _ in range(n):
                assignments.append((cid, dept))

    random.shuffle(assignments)
    used_names = set()
    idx = 0
    for cid, specialty in assignments:
        while True:
            first = random.choice(DOCTOR_FIRST)
            last = random.choice(DOCTOR_LAST)
            full = f"Dr. {first} {last}"
            if full not in used_names:
                used_names.add(full)
                break

        days_options = [
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            ["Monday", "Wednesday", "Friday"],
            ["Tuesday", "Thursday", "Saturday"],
            ["Monday", "Tuesday", "Thursday", "Friday"],
            ["Wednesday", "Thursday", "Friday", "Saturday"],
        ]
        hours_options = ["8:00-16:00", "9:00-17:00", "10:00-18:00", "7:00-15:00"]

        did = make_id("doc", f"{first}_{last}")
        if did in doctors:
            did = f"{did}_{idx}"
        doctors[did] = {
            "doctor_id": did,
            "name": full,
            "clinic_id": cid,
            "specialty": specialty,
            "available_days": random.choice(days_options),
            "available_hours": random.choice(hours_options),
            "accepting_new_patients": random.random() < 0.7,
        }
        idx += 1
    return doctors


def generate_patients(doctors, clinics):
    patients = {}
    used_names = set()
    general_doctors = [d for d in doctors.values() if d["specialty"] == "general"]

    for i in range(200):
        while True:
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            full = f"{first} {last}"
            if full not in used_names:
                used_names.add(full)
                break

        pid = make_id("pat", f"{first}_{last}")
        dob_year = random.randint(1945, 2015)
        dob_month = random.randint(1, 12)
        dob_day = random.randint(1, 28)
        dob = f"{dob_year}-{dob_month:02d}-{dob_day:02d}"

        street_num = random.randint(1, 999)
        street = random.choice(STREETS)
        city = random.choice(CITIES)
        address = f"{street_num} {street}, {city}"

        n_allergies = random.choices([0, 1, 2], weights=[0.5, 0.35, 0.15])[0]
        allergies = random.sample([a for a in ALLERGIES if a != "none"], n_allergies)

        n_meds = random.choices([0, 1, 2, 3], weights=[0.3, 0.3, 0.25, 0.15])[0]
        medications = random.sample(MEDICATIONS, n_meds)

        primary = random.choice(general_doctors)["doctor_id"] if random.random() < 0.85 else None

        emergency_first = random.choice(FIRST_NAMES)
        emergency_last = last  # same family
        emergency_phone = rand_phone()

        patients[pid] = {
            "patient_id": pid,
            "name": full,
            "email": f"{first.lower()}.{last.lower()}@email.com",
            "phone": rand_phone(),
            "dob": dob,
            "address": address,
            "insurance_id": None,  # filled later
            "emergency_contact": f"{emergency_first} {emergency_last} - {emergency_phone}",
            "allergies": allergies,
            "current_medications": medications,
            "primary_doctor_id": primary,
            "appointment_ids": [],
            "balance_due": 0.0,
            "payment_method_ids": [],
        }
    return patients


def generate_insurance(patients, clinics):
    insurance = {}
    clinic_ids = list(clinics.keys())
    for pid, patient in patients.items():
        if random.random() < 0.15:  # 15% uninsured
            continue
        provider = random.choice(INSURANCE_PROVIDERS)
        plan = random.choice(PLAN_NAMES)
        group = f"GRP{random.randint(10000, 99999)}"
        member = f"MEM{random.randint(100000, 999999)}"
        copay = random.choice([20, 25, 30, 40, 50])
        deductible = random.choice([500, 1000, 1500, 2000, 2500, 3000])
        deductible_met = round(random.uniform(0, deductible), 2) if random.random() < 0.6 else 0.0

        # Most patients have in-network clinics
        n_in_network = random.randint(1, len(clinic_ids))
        in_network = random.sample(clinic_ids, n_in_network)

        status_opts = ["active", "active", "active", "active", "expired", "pending_verification"]
        status = random.choice(status_opts)

        iid = make_id("ins", patient["name"].split()[-1].lower())
        if iid in insurance:
            iid = f"{iid}_{random.randint(2, 99)}"
        insurance[iid] = {
            "insurance_id": iid,
            "patient_id": pid,
            "provider": provider,
            "plan_name": plan,
            "group_number": group,
            "member_id": member,
            "copay": copay,
            "deductible": deductible,
            "deductible_met": deductible_met,
            "in_network_clinics": in_network,
            "status": status,
        }
        patient["insurance_id"] = iid
    return insurance


def generate_payment_methods(patients):
    methods = {}
    types = ["credit_card", "debit_card", "hsa"]
    for pid, patient in patients.items():
        n = random.choices([1, 2], weights=[0.7, 0.3])[0]
        for j in range(n):
            last_four = f"{random.randint(1000, 9999)}"
            pm_type = random.choice(types)
            pmid = f"pm_{patient['name'].split()[-1].lower()}_{j+1}"
            if pmid in methods:
                pmid = f"{pmid}_{random.randint(2, 99)}"
            methods[pmid] = {
                "payment_method_id": pmid,
                "patient_id": pid,
                "type": pm_type,
                "last_four": last_four,
            }
            patient["payment_method_ids"].append(pmid)
    return methods


def generate_appointments(patients, doctors, clinics):
    appointments = {}
    patient_list = list(patients.keys())

    # Past completed appointments (important for prescription refill checks)
    for _ in range(400):
        pid = random.choice(patient_list)
        patient = patients[pid]
        # Pick a doctor
        if patient["primary_doctor_id"] and random.random() < 0.6:
            did = patient["primary_doctor_id"]
        else:
            did = random.choice(list(doctors.keys()))
        doctor = doctors[did]
        cid = doctor["clinic_id"]

        date = rand_past_date(1, 365)
        hour = random.randint(8, 16)
        time_str = f"{hour:02d}:00"
        atype = random.choices(
            APPOINTMENT_TYPES,
            weights=[30, 25, 15, 10, 5, 15],
        )[0]

        aid = f"appt_{patient['name'].split()[-1].lower()}_{date.replace('-', '')}"
        if aid in appointments:
            aid = f"{aid}_{random.randint(2, 999)}"

        status = random.choices(
            ["completed", "no_show", "cancelled"],
            weights=[0.8, 0.1, 0.1],
        )[0]

        appointments[aid] = {
            "appointment_id": aid,
            "patient_id": pid,
            "doctor_id": did,
            "clinic_id": cid,
            "date": date,
            "time": time_str,
            "type": atype,
            "status": status,
            "notes": None,
            "referral_id": None,
        }
        patient["appointment_ids"].append(aid)

    # Future scheduled appointments
    for _ in range(100):
        pid = random.choice(patient_list)
        patient = patients[pid]
        if patient["primary_doctor_id"] and random.random() < 0.5:
            did = patient["primary_doctor_id"]
        else:
            did = random.choice(list(doctors.keys()))
        doctor = doctors[did]
        cid = doctor["clinic_id"]

        date = rand_future_date(1, 60)
        hour = random.randint(8, 16)
        time_str = f"{hour:02d}:00"
        atype = random.choices(
            APPOINTMENT_TYPES,
            weights=[30, 25, 15, 10, 5, 15],
        )[0]

        aid = f"appt_{patient['name'].split()[-1].lower()}_{date.replace('-', '')}"
        if aid in appointments:
            aid = f"{aid}_{random.randint(2, 999)}"

        status = random.choice(["scheduled", "confirmed"])

        appointments[aid] = {
            "appointment_id": aid,
            "patient_id": pid,
            "doctor_id": did,
            "clinic_id": cid,
            "date": date,
            "time": time_str,
            "type": atype,
            "status": status,
            "notes": None,
            "referral_id": None,
        }
        patient["appointment_ids"].append(aid)

    return appointments


def generate_prescriptions(patients, doctors):
    prescriptions = {}
    patient_list = list(patients.keys())

    med_details = [
        ("lisinopril", "10mg", "once daily", False),
        ("metformin", "500mg", "twice daily", False),
        ("atorvastatin", "20mg", "once daily", False),
        ("levothyroxine", "50mcg", "once daily", False),
        ("amlodipine", "5mg", "once daily", False),
        ("omeprazole", "20mg", "once daily", False),
        ("sertraline", "50mg", "once daily", False),
        ("gabapentin", "300mg", "three times daily", False),
        ("losartan", "50mg", "once daily", False),
        ("montelukast", "10mg", "once daily", False),
        ("prednisone", "10mg", "as directed", False),
        ("amoxicillin", "500mg", "three times daily", False),
        ("fluoxetine", "20mg", "once daily", False),
        ("oxycodone", "5mg", "every 6 hours as needed", True),
        ("adderall", "20mg", "once daily", True),
        ("alprazolam", "0.5mg", "twice daily as needed", True),
        ("methylphenidate", "10mg", "twice daily", True),
        ("tramadol", "50mg", "every 6 hours as needed", True),
    ]

    for i in range(250):
        pid = random.choice(patient_list)
        patient = patients[pid]
        did = patient["primary_doctor_id"] or random.choice(list(doctors.keys()))

        med, dosage, freq, controlled = random.choice(med_details)
        start = rand_past_date(30, 300)
        end = rand_future_date(30, 180) if random.random() < 0.7 else None
        refills = random.choices([0, 1, 2, 3], weights=[0.2, 0.3, 0.3, 0.2])[0]

        rxid = f"rx_{patient['name'].split()[-1].lower()}_{med}"
        if rxid in prescriptions:
            rxid = f"{rxid}_{random.randint(2, 99)}"

        prescriptions[rxid] = {
            "prescription_id": rxid,
            "patient_id": pid,
            "medication": med,
            "dosage": dosage,
            "frequency": freq,
            "start_date": start,
            "end_date": end,
            "refills_remaining": refills,
            "doctor_id": did,
            "controlled_substance": controlled,
        }
    return prescriptions


def generate_referrals(patients, doctors):
    referrals = {}
    patient_list = list(patients.keys())
    specialist_specialties = ["dental", "dermatology", "orthopedics", "pediatrics", "cardiology"]

    for i in range(60):
        pid = random.choice(patient_list)
        patient = patients[pid]
        if not patient["primary_doctor_id"]:
            continue

        specialty = random.choice(specialist_specialties)
        specialist_doctors = [d for d in doctors.values() if d["specialty"] == specialty]
        specialist = random.choice(specialist_doctors) if specialist_doctors else None

        reasons = {
            "dental": ["routine dental exam", "tooth pain", "wisdom tooth evaluation"],
            "dermatology": ["persistent skin rash", "mole check", "acne treatment"],
            "orthopedics": ["chronic knee pain", "back injury follow-up", "shoulder evaluation"],
            "pediatrics": ["well-child checkup", "developmental screening", "vaccination series"],
            "cardiology": ["chest pain evaluation", "heart murmur follow-up", "hypertension management"],
        }
        reason = random.choice(reasons[specialty])

        # Mix of active and expired referrals
        if random.random() < 0.6:
            expiry = rand_future_date(1, 90)
            status = random.choice(["pending", "pending", "scheduled"])
        else:
            expiry = rand_past_date(1, 60)
            status = random.choice(["expired", "completed"])

        rid = f"ref_{patient['name'].split()[-1].lower()}_{specialty}"
        if rid in referrals:
            rid = f"{rid}_{random.randint(2, 99)}"

        referrals[rid] = {
            "referral_id": rid,
            "patient_id": pid,
            "referring_doctor_id": patient["primary_doctor_id"],
            "specialist_doctor_id": specialist["doctor_id"] if specialist else None,
            "specialty": specialty,
            "reason": reason,
            "status": status,
            "expiry_date": expiry,
        }
    return referrals


def generate_invoices(patients, appointments):
    invoices = {}
    # Generate invoices for completed appointments
    completed = [a for a in appointments.values() if a["status"] == "completed"]
    random.shuffle(completed)

    for appt in completed[:200]:
        pid = appt["patient_id"]
        patient = patients[pid]

        # Generate line items
        items = []
        base_amount = random.choice([150, 200, 250, 300, 350, 400])
        items.append({
            "description": f"{appt['type'].replace('_', ' ').title()} visit",
            "amount": base_amount,
            "category": "consultation",
            "insurance_code": f"CPT-{random.randint(90000, 99999)}",
        })

        # Some appointments have additional charges
        if random.random() < 0.3:
            lab_amount = random.choice([50, 75, 100, 150])
            items.append({
                "description": "Lab work",
                "amount": lab_amount,
                "category": "lab",
                "insurance_code": f"CPT-{random.randint(80000, 89999)}",
            })

        if random.random() < 0.15:
            proc_amount = random.choice([200, 350, 500, 750, 1000])
            items.append({
                "description": "Procedure",
                "amount": proc_amount,
                "category": "procedure",
                "insurance_code": f"CPT-{random.randint(10000, 69999)}",
            })

        total = sum(item["amount"] for item in items)

        # Insurance coverage
        if patient["insurance_id"]:
            coverage_pct = random.uniform(0.5, 0.9)
            insurance_covered = round(total * coverage_pct, 2)
        else:
            insurance_covered = 0.0

        patient_resp = round(total - insurance_covered, 2)

        # Status distribution
        status = random.choices(
            ["paid", "pending", "overdue", "insurance_pending"],
            weights=[0.5, 0.2, 0.15, 0.15],
        )[0]

        if status == "paid":
            patient_resp_display = 0.0
        else:
            patient_resp_display = patient_resp
            patient["balance_due"] += patient_resp

        due_date = rand_future_date(-30, 60)

        iid = f"inv_{patient['name'].split()[-1].lower()}_{appt['date'].replace('-', '')}"
        if iid in invoices:
            iid = f"{iid}_{random.randint(2, 99)}"

        invoices[iid] = {
            "invoice_id": iid,
            "patient_id": pid,
            "appointment_id": appt["appointment_id"],
            "items": items,
            "insurance_covered": insurance_covered,
            "patient_responsibility": patient_resp_display,
            "total": total,
            "status": status,
            "due_date": due_date,
        }

    # Round balances
    for patient in patients.values():
        patient["balance_due"] = round(patient["balance_due"], 2)

    return invoices


def generate_lab_results(patients, doctors):
    lab_results = {}
    patient_list = list(patients.keys())

    for i in range(80):
        pid = random.choice(patient_list)
        patient = patients[pid]
        did = patient["primary_doctor_id"] or random.choice(list(doctors.keys()))

        test = random.choice(LAB_TESTS)
        date = rand_past_date(1, 90)
        status = random.choices(
            ["pending", "completed", "reviewed"],
            weights=[0.2, 0.4, 0.4],
        )[0]

        rid = f"lab_{patient['name'].split()[-1].lower()}_{test.lower().replace(' ', '_')}"
        if rid in lab_results:
            rid = f"{rid}_{random.randint(2, 99)}"

        lab_results[rid] = {
            "result_id": rid,
            "patient_id": pid,
            "test_name": test,
            "ordered_by": did,
            "date": date,
            "status": status,
            "results_summary": f"Results for {test}" if status != "pending" else None,
        }
    return lab_results


def generate():
    clinics = generate_clinics()
    doctors = generate_doctors(clinics)
    patients = generate_patients(doctors, clinics)
    insurance = generate_insurance(patients, clinics)
    payment_methods = generate_payment_methods(patients)
    appointments = generate_appointments(patients, doctors, clinics)
    prescriptions = generate_prescriptions(patients, doctors)
    referrals = generate_referrals(patients, doctors)
    invoices = generate_invoices(patients, appointments)
    lab_results = generate_lab_results(patients, doctors)

    db = {
        "patients": patients,
        "doctors": doctors,
        "clinics": clinics,
        "appointments": appointments,
        "prescriptions": prescriptions,
        "referrals": referrals,
        "invoices": invoices,
        "insurance": insurance,
        "lab_results": lab_results,
        "payment_methods": payment_methods,
    }
    return db


if __name__ == "__main__":
    db = generate()
    with open(HERE / "db.json", "w") as f:
        json.dump(db, f, indent=2)

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

    # Balance distribution
    balances = [p["balance_due"] for p in db["patients"].values()]
    with_balance = [b for b in balances if b > 0]
    print(f"\n=== Patient Balances ===")
    print(f"  Patients with balance: {len(with_balance)}")
    if with_balance:
        print(f"  Min: ${min(with_balance):.2f}")
        print(f"  Max: ${max(with_balance):.2f}")
        print(f"  Avg: ${sum(with_balance)/len(with_balance):.2f}")

    # Referral status
    ref_statuses = {}
    for r in db["referrals"].values():
        ref_statuses[r["status"]] = ref_statuses.get(r["status"], 0) + 1
    print(f"\n=== Referral Statuses ===")
    for s, c in sorted(ref_statuses.items()):
        print(f"  {s}: {c}")

    # Insurance status
    ins_statuses = {}
    for ins in db["insurance"].values():
        ins_statuses[ins["status"]] = ins_statuses.get(ins["status"], 0) + 1
    print(f"\n=== Insurance Statuses ===")
    for s, c in sorted(ins_statuses.items()):
        print(f"  {s}: {c}")
