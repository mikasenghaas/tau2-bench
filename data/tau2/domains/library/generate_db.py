#!/usr/bin/env python3
"""Generate a realistically-sized library database (db.json).

Deterministic via random.seed(42). Uses only stdlib modules.
Run from repo root:
    uv run python environments/service_agent/tau2/data/tau2/domains/library/generate_db.py
"""

import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

# ── Reference date (anchor for all date math) ──────────────────────────────
TODAY = datetime(2025, 10, 15)

# ── Policy constants (mirrors tools.py) ─────────────────────────────────────
LOAN_PERIOD_STANDARD_WEEKS = 3
LOAN_PERIOD_STUDENT_WEEKS = 4
MAX_RENEWALS_STANDARD = 2
MAX_RENEWALS_STUDENT = 3
OVERDUE_FINE_PER_DAY = 0.25
MAX_FINE_PER_ITEM = 25.0
LOST_BOOK_FINE = 50.0
BORROWING_LIMITS = {"standard": 10, "student": 15, "senior": 10, "child": 10}


# ── Helpers ─────────────────────────────────────────────────────────────────
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
# Step 1: Branches (4)
# ═══════════════════════════════════════════════════════════════════════════
BRANCH_SPECS = [
    {
        "branch_id": "springfield_central",
        "name": "Springfield Central Library",
        "address": "100 Main Street, Springfield",
        "hours": "Mon-Sat 9AM-9PM, Sun 12PM-6PM",
        "phone": "555-1000",
        "weight": 0.40,
        "short": "springfield",
    },
    {
        "branch_id": "westside",
        "name": "Westside Branch Library",
        "address": "450 West Avenue, Springfield",
        "hours": "Mon-Fri 10AM-7PM, Sat 10AM-5PM",
        "phone": "555-2000",
        "weight": 0.25,
        "short": "westside",
    },
    {
        "branch_id": "northgate",
        "name": "Northgate Branch Library",
        "address": "822 North Boulevard, Springfield",
        "hours": "Mon-Fri 10AM-8PM, Sat 10AM-4PM",
        "phone": "555-3000",
        "weight": 0.20,
        "short": "northgate",
    },
    {
        "branch_id": "riverside",
        "name": "Riverside Branch Library",
        "address": "15 River Road, Springfield",
        "hours": "Tue-Sat 10AM-6PM",
        "phone": "555-4000",
        "weight": 0.15,
        "short": "riverside",
    },
]

branches = {}
branch_ids = [b["branch_id"] for b in BRANCH_SPECS]
branch_weights = [b["weight"] for b in BRANCH_SPECS]
branch_short = {b["branch_id"]: b["short"] for b in BRANCH_SPECS}

for spec in BRANCH_SPECS:
    branches[spec["branch_id"]] = {
        "branch_id": spec["branch_id"],
        "name": spec["name"],
        "address": spec["address"],
        "hours": spec["hours"],
        "phone": spec["phone"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Books (30)
# ═══════════════════════════════════════════════════════════════════════════
# (book_id, short_name, title, author, isbn, category)
BOOK_CATALOG = [
    # Fiction (8)
    (
        "the_great_gatsby",
        "gatsby",
        "The Great Gatsby",
        "F. Scott Fitzgerald",
        "978-0743273565",
        "fiction",
    ),
    (
        "to_kill_a_mockingbird",
        "mockingbird",
        "To Kill a Mockingbird",
        "Harper Lee",
        "978-0061120084",
        "fiction",
    ),
    (
        "pride_and_prejudice",
        "pride",
        "Pride and Prejudice",
        "Jane Austen",
        "978-0141439518",
        "fiction",
    ),
    (
        "nineteen_eighty_four",
        "nineteen84",
        "1984",
        "George Orwell",
        "978-0451524935",
        "fiction",
    ),
    (
        "the_catcher_in_the_rye",
        "catcher",
        "The Catcher in the Rye",
        "J.D. Salinger",
        "978-0316769488",
        "fiction",
    ),
    (
        "brave_new_world",
        "brave_new",
        "Brave New World",
        "Aldous Huxley",
        "978-0060850524",
        "fiction",
    ),
    (
        "the_road",
        "the_road",
        "The Road",
        "Cormac McCarthy",
        "978-0307387899",
        "fiction",
    ),
    ("beloved", "beloved", "Beloved", "Toni Morrison", "978-1400033416", "fiction"),
    # Non-fiction (5)
    (
        "intro_to_algorithms",
        "algorithms",
        "Introduction to Algorithms",
        "Thomas Cormen",
        "978-0262033848",
        "non-fiction",
    ),
    (
        "organic_chemistry",
        "organic_chem",
        "Organic Chemistry",
        "Jonathan Clayden",
        "978-0199270293",
        "non-fiction",
    ),
    (
        "thinking_fast_and_slow",
        "thinking_fast",
        "Thinking, Fast and Slow",
        "Daniel Kahneman",
        "978-0374533557",
        "non-fiction",
    ),
    (
        "sapiens",
        "sapiens",
        "Sapiens: A Brief History of Humankind",
        "Yuval Noah Harari",
        "978-0062316097",
        "non-fiction",
    ),
    (
        "the_elements_of_style",
        "elements_style",
        "The Elements of Style",
        "William Strunk Jr.",
        "978-0205309023",
        "non-fiction",
    ),
    # Science (4)
    (
        "a_brief_history_of_time",
        "brief_history",
        "A Brief History of Time",
        "Stephen Hawking",
        "978-0553380163",
        "science",
    ),
    (
        "the_selfish_gene",
        "selfish_gene",
        "The Selfish Gene",
        "Richard Dawkins",
        "978-0198788607",
        "science",
    ),
    (
        "quantum_computing",
        "quantum",
        "Quantum Computing: An Applied Approach",
        "Jack Hidary",
        "978-3030239220",
        "science",
    ),
    ("cosmos", "cosmos", "Cosmos", "Carl Sagan", "978-0345539434", "science"),
    # Children (4)
    (
        "charlottes_web",
        "charlottes_web",
        "Charlotte's Web",
        "E.B. White",
        "978-0064400558",
        "children",
    ),
    (
        "goodnight_moon",
        "goodnight_moon",
        "Goodnight Moon",
        "Margaret Wise Brown",
        "978-0694003617",
        "children",
    ),
    (
        "where_the_wild_things_are",
        "wild_things",
        "Where the Wild Things Are",
        "Maurice Sendak",
        "978-0064431781",
        "children",
    ),
    (
        "the_very_hungry_caterpillar",
        "hungry_caterpillar",
        "The Very Hungry Caterpillar",
        "Eric Carle",
        "978-0399226908",
        "children",
    ),
    # History (3)
    (
        "a_peoples_history",
        "peoples_history",
        "A People's History of the United States",
        "Howard Zinn",
        "978-0062397348",
        "history",
    ),
    (
        "the_guns_of_august",
        "guns_august",
        "The Guns of August",
        "Barbara Tuchman",
        "978-0345386236",
        "history",
    ),
    (
        "team_of_rivals",
        "team_rivals",
        "Team of Rivals",
        "Doris Kearns Goodwin",
        "978-0743270755",
        "history",
    ),
    # Mystery (3)
    (
        "the_hound_of_the_baskervilles",
        "hound",
        "The Hound of the Baskervilles",
        "Arthur Conan Doyle",
        "978-0451528018",
        "mystery",
    ),
    (
        "gone_girl",
        "gone_girl",
        "Gone Girl",
        "Gillian Flynn",
        "978-0307588371",
        "mystery",
    ),
    (
        "the_girl_with_the_dragon_tattoo",
        "dragon_tattoo",
        "The Girl with the Dragon Tattoo",
        "Stieg Larsson",
        "978-0307454546",
        "mystery",
    ),
    # Biography (2)
    (
        "steve_jobs",
        "steve_jobs",
        "Steve Jobs",
        "Walter Isaacson",
        "978-1451648539",
        "biography",
    ),
    (
        "the_diary_of_a_young_girl",
        "diary_anne",
        "The Diary of a Young Girl",
        "Anne Frank",
        "978-0553296983",
        "biography",
    ),
    # Reference (1)
    (
        "merriams_dictionary",
        "dictionary",
        "Merriam-Webster's Collegiate Dictionary",
        "Merriam-Webster",
        "978-0877798095",
        "reference",
    ),
]

books = {}
book_short_names = {}  # book_id -> short_name

for book_id, short_name, title, author, isbn, category in BOOK_CATALOG:
    books[book_id] = {
        "book_id": book_id,
        "title": title,
        "author": author,
        "isbn": isbn,
        "category": category,
        "copies": [],
    }
    book_short_names[book_id] = short_name

book_ids = list(books.keys())


# ═══════════════════════════════════════════════════════════════════════════
# Step 3: Copies (100)
# ═══════════════════════════════════════════════════════════════════════════
CATEGORY_WEIGHTS = {
    "fiction": 3.0,
    "children": 2.5,
    "non-fiction": 2.0,
    "science": 1.5,
    "mystery": 2.0,
    "history": 1.0,
    "biography": 1.0,
    "reference": 0.5,
}

copies = {}
copy_id_counts = defaultdict(int)  # (short_name, branch_short) -> count


def add_copy(book_id, branch_id):
    short = book_short_names[book_id]
    bshort = branch_short[branch_id]
    key = (short, bshort)
    copy_id_counts[key] += 1
    if copy_id_counts[key] == 1:
        cid = f"{short}_{bshort}"
    else:
        cid = f"{short}_{bshort}_{copy_id_counts[key]}"
    copies[cid] = {
        "copy_id": cid,
        "book_id": book_id,
        "branch_id": branch_id,
        "status": "available",
        "due_date": None,
        "borrower_id": None,
    }
    books[book_id]["copies"].append(cid)
    return cid


# Baseline: 1 copy per book at a weighted-random branch
for bid in book_ids:
    br = random.choices(branch_ids, weights=branch_weights, k=1)[0]
    add_copy(bid, br)

# Remaining 70 copies distributed by category popularity
book_pool_weights = [
    CATEGORY_WEIGHTS.get(books[bid]["category"], 1.0) for bid in book_ids
]
for _ in range(100 - len(copies)):
    bid = random.choices(book_ids, weights=book_pool_weights, k=1)[0]
    br = random.choices(branch_ids, weights=branch_weights, k=1)[0]
    add_copy(bid, br)


# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Patrons (200)
# ═══════════════════════════════════════════════════════════════════════════
FIRST_NAMES = [
    "James",
    "Mary",
    "Robert",
    "Patricia",
    "John",
    "Jennifer",
    "Michael",
    "Linda",
    "David",
    "Elizabeth",
    "William",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
    "Thomas",
    "Sarah",
    "Christopher",
    "Karen",
    "Charles",
    "Lisa",
    "Daniel",
    "Nancy",
    "Matthew",
    "Betty",
    "Anthony",
    "Margaret",
    "Mark",
    "Sandra",
    "Donald",
    "Ashley",
    "Steven",
    "Dorothy",
    "Paul",
    "Kimberly",
    "Andrew",
    "Emily",
    "Joshua",
    "Donna",
    "Kenneth",
    "Michelle",
    "Kevin",
    "Carol",
    "Brian",
    "Amanda",
    "George",
    "Melissa",
    "Timothy",
    "Deborah",
]

LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Perez",
    "Thompson",
    "White",
    "Harris",
    "Sanchez",
    "Clark",
    "Ramirez",
    "Lewis",
    "Robinson",
    "Walker",
    "Young",
    "Allen",
    "King",
    "Wright",
    "Scott",
    "Torres",
    "Nguyen",
    "Hill",
    "Flores",
    "Green",
    "Adams",
    "Nelson",
    "Baker",
    "Hall",
    "Rivera",
    "Campbell",
    "Mitchell",
    "Carter",
    "Roberts",
]

EMAIL_DOMAINS = ["email.com", "mail.com", "inbox.com", "webmail.net"]
STREETS = [
    "Elm Street",
    "Oak Lane",
    "Pine Road",
    "Maple Avenue",
    "Cedar Drive",
    "Birch Way",
    "Walnut Court",
    "Cherry Lane",
    "Spruce Street",
    "Willow Place",
    "Main Street",
    "College Ave",
    "University Blvd",
    "Park Drive",
    "Lake Road",
    "Hill Street",
    "River Road",
    "Garden Way",
    "Forest Lane",
    "Valley Drive",
]
MEMBERSHIP_TYPES = ["standard", "student", "senior", "child"]
MEMBERSHIP_WEIGHTS = [50, 25, 15, 10]

patrons = {}
patron_ids_set = set()
patron_names_set: set[str] = set()  # Track display names to prevent duplicates

# Pre-select indices for expired memberships (~5% = 10 patrons)
expired_indices = set(random.sample(range(200), 10))

for i in range(200):
    # Pick a unique (first, last) combination — no duplicate display names
    for _attempt in range(500):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        display_name = f"{first} {last}"
        if display_name not in patron_names_set:
            break
    else:
        raise RuntimeError("Could not find a unique name after 500 attempts")
    patron_names_set.add(display_name)
    base_id = f"{first.lower()}_{last.lower()}"
    pid = base_id  # Guaranteed unique since display name is unique
    patron_ids_set.add(pid)

    mtype = random.choices(MEMBERSHIP_TYPES, weights=MEMBERSHIP_WEIGHTS, k=1)[0]

    if i in expired_indices:
        exp_date = TODAY - timedelta(days=random.randint(30, 365))
    else:
        exp_date = TODAY + timedelta(days=random.randint(60, 400))

    if mtype == "student":
        domain = "university.edu"
    else:
        domain = random.choice(EMAIL_DOMAINS)

    digits = random.randint(1, 99)
    email = f"{first.lower()}.{last.lower()}{digits}@{domain}"
    phone = f"555-{random.randint(1000, 9999):04d}"
    house_num = random.randint(1, 500)
    street = random.choice(STREETS)
    address = f"{house_num} {street}, Springfield"

    patrons[pid] = {
        "patron_id": pid,
        "name": f"{first} {last}",
        "email": email,
        "phone": phone,
        "address": address,
        "membership_type": mtype,
        "membership_expiry": date_str(exp_date),
        "active_loans": [],
        "holds": [],
        "fines_owed": 0.0,
        "borrowing_limit": BORROWING_LIMITS[mtype],
    }

all_patron_ids = list(patrons.keys())
active_patron_ids = [
    pid
    for pid in all_patron_ids
    if patrons[pid]["membership_expiry"] >= date_str(TODAY)
]


# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Loans (500)
# ═══════════════════════════════════════════════════════════════════════════
loans = {}
loan_id_set = set()


def patron_last(pid):
    return patrons[pid]["name"].split()[-1].lower()


def book_short_from_copy(copy_id):
    return book_short_names[copies[copy_id]["book_id"]]


def loan_period_weeks(membership_type):
    return (
        LOAN_PERIOD_STUDENT_WEEKS
        if membership_type == "student"
        else LOAN_PERIOD_STANDARD_WEEKS
    )


# ── Phase A: Returned loans (~450) ─────────────────────────────────────────
returned_loans = []
all_copy_ids = list(copies.keys())

for _ in range(450):
    pid = random.choice(all_patron_ids)
    cid = random.choice(all_copy_ids)

    mtype = patrons[pid]["membership_type"]
    weeks = loan_period_weeks(mtype)

    # Checkout date: random in past 12 months
    checkout_date = TODAY - timedelta(days=random.randint(21, 365))
    due_date = checkout_date + timedelta(weeks=weeks)

    # Return distribution: 80% on time, 15% slightly late, 5% very late
    r = random.random()
    if r < 0.80:
        return_date = due_date - timedelta(days=random.randint(0, 3))
    elif r < 0.95:
        return_date = due_date + timedelta(days=random.randint(1, 14))
    else:
        return_date = due_date + timedelta(days=random.randint(15, 60))

    # Don't let return date be in the future
    if return_date > TODAY:
        return_date = TODAY - timedelta(days=random.randint(1, 14))

    renewals = random.choices([0, 1, 2], weights=[70, 20, 10], k=1)[0]
    if mtype == "student":
        renewals = random.choices([0, 1, 2, 3], weights=[60, 20, 12, 8], k=1)[0]

    fine_amount = 0.0
    if return_date > due_date:
        days_late = (return_date - due_date).days
        fine_amount = round(min(days_late * OVERDUE_FINE_PER_DAY, MAX_FINE_PER_ITEM), 2)

    bshort_name = book_short_from_copy(cid)
    plast = patron_last(pid)
    base_lid = f"loan_{plast}_{bshort_name}"
    lid = make_unique_id(base_lid, loan_id_set)
    loan_id_set.add(lid)

    loan = {
        "loan_id": lid,
        "patron_id": pid,
        "copy_id": cid,
        "checkout_date": date_str(checkout_date),
        "due_date": date_str(due_date),
        "return_date": date_str(return_date),
        "renewals_count": renewals,
        "fine_amount": fine_amount,
    }
    loans[lid] = loan
    returned_loans.append(loan)


# ── Phase B: Active loans (~50) ────────────────────────────────────────────
# Target: ~50 copies checked out (50% of 100 copies).
# We'll deliberately concentrate some loans to create edge-case patrons:
#   - 1 child patron at borrowing limit (5 loans)
#   - 2 standard/senior patrons at borrowing limit (10 loans each)
# Then distribute the remaining ~25 randomly.

ACTIVE_LOAN_TARGET = 50

available_copy_ids = [cid for cid, c in copies.items() if c["status"] == "available"]
random.shuffle(available_copy_ids)
copy_iter = iter(available_copy_ids)


def create_active_loan(pid, cid):
    """Create an active loan for patron pid on copy cid. Returns loan_id."""
    mtype = patrons[pid]["membership_type"]
    weeks = loan_period_weeks(mtype)
    checkout_date = TODAY - timedelta(days=random.randint(1, 42))
    due_date = checkout_date + timedelta(weeks=weeks)

    bshort_name = book_short_from_copy(cid)
    plast = patron_last(pid)
    base_lid = f"loan_{plast}_{bshort_name}"
    lid = make_unique_id(base_lid, loan_id_set)
    loan_id_set.add(lid)

    loan = {
        "loan_id": lid,
        "patron_id": pid,
        "copy_id": cid,
        "checkout_date": date_str(checkout_date),
        "due_date": date_str(due_date),
        "return_date": None,
        "renewals_count": 0,
        "fine_amount": 0.0,
    }
    loans[lid] = loan

    copies[cid]["status"] = "checked_out"
    copies[cid]["due_date"] = date_str(due_date)
    copies[cid]["borrower_id"] = pid
    patrons[pid]["active_loans"].append(lid)
    return lid


active_loan_count = 0

# Edge case: 1 child patron at borrowing limit (5 loans)
child_patrons = [
    pid for pid in active_patron_ids if patrons[pid]["membership_type"] == "child"
]
if child_patrons:
    at_limit_child = random.choice(child_patrons)
    for _ in range(BORROWING_LIMITS["child"]):
        cid = next(copy_iter)
        create_active_loan(at_limit_child, cid)
        active_loan_count += 1

# Edge case: 2 standard/senior patrons at borrowing limit (10 loans each)
std_senior = [
    pid
    for pid in active_patron_ids
    if patrons[pid]["membership_type"] in ("standard", "senior")
    and len(patrons[pid]["active_loans"]) == 0
]
random.shuffle(std_senior)
for heavy_pid in std_senior[:2]:
    limit = patrons[heavy_pid]["borrowing_limit"]
    for _ in range(limit):
        cid = next(copy_iter)
        create_active_loan(heavy_pid, cid)
        active_loan_count += 1

# Distribute remaining active loans randomly among eligible patrons
for cid in copy_iter:
    if active_loan_count >= ACTIVE_LOAN_TARGET:
        break
    eligible = [
        pid
        for pid in active_patron_ids
        if len(patrons[pid]["active_loans"]) < patrons[pid]["borrowing_limit"]
    ]
    if not eligible:
        break
    pid = random.choice(eligible)
    create_active_loan(pid, cid)
    active_loan_count += 1


# ── Make ~15% of active loans overdue (shift checkout date back) ────────────
active_loans_list = [l for l in loans.values() if l["return_date"] is None]
overdue_target = max(8, int(len(active_loans_list) * 0.15))
non_overdue = [l for l in active_loans_list if l["due_date"] >= date_str(TODAY)]
random.shuffle(non_overdue)

for loan in non_overdue[:overdue_target]:
    mtype = patrons[loan["patron_id"]]["membership_type"]
    weeks = loan_period_weeks(mtype)
    shift = random.randint(21, 50)
    new_checkout = datetime.strptime(loan["checkout_date"], "%Y-%m-%d") - timedelta(
        days=shift
    )
    new_due = new_checkout + timedelta(weeks=weeks)
    loan["checkout_date"] = date_str(new_checkout)
    loan["due_date"] = date_str(new_due)
    copies[loan["copy_id"]]["due_date"] = date_str(new_due)


# ── Edge case: ensure >= 5 loans at max renewals ────────────────────────────
def max_renewals_for(patron_id):
    mtype = patrons[patron_id]["membership_type"]
    return MAX_RENEWALS_STUDENT if mtype == "student" else MAX_RENEWALS_STANDARD


maxed_renewals = [
    l
    for l in loans.values()
    if l["return_date"] is None
    and l["renewals_count"] >= max_renewals_for(l["patron_id"])
]
need_maxed = 5 - len(maxed_renewals)
if need_maxed > 0:
    candidates = [
        l
        for l in loans.values()
        if l["return_date"] is None and l not in maxed_renewals
    ]
    random.shuffle(candidates)
    for loan in candidates[:need_maxed]:
        loan["renewals_count"] = max_renewals_for(loan["patron_id"])


# ═══════════════════════════════════════════════════════════════════════════
# Step 6: Fines (50)
# ═══════════════════════════════════════════════════════════════════════════
fines = {}
fine_id_set = set()

# Find late-returned loans for overdue fines
late_returned = [
    l
    for l in returned_loans
    if l["return_date"] and l["due_date"] and l["return_date"] > l["due_date"]
]
random.shuffle(late_returned)

# Overdue fines (37)
overdue_fine_count = 0
for loan in late_returned:
    if overdue_fine_count >= 37:
        break
    days_late = (
        datetime.strptime(loan["return_date"], "%Y-%m-%d")
        - datetime.strptime(loan["due_date"], "%Y-%m-%d")
    ).days
    amount = round(min(days_late * OVERDUE_FINE_PER_DAY, MAX_FINE_PER_ITEM), 2)
    if amount <= 0:
        continue

    plast = patron_last(loan["patron_id"])
    base_fid = f"fine_{plast}_overdue"
    fid = make_unique_id(base_fid, fine_id_set)
    fine_id_set.add(fid)

    fines[fid] = {
        "fine_id": fid,
        "patron_id": loan["patron_id"],
        "loan_id": loan["loan_id"],
        "amount": amount,
        "reason": "overdue",
        "status": "outstanding",
        "issued_date": loan["return_date"],
    }
    overdue_fine_count += 1

# Lost fines (8): pick returned loans whose copies are currently available
available_returned = [
    l for l in returned_loans if copies[l["copy_id"]]["status"] == "available"
]
random.shuffle(available_returned)
lost_loan_ids = set()

for loan in available_returned[:8]:
    cid = loan["copy_id"]
    copies[cid]["status"] = "lost"
    lost_loan_ids.add(loan["loan_id"])

    plast = patron_last(loan["patron_id"])
    base_fid = f"fine_{plast}_lost"
    fid = make_unique_id(base_fid, fine_id_set)
    fine_id_set.add(fid)

    fines[fid] = {
        "fine_id": fid,
        "patron_id": loan["patron_id"],
        "loan_id": loan["loan_id"],
        "amount": LOST_BOOK_FINE,
        "reason": "lost",
        "status": "outstanding",
        "issued_date": loan["return_date"],
    }

# Damaged fines (5): pick returned loans with available copies (not already used for lost)
available_for_damage = [
    l
    for l in returned_loans
    if copies[l["copy_id"]]["status"] == "available"
    and l["loan_id"] not in lost_loan_ids
]
random.shuffle(available_for_damage)

for loan in available_for_damage[:5]:
    cid = loan["copy_id"]
    copies[cid]["status"] = "damaged"
    amount = round(random.uniform(5.0, 30.0), 2)

    plast = patron_last(loan["patron_id"])
    base_fid = f"fine_{plast}_damaged"
    fid = make_unique_id(base_fid, fine_id_set)
    fine_id_set.add(fid)

    fines[fid] = {
        "fine_id": fid,
        "patron_id": loan["patron_id"],
        "loan_id": loan["loan_id"],
        "amount": amount,
        "reason": "damaged",
        "status": "outstanding",
        "issued_date": loan["return_date"],
    }

# Distribute fine statuses: 40% outstanding, 45% paid, 15% waived
fine_list = list(fines.keys())
random.shuffle(fine_list)
n_fines = len(fine_list)
n_paid = int(n_fines * 0.45)
n_waived = int(n_fines * 0.15)

for fid in fine_list[:n_paid]:
    fines[fid]["status"] = "paid"
for fid in fine_list[n_paid : n_paid + n_waived]:
    fines[fid]["status"] = "waived"
# Remaining stay "outstanding"

# Edge case: ensure >= 3 patrons with outstanding fines > $10
outstanding_by_patron = defaultdict(float)
for f in fines.values():
    if f["status"] == "outstanding":
        outstanding_by_patron[f["patron_id"]] += f["amount"]

high_fine_patrons = {pid for pid, amt in outstanding_by_patron.items() if amt > 10}
if len(high_fine_patrons) < 3:
    paid_fines_sorted = sorted(
        [f for f in fines.values() if f["status"] == "paid"],
        key=lambda x: x["amount"],
        reverse=True,
    )
    for f in paid_fines_sorted:
        if len(high_fine_patrons) >= 3:
            break
        f["status"] = "outstanding"
        outstanding_by_patron[f["patron_id"]] += f["amount"]
        if outstanding_by_patron[f["patron_id"]] > 10:
            high_fine_patrons.add(f["patron_id"])


# ═══════════════════════════════════════════════════════════════════════════
# Step 7: Holds (40)
# ═══════════════════════════════════════════════════════════════════════════
holds = {}
hold_id_set = set()

# ── Pending holds (20) ──────────────────────────────────────────────────────
pending_created = 0
attempts = 0
while pending_created < 20 and attempts < 2000:
    attempts += 1
    pid = random.choice(active_patron_ids)
    bid = random.choice(book_ids)
    brid = random.choices(branch_ids, weights=branch_weights, k=1)[0]

    # All copies of this book at this branch must be non-available
    branch_copies = [
        cid
        for cid, c in copies.items()
        if c["book_id"] == bid and c["branch_id"] == brid
    ]
    if not branch_copies:
        continue
    if any(copies[cid]["status"] == "available" for cid in branch_copies):
        continue

    # No duplicate pending hold for same patron+book+branch
    dup = any(
        h["patron_id"] == pid
        and h["book_id"] == bid
        and h["branch_id"] == brid
        and h["status"] == "pending"
        for h in holds.values()
    )
    if dup:
        continue

    plast = patron_last(pid)
    bshort_name = book_short_names[bid]
    base_hid = f"hold_{plast}_{bshort_name}"
    hid = make_unique_id(base_hid, hold_id_set)
    hold_id_set.add(hid)

    position = (
        sum(
            1
            for h in holds.values()
            if h["book_id"] == bid
            and h["branch_id"] == brid
            and h["status"] == "pending"
        )
        + 1
    )

    placed_date = TODAY - timedelta(days=random.randint(1, 30))

    holds[hid] = {
        "hold_id": hid,
        "patron_id": pid,
        "book_id": bid,
        "branch_id": brid,
        "placed_date": date_str(placed_date),
        "status": "pending",
        "position_in_queue": position,
        "expiry_date": None,
    }
    patrons[pid]["holds"].append(hid)
    pending_created += 1

# ── Ready holds (6) ─────────────────────────────────────────────────────────
ready_created = 0
available_for_hold = [cid for cid, c in copies.items() if c["status"] == "available"]
random.shuffle(available_for_hold)

for cid in available_for_hold:
    if ready_created >= 6:
        break

    pid = random.choice(active_patron_ids)
    bid = copies[cid]["book_id"]
    brid = copies[cid]["branch_id"]

    plast = patron_last(pid)
    bshort_name = book_short_names[bid]
    base_hid = f"hold_{plast}_{bshort_name}"
    hid = make_unique_id(base_hid, hold_id_set)
    hold_id_set.add(hid)

    placed_date = TODAY - timedelta(days=random.randint(5, 20))
    expiry_date = TODAY + timedelta(days=random.randint(1, 7))

    holds[hid] = {
        "hold_id": hid,
        "patron_id": pid,
        "book_id": bid,
        "branch_id": brid,
        "placed_date": date_str(placed_date),
        "status": "ready",
        "position_in_queue": 1,
        "expiry_date": date_str(expiry_date),
    }
    copies[cid]["status"] = "on_hold"
    patrons[pid]["holds"].append(hid)
    ready_created += 1

# ── Expired holds (8) ───────────────────────────────────────────────────────
for _ in range(8):
    pid = random.choice(all_patron_ids)
    bid = random.choice(book_ids)
    brid = random.choices(branch_ids, weights=branch_weights, k=1)[0]

    plast = patron_last(pid)
    bshort_name = book_short_names[bid]
    base_hid = f"hold_{plast}_{bshort_name}"
    hid = make_unique_id(base_hid, hold_id_set)
    hold_id_set.add(hid)

    placed_date = TODAY - timedelta(days=random.randint(30, 90))
    expiry_date = TODAY - timedelta(days=random.randint(1, 20))

    holds[hid] = {
        "hold_id": hid,
        "patron_id": pid,
        "book_id": bid,
        "branch_id": brid,
        "placed_date": date_str(placed_date),
        "status": "expired",
        "position_in_queue": 1,
        "expiry_date": date_str(expiry_date),
    }
    # Do NOT add to patron.holds

# ── Cancelled holds (6) ─────────────────────────────────────────────────────
for _ in range(6):
    pid = random.choice(all_patron_ids)
    bid = random.choice(book_ids)
    brid = random.choices(branch_ids, weights=branch_weights, k=1)[0]

    plast = patron_last(pid)
    bshort_name = book_short_names[bid]
    base_hid = f"hold_{plast}_{bshort_name}"
    hid = make_unique_id(base_hid, hold_id_set)
    hold_id_set.add(hid)

    placed_date = TODAY - timedelta(days=random.randint(10, 60))

    holds[hid] = {
        "hold_id": hid,
        "patron_id": pid,
        "book_id": bid,
        "branch_id": brid,
        "placed_date": date_str(placed_date),
        "status": "cancelled",
        "position_in_queue": 1,
        "expiry_date": None,
    }
    # Do NOT add to patron.holds


# ═══════════════════════════════════════════════════════════════════════════
# Step 8: Events (12)
# ═══════════════════════════════════════════════════════════════════════════
EVENT_TEMPLATES = [
    # Springfield Central (3): upcoming, full, upcoming
    {
        "event_id": "story_hour_springfield",
        "branch_id": "springfield_central",
        "title": "Children's Story Hour",
        "description": "Weekly story time for children ages 3-8, featuring picture books and interactive reading.",
        "time": "10:00",
        "capacity": 25,
        "target_status": "upcoming",
    },
    {
        "event_id": "scifi_book_club_springfield",
        "branch_id": "springfield_central",
        "title": "Book Club: Science Fiction Classics",
        "description": "Monthly book club meeting discussing science fiction classics. This month: Dune by Frank Herbert.",
        "time": "18:30",
        "capacity": 15,
        "target_status": "full",
    },
    {
        "event_id": "author_talk_springfield",
        "branch_id": "springfield_central",
        "title": "Author Talk: Local Writers Series",
        "description": "Local authors share their writing process and latest works, followed by Q&A and book signing.",
        "time": "19:00",
        "capacity": 40,
        "target_status": "upcoming",
    },
    # Westside (3): upcoming, completed, upcoming
    {
        "event_id": "research_workshop_westside",
        "branch_id": "westside",
        "title": "Research Workshop: Academic Databases",
        "description": "Learn how to effectively use academic databases and research tools for papers and projects.",
        "time": "14:00",
        "capacity": 20,
        "target_status": "upcoming",
    },
    {
        "event_id": "poetry_night_westside",
        "branch_id": "westside",
        "title": "Poetry Open Mic Night",
        "description": "Share your original poetry or favorite poems in a welcoming, supportive environment.",
        "time": "19:00",
        "capacity": 30,
        "target_status": "completed",
    },
    {
        "event_id": "craft_hour_westside",
        "branch_id": "westside",
        "title": "Kids Craft Hour",
        "description": "Arts and crafts session for children ages 5-12. All materials provided.",
        "time": "11:00",
        "capacity": 15,
        "target_status": "upcoming",
    },
    # Northgate (3): full, upcoming, cancelled
    {
        "event_id": "mystery_book_club_northgate",
        "branch_id": "northgate",
        "title": "Mystery Book Club",
        "description": "Monthly mystery book club. This month: The Girl with the Dragon Tattoo by Stieg Larsson.",
        "time": "18:00",
        "capacity": 12,
        "target_status": "full",
    },
    {
        "event_id": "tech_talk_northgate",
        "branch_id": "northgate",
        "title": "Tech Talk: Introduction to Coding",
        "description": "Beginner-friendly introduction to programming concepts using Python.",
        "time": "15:00",
        "capacity": 20,
        "target_status": "upcoming",
    },
    {
        "event_id": "senior_social_northgate",
        "branch_id": "northgate",
        "title": "Senior Social: Coffee & Conversation",
        "description": "Weekly social gathering for seniors with coffee, tea, and lively discussion.",
        "time": "10:30",
        "capacity": 25,
        "target_status": "cancelled",
    },
    # Riverside (3): upcoming, completed, upcoming
    {
        "event_id": "garden_club_riverside",
        "branch_id": "riverside",
        "title": "Garden Club Meeting",
        "description": "Monthly meeting for gardening enthusiasts. Topic: Spring planting preparation.",
        "time": "13:00",
        "capacity": 18,
        "target_status": "upcoming",
    },
    {
        "event_id": "history_lecture_riverside",
        "branch_id": "riverside",
        "title": "History Lecture: Springfield Through the Ages",
        "description": "Local historian presents the rich history of Springfield from founding to present day.",
        "time": "17:00",
        "capacity": 35,
        "target_status": "completed",
    },
    {
        "event_id": "toddler_time_riverside",
        "branch_id": "riverside",
        "title": "Toddler Time: Music & Movement",
        "description": "Fun interactive session with songs, dancing, and musical instruments for toddlers and parents.",
        "time": "09:30",
        "capacity": 15,
        "target_status": "upcoming",
    },
]

events = {}
for tmpl in EVENT_TEMPLATES:
    status = tmpl["target_status"]
    capacity = tmpl["capacity"]

    if status == "upcoming":
        event_date = TODAY + timedelta(days=random.randint(14, 28))
        n_registered = int(capacity * random.uniform(0.30, 0.70))
    elif status == "full":
        event_date = TODAY + timedelta(days=random.randint(14, 28))
        n_registered = capacity
    elif status == "cancelled":
        event_date = TODAY + timedelta(days=random.randint(7, 21))
        n_registered = random.randint(2, 5)
    elif status == "completed":
        event_date = TODAY - timedelta(days=random.randint(7, 30))
        n_registered = int(capacity * random.uniform(0.60, 0.90))
    else:
        raise ValueError(f"Unknown status: {status}")

    eligible = list(active_patron_ids)
    random.shuffle(eligible)
    registered = eligible[: min(n_registered, len(eligible))]

    events[tmpl["event_id"]] = {
        "event_id": tmpl["event_id"],
        "branch_id": tmpl["branch_id"],
        "title": tmpl["title"],
        "description": tmpl["description"],
        "date": date_str(event_date),
        "time": tmpl["time"],
        "capacity": capacity,
        "registered_patrons": registered,
        "status": status,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 9: In-transit copies (3)
# ═══════════════════════════════════════════════════════════════════════════
available_copies = [cid for cid, c in copies.items() if c["status"] == "available"]
random.shuffle(available_copies)
for cid in available_copies[:3]:
    copies[cid]["status"] = "in_transit"


# ═══════════════════════════════════════════════════════════════════════════
# Step 10: Reconcile & Validate
# ═══════════════════════════════════════════════════════════════════════════

# Recompute patron fines_owed from outstanding fines
for pid in patrons:
    patrons[pid]["fines_owed"] = 0.0
for f in fines.values():
    if f["status"] == "outstanding":
        patrons[f["patron_id"]]["fines_owed"] += f["amount"]
for pid in patrons:
    patrons[pid]["fines_owed"] = round(patrons[pid]["fines_owed"], 2)

# ── Validation ──────────────────────────────────────────────────────────────
errors = []

# Foreign key checks
for lid, loan in loans.items():
    if loan["patron_id"] not in patrons:
        errors.append(f"Loan {lid}: patron {loan['patron_id']} not found")
    if loan["copy_id"] not in copies:
        errors.append(f"Loan {lid}: copy {loan['copy_id']} not found")

for hid, hold in holds.items():
    if hold["patron_id"] not in patrons:
        errors.append(f"Hold {hid}: patron {hold['patron_id']} not found")
    if hold["book_id"] not in books:
        errors.append(f"Hold {hid}: book {hold['book_id']} not found")
    if hold["branch_id"] not in branches:
        errors.append(f"Hold {hid}: branch {hold['branch_id']} not found")

for fid, fine in fines.items():
    if fine["patron_id"] not in patrons:
        errors.append(f"Fine {fid}: patron {fine['patron_id']} not found")
    if fine["loan_id"] not in loans:
        errors.append(f"Fine {fid}: loan {fine['loan_id']} not found")

for cid, copy in copies.items():
    if copy["book_id"] not in books:
        errors.append(f"Copy {cid}: book {copy['book_id']} not found")
    if copy["branch_id"] not in branches:
        errors.append(f"Copy {cid}: branch {copy['branch_id']} not found")

for eid, event in events.items():
    if event["branch_id"] not in branches:
        errors.append(f"Event {eid}: branch {event['branch_id']} not found")
    for pid in event["registered_patrons"]:
        if pid not in patrons:
            errors.append(f"Event {eid}: patron {pid} not found")

# Verify active_loans back-references
for pid, patron in patrons.items():
    for lid in patron["active_loans"]:
        if lid not in loans:
            errors.append(f"Patron {pid}: active_loan {lid} not in loans")
        elif loans[lid]["return_date"] is not None:
            errors.append(f"Patron {pid}: active_loan {lid} is returned")

# Verify holds back-references
for pid, patron in patrons.items():
    for hid in patron["holds"]:
        if hid not in holds:
            errors.append(f"Patron {pid}: hold {hid} not in holds")
        elif holds[hid]["status"] not in ("pending", "ready"):
            errors.append(f"Patron {pid}: hold {hid} status is {holds[hid]['status']}")

# Verify copy status consistency
for cid, copy in copies.items():
    if copy["status"] == "checked_out":
        if copy["due_date"] is None:
            errors.append(f"Copy {cid}: checked_out but no due_date")
        if copy["borrower_id"] is None:
            errors.append(f"Copy {cid}: checked_out but no borrower_id")
    elif copy["status"] in ("available", "in_transit", "damaged", "lost"):
        if copy["borrower_id"] is not None:
            errors.append(f"Copy {cid}: status={copy['status']} but has borrower_id")

# Verify hold queue positions are sequential per (book, branch)
pending_holds_by_key = defaultdict(list)
for h in holds.values():
    if h["status"] == "pending":
        pending_holds_by_key[(h["book_id"], h["branch_id"])].append(h)

for key, hold_list in pending_holds_by_key.items():
    positions = sorted(h["position_in_queue"] for h in hold_list)
    expected = list(range(1, len(hold_list) + 1))
    if positions != expected:
        errors.append(f"Hold queue {key}: positions {positions} != expected {expected}")


# ── Statistics ──────────────────────────────────────────────────────────────
active_loans_final = [l for l in loans.values() if l["return_date"] is None]
overdue_active = [l for l in active_loans_final if l["due_date"] < date_str(TODAY)]
copy_statuses = defaultdict(int)
for c in copies.values():
    copy_statuses[c["status"]] += 1
membership_counts = defaultdict(int)
for p in patrons.values():
    membership_counts[p["membership_type"]] += 1
cat_counts = defaultdict(int)
for b in books.values():
    cat_counts[b["category"]] += 1
expired_patrons = [
    p for p in patrons.values() if p["membership_expiry"] < date_str(TODAY)
]
high_fine_pats = [p for p in patrons.values() if p["fines_owed"] > 10]
at_limit_pats = [
    p
    for p in patrons.values()
    if len(p["active_loans"]) >= p["borrowing_limit"] and p["borrowing_limit"] > 0
]
maxed_renewal_loans = [
    l
    for l in loans.values()
    if l["return_date"] is None
    and l["renewals_count"] >= max_renewals_for(l["patron_id"])
]
books_with_pending_holds = {
    h["book_id"] for h in holds.values() if h["status"] == "pending"
}
loans_blocked_by_holds = [
    l
    for l in active_loans_final
    if copies[l["copy_id"]]["book_id"] in books_with_pending_holds
]
patron_fine_counts = defaultdict(int)
for f in fines.values():
    patron_fine_counts[f["patron_id"]] += 1
waiver_eligible = [
    pid
    for pid, cnt in patron_fine_counts.items()
    if cnt == 1
    and any(
        f["patron_id"] == pid and f["status"] == "outstanding" for f in fines.values()
    )
]
book_hold_counts = defaultdict(int)
for h in holds.values():
    if h["status"] == "pending":
        book_hold_counts[h["book_id"]] += 1
multi_hold_books = [bid for bid, cnt in book_hold_counts.items() if cnt >= 2]

print("=" * 60)
print("LIBRARY DATABASE GENERATION COMPLETE")
print("=" * 60)
print(f"\nPatrons:     {len(patrons)}")
print(f"  Standard:  {membership_counts['standard']}")
print(f"  Student:   {membership_counts['student']}")
print(f"  Senior:    {membership_counts['senior']}")
print(f"  Child:     {membership_counts['child']}")
print(f"  Expired:   {len(expired_patrons)}")
print(f"\nBooks:       {len(books)}")
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat}: {cnt}")
print(f"\nBranches:    {len(branches)}")
print(f"\nCopies:      {len(copies)}")
for status, cnt in sorted(copy_statuses.items()):
    print(f"  {status}: {cnt}")
print(f"\nLoans:       {len(loans)}")
print(f"  Active:    {len(active_loans_final)}")
print(f"  Returned:  {len(loans) - len(active_loans_final)}")
print(f"  Overdue (active): {len(overdue_active)}")
print(f"\nHolds:       {len(holds)}")
print(f"  Pending:   {sum(1 for h in holds.values() if h['status'] == 'pending')}")
print(f"  Ready:     {sum(1 for h in holds.values() if h['status'] == 'ready')}")
print(f"  Expired:   {sum(1 for h in holds.values() if h['status'] == 'expired')}")
print(f"  Cancelled: {sum(1 for h in holds.values() if h['status'] == 'cancelled')}")
print(f"\nFines:       {len(fines)}")
print(
    f"  Outstanding: {sum(1 for f in fines.values() if f['status'] == 'outstanding')}"
)
print(f"  Paid:      {sum(1 for f in fines.values() if f['status'] == 'paid')}")
print(f"  Waived:    {sum(1 for f in fines.values() if f['status'] == 'waived')}")
print(f"\nEvents:      {len(events)}")
print(f"  Upcoming:  {sum(1 for e in events.values() if e['status'] == 'upcoming')}")
print(f"  Full:      {sum(1 for e in events.values() if e['status'] == 'full')}")
print(f"  Cancelled: {sum(1 for e in events.values() if e['status'] == 'cancelled')}")
print(f"  Completed: {sum(1 for e in events.values() if e['status'] == 'completed')}")
print(f"\n-- Edge Cases --")
print(f"  Patrons with fines > $10:       {len(high_fine_pats)}")
print(f"  Expired memberships:            {len(expired_patrons)}")
print(f"  Patrons at borrowing limit:     {len(at_limit_pats)}")
print(f"  Maxed-out loan renewals:        {len(maxed_renewal_loans)}")
print(f"  Loans blocked by holds:         {len(loans_blocked_by_holds)}")
print(f"  Overdue active loans:           {len(overdue_active)}")
print(f"  Lost copies:                    {copy_statuses.get('lost', 0)}")
print(f"  Damaged copies:                 {copy_statuses.get('damaged', 0)}")
print(f"  In-transit copies:              {copy_statuses.get('in_transit', 0)}")
print(f"  On-hold copies:                 {copy_statuses.get('on_hold', 0)}")
print(f"  Waiver-eligible patrons:        {len(waiver_eligible)}")
print(f"  Books with multiple holds:      {len(multi_hold_books)}")

if errors:
    print(f"\n!! VALIDATION ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
else:
    print("\nAll validation checks passed")


# ── Write db.json ───────────────────────────────────────────────────────────
db = {
    "patrons": patrons,
    "books": books,
    "copies": copies,
    "branches": branches,
    "loans": loans,
    "holds": holds,
    "fines": fines,
    "events": events,
}

output_path = Path(__file__).parent / "db.json"
with open(output_path, "w") as f:
    json.dump(db, f, indent=2)

print(f"\nWritten to {output_path}")
