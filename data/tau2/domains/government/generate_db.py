#!/usr/bin/env python3
"""Generate a realistically-sized government services database (db.json).

Deterministic via random.seed(42). Uses only stdlib modules.
Run from repo root:
    uv run python data/tau2/domains/government/generate_db.py
"""

import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

# ── Reference date (anchor for all date math) ──────────────────────────────
TODAY = datetime(2025, 10, 15)

# ── Policy constants ───────────────────────────────────────────────────────
LICENSE_RENEWAL_WINDOW_DAYS = 30
LATE_RENEWAL_SURCHARGE_RATE = 0.20
PAYMENT_PLAN_MAX_INSTALLMENTS = 12
APPEAL_WINDOW_DAYS = 30


# ── Helpers ────────────────────────────────────────────────────────────────
def date_str(dt):
    return dt.strftime("%Y-%m-%d")


def make_unique_id(base, existing):
    """Return base if unique, else base_2, base_3, ..."""
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


# ═══════════════════════════════════════════════════════════════════════════
# Step 1: Departments (6)
# ═══════════════════════════════════════════════════════════════════════════
DEPT_SPECS = [
    {
        "department_id": "public_works",
        "name": "Department of Public Works",
        "contact_email": "publicworks@riverside.gov",
        "phone": "555-7100",
        "hours": "Mon-Fri 8AM-5PM",
        "services": ["road maintenance", "streetlights", "waste collection", "water"],
    },
    {
        "department_id": "planning_zoning",
        "name": "Department of Planning & Zoning",
        "contact_email": "planning@riverside.gov",
        "phone": "555-7200",
        "hours": "Mon-Fri 8AM-5PM",
        "services": ["zoning permits", "building permits", "variance applications", "land use"],
    },
    {
        "department_id": "public_safety",
        "name": "Department of Public Safety",
        "contact_email": "safety@riverside.gov",
        "phone": "555-7300",
        "hours": "Mon-Fri 8AM-5PM, emergencies 24/7",
        "services": ["noise complaints", "code enforcement", "fire permits"],
    },
    {
        "department_id": "finance",
        "name": "Department of Finance",
        "contact_email": "finance@riverside.gov",
        "phone": "555-7400",
        "hours": "Mon-Fri 8AM-4:30PM",
        "services": ["property tax", "income tax", "business tax", "payment plans"],
    },
    {
        "department_id": "transportation",
        "name": "Department of Transportation",
        "contact_email": "transport@riverside.gov",
        "phone": "555-7500",
        "hours": "Mon-Fri 8AM-5PM",
        "services": ["parking permits", "traffic management", "public transit"],
    },
    {
        "department_id": "licensing",
        "name": "Department of Licensing",
        "contact_email": "licensing@riverside.gov",
        "phone": "555-7600",
        "hours": "Mon-Fri 9AM-4PM",
        "services": ["business licenses", "dog licenses", "vendor permits", "liquor licenses"],
    },
]

departments = {}
for spec in DEPT_SPECS:
    departments[spec["department_id"]] = spec


# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Fees (10)
# ═══════════════════════════════════════════════════════════════════════════
FEE_SPECS = [
    ("building_permit", "Building permit application fee", 150.00),
    ("parking_permit", "Residential/commercial parking permit", 50.00),
    ("event_permit", "Event hosting permit", 75.00),
    ("noise_permit", "Noise variance permit", 40.00),
    ("business_permit", "Business operating permit", 200.00),
    ("business_license", "Annual business license fee", 250.00),
    ("dog_license", "Annual dog license fee", 25.00),
    ("vendor_license", "Vendor license fee", 100.00),
    ("liquor_license", "Liquor license fee", 500.00),
    ("zoning_variance", "Zoning variance application fee", 300.00),
]

fees = {}
for ftype, fdesc, famount in FEE_SPECS:
    fid = f"fee_{ftype}"
    fees[fid] = {
        "fee_id": fid,
        "type": ftype,
        "amount": famount,
        "description": fdesc,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 3: Households (80)
# ═══════════════════════════════════════════════════════════════════════════
STREETS = [
    "Oak Street", "Elm Avenue", "Pine Road", "Maple Drive", "Cedar Lane",
    "Birch Way", "Walnut Court", "Cherry Street", "Spruce Avenue", "Willow Place",
    "Main Street", "College Avenue", "River Road", "Hill Street", "Park Drive",
    "Lake Road", "Garden Way", "Forest Lane", "Valley Drive", "Summit Road",
]
WASTE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
ZONING_TYPES = ["residential", "commercial", "mixed"]
ZONING_WEIGHTS = [60, 25, 15]

households = {}
for i in range(80):
    house_num = random.randint(100, 9999)
    street = random.choice(STREETS)
    address = f"{house_num} {street}, Riverside"
    zoning = random.choices(ZONING_TYPES, weights=ZONING_WEIGHTS, k=1)[0]
    waste_day = random.choice(WASTE_DAYS)

    hid = f"household_{i + 1:03d}"
    households[hid] = {
        "household_id": hid,
        "address": address,
        "members": [],
        "property_tax_account_id": None,
        "waste_collection_day": waste_day,
        "zoning_type": zoning,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Citizens (200)
# ═══════════════════════════════════════════════════════════════════════════
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen",
    "Charles", "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony",
    "Margaret", "Mark", "Sandra", "Donald", "Ashley", "Steven", "Dorothy",
    "Paul", "Kimberly", "Andrew", "Emily", "Joshua", "Donna", "Kenneth",
    "Michelle", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Timothy", "Deborah",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts",
]
EMAIL_DOMAINS = ["email.com", "mail.com", "inbox.com", "webmail.net"]

citizens = {}
citizen_names_set: set[str] = set()
household_ids = list(households.keys())

for i in range(200):
    # Pick unique name
    for _attempt in range(500):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        display_name = f"{first} {last}"
        if display_name not in citizen_names_set:
            break
    else:
        raise RuntimeError("Could not find unique name after 500 attempts")
    citizen_names_set.add(display_name)

    cid = f"{first.lower()}_{last.lower()}"

    # Date of birth: ages 22-85
    age = random.randint(22, 85)
    dob = TODAY - timedelta(days=age * 365 + random.randint(0, 364))
    ssn_last4 = f"{random.randint(1000, 9999)}"

    # Assign to household (2-3 citizens per household on average)
    hid = random.choice(household_ids)
    address = households[hid]["address"]

    email_domain = random.choice(EMAIL_DOMAINS)
    digits = random.randint(1, 99)
    email = f"{first.lower()}.{last.lower()}{digits}@{email_domain}"
    phone = f"555-{random.randint(1000, 9999):04d}"

    citizens[cid] = {
        "citizen_id": cid,
        "name": display_name,
        "dob": date_str(dob),
        "ssn_last4": ssn_last4,
        "address": address,
        "email": email,
        "phone": phone,
        "household_id": hid,
        "tax_account_ids": [],
        "permit_ids": [],
        "license_ids": [],
        "case_ids": [],
    }
    households[hid]["members"].append(cid)

all_citizen_ids = list(citizens.keys())


# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Tax Accounts (250)
# ═══════════════════════════════════════════════════════════════════════════
tax_accounts = {}
tax_id_set = set()

# Property tax accounts: one per household
for hid, h in households.items():
    if not h["members"]:
        continue
    owner = h["members"][0]  # first member is the "owner"
    aid = f"tax_prop_{hid}"
    tax_id_set.add(aid)

    # Most current, some overdue
    r = random.random()
    if r < 0.60:
        balance = 0.0
        penalties = 0.0
        last_payment = TODAY - timedelta(days=random.randint(1, 60))
    elif r < 0.85:
        balance = round(random.uniform(200, 3000), 2)
        penalties = 0.0
        last_payment = TODAY - timedelta(days=random.randint(60, 180))
    else:
        balance = round(random.uniform(500, 5000), 2)
        penalties = round(random.uniform(50, 500), 2)
        last_payment = TODAY - timedelta(days=random.randint(180, 400))

    tax_accounts[aid] = {
        "account_id": aid,
        "citizen_id": owner,
        "type": "property",
        "balance_due": balance,
        "last_payment_date": date_str(last_payment) if balance == 0 else (
            date_str(last_payment) if random.random() < 0.5 else None
        ),
        "payment_plan_active": False,
        "installments_remaining": 0,
        "penalties": penalties,
    }
    citizens[owner]["tax_account_ids"].append(aid)
    h["property_tax_account_id"] = aid

# Income tax: ~100 citizens
income_tax_citizens = random.sample(all_citizen_ids, 100)
for cid in income_tax_citizens:
    aid = f"tax_income_{cid}"
    tax_id_set.add(aid)

    r = random.random()
    if r < 0.70:
        balance = 0.0
        penalties = 0.0
    elif r < 0.90:
        balance = round(random.uniform(100, 2000), 2)
        penalties = 0.0
    else:
        balance = round(random.uniform(500, 3000), 2)
        penalties = round(random.uniform(25, 300), 2)

    last_pay = TODAY - timedelta(days=random.randint(30, 365))

    tax_accounts[aid] = {
        "account_id": aid,
        "citizen_id": cid,
        "type": "income",
        "balance_due": balance,
        "last_payment_date": date_str(last_pay) if balance == 0 else None,
        "payment_plan_active": False,
        "installments_remaining": 0,
        "penalties": penalties,
    }
    citizens[cid]["tax_account_ids"].append(aid)

# Business tax: for citizens in commercial/mixed zones
commercial_citizens = [
    cid for cid in all_citizen_ids
    if households[citizens[cid]["household_id"]]["zoning_type"] in ("commercial", "mixed")
]
biz_tax_sample = random.sample(
    commercial_citizens, min(40, len(commercial_citizens))
)
for cid in biz_tax_sample:
    aid = f"tax_biz_{cid}"
    tax_id_set.add(aid)

    r = random.random()
    if r < 0.65:
        balance = 0.0
        penalties = 0.0
    elif r < 0.85:
        balance = round(random.uniform(200, 2000), 2)
        penalties = 0.0
    else:
        balance = round(random.uniform(500, 4000), 2)
        penalties = round(random.uniform(50, 400), 2)

    tax_accounts[aid] = {
        "account_id": aid,
        "citizen_id": cid,
        "type": "business",
        "balance_due": balance,
        "last_payment_date": None,
        "payment_plan_active": False,
        "installments_remaining": 0,
        "penalties": penalties,
    }
    citizens[cid]["tax_account_ids"].append(aid)

# Edge cases: ensure >= 5 accounts with penalties > $100
accts_with_penalties = [
    a for a in tax_accounts.values() if a["penalties"] > 100
]
while len(accts_with_penalties) < 5:
    candidates = [
        a for a in tax_accounts.values()
        if a["penalties"] == 0 and a["balance_due"] > 0
    ]
    if not candidates:
        break
    acct = random.choice(candidates)
    acct["penalties"] = round(random.uniform(100, 400), 2)
    accts_with_penalties.append(acct)

# Edge cases: set up ~5 accounts with active payment plans
plan_candidates = [
    a for a in tax_accounts.values()
    if a["balance_due"] > 500 and not a["payment_plan_active"]
]
random.shuffle(plan_candidates)
for acct in plan_candidates[:5]:
    acct["payment_plan_active"] = True
    acct["installments_remaining"] = random.randint(3, 10)

# Edge case: ensure >= 3 accounts with high balance + penalties (for payment
# plan tasks)
high_balance = [
    a for a in tax_accounts.values()
    if (a["balance_due"] + a["penalties"]) > 2000
    and not a["payment_plan_active"]
]
if len(high_balance) < 3:
    for a in plan_candidates[5:8]:
        if a["balance_due"] < 2000:
            a["balance_due"] = round(random.uniform(2000, 4000), 2)
        if a["penalties"] == 0:
            a["penalties"] = round(random.uniform(100, 300), 2)


# ═══════════════════════════════════════════════════════════════════════════
# Step 6: Permits (60)
# ═══════════════════════════════════════════════════════════════════════════
permits = {}
permit_id_set = set()

PERMIT_TYPES = ["building", "parking", "event", "noise", "business"]
PERMIT_WEIGHTS = [30, 25, 15, 10, 20]
PERMIT_STATUSES = ["pending", "approved", "denied", "expired"]
PERMIT_STATUS_WEIGHTS_STANDARD = [25, 40, 15, 20]

fee_lookup = {f["type"]: f["amount"] for f in fees.values()}

for _ in range(60):
    cid = random.choice(all_citizen_ids)
    ptype = random.choices(PERMIT_TYPES, weights=PERMIT_WEIGHTS, k=1)[0]
    hid = citizens[cid]["household_id"]
    zoning = households[hid]["zoning_type"]

    # Enforce zoning: no business permits in residential
    if ptype == "business" and zoning == "residential":
        ptype = random.choice(["building", "parking", "event", "noise"])

    status = random.choices(
        PERMIT_STATUSES, weights=PERMIT_STATUS_WEIGHTS_STANDARD, k=1
    )[0]

    app_date = TODAY - timedelta(days=random.randint(10, 365))
    decision_date = None
    expiry_date = None
    conditions = None
    inspector_notes = None

    if status == "approved":
        decision_date = app_date + timedelta(days=random.randint(10, 20))
        expiry_date = decision_date + timedelta(days=365)
        conditions = random.choice([
            None, "Must complete work within 6 months",
            "Requires inspection upon completion",
            "Noise limited to 7AM-8PM",
            "Must maintain 10ft setback",
        ])
    elif status == "denied":
        decision_date = app_date + timedelta(days=random.randint(10, 20))
        inspector_notes = random.choice([
            "Does not meet code requirements",
            "Incomplete application documents",
            "Zoning conflict",
            "Exceeds lot coverage limit",
        ])
    elif status == "expired":
        decision_date = app_date + timedelta(days=random.randint(10, 20))
        expiry_date = TODAY - timedelta(days=random.randint(1, 180))

    fee_key = f"{ptype}_permit"
    fee_amount = fee_lookup.get(fee_key, 0.0)

    details_options = {
        "building": [
            "Construct a wooden deck in backyard",
            "Add a second-story addition",
            "Build a detached garage",
            "Renovate kitchen and bathroom",
            "Install solar panels on roof",
        ],
        "parking": [
            "Residential street parking permit",
            "Commercial lot parking permit",
            "Temporary event parking",
        ],
        "event": [
            "Block party for neighborhood",
            "Outdoor wedding reception",
            "Charity fundraiser event",
            "Community farmers market",
        ],
        "noise": [
            "Construction noise during renovation",
            "Live music at outdoor venue",
            "Early morning delivery operations",
        ],
        "business": [
            "Open a retail store",
            "Start a restaurant",
            "Operate a consulting office",
            "Open a hair salon",
        ],
    }
    details = random.choice(details_options.get(ptype, ["General permit"]))

    last = citizens[cid]["name"].split()[-1].lower()
    base_pid = f"permit_{last}_{ptype}"
    pid = make_unique_id(base_pid, permit_id_set)
    permit_id_set.add(pid)

    permits[pid] = {
        "permit_id": pid,
        "citizen_id": cid,
        "type": ptype,
        "status": status,
        "application_date": date_str(app_date),
        "decision_date": date_str(decision_date) if decision_date else None,
        "expiry_date": date_str(expiry_date) if expiry_date else None,
        "conditions": conditions,
        "fee_paid": fee_amount,
        "inspector_notes": inspector_notes,
        "details": details,
    }
    citizens[cid]["permit_ids"].append(pid)

# Edge case: ensure >= 3 denied permits with recent decision (for appeal tasks)
recent_denied = [
    p for p in permits.values()
    if p["status"] == "denied"
    and p["decision_date"]
    and (TODAY - datetime.strptime(p["decision_date"], "%Y-%m-%d")).days <= APPEAL_WINDOW_DAYS
]
while len(recent_denied) < 3:
    candidates = [
        p for p in permits.values()
        if p["status"] == "denied" and p not in recent_denied
    ]
    if not candidates:
        # Change some approved ones to denied
        approved = [p for p in permits.values() if p["status"] == "approved"]
        if not approved:
            break
        p = random.choice(approved)
        p["status"] = "denied"
        p["decision_date"] = date_str(TODAY - timedelta(days=random.randint(5, 25)))
        p["expiry_date"] = None
        p["inspector_notes"] = "Does not meet code requirements"
        p["conditions"] = None
        recent_denied.append(p)
    else:
        p = random.choice(candidates)
        p["decision_date"] = date_str(TODAY - timedelta(days=random.randint(5, 25)))
        recent_denied.append(p)


# ═══════════════════════════════════════════════════════════════════════════
# Step 7: Licenses (80)
# ═══════════════════════════════════════════════════════════════════════════
licenses = {}
license_id_set = set()

LICENSE_TYPES = ["business", "dog", "vendor", "liquor"]
LICENSE_WEIGHTS = [30, 35, 20, 15]

for _ in range(80):
    cid = random.choice(all_citizen_ids)
    ltype = random.choices(LICENSE_TYPES, weights=LICENSE_WEIGHTS, k=1)[0]

    # Business/vendor/liquor licenses only for commercial/mixed zones
    hid = citizens[cid]["household_id"]
    zoning = households[hid]["zoning_type"]
    if ltype in ("business", "vendor", "liquor") and zoning == "residential":
        ltype = "dog"

    r = random.random()
    if r < 0.50:
        # Active, not expiring soon
        issue_date = TODAY - timedelta(days=random.randint(60, 300))
        expiry_date = TODAY + timedelta(days=random.randint(60, 300))
        status = "active"
    elif r < 0.70:
        # Active, expiring within renewal window (30 days)
        issue_date = TODAY - timedelta(days=random.randint(300, 350))
        expiry_date = TODAY + timedelta(days=random.randint(1, 30))
        status = "active"
    elif r < 0.85:
        # Expired
        issue_date = TODAY - timedelta(days=random.randint(400, 700))
        expiry_date = TODAY - timedelta(days=random.randint(1, 90))
        status = "expired"
    elif r < 0.93:
        # Suspended
        issue_date = TODAY - timedelta(days=random.randint(200, 400))
        expiry_date = TODAY + timedelta(days=random.randint(30, 200))
        status = "suspended"
    else:
        # Revoked
        issue_date = TODAY - timedelta(days=random.randint(200, 500))
        expiry_date = TODAY - timedelta(days=random.randint(0, 100))
        status = "revoked"

    fee_key = f"{ltype}_license"
    fee_amount = fee_lookup.get(fee_key, 0.0)

    renewal_eligible = status not in ("suspended", "revoked")

    last = citizens[cid]["name"].split()[-1].lower()
    base_lid = f"license_{last}_{ltype}"
    lid = make_unique_id(base_lid, license_id_set)
    license_id_set.add(lid)

    licenses[lid] = {
        "license_id": lid,
        "citizen_id": cid,
        "type": ltype,
        "status": status,
        "issue_date": date_str(issue_date),
        "expiry_date": date_str(expiry_date),
        "fee_paid": fee_amount,
        "renewal_eligible": renewal_eligible,
    }
    citizens[cid]["license_ids"].append(lid)

# Edge case: ensure >= 5 licenses within renewal window
renewable = [
    l for l in licenses.values()
    if l["status"] in ("active", "expired")
    and l["renewal_eligible"]
    and (datetime.strptime(l["expiry_date"], "%Y-%m-%d") - TODAY).days <= LICENSE_RENEWAL_WINDOW_DAYS
]
while len(renewable) < 5:
    candidates = [
        l for l in licenses.values()
        if l["status"] == "active"
        and l["renewal_eligible"]
        and l not in renewable
    ]
    if not candidates:
        break
    lic = random.choice(candidates)
    lic["expiry_date"] = date_str(TODAY + timedelta(days=random.randint(1, 25)))
    renewable.append(lic)

# Edge case: ensure >= 3 expired licenses (for late renewal surcharge tasks)
expired_licenses = [
    l for l in licenses.values()
    if l["status"] == "expired" and l["renewal_eligible"]
]
while len(expired_licenses) < 3:
    candidates = [
        l for l in licenses.values()
        if l["status"] == "active" and l["renewal_eligible"] and l not in renewable
    ]
    if not candidates:
        break
    lic = random.choice(candidates)
    lic["status"] = "expired"
    lic["expiry_date"] = date_str(TODAY - timedelta(days=random.randint(5, 60)))
    expired_licenses.append(lic)


# ═══════════════════════════════════════════════════════════════════════════
# Step 8: Cases (50)
# ═══════════════════════════════════════════════════════════════════════════
cases = {}
case_id_set = set()

CASE_TYPES = ["complaint", "request", "appeal"]
CASE_TYPE_WEIGHTS = [50, 35, 15]
CASE_CATEGORIES = ["noise", "pothole", "streetlight", "zoning", "parking", "waste"]
CASE_CATEGORY_WEIGHTS = [20, 20, 10, 15, 20, 15]
CASE_STATUSES = ["open", "assigned", "in_progress", "resolved", "closed"]
CASE_STATUS_WEIGHTS = [20, 15, 20, 25, 20]

DEPT_MAPPING = {
    "noise": "public_safety",
    "pothole": "public_works",
    "streetlight": "public_works",
    "zoning": "planning_zoning",
    "parking": "transportation",
    "waste": "public_works",
}

DESCRIPTION_TEMPLATES = {
    "noise": [
        "Excessive noise from construction site at {addr} during late hours",
        "Loud music from neighboring property at {addr} after 10 PM",
        "Barking dogs at {addr} causing disturbance",
        "Commercial truck deliveries at {addr} before 7 AM",
    ],
    "pothole": [
        "Large pothole on {street} near the intersection",
        "Multiple potholes on {street} causing vehicle damage",
        "Sinkhole forming on {street}",
    ],
    "streetlight": [
        "Streetlight out on {street}",
        "Flickering streetlight on {street} near house number {num}",
        "Broken streetlight pole on {street}",
    ],
    "zoning": [
        "Neighbor appears to be running a business from residential property at {addr}",
        "Commercial property at {addr} being used as residential",
        "Unpermitted construction at {addr}",
    ],
    "parking": [
        "Abandoned vehicle on {street} for over 2 weeks",
        "Vehicles blocking sidewalk on {street}",
        "No parking signs needed on {street} near school",
        "Double parking on {street} during business hours",
    ],
    "waste": [
        "Missed waste collection on {street} this week",
        "Overflowing dumpster at {addr}",
        "Illegal dumping at vacant lot on {street}",
        "Need additional recycling bin at {addr}",
    ],
}

RESOLUTION_TEMPLATES = [
    "Issue resolved. Work order completed on {date}.",
    "Addressed by department. No further action needed.",
    "Inspection completed. Violation notice issued.",
    "Referred to appropriate department for follow-up.",
    "Temporary fix applied. Permanent repair scheduled.",
]

for _ in range(50):
    cid = random.choice(all_citizen_ids)
    ctype = random.choices(CASE_TYPES, weights=CASE_TYPE_WEIGHTS, k=1)[0]
    category = random.choices(CASE_CATEGORIES, weights=CASE_CATEGORY_WEIGHTS, k=1)[0]
    status = random.choices(CASE_STATUSES, weights=CASE_STATUS_WEIGHTS, k=1)[0]

    created = TODAY - timedelta(days=random.randint(1, 180))
    dept = DEPT_MAPPING.get(category)

    # Generate description
    addr = citizens[cid]["address"]
    street = addr.split(",")[0].split(" ", 1)[1] if "," in addr else "Main Street"
    num = addr.split(" ")[0]
    tmpl = random.choice(DESCRIPTION_TEMPLATES.get(category, ["General issue"]))
    description = tmpl.format(addr=addr, street=street, num=num)

    resolution = None
    if status in ("resolved", "closed"):
        res_date = created + timedelta(days=random.randint(3, 30))
        resolution = random.choice(RESOLUTION_TEMPLATES).format(date=date_str(res_date))

    last = citizens[cid]["name"].split()[-1].lower()
    base_caseid = f"case_{last}_{category}"
    case_id = make_unique_id(base_caseid, case_id_set)
    case_id_set.add(case_id)

    cases[case_id] = {
        "case_id": case_id,
        "citizen_id": cid,
        "type": ctype,
        "category": category,
        "status": status,
        "description": description,
        "created_at": date_str(created),
        "assigned_department": dept,
        "resolution": resolution,
    }
    citizens[cid]["case_ids"].append(case_id)

# Edge case: ensure >= 3 open cases per category
for cat in CASE_CATEGORIES:
    open_in_cat = [c for c in cases.values() if c["category"] == cat and c["status"] == "open"]
    while len(open_in_cat) < 2:
        candidates = [
            c for c in cases.values()
            if c["category"] == cat and c["status"] in ("resolved", "closed")
        ]
        if not candidates:
            break
        c = random.choice(candidates)
        c["status"] = "open"
        c["resolution"] = None
        open_in_cat.append(c)


# ═══════════════════════════════════════════════════════════════════════════
# Step 9: Validation
# ═══════════════════════════════════════════════════════════════════════════
errors = []

# Foreign key checks
for cid, c in citizens.items():
    if c["household_id"] not in households:
        errors.append(f"Citizen {cid}: household {c['household_id']} not found")
    for aid in c["tax_account_ids"]:
        if aid not in tax_accounts:
            errors.append(f"Citizen {cid}: tax account {aid} not found")
    for pid in c["permit_ids"]:
        if pid not in permits:
            errors.append(f"Citizen {cid}: permit {pid} not found")
    for lid in c["license_ids"]:
        if lid not in licenses:
            errors.append(f"Citizen {cid}: license {lid} not found")
    for caseid in c["case_ids"]:
        if caseid not in cases:
            errors.append(f"Citizen {cid}: case {caseid} not found")

for hid, h in households.items():
    for member in h["members"]:
        if member not in citizens:
            errors.append(f"Household {hid}: member {member} not found")
    if h["property_tax_account_id"] and h["property_tax_account_id"] not in tax_accounts:
        errors.append(f"Household {hid}: tax account {h['property_tax_account_id']} not found")

for aid, a in tax_accounts.items():
    if a["citizen_id"] not in citizens:
        errors.append(f"Tax account {aid}: citizen {a['citizen_id']} not found")

for pid, p in permits.items():
    if p["citizen_id"] not in citizens:
        errors.append(f"Permit {pid}: citizen {p['citizen_id']} not found")

for lid, l in licenses.items():
    if l["citizen_id"] not in citizens:
        errors.append(f"License {lid}: citizen {l['citizen_id']} not found")

for caseid, c in cases.items():
    if c["citizen_id"] not in citizens:
        errors.append(f"Case {caseid}: citizen {c['citizen_id']} not found")

# Zoning consistency: no business permits in residential
for pid, p in permits.items():
    if p["type"] == "business":
        hid = citizens[p["citizen_id"]]["household_id"]
        if households[hid]["zoning_type"] == "residential":
            errors.append(f"Permit {pid}: business permit in residential zone")


# ── Statistics ────────────────────────────────────────────────────────────
zoning_counts = defaultdict(int)
for h in households.values():
    zoning_counts[h["zoning_type"]] += 1

permit_status_counts = defaultdict(int)
for p in permits.values():
    permit_status_counts[p["status"]] += 1

license_status_counts = defaultdict(int)
for l in licenses.values():
    license_status_counts[l["status"]] += 1

case_status_counts = defaultdict(int)
for c in cases.values():
    case_status_counts[c["status"]] += 1

accts_with_balance = [a for a in tax_accounts.values() if a["balance_due"] > 0]
accts_with_pen = [a for a in tax_accounts.values() if a["penalties"] > 0]
accts_with_plan = [a for a in tax_accounts.values() if a["payment_plan_active"]]

print("=" * 60)
print("GOVERNMENT DATABASE GENERATION COMPLETE")
print("=" * 60)
print(f"\nCitizens:      {len(citizens)}")
print(f"Households:    {len(households)}")
for z, cnt in sorted(zoning_counts.items()):
    print(f"  {z}: {cnt}")
print(f"\nDepartments:   {len(departments)}")
print(f"Fees:          {len(fees)}")
print(f"\nTax Accounts:  {len(tax_accounts)}")
print(f"  With balance:   {len(accts_with_balance)}")
print(f"  With penalties:  {len(accts_with_pen)}")
print(f"  With plans:      {len(accts_with_plan)}")
print(f"\nPermits:       {len(permits)}")
for s, cnt in sorted(permit_status_counts.items()):
    print(f"  {s}: {cnt}")
print(f"\nLicenses:      {len(licenses)}")
for s, cnt in sorted(license_status_counts.items()):
    print(f"  {s}: {cnt}")
print(f"\nCases:         {len(cases)}")
for s, cnt in sorted(case_status_counts.items()):
    print(f"  {s}: {cnt}")

renewable_lics = [
    l for l in licenses.values()
    if l["status"] in ("active", "expired")
    and l["renewal_eligible"]
    and (datetime.strptime(l["expiry_date"], "%Y-%m-%d") - TODAY).days <= LICENSE_RENEWAL_WINDOW_DAYS
]
expired_lics = [
    l for l in licenses.values()
    if l["status"] == "expired" and l["renewal_eligible"]
]
denied_recent = [
    p for p in permits.values()
    if p["status"] == "denied"
    and p["decision_date"]
    and (TODAY - datetime.strptime(p["decision_date"], "%Y-%m-%d")).days <= APPEAL_WINDOW_DAYS
]

print(f"\n-- Edge Cases --")
print(f"  Renewable licenses (within window):  {len(renewable_lics)}")
print(f"  Expired licenses (late renewal):     {len(expired_lics)}")
print(f"  Recently denied permits (appealable): {len(denied_recent)}")
print(f"  High-penalty accounts (>$100):       {len([a for a in tax_accounts.values() if a['penalties'] > 100])}")
print(f"  Active payment plans:                {len(accts_with_plan)}")

if errors:
    print(f"\n!! VALIDATION ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
else:
    print("\nAll validation checks passed")


# ── Write db.json ─────────────────────────────────────────────────────────
db = {
    "citizens": citizens,
    "households": households,
    "permits": permits,
    "licenses": licenses,
    "tax_accounts": tax_accounts,
    "cases": cases,
    "departments": departments,
    "fees": fees,
}

output_path = Path(__file__).parent / "db.json"
with open(output_path, "w") as f:
    json.dump(db, f, indent=2)

print(f"\nWritten to {output_path}")
