#!/usr/bin/env python3
"""Generate ~200 car rental tasks from db.json.

Standalone script (stdlib only). Deterministic via random.seed(42).

Usage:
    python generate_tasks.py
"""
import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

HERE = Path(__file__).parent
DB_PATH = HERE / "db.json"
TASKS_PATH = HERE / "tasks.json"
SPLIT_PATH = HERE / "split_tasks.json"

TODAY = datetime(2025, 10, 15)
TODAY_STR = "2025-10-15"

DOMAIN = "car_rental"

# ── Policy constants (mirror tools.py) ──────────────────────────

BASE_RATES = {
    "economy": 35.0,
    "compact": 45.0,
    "midsize": 55.0,
    "suv": 75.0,
    "luxury": 120.0,
    "van": 85.0,
}
LOYALTY_DISCOUNTS = {
    "none": 0.0,
    "silver": 0.10,
    "gold": 0.15,
    "platinum": 0.20,
}
ONE_WAY_SURCHARGE = 75.0
INSURANCE_BASIC_DAILY = 15.0
INSURANCE_PREMIUM_DAILY = 30.0
ROADSIDE_FEE = 150.0
MAX_CREDIT = 200.0
CANCEL_FEE = 50.0

# ── Grammar Helpers ──────────────────────────────────────────────

CATEGORY_DISPLAY = {
    "economy": "economy",
    "compact": "compact",
    "midsize": "midsize",
    "suv": "SUV",
    "luxury": "luxury",
    "van": "van",
}

CATEGORY_ARTICLE = {
    "economy": "an",
    "compact": "a",
    "midsize": "a",
    "suv": "an",
    "luxury": "a",
    "van": "a",
}


def fmt_cat(cat):
    """Display name for vehicle category ('suv' → 'SUV')."""
    return CATEGORY_DISPLAY.get(cat, cat)


def a_cat(cat):
    """Article + display category: 'an economy', 'an SUV', 'a compact'."""
    return f"{CATEGORY_ARTICLE.get(cat, 'a')} {fmt_cat(cat)}"


def days_str(n):
    """Pluralize day: '1 day', '2 days'."""
    return f"{n} day" if n == 1 else f"{n} days"


# ── Load DB ─────────────────────────────────────────────────────

def load_db():
    return json.loads(DB_PATH.read_text())


# ── Entity Indexes ──────────────────────────────────────────────

@dataclass
class EntityIndexes:
    # Customers
    all_customers: list = field(default_factory=list)
    customers_with_loyalty: list = field(default_factory=list)
    customers_platinum: list = field(default_factory=list)
    customers_gold: list = field(default_factory=list)
    customers_silver: list = field(default_factory=list)
    customers_no_loyalty: list = field(default_factory=list)
    customers_expired_license: list = field(default_factory=list)
    customers_valid_license: list = field(default_factory=list)
    customers_under_25: list = field(default_factory=list)
    customers_25_plus: list = field(default_factory=list)

    # Reservations
    confirmed_reservations: list = field(default_factory=list)
    active_reservations: list = field(default_factory=list)
    completed_reservations: list = field(default_factory=list)
    cancelled_reservations: list = field(default_factory=list)
    confirmed_with_insurance: list = field(default_factory=list)
    confirmed_no_insurance: list = field(default_factory=list)
    confirmed_with_extras: list = field(default_factory=list)
    confirmed_one_way: list = field(default_factory=list)
    confirmed_same_location: list = field(default_factory=list)

    # Vehicles
    available_vehicles: list = field(default_factory=list)
    available_by_category_location: dict = field(default_factory=dict)

    # Agreements
    active_agreements: list = field(default_factory=list)
    active_agreements_with_premium: list = field(default_factory=list)
    active_agreements_without_premium: list = field(default_factory=list)
    completed_agreements: list = field(default_factory=list)

    # Invoices
    disputed_invoices: list = field(default_factory=list)
    paid_invoices: list = field(default_factory=list)

    # Locations
    all_locations: list = field(default_factory=list)
    airport_locations: list = field(default_factory=list)
    city_locations: list = field(default_factory=list)


def build_indexes(db):
    ix = EntityIndexes()

    customers = db["customers"]
    reservations = db["reservations"]
    vehicles = db["vehicles"]
    agreements = db["rental_agreements"]
    invoices = db["invoices"]
    locations = db["locations"]

    # ── Filter ambiguous names ──
    name_count = {}
    for c in customers.values():
        name_count[c["name"]] = name_count.get(c["name"], 0) + 1
    ambiguous_names = {n for n, cnt in name_count.items() if cnt > 1}
    ambiguous_cids = {
        c["customer_id"]
        for c in customers.values()
        if c["name"] in ambiguous_names
    }

    # ── Customers ──
    for cid, c in customers.items():
        if cid in ambiguous_cids:
            continue

        ix.all_customers.append(cid)

        dob = datetime.strptime(c["dob"], "%Y-%m-%d")
        age = (TODAY - dob).days // 365
        lic_exp = datetime.strptime(c["license_expiry"], "%Y-%m-%d")

        if lic_exp < TODAY:
            ix.customers_expired_license.append(cid)
        else:
            ix.customers_valid_license.append(cid)

        if age < 25:
            ix.customers_under_25.append(cid)
        else:
            ix.customers_25_plus.append(cid)

        tier = c["loyalty_tier"]
        if tier == "platinum":
            ix.customers_platinum.append(cid)
            ix.customers_with_loyalty.append(cid)
        elif tier == "gold":
            ix.customers_gold.append(cid)
            ix.customers_with_loyalty.append(cid)
        elif tier == "silver":
            ix.customers_silver.append(cid)
            ix.customers_with_loyalty.append(cid)
        else:
            ix.customers_no_loyalty.append(cid)

    # ── Reservations ──
    for rid, r in reservations.items():
        cid = r["customer_id"]
        if cid in ambiguous_cids:
            continue

        status = r["status"]
        if status == "confirmed":
            ix.confirmed_reservations.append(rid)
            if r["insurance_type"] != "none":
                ix.confirmed_with_insurance.append(rid)
            else:
                ix.confirmed_no_insurance.append(rid)
            if r["extras"]:
                ix.confirmed_with_extras.append(rid)
            if r["pickup_location_id"] != r["dropoff_location_id"]:
                ix.confirmed_one_way.append(rid)
            else:
                ix.confirmed_same_location.append(rid)
        elif status == "active":
            ix.active_reservations.append(rid)
        elif status == "completed":
            ix.completed_reservations.append(rid)
        elif status == "cancelled":
            ix.cancelled_reservations.append(rid)

    # ── Vehicles ──
    for vid, v in vehicles.items():
        if v["status"] == "available":
            ix.available_vehicles.append(vid)
            key = (v["category"], v["location_id"])
            ix.available_by_category_location.setdefault(key, []).append(vid)

    # ── Agreements ──
    for aid, a in agreements.items():
        cid = a["customer_id"]
        if cid in ambiguous_cids:
            continue
        if a["actual_dropoff"] is None:
            ix.active_agreements.append(aid)
            res_id = a["reservation_id"]
            if res_id in reservations:
                ins = reservations[res_id].get("insurance_type", "none")
                if ins == "premium":
                    ix.active_agreements_with_premium.append(aid)
                else:
                    ix.active_agreements_without_premium.append(aid)
        else:
            ix.completed_agreements.append(aid)

    # ── Invoices ──
    for iid, inv in invoices.items():
        if inv["customer_id"] in ambiguous_cids:
            continue
        if inv["status"] == "disputed":
            ix.disputed_invoices.append(iid)
        elif inv["status"] == "paid":
            ix.paid_invoices.append(iid)

    # ── Locations ──
    for lid, loc in locations.items():
        ix.all_locations.append(lid)
        if loc.get("airport_code"):
            ix.airport_locations.append(lid)
        else:
            ix.city_locations.append(lid)

    return ix


# ── Persona System ──────────────────────────────────────────────

@dataclass
class Persona:
    label: str
    instructions: str
    auth: str  # "name" or "email"
    difficulty: str  # "easy", "medium", "hard"


EASY_PERSONAS = [
    Persona(
        label="Friendly and direct business traveler",
        instructions=(
            "You are polite and efficient. Provide all requested information "
            "clearly and promptly. If the agent asks clarifying questions, answer "
            "them directly without extra commentary."
        ),
        auth="name",
        difficulty="easy",
    ),
    Persona(
        label="Organized frequent renter",
        instructions=(
            "You know the rental process well. State your request clearly, "
            "provide your name and details upfront. You are cooperative and "
            "concise in your responses."
        ),
        auth="name",
        difficulty="easy",
    ),
]

MEDIUM_PERSONAS = [
    Persona(
        label="Casual vacation planner",
        instructions=(
            "You're planning a trip and are somewhat flexible. You provide "
            "information gradually — you might not mention all details upfront "
            "but respond helpfully when asked. You're friendly but not in a rush."
        ),
        auth="name",
        difficulty="medium",
    ),
    Persona(
        label="Busy professional, terse communicator",
        instructions=(
            "You're short on time. Give brief, sometimes incomplete answers. "
            "You might skip details you think are obvious. If asked to repeat "
            "or clarify, do so but with slight impatience."
        ),
        auth="name",
        difficulty="medium",
    ),
    Persona(
        label="Family trip coordinator",
        instructions=(
            "You're organizing for your family and juggling logistics. You may "
            "mention tangential concerns (child seats, space for luggage) before "
            "getting to the core request. You eventually provide all needed info."
        ),
        auth="name",
        difficulty="medium",
    ),
]

HARD_PERSONAS = [
    Persona(
        label="Confused first-time renter",
        instructions=(
            "You've never rented a car before. You don't know the categories, "
            "insurance options, or process. Ask basic questions and provide "
            "information only when specifically asked. You're unsure about what "
            "you need and rely on the agent to guide you."
        ),
        auth="name",
        difficulty="hard",
    ),
    Persona(
        label="Frustrated customer with a complaint",
        instructions=(
            "You're upset about a previous experience or charge. You may vent "
            "before stating your actual request. You're curt and impatient, but "
            "eventually cooperate once the agent addresses your concern. Provide "
            "information grudgingly."
        ),
        auth="name",
        difficulty="hard",
    ),
    Persona(
        label="Vague and indecisive renter",
        instructions=(
            "You're not sure exactly what you want. You describe your needs in "
            "general terms ('something not too big', 'maybe for a week or so'). "
            "You change your mind when presented with options. Provide details "
            "only when specifically pressed."
        ),
        auth="name",
        difficulty="hard",
    ),
    Persona(
        label="Chatty traveler who goes off-topic",
        instructions=(
            "You're talkative and friendly but digressive. You embed your request "
            "in stories about your trip, your family, your previous rentals. The "
            "agent needs to extract the key details from your conversation. You "
            "eventually answer direct questions but always add extra context."
        ),
        auth="name",
        difficulty="hard",
    ),
    Persona(
        label="Budget-conscious renter questioning every charge",
        instructions=(
            "You're very cost-conscious. You question every line item, ask about "
            "hidden fees, and compare options before committing. You want the "
            "cheapest option for everything. Provide your details, but always "
            "follow up with price-related questions."
        ),
        auth="name",
        difficulty="hard",
    ),
]

ALL_EASY_MEDIUM = EASY_PERSONAS + MEDIUM_PERSONAS


def pick_easy_persona():
    return random.choice(ALL_EASY_MEDIUM)


def pick_hard_persona():
    return random.choice(HARD_PERSONAS)


# ── Vague Descriptions ──────────────────────────────────────────

VAGUE_CATEGORY_DESCRIPTIONS = {
    "economy": "something small and cheap, just basic transportation",
    "compact": "a smallish car, nothing fancy but comfortable enough",
    "midsize": "a regular-sized car, not too small and not too big",
    "suv": "something bigger, maybe one of those SUV things for my family",
    "luxury": "a nice car, something premium and comfortable for a special occasion",
    "van": "a big vehicle, we need space for everyone and all the luggage",
}


# ── Entity Usage Tracking ───────────────────────────────────────

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


# ── Task Builders ───────────────────────────────────────────────

def make_task(
    task_id,
    purpose,
    relevant_policies,
    notes,
    persona,
    task_instructions,
    reason_for_call,
    known_info,
    unknown_info,
    ticket,
    actions,
    env_assertions=None,
    nl_assertions=None,
    reward_basis=None,
):
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
                "domain": DOMAIN,
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


# ── Helpers ─────────────────────────────────────────────────────

def rental_days(pickup_str, dropoff_str):
    p = datetime.strptime(pickup_str, "%Y-%m-%d %H:%M")
    d = datetime.strptime(dropoff_str, "%Y-%m-%d %H:%M")
    hours = (d - p).total_seconds() / 3600
    return max(1, math.ceil(hours / 24))


def future_date(days_ahead, hour=10):
    dt = TODAY + timedelta(days=days_ahead)
    return dt.strftime(f"%Y-%m-%d {hour:02d}:00")


def customer_name(db, cid):
    return db["customers"][cid]["name"]


def first_available_vehicle(db, ix, category, location_id):
    """Return the first available vehicle of category at location (mirrors tool order)."""
    key = (category, location_id)
    vids = ix.available_by_category_location.get(key, [])
    if vids:
        return vids[0]
    return None


# ── Tier 1: Simple Single-Action Generators ─────────────────────

def gen_create_reservation(db, ix, n):
    """Simple reservation creation — customer wants to book a car."""
    tasks = []
    pool = [c for c in ix.customers_valid_license if c in ix.customers_25_plus]
    random.shuffle(pool)

    categories = ["economy", "compact", "midsize", "suv"]
    locations = ix.all_locations[:]

    for i in range(min(n, len(pool))):
        cid = pool[i]
        track_use(cid)
        cust = db["customers"][cid]
        name = cust["name"]

        cat = categories[i % len(categories)]
        loc_id = locations[i % len(locations)]
        loc_name = db["locations"][loc_id]["name"]

        vid = first_available_vehicle(db, ix, cat, loc_id)
        if vid is None:
            continue

        days_ahead = random.randint(5, 30)
        rent_days = random.randint(2, 7)
        pickup = future_date(days_ahead)
        dropoff = future_date(days_ahead + rent_days)

        # Easy variant
        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"create_reservation_{i+1}a",
            purpose=f"Simple reservation creation — {cat} at {loc_name}",
            relevant_policies="Driver must be 21+, 25+ for luxury. Valid license required.",
            notes=f"{name} books a {cat} vehicle at {loc_name} for {rent_days} days.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You want to rent {a_cat(cat)} car. "
                f"{ep.instructions} State your request clearly."
            ),
            reason_for_call=(
                f"I'd like to book {a_cat(cat)} car at {loc_name}, "
                f"picking up on {pickup.split(' ')[0]} and returning {rent_days} days later."
            ),
            known_info=(
                f"Your name is {name}. You want {a_cat(cat)} car at {loc_name}. "
                f"Pickup: {pickup}, return {rent_days} days later. No insurance needed."
            ),
            unknown_info="You don't know the exact vehicle ID or your customer ID.",
            ticket=f"Customer {name} wants to book {a_cat(cat)} at {loc_name}.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up customer {name}", compare_args=[]),
                action("create_1", "create_reservation", {
                    "customer_id": cid, "category": cat,
                    "pickup_location_id": loc_id, "dropoff_location_id": loc_id,
                    "pickup_datetime": pickup, "dropoff_datetime": dropoff,
                    "insurance_type": "none",
                }, f"Create {cat} reservation for {name}",
                       compare_args=["customer_id", "category", "pickup_location_id", "dropoff_location_id"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_exists", {"customer_id": cid}),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        # Hard variant
        hp = pick_hard_persona()
        vague_cat = VAGUE_CATEGORY_DESCRIPTIONS.get(cat, f"a {cat} car")
        tasks.append(make_task(
            task_id=f"create_reservation_{i+1}b",
            purpose=f"Simple reservation creation — vague request for {cat}",
            relevant_policies="Driver must be 21+, 25+ for luxury. Valid license required.",
            notes=f"{name} vaguely asks for a rental car. Target: {cat} at {loc_name}.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You need to rent a car but aren't sure about categories. "
                f"{hp.instructions} You want {vague_cat}."
            ),
            reason_for_call=(
                f"I need to rent a car... {vague_cat}. "
                f"Sometime around {pickup.split(' ')[0]} for about {rent_days} days."
            ),
            known_info=(
                f"Your name is {name}. You want {vague_cat}. "
                f"Around {pickup.split(' ')[0]} for roughly {rent_days} days. "
                f"Prefer {loc_name} area but flexible."
            ),
            unknown_info="You don't know car categories, exact pricing, or your customer ID.",
            ticket=f"Customer {name} wants to rent a car (vague). Target: {cat} at {loc_name}.",
            actions=[
                action("create_1", "create_reservation", {
                    "customer_id": cid, "category": cat,
                    "pickup_location_id": loc_id, "dropoff_location_id": loc_id,
                    "pickup_datetime": pickup, "dropoff_datetime": dropoff,
                }, f"Create reservation for {name}",
                       compare_args=["customer_id", "category"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_exists", {"customer_id": cid}),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_cancel_reservation(db, ix, n):
    """Cancel a confirmed reservation."""
    tasks = []
    pool = list(ix.confirmed_reservations)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        rid = pool[i]
        res = db["reservations"][rid]
        cid = res["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        cat = res["vehicle_category"]
        pickup_loc = db["locations"][res["pickup_location_id"]]["name"]

        # Easy
        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"cancel_reservation_{i+1}a",
            purpose=f"Cancel confirmed {cat} reservation",
            relevant_policies="Free cancel >48h before pickup, $50 fee within 48h.",
            notes=f"{name} cancels reservation {rid} for {cat} at {pickup_loc}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You need to cancel your upcoming car rental. "
                f"{ep.instructions}"
            ),
            reason_for_call=(
                f"I need to cancel my reservation for the {fmt_cat(cat)} at {pickup_loc}. "
                f"My plans changed."
            ),
            known_info=(
                f"Your name is {name}. You have a reservation for {a_cat(cat)} "
                f"at {pickup_loc}. You want to cancel because your plans changed."
            ),
            unknown_info="You don't know the reservation ID or exact cancellation fee.",
            ticket=f"{name} wants to cancel {cat} reservation at {pickup_loc}.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up customer {name}", compare_args=[]),
                action("cancel_1", "cancel_reservation", {
                    "reservation_id": rid, "reason": "Plans changed",
                }, f"Cancel reservation {rid}",
                       compare_args=["reservation_id"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_status", {
                    "reservation_id": rid, "expected_status": "cancelled",
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        # Hard
        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"cancel_reservation_{i+1}b",
            purpose=f"Cancel reservation — difficult customer interaction",
            relevant_policies="Free cancel >48h before pickup, $50 fee within 48h.",
            notes=f"{name} wants to cancel but is vague about which reservation.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You want to cancel a car rental but you're "
                f"unsure about the details. {hp.instructions}"
            ),
            reason_for_call=(
                f"I think I have a rental coming up that I need to cancel... "
                f"it was for some kind of car at {pickup_loc}?"
            ),
            known_info=(
                f"Your name is {name}. You think you have an upcoming rental. "
                f"It was near {pickup_loc}. Confirm details when the agent finds it."
            ),
            unknown_info="You don't remember the exact dates or car type.",
            ticket=f"{name} wants to cancel a reservation (vague).",
            actions=[
                action("cancel_1", "cancel_reservation", {
                    "reservation_id": rid, "reason": "Plans changed",
                }, f"Cancel reservation {rid}",
                       compare_args=["reservation_id"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_status", {
                    "reservation_id": rid, "expected_status": "cancelled",
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_modify_reservation_dates(db, ix, n):
    """Modify reservation pickup/dropoff dates."""
    tasks = []
    pool = list(ix.confirmed_same_location)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        rid = pool[i]
        res = db["reservations"][rid]
        cid = res["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        # New dates: shift by 2 days later
        old_pickup = datetime.strptime(res["pickup_datetime"], "%Y-%m-%d %H:%M")
        new_pickup = old_pickup + timedelta(days=2)
        old_dropoff = datetime.strptime(res["dropoff_datetime"], "%Y-%m-%d %H:%M")
        new_dropoff = old_dropoff + timedelta(days=2)
        new_pickup_str = new_pickup.strftime("%Y-%m-%d %H:%M")
        new_dropoff_str = new_dropoff.strftime("%Y-%m-%d %H:%M")

        cat = res["vehicle_category"]

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"modify_dates_{i+1}a",
            purpose=f"Modify reservation dates for {cat}",
            relevant_policies="Only confirmed reservations can be modified.",
            notes=f"{name} shifts reservation {rid} dates by 2 days later.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You need to change your pickup and return dates "
                f"to 2 days later than originally booked. {ep.instructions}"
            ),
            reason_for_call=(
                f"I need to push my rental dates back by 2 days. "
                f"New pickup: {new_pickup_str.split(' ')[0]}."
            ),
            known_info=(
                f"Your name is {name}. You have {a_cat(cat)} reservation. "
                f"You want to move pickup to {new_pickup_str} and "
                f"dropoff to {new_dropoff_str}."
            ),
            unknown_info="You don't know the reservation ID or the new total.",
            ticket=f"{name} wants to change rental dates for {cat} reservation.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("modify_1", "modify_reservation", {
                    "reservation_id": rid,
                    "pickup_datetime": new_pickup_str,
                    "dropoff_datetime": new_dropoff_str,
                }, f"Modify dates for {rid}",
                       compare_args=["reservation_id"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_status", {
                    "reservation_id": rid, "expected_status": "confirmed",
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"modify_dates_{i+1}b",
            purpose=f"Modify reservation dates — vague customer",
            relevant_policies="Only confirmed reservations can be modified.",
            notes=f"{name} vaguely asks to shift dates.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You need to change your dates but aren't sure "
                f"of the exact new dates. {hp.instructions} "
                f"Eventually confirm: 2 days later than currently booked."
            ),
            reason_for_call=(
                f"My trip got delayed a couple days... can we push my car rental back?"
            ),
            known_info=(
                f"Your name is {name}. You have an upcoming rental. "
                f"You want to delay by about 2 days. Confirm when agent proposes new dates."
            ),
            unknown_info="You don't remember exact current dates or reservation ID.",
            ticket=f"{name} wants to shift dates (vague).",
            actions=[
                action("modify_1", "modify_reservation", {
                    "reservation_id": rid,
                    "pickup_datetime": new_pickup_str,
                    "dropoff_datetime": new_dropoff_str,
                }, f"Modify dates for {rid}",
                       compare_args=["reservation_id"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_status", {
                    "reservation_id": rid, "expected_status": "confirmed",
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_modify_insurance(db, ix, n):
    """Modify insurance type on a reservation."""
    tasks = []
    pool = list(ix.confirmed_no_insurance)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        rid = pool[i]
        res = db["reservations"][rid]
        cid = res["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        # Upgrade to basic or premium
        new_insurance = random.choice(["basic", "premium"])

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"modify_insurance_{i+1}a",
            purpose=f"Add {new_insurance} insurance to reservation",
            relevant_policies="Insurance: none ($0), basic ($15/day, $500 deductible), premium ($30/day, $0 deductible).",
            notes=f"{name} adds {new_insurance} insurance to reservation {rid}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You want to add {new_insurance} insurance to your "
                f"upcoming rental. {ep.instructions}"
            ),
            reason_for_call=(
                f"I'd like to add {new_insurance} insurance to my reservation, please."
            ),
            known_info=(
                f"Your name is {name}. You have a reservation without insurance. "
                f"You want to add {new_insurance} insurance."
            ),
            unknown_info="You don't know the exact cost increase or reservation ID.",
            ticket=f"{name} wants to add {new_insurance} insurance.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("modify_1", "modify_reservation", {
                    "reservation_id": rid, "insurance_type": new_insurance,
                }, f"Add {new_insurance} insurance to {rid}",
                       compare_args=["reservation_id", "insurance_type"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_insurance", {
                    "reservation_id": rid, "expected_insurance": new_insurance,
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"modify_insurance_{i+1}b",
            purpose=f"Add insurance — customer unsure about options",
            relevant_policies="Insurance: basic ($15/day), premium ($30/day).",
            notes=f"{name} unsure about insurance options, wants coverage.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You're worried about driving a rental without "
                f"insurance but don't know the options. {hp.instructions} "
                f"Accept {new_insurance} when the agent explains the options."
            ),
            reason_for_call=(
                f"I'm a bit nervous about driving without insurance... "
                f"what coverage options do you have?"
            ),
            known_info=(
                f"Your name is {name}. You have a reservation. "
                f"You want insurance but don't know the types. "
                f"You'll pick {new_insurance} when presented with options."
            ),
            unknown_info="You don't know insurance types, pricing, or deductibles.",
            ticket=f"{name} wants insurance (unsure which).",
            actions=[
                action("modify_1", "modify_reservation", {
                    "reservation_id": rid, "insurance_type": new_insurance,
                }, f"Add insurance to {rid}",
                       compare_args=["reservation_id", "insurance_type"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_insurance", {
                    "reservation_id": rid, "expected_insurance": new_insurance,
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_apply_loyalty_points(db, ix, n):
    """Apply loyalty points discount to a reservation."""
    tasks = []
    # Need customers with loyalty points AND a confirmed reservation
    pool = []
    for rid in ix.confirmed_reservations:
        res = db["reservations"][rid]
        cid = res["customer_id"]
        cust = db["customers"][cid]
        if cust["loyalty_points"] >= 200:
            pool.append((cid, rid))

    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        cid, rid = pool[i]
        cust = db["customers"][cid]
        name = cust["name"]
        track_use(cid)

        points = min(500, cust["loyalty_points"])
        discount = (points / 100) * 10

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"apply_loyalty_{i+1}",
            purpose=f"Apply {points} loyalty points to reservation",
            relevant_policies="100 points = $10 discount. Cannot exceed total.",
            notes=f"{name} ({cust['loyalty_tier']}) applies {points} points to {rid}. Discount: ${discount:.2f}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You want to use your loyalty points on your "
                f"upcoming rental. {ep.instructions}"
            ),
            reason_for_call=(
                f"I'd like to use some of my loyalty points on my reservation. "
                f"I'd like to use {points} points."
            ),
            known_info=(
                f"Your name is {name}. You are a {cust['loyalty_tier']} member. "
                f"You want to redeem {points} loyalty points."
            ),
            unknown_info="You don't know the exact dollar discount or reservation ID.",
            ticket=f"{name} wants to apply {points} loyalty points to reservation.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("apply_1", "apply_loyalty_discount", {
                    "reservation_id": rid, "points": points,
                }, f"Apply {points} points to {rid}",
                       compare_args=["reservation_id", "points"]),
            ],
            env_assertions=[
                env_assert("assert_customer_loyalty_points_decreased", {
                    "customer_id": cid, "max_points": cust["loyalty_points"] - points,
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_extend_rental(db, ix, n):
    """Extend an active rental by additional days."""
    tasks = []
    pool = list(ix.active_agreements)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        aid = pool[i]
        agr = db["rental_agreements"][aid]
        cid = agr["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        res = db["reservations"][agr["reservation_id"]]
        old_dropoff = datetime.strptime(res["dropoff_datetime"], "%Y-%m-%d %H:%M")
        extra_days = random.randint(1, 3)
        new_dropoff = old_dropoff + timedelta(days=extra_days)
        new_dropoff_str = new_dropoff.strftime("%Y-%m-%d %H:%M")

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"extend_rental_{i+1}a",
            purpose=f"Extend active rental by {extra_days} days",
            relevant_policies="Active rentals can be extended. Late returns after grace period incur extra day charge.",
            notes=f"{name} extends rental agreement {aid} by {extra_days} days.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You currently have a car rented and need it for "
                f"{days_str(extra_days)} more than planned. {ep.instructions}"
            ),
            reason_for_call=(
                f"I need to keep my rental car for {days_str(extra_days)} extra. "
                f"Can you extend my rental?"
            ),
            known_info=(
                f"Your name is {name}. You have an active rental. "
                f"You need {days_str(extra_days)} more."
            ),
            unknown_info="You don't know the agreement ID or new total cost.",
            ticket=f"{name} wants to extend active rental by {extra_days} days.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("extend_1", "extend_rental", {
                    "agreement_id": aid,
                    "new_dropoff_datetime": new_dropoff_str,
                }, f"Extend rental {aid}",
                       compare_args=["agreement_id"]),
            ],
            reward_basis=["ACTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"extend_rental_{i+1}b",
            purpose=f"Extend rental — customer unsure about duration",
            relevant_policies="Active rentals can be extended.",
            notes=f"{name} vaguely wants to keep the car longer.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. Your trip is taking longer than expected. "
                f"{hp.instructions} Eventually confirm you need {days_str(extra_days)} more."
            ),
            reason_for_call=(
                f"My trip is running longer than I thought... "
                f"I might need the car a bit longer."
            ),
            known_info=(
                f"Your name is {name}. You have a rental. "
                f"Confirm {days_str(extra_days)} more when asked."
            ),
            unknown_info="You aren't sure exactly how many more days at first.",
            ticket=f"{name} wants to extend rental (vague).",
            actions=[
                action("extend_1", "extend_rental", {
                    "agreement_id": aid,
                    "new_dropoff_datetime": new_dropoff_str,
                }, f"Extend rental {aid}",
                       compare_args=["agreement_id"]),
            ],
            reward_basis=["ACTION"],
        ))

    return tasks


def gen_report_damage(db, ix, n):
    """Report damage on an active rental."""
    tasks = []
    pool = list(ix.active_agreements)
    random.shuffle(pool)

    damages = [
        ("scratch on the front bumper", "Minor scratch on front bumper from parking incident"),
        ("dent on the driver side door", "Dent on driver side door, hit by shopping cart"),
        ("cracked windshield", "Windshield cracked by road debris"),
        ("flat tire", "Flat tire from pothole"),
        ("side mirror damaged", "Side mirror damaged in parking garage"),
    ]

    for i in range(min(n, len(pool))):
        aid = pool[i]
        agr = db["rental_agreements"][aid]
        cid = agr["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        damage_desc, damage_formal = damages[i % len(damages)]

        tasks.append(make_task(
            task_id=f"report_damage_{i+1}",
            purpose=f"Report vehicle damage on active rental",
            relevant_policies="Damage must be reported immediately. Liability depends on insurance type.",
            notes=f"{name} reports {damage_desc} on agreement {aid}.",
            persona=pick_easy_persona().label,
            task_instructions=(
                f"You are {name}. Your rental car got a {damage_desc}. "
                f"You want to report the damage."
            ),
            reason_for_call=f"I need to report some damage to my rental car — there's a {damage_desc}.",
            known_info=f"Your name is {name}. You have an active rental. The damage is: {damage_desc}.",
            unknown_info="You don't know the agreement ID or what insurance you have.",
            ticket=f"{name} reports {damage_desc} on active rental.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("report_1", "report_damage", {
                    "agreement_id": aid, "description": damage_formal,
                }, f"Report damage on {aid}",
                       compare_args=["agreement_id"]),
            ],
            env_assertions=[
                env_assert("assert_damage_reported", {"agreement_id": aid}),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


# ── Tier 2: Information & Search ────────────────────────────────

def gen_search_vehicles(db, ix, n):
    """Search for available vehicles by category and location."""
    tasks = []
    categories = ["economy", "compact", "midsize", "suv"]
    locations = ix.all_locations[:]
    random.shuffle(locations)

    customers = list(ix.customers_valid_license)
    random.shuffle(customers)

    for i in range(min(n, len(customers), len(locations))):
        cid = customers[i]
        name = customer_name(db, cid)
        track_use(cid)

        cat = categories[i % len(categories)]
        loc_id = locations[i % len(locations)]
        loc_name = db["locations"][loc_id]["name"]

        pickup_date = future_date(random.randint(3, 20)).split(" ")[0]
        dropoff_date = future_date(random.randint(23, 30)).split(" ")[0]

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"search_vehicles_{i+1}a",
            purpose=f"Search for {cat} vehicles at {loc_name}",
            relevant_policies="Vehicle search shows available inventory.",
            notes=f"{name} searches for {cat} cars at {loc_name}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You want to see what {cat} cars are available "
                f"at {loc_name}. {ep.instructions}"
            ),
            reason_for_call=(
                f"What {cat} cars do you have available at {loc_name}?"
            ),
            known_info=f"Your name is {name}. You want to see {cat} availability at {loc_name}.",
            unknown_info="You don't know specific vehicle models or IDs.",
            ticket=f"{name} asks about {cat} availability at {loc_name}.",
            actions=[
                action("search_1", "search_vehicles", {
                    "location_id": loc_id, "category": cat,
                    "pickup_date": pickup_date, "dropoff_date": dropoff_date,
                }, f"Search {cat} at {loc_name}",
                       compare_args=["location_id", "category"]),
            ],
            nl_assertions=[
                f"The agent told the customer about available {cat} vehicles at {loc_name}.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

        hp = pick_hard_persona()
        vague = VAGUE_CATEGORY_DESCRIPTIONS.get(cat, f"a {cat}")
        tasks.append(make_task(
            task_id=f"search_vehicles_{i+1}b",
            purpose=f"Search vehicles — vague category description",
            relevant_policies="Vehicle search shows available inventory.",
            notes=f"{name} vaguely asks about cars. Target: {cat} at {loc_name}.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You want to see available cars but describe "
                f"your needs vaguely. {hp.instructions} You want {vague}."
            ),
            reason_for_call=f"What do you have available? I need {vague}.",
            known_info=f"Your name is {name}. You want {vague}. Prefer {loc_name} area.",
            unknown_info="You don't know car categories or specific locations.",
            ticket=f"{name} asks about cars (vague). Target: {cat}.",
            actions=[
                action("search_1", "search_vehicles", {
                    "location_id": loc_id, "category": cat,
                    "pickup_date": pickup_date, "dropoff_date": dropoff_date,
                }, f"Search {cat} at {loc_name}",
                       compare_args=["location_id", "category"]),
            ],
            nl_assertions=[
                f"The agent told the customer about available vehicles.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_check_reservation(db, ix, n):
    """Customer wants to check their reservation details."""
    tasks = []
    pool = list(ix.confirmed_reservations)
    random.shuffle(pool)

    customers_used = set()
    for i, rid in enumerate(pool):
        if len(tasks) >= n:
            break
        res = db["reservations"][rid]
        cid = res["customer_id"]
        if cid in customers_used:
            continue
        customers_used.add(cid)

        name = customer_name(db, cid)
        track_use(cid)

        cat = res["vehicle_category"]
        pickup_loc = db["locations"][res["pickup_location_id"]]["name"]

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"check_reservation_{len(tasks)+1}a",
            purpose=f"Check reservation details",
            relevant_policies="Customers can inquire about their reservations.",
            notes=f"{name} checks details of {cat} reservation at {pickup_loc}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You want to confirm the details of your "
                f"upcoming rental. {ep.instructions}"
            ),
            reason_for_call=(
                f"Can you pull up my reservation details? I have a {cat} booked."
            ),
            known_info=f"Your name is {name}. You know you have a {cat} reservation.",
            unknown_info="You don't remember exact dates or reservation ID.",
            ticket=f"{name} wants to check {cat} reservation details.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
            ],
            nl_assertions=[
                f"The agent provided the customer with their reservation details including vehicle category, dates, and pickup location.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"check_reservation_{len(tasks)+1}b",
            purpose=f"Check reservation — vague inquiry",
            relevant_policies="Customers can inquire about their reservations.",
            notes=f"{name} vaguely asks about their booking.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You want to know about your rental booking "
                f"but are vague. {hp.instructions}"
            ),
            reason_for_call="I think I have a car booked... can you check?",
            known_info=f"Your name is {name}. You have a reservation.",
            unknown_info="You don't remember what type of car or when.",
            ticket=f"{name} wants reservation details (vague).",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
            ],
            nl_assertions=[
                f"The agent found and shared the customer's reservation details.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_list_extras(db, ix, n):
    """Customer asks about available extras."""
    tasks = []
    pool = list(ix.customers_valid_license)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        cid = pool[i]
        name = customer_name(db, cid)
        track_use(cid)

        tasks.append(make_task(
            task_id=f"list_extras_{i+1}",
            purpose="Customer asks about available rental extras",
            relevant_policies="Extras available: GPS, child seat, additional driver, roadside pkg, roof rack, ski rack, wifi hotspot.",
            notes=f"{name} asks what add-ons are available for rentals.",
            persona=pick_easy_persona().label,
            task_instructions=(
                f"You are {name}. You want to know what extras are available "
                f"and how much they cost."
            ),
            reason_for_call="What add-ons or extras can I get with my rental?",
            known_info=f"Your name is {name}.",
            unknown_info="You don't know what extras are available or their prices.",
            ticket=f"{name} asks about available extras and pricing.",
            actions=[
                action("list_1", "list_extras", {},
                       "List available extras", compare_args=[]),
            ],
            nl_assertions=[
                "The agent listed available extras with their daily rates.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_check_invoice(db, ix, n):
    """Customer asks about an invoice from a completed rental."""
    tasks = []
    pool = list(ix.paid_invoices)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        iid = pool[i]
        inv = db["invoices"][iid]
        cid = inv["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"check_invoice_{i+1}a",
            purpose="Check invoice details from past rental",
            relevant_policies="Customers can view their invoice details.",
            notes=f"{name} asks about invoice {iid}, total ${inv['total']:.2f}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You want to see the breakdown of a recent "
                f"rental charge. {ep.instructions}"
            ),
            reason_for_call=(
                f"I saw a charge on my card for a recent rental. "
                f"Can you show me the invoice breakdown?"
            ),
            known_info=f"Your name is {name}. You had a recent rental and want the invoice.",
            unknown_info="You don't know the invoice ID or exact amount.",
            ticket=f"{name} wants invoice details for a past rental.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
            ],
            nl_assertions=[
                "The agent provided the customer with their invoice details including line items and total.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"check_invoice_{i+1}b",
            purpose="Check invoice — frustrated about charge",
            relevant_policies="Customers can view invoices. Disputes escalate to human.",
            notes=f"{name} frustrated about invoice amount.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You're unhappy about a charge from a rental. "
                f"{hp.instructions} You want to understand the charges."
            ),
            reason_for_call=(
                "I got charged way more than I expected for my rental. "
                "What's going on with my bill?"
            ),
            known_info=f"Your name is {name}. You had a recent rental.",
            unknown_info="You don't know what each charge is for.",
            ticket=f"{name} questions invoice charges (frustrated).",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
            ],
            nl_assertions=[
                "The agent explained the invoice line items to the customer.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


# ── Tier 3: Moderate Multi-Step ─────────────────────────────────

def gen_reservation_with_insurance_and_extras(db, ix, n):
    """Customer wants to create a reservation with insurance AND extras."""
    tasks = []
    pool = [c for c in ix.customers_valid_license if c in ix.customers_25_plus]
    random.shuffle(pool)

    extras_pool = list(db["extras"].keys())

    for i in range(min(n, len(pool))):
        cid = pool[i]
        cust = db["customers"][cid]
        name = cust["name"]
        track_use(cid)

        cat = random.choice(["midsize", "suv", "compact"])
        loc_id = random.choice(ix.all_locations)
        loc_name = db["locations"][loc_id]["name"]

        vid = first_available_vehicle(db, ix, cat, loc_id)
        if vid is None:
            continue

        days_ahead = random.randint(5, 25)
        rent_days = random.randint(3, 7)
        pickup = future_date(days_ahead)
        dropoff = future_date(days_ahead + rent_days)

        ins = random.choice(["basic", "premium"])
        chosen_extras = random.sample(extras_pool, 2)

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"res_ins_extras_{i+1}a",
            purpose=f"Create reservation with {ins} insurance and extras",
            relevant_policies="Insurance options: basic ($15/day), premium ($30/day). Extras available.",
            notes=f"{name} books {cat} with {ins} insurance and extras {chosen_extras}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You want to rent {a_cat(cat)} car with {ins} insurance "
                f"and add {', '.join(db['extras'][e]['name'] for e in chosen_extras)}. "
                f"{ep.instructions}"
            ),
            reason_for_call=(
                f"I'd like to book {a_cat(cat)} at {loc_name} with {ins} insurance. "
                f"Also please add {' and '.join(db['extras'][e]['name'] for e in chosen_extras)}."
            ),
            known_info=(
                f"Your name is {name}. Pickup: {pickup}, return: {dropoff}. "
                f"Want {a_cat(cat)} with {ins} insurance. "
                f"Extras: {', '.join(db['extras'][e]['name'] for e in chosen_extras)}."
            ),
            unknown_info="You don't know exact pricing or vehicle ID.",
            ticket=f"{name} books {cat} with insurance and extras.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("create_1", "create_reservation", {
                    "customer_id": cid, "category": cat,
                    "pickup_location_id": loc_id, "dropoff_location_id": loc_id,
                    "pickup_datetime": pickup, "dropoff_datetime": dropoff,
                    "insurance_type": ins, "extras": chosen_extras,
                }, f"Create reservation with insurance and extras",
                       compare_args=["customer_id", "category", "insurance_type"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_exists", {"customer_id": cid}),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"res_ins_extras_{i+1}b",
            purpose=f"Create reservation with add-ons — indecisive customer",
            relevant_policies="Insurance and extras available. Agent should explain options.",
            notes=f"{name} unsure about add-ons, eventually picks {ins} + extras.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You want to rent a car and need some add-ons "
                f"but aren't sure what. {hp.instructions} "
                f"Accept {ins} insurance and "
                f"{', '.join(db['extras'][e]['name'] for e in chosen_extras)} when offered."
            ),
            reason_for_call=(
                f"I need a car and I think I need some extras... "
                f"what do you recommend for a family trip?"
            ),
            known_info=(
                f"Your name is {name}. You want a car for {rent_days} days "
                f"near {loc_name}. Accept {ins} insurance and recommended extras."
            ),
            unknown_info="You don't know categories, insurance options, or extras available.",
            ticket=f"{name} wants rental with add-ons (needs guidance).",
            actions=[
                action("create_1", "create_reservation", {
                    "customer_id": cid, "category": cat,
                    "pickup_location_id": loc_id, "dropoff_location_id": loc_id,
                    "pickup_datetime": pickup, "dropoff_datetime": dropoff,
                    "insurance_type": ins,
                }, f"Create reservation",
                       compare_args=["customer_id", "category", "insurance_type"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_exists", {"customer_id": cid}),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_one_way_rental(db, ix, n):
    """Customer wants a one-way rental (different pickup/dropoff)."""
    tasks = []
    pool = [c for c in ix.customers_valid_license if c in ix.customers_25_plus]
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        cid = pool[i]
        name = customer_name(db, cid)
        track_use(cid)

        cat = random.choice(["compact", "midsize", "suv"])
        locs = random.sample(ix.all_locations, 2)
        pickup_loc, dropoff_loc = locs[0], locs[1]
        pickup_name = db["locations"][pickup_loc]["name"]
        dropoff_name = db["locations"][dropoff_loc]["name"]

        vid = first_available_vehicle(db, ix, cat, pickup_loc)
        if vid is None:
            continue

        days_ahead = random.randint(5, 20)
        rent_days = random.randint(2, 5)
        pickup = future_date(days_ahead)
        dropoff = future_date(days_ahead + rent_days)

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"one_way_{i+1}a",
            purpose=f"One-way rental from {pickup_name} to {dropoff_name}",
            relevant_policies="$75 one-way surcharge when pickup != dropoff.",
            notes=f"{name} books one-way {cat} from {pickup_name} to {dropoff_name}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You need to pick up a car at {pickup_name} "
                f"and drop it off at {dropoff_name}. {ep.instructions}"
            ),
            reason_for_call=(
                f"I need {a_cat(cat)} from {pickup_name} to {dropoff_name}. "
                f"Pickup {pickup.split(' ')[0]} for {rent_days} days."
            ),
            known_info=(
                f"Your name is {name}. Pickup: {pickup_name}, dropoff: {dropoff_name}. "
                f"Want {a_cat(cat)} for {rent_days} days."
            ),
            unknown_info="You don't know the one-way fee or vehicle ID.",
            ticket=f"{name} books one-way {cat} rental.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("create_1", "create_reservation", {
                    "customer_id": cid, "category": cat,
                    "pickup_location_id": pickup_loc,
                    "dropoff_location_id": dropoff_loc,
                    "pickup_datetime": pickup, "dropoff_datetime": dropoff,
                }, f"Create one-way reservation",
                       compare_args=["customer_id", "category", "pickup_location_id", "dropoff_location_id"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_exists", {"customer_id": cid}),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"one_way_{i+1}b",
            purpose=f"One-way rental — vague about locations",
            relevant_policies="$75 one-way surcharge.",
            notes=f"{name} vaguely describes one-way trip.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You need to drive from one city to another "
                f"and drop the car off at a different location. {hp.instructions} "
                f"Confirm {pickup_name} to {dropoff_name} when suggested."
            ),
            reason_for_call=(
                f"I need to rent a car for a road trip... "
                f"I'll be going from around {pickup_name} area to near {dropoff_name}."
            ),
            known_info=(
                f"Your name is {name}. Going from {pickup_name} area to {dropoff_name} area. "
                f"Need the car for about {rent_days} days."
            ),
            unknown_info="You don't know exact locations, one-way fees, or categories.",
            ticket=f"{name} needs one-way rental (vague).",
            actions=[
                action("create_1", "create_reservation", {
                    "customer_id": cid, "category": cat,
                    "pickup_location_id": pickup_loc,
                    "dropoff_location_id": dropoff_loc,
                    "pickup_datetime": pickup, "dropoff_datetime": dropoff,
                }, f"Create one-way reservation",
                       compare_args=["customer_id", "pickup_location_id", "dropoff_location_id"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_exists", {"customer_id": cid}),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_modify_category_upgrade(db, ix, n):
    """Customer wants to upgrade vehicle category on existing reservation."""
    tasks = []
    upgrades = {
        "economy": "compact",
        "compact": "midsize",
        "midsize": "suv",
        "suv": "luxury",
    }
    pool = [
        rid for rid in ix.confirmed_reservations
        if db["reservations"][rid]["vehicle_category"] in upgrades
    ]
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        rid = pool[i]
        res = db["reservations"][rid]
        cid = res["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        old_cat = res["vehicle_category"]
        new_cat = upgrades[old_cat]

        # Check age for luxury
        cust = db["customers"][cid]
        dob = datetime.strptime(cust["dob"], "%Y-%m-%d")
        age = (TODAY - dob).days // 365
        if new_cat == "luxury" and age < 25:
            continue

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"upgrade_category_{i+1}a",
            purpose=f"Upgrade from {old_cat} to {new_cat}",
            relevant_policies="Category changes recalculate pricing. 25+ required for luxury.",
            notes=f"{name} upgrades from {old_cat} to {new_cat} on reservation {rid}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You want to upgrade your rental from {fmt_cat(old_cat)} "
                f"to {fmt_cat(new_cat)}. {ep.instructions}"
            ),
            reason_for_call=(
                f"I'd like to upgrade my reservation from {fmt_cat(old_cat)} to {fmt_cat(new_cat)}, please."
            ),
            known_info=(
                f"Your name is {name}. You have {a_cat(old_cat)} reservation. "
                f"You want to upgrade to {fmt_cat(new_cat)}."
            ),
            unknown_info="You don't know the price difference or reservation ID.",
            ticket=f"{name} wants to upgrade from {old_cat} to {new_cat}.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("modify_1", "modify_reservation", {
                    "reservation_id": rid, "category": new_cat,
                }, f"Upgrade to {new_cat}",
                       compare_args=["reservation_id", "category"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_category", {
                    "reservation_id": rid, "expected_category": new_cat,
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"upgrade_category_{i+1}b",
            purpose=f"Upgrade category — customer unsure what's bigger",
            relevant_policies="Category changes recalculate pricing.",
            notes=f"{name} wants something bigger, ends up upgrading to {new_cat}.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You feel your reserved car might be too small "
                f"but aren't sure about categories. {hp.instructions} "
                f"Accept upgrade to {new_cat} when suggested."
            ),
            reason_for_call=(
                f"I'm worried my car might be too small... is there something bigger?"
            ),
            known_info=(
                f"Your name is {name}. Your current reservation is for {fmt_cat(old_cat)}. "
                f"Accept upgrade to {fmt_cat(new_cat)}."
            ),
            unknown_info="You don't know the category hierarchy or pricing.",
            ticket=f"{name} wants upgrade (unsure of categories).",
            actions=[
                action("modify_1", "modify_reservation", {
                    "reservation_id": rid, "category": new_cat,
                }, f"Upgrade to {new_cat}",
                       compare_args=["reservation_id", "category"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_category", {
                    "reservation_id": rid, "expected_category": new_cat,
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_roadside_assistance(db, ix, n):
    """Customer needs roadside assistance during active rental."""
    tasks = []
    pool = list(ix.active_agreements)
    random.shuffle(pool)

    issues = [
        ("flat tire", "flat_tire", "I have a flat tire on the highway"),
        ("dead battery", "dead_battery", "my car won't start, I think the battery is dead"),
        ("locked keys in car", "lockout", "I accidentally locked my keys in the car"),
        ("ran out of gas", "fuel", "I'm out of gas on a rural road"),
        ("need a tow", "tow", "the car is making terrible noises and won't move"),
    ]

    for i in range(min(n, len(pool))):
        aid = pool[i]
        agr = db["rental_agreements"][aid]
        cid = agr["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        issue_desc, issue_type, reason = issues[i % len(issues)]
        location_str = f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Highway', 'Interstate'])} {random.choice(['St', 'Ave', 'Rd', 'Blvd'])}"

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"roadside_{i+1}a",
            purpose=f"Roadside assistance — {issue_desc}",
            relevant_policies="Roadside free with premium insurance, $150 otherwise. 24/7 service.",
            notes=f"{name} has {issue_desc} at {location_str}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You're stranded with {issue_desc}. "
                f"{ep.instructions} You're at {location_str}."
            ),
            reason_for_call=f"I need help — {reason}! I'm at {location_str}.",
            known_info=(
                f"Your name is {name}. You have an active rental. "
                f"Issue: {issue_desc}. Location: {location_str}."
            ),
            unknown_info="You don't know the agreement ID or whether you have premium insurance.",
            ticket=f"{name} needs roadside help: {issue_desc} at {location_str}.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("roadside_1", "initiate_roadside_assistance", {
                    "agreement_id": aid, "location": location_str, "issue": issue_type,
                }, f"Dispatch roadside for {issue_desc}",
                       compare_args=["agreement_id"]),
            ],
            reward_basis=["ACTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"roadside_{i+1}b",
            purpose=f"Roadside assistance — stressed customer",
            relevant_policies="Roadside assistance. $150 fee without premium.",
            notes=f"{name} stressed about {issue_desc}.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You're stranded and stressed. {hp.instructions} "
                f"Your issue is {issue_desc}. You're at {location_str}."
            ),
            reason_for_call=(
                f"I'm stuck on the road and I don't know what to do! "
                f"{reason}! Please help!"
            ),
            known_info=(
                f"Your name is {name}. Issue: {issue_desc}. "
                f"Location: {location_str}. Provide when asked."
            ),
            unknown_info="You don't know your agreement ID or insurance details.",
            ticket=f"{name} stranded: {issue_desc} (stressed).",
            actions=[
                action("roadside_1", "initiate_roadside_assistance", {
                    "agreement_id": aid, "location": location_str, "issue": issue_type,
                }, f"Dispatch roadside for {issue_desc}",
                       compare_args=["agreement_id"]),
            ],
            reward_basis=["ACTION"],
        ))

    return tasks


def gen_issue_credit(db, ix, n):
    """Issue credit for a service failure (completed rental with issues)."""
    tasks = []
    pool = list(ix.all_customers)
    random.shuffle(pool)

    complaints = [
        ("car wasn't clean when I picked it up", 50.0, "Vehicle not cleaned at pickup"),
        ("waited over an hour at the counter", 75.0, "Excessive wait time at pickup"),
        ("reserved car category wasn't available and I got a downgrade", 100.0, "Vehicle category downgrade"),
        ("the GPS device didn't work", 40.0, "Defective GPS equipment"),
        ("AC was broken during my rental", 80.0, "Non-functional AC"),
    ]

    for i in range(min(n, len(pool))):
        cid = pool[i]
        name = customer_name(db, cid)
        track_use(cid)

        complaint, amount, formal = complaints[i % len(complaints)]

        tasks.append(make_task(
            task_id=f"issue_credit_{i+1}",
            purpose=f"Issue credit for service failure: {formal}",
            relevant_policies="Credits up to $200 per incident. Higher amounts need manager.",
            notes=f"{name} gets ${amount:.0f} credit for: {formal}.",
            persona=pick_hard_persona().label,
            task_instructions=(
                f"You are {name}. You had a bad experience: {complaint}. "
                f"You want compensation. Be firm but cooperative."
            ),
            reason_for_call=f"I had a terrible experience — {complaint}. I want compensation.",
            known_info=f"Your name is {name}. Your complaint: {complaint}.",
            unknown_info="You don't know what compensation you'll receive.",
            ticket=f"{name} complains: {complaint}. Eligible for ${amount:.0f} credit.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("credit_1", "issue_credit", {
                    "customer_id": cid, "amount": amount, "reason": formal,
                }, f"Issue ${amount:.0f} credit",
                       compare_args=["customer_id", "amount"]),
            ],
            reward_basis=["ACTION"],
        ))

    return tasks


# ── Tier 4: Complex Multi-Step ──────────────────────────────────

def gen_cancel_and_rebook(db, ix, n):
    """Cancel existing reservation and create a new one (different category/dates)."""
    tasks = []
    pool = list(ix.confirmed_reservations)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        rid = pool[i]
        res = db["reservations"][rid]
        cid = res["customer_id"]
        name = customer_name(db, cid)

        # Check valid license
        cust = db["customers"][cid]
        lic_exp = datetime.strptime(cust["license_expiry"], "%Y-%m-%d")
        if lic_exp < TODAY:
            continue

        dob = datetime.strptime(cust["dob"], "%Y-%m-%d")
        age = (TODAY - dob).days // 365
        if age < 21:
            continue

        track_use(cid)

        old_cat = res["vehicle_category"]
        new_cat = random.choice([c for c in ["economy", "compact", "midsize", "suv"] if c != old_cat])
        if new_cat == "luxury" and age < 25:
            new_cat = "midsize"

        loc_id = res["pickup_location_id"]
        loc_name = db["locations"][loc_id]["name"]

        vid = first_available_vehicle(db, ix, new_cat, loc_id)
        if vid is None:
            continue

        days_ahead = random.randint(7, 25)
        rent_days = random.randint(3, 7)
        pickup = future_date(days_ahead)
        dropoff = future_date(days_ahead + rent_days)

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"cancel_rebook_{i+1}a",
            purpose=f"Cancel {old_cat} and rebook as {new_cat}",
            relevant_policies="Cancellation policy + new reservation rules apply.",
            notes=f"{name} cancels {rid} ({old_cat}) and books new {new_cat}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. Your plans changed. Cancel your current {fmt_cat(old_cat)} "
                f"reservation and book {a_cat(new_cat)} instead for different dates. "
                f"{ep.instructions}"
            ),
            reason_for_call=(
                f"I need to cancel my {fmt_cat(old_cat)} reservation and book {a_cat(new_cat)} "
                f"instead, for {pickup.split(' ')[0]} to {dropoff.split(' ')[0]}."
            ),
            known_info=(
                f"Your name is {name}. Cancel the {fmt_cat(old_cat)} reservation. "
                f"New booking: {fmt_cat(new_cat)} at {loc_name}, {pickup} to {dropoff}."
            ),
            unknown_info="You don't know your reservation ID or the new total.",
            ticket=f"{name}: cancel {old_cat}, rebook {new_cat}.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("cancel_1", "cancel_reservation", {
                    "reservation_id": rid, "reason": "Rebooking different category",
                }, f"Cancel {rid}",
                       compare_args=["reservation_id"]),
                action("create_1", "create_reservation", {
                    "customer_id": cid, "category": new_cat,
                    "pickup_location_id": loc_id, "dropoff_location_id": loc_id,
                    "pickup_datetime": pickup, "dropoff_datetime": dropoff,
                }, f"Create new {new_cat} reservation",
                       compare_args=["customer_id", "category"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_status", {
                    "reservation_id": rid, "expected_status": "cancelled",
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"cancel_rebook_{i+1}b",
            purpose=f"Cancel and rebook — indecisive customer",
            relevant_policies="Cancellation + rebooking.",
            notes=f"{name} wants to change everything about their reservation.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. You're not happy with your current booking and "
                f"want to start over. {hp.instructions} "
                f"Eventually decide on {fmt_cat(new_cat)} for {pickup.split(' ')[0]}."
            ),
            reason_for_call=(
                f"I booked the wrong thing... I need to change everything about "
                f"my reservation. Can we just cancel it and start fresh?"
            ),
            known_info=(
                f"Your name is {name}. Cancel existing, rebook as {fmt_cat(new_cat)} "
                f"at {loc_name}. Accept dates when proposed."
            ),
            unknown_info="You're not sure what you want initially.",
            ticket=f"{name}: cancel and rebook (indecisive).",
            actions=[
                action("cancel_1", "cancel_reservation", {
                    "reservation_id": rid, "reason": "Rebooking",
                }, f"Cancel {rid}",
                       compare_args=["reservation_id"]),
                action("create_1", "create_reservation", {
                    "customer_id": cid, "category": new_cat,
                    "pickup_location_id": loc_id, "dropoff_location_id": loc_id,
                    "pickup_datetime": pickup, "dropoff_datetime": dropoff,
                }, f"Create new reservation",
                       compare_args=["customer_id", "category"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_status", {
                    "reservation_id": rid, "expected_status": "cancelled",
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_extend_and_add_extras(db, ix, n):
    """Extend rental AND add extras to the reservation."""
    tasks = []
    pool = list(ix.active_agreements)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        aid = pool[i]
        agr = db["rental_agreements"][aid]
        cid = agr["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        res_id = agr["reservation_id"]
        if res_id not in db["reservations"]:
            continue
        res = db["reservations"][res_id]

        old_dropoff = datetime.strptime(res["dropoff_datetime"], "%Y-%m-%d %H:%M")
        extra_days = 2
        new_dropoff = old_dropoff + timedelta(days=extra_days)
        new_dropoff_str = new_dropoff.strftime("%Y-%m-%d %H:%M")

        # Pick an extra not already on the reservation
        available_extras = [e for e in db["extras"].keys() if e not in res["extras"]]
        if not available_extras:
            continue
        new_extra = random.choice(available_extras)
        new_extras_list = res["extras"] + [new_extra]

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"extend_add_extras_{i+1}a",
            purpose=f"Extend rental + add {db['extras'][new_extra]['name']}",
            relevant_policies="Rentals can be extended. Extras can be modified.",
            notes=f"{name} extends {aid} by {extra_days} days and adds {new_extra}.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}. You need your rental for {extra_days} more days "
                f"and also want to add {db['extras'][new_extra]['name']}. {ep.instructions}"
            ),
            reason_for_call=(
                f"I need to keep my car {extra_days} more days, and can you also add "
                f"{db['extras'][new_extra]['name']}?"
            ),
            known_info=(
                f"Your name is {name}. Extend by {extra_days} days. "
                f"Add {db['extras'][new_extra]['name']}."
            ),
            unknown_info="You don't know agreement or reservation IDs.",
            ticket=f"{name}: extend rental + add extra.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("extend_1", "extend_rental", {
                    "agreement_id": aid,
                    "new_dropoff_datetime": new_dropoff_str,
                }, f"Extend rental {aid}",
                       compare_args=["agreement_id"]),
                action("modify_1", "modify_reservation", {
                    "reservation_id": res_id,
                    "extras": new_extras_list,
                }, f"Add extra to reservation",
                       compare_args=["reservation_id"]),
            ],
            reward_basis=["ACTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"extend_add_extras_{i+1}b",
            purpose=f"Extend + extras — disorganized customer",
            relevant_policies="Rentals can be extended. Extras available.",
            notes=f"{name} needs extension and extra but is disorganized.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}. Your trip is running long and you also want "
                f"to add something. {hp.instructions} "
                f"Confirm: {extra_days} more days and {db['extras'][new_extra]['name']}."
            ),
            reason_for_call=(
                f"Hey, so my trip isn't going as planned... I need the car longer "
                f"and also there's this thing I need added..."
            ),
            known_info=(
                f"Your name is {name}. Need {extra_days} more days. "
                f"Want {db['extras'][new_extra]['name']}."
            ),
            unknown_info="You're scattered about details at first.",
            ticket=f"{name}: extend + add extra (disorganized).",
            actions=[
                action("extend_1", "extend_rental", {
                    "agreement_id": aid,
                    "new_dropoff_datetime": new_dropoff_str,
                }, f"Extend rental",
                       compare_args=["agreement_id"]),
                action("modify_1", "modify_reservation", {
                    "reservation_id": res_id,
                    "extras": new_extras_list,
                }, f"Add extra",
                       compare_args=["reservation_id"]),
            ],
            reward_basis=["ACTION"],
        ))

    return tasks


def gen_loyalty_booking(db, ix, n):
    """Loyalty member books with points discount + preferred extras."""
    tasks = []
    pool = []
    for cid in ix.customers_with_loyalty:
        cust = db["customers"][cid]
        if cust["loyalty_points"] >= 500 and cid in ix.customers_valid_license:
            pool.append(cid)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        cid = pool[i]
        cust = db["customers"][cid]
        name = cust["name"]
        track_use(cid)

        dob = datetime.strptime(cust["dob"], "%Y-%m-%d")
        age = (TODAY - dob).days // 365

        cat = random.choice(["midsize", "suv"])
        if cat == "luxury" and age < 25:
            cat = "midsize"

        loc_id = random.choice(ix.all_locations)
        loc_name = db["locations"][loc_id]["name"]

        vid = first_available_vehicle(db, ix, cat, loc_id)
        if vid is None:
            continue

        days_ahead = random.randint(5, 20)
        rent_days = random.randint(3, 5)
        pickup = future_date(days_ahead)
        dropoff = future_date(days_ahead + rent_days)

        points = 500

        ep = pick_easy_persona()
        tasks.append(make_task(
            task_id=f"loyalty_booking_{i+1}a",
            purpose=f"Loyalty member ({cust['loyalty_tier']}) books with points",
            relevant_policies="Loyalty discounts apply. 100 pts = $10 discount.",
            notes=f"{name} ({cust['loyalty_tier']}, {cust['loyalty_points']} pts) books {cat} + redeems {points} pts.",
            persona=ep.label,
            task_instructions=(
                f"You are {name}, a {cust['loyalty_tier']} member. "
                f"Book {a_cat(cat)} and use {points} loyalty points. {ep.instructions}"
            ),
            reason_for_call=(
                f"I'd like to book {a_cat(cat)} at {loc_name} and use {points} of my loyalty points."
            ),
            known_info=(
                f"Your name is {name}. {cust['loyalty_tier']} member. "
                f"Want {a_cat(cat)} at {loc_name}, {rent_days} days. Use {points} points."
            ),
            unknown_info="You don't know exact pricing or vehicle ID.",
            ticket=f"{name}: loyalty booking + {points} points.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("create_1", "create_reservation", {
                    "customer_id": cid, "category": cat,
                    "pickup_location_id": loc_id, "dropoff_location_id": loc_id,
                    "pickup_datetime": pickup, "dropoff_datetime": dropoff,
                }, f"Create reservation",
                       compare_args=["customer_id", "category"]),
                action("apply_1", "apply_loyalty_discount", {
                    "reservation_id": f"res_{cid.split('_')[-1]}_{(TODAY + timedelta(days=days_ahead)).strftime('%Y%m%d')}",
                    "points": points,
                }, f"Apply {points} points",
                       compare_args=["points"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_exists", {"customer_id": cid}),
                env_assert("assert_customer_loyalty_points_decreased", {
                    "customer_id": cid, "max_points": cust["loyalty_points"] - points,
                }),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        hp = pick_hard_persona()
        tasks.append(make_task(
            task_id=f"loyalty_booking_{i+1}b",
            purpose=f"Loyalty booking — customer unclear about points",
            relevant_policies="Loyalty discounts + points redemption.",
            notes=f"{name} wants to use loyalty benefits but isn't clear how.",
            persona=hp.label,
            task_instructions=(
                f"You are {name}, a {cust['loyalty_tier']} member. "
                f"You want a car and to use some points but aren't sure how it works. "
                f"{hp.instructions} Accept {cat} and agree to use {points} points."
            ),
            reason_for_call=(
                f"I have some loyalty points... can I use them for a rental?"
            ),
            known_info=(
                f"Your name is {name}. Want a car for {rent_days} days. "
                f"Use {points} points. Accept {fmt_cat(cat)} when suggested."
            ),
            unknown_info="You don't understand the points system or categories.",
            ticket=f"{name}: loyalty booking (confused about points).",
            actions=[
                action("create_1", "create_reservation", {
                    "customer_id": cid, "category": cat,
                    "pickup_location_id": loc_id, "dropoff_location_id": loc_id,
                    "pickup_datetime": pickup, "dropoff_datetime": dropoff,
                }, f"Create reservation",
                       compare_args=["customer_id", "category"]),
                action("apply_1", "apply_loyalty_discount", {
                    "reservation_id": f"res_{cid.split('_')[-1]}_{(TODAY + timedelta(days=days_ahead)).strftime('%Y%m%d')}",
                    "points": points,
                }, f"Apply points",
                       compare_args=["points"]),
            ],
            env_assertions=[
                env_assert("assert_reservation_exists", {"customer_id": cid}),
            ],
            reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


# ── Tier 5: Edge Cases & Policy Violations ──────────────────────

def gen_luxury_underage(db, ix, n):
    """Customer under 25 tries to book luxury — should be denied."""
    tasks = []
    pool = [c for c in ix.customers_under_25 if c in ix.customers_valid_license]
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        cid = pool[i]
        name = customer_name(db, cid)
        cust = db["customers"][cid]
        dob = datetime.strptime(cust["dob"], "%Y-%m-%d")
        age = (TODAY - dob).days // 365
        track_use(cid)

        tasks.append(make_task(
            task_id=f"luxury_underage_{i+1}",
            purpose="Under-25 customer requests luxury vehicle — should be denied",
            relevant_policies="Luxury vehicles require driver age 25+.",
            notes=f"{name} (age {age}) tries to book luxury. Should be denied.",
            persona=pick_easy_persona().label,
            task_instructions=(
                f"You are {name}. You want to rent a luxury car for a special "
                f"occasion. Accept the denial gracefully and ask about alternatives."
            ),
            reason_for_call="I'd like to rent a luxury car, something nice like a BMW or Mercedes.",
            known_info=f"Your name is {name}. You want a luxury car.",
            unknown_info="You don't know about the age restriction for luxury.",
            ticket=f"{name} (age {age}) wants luxury — ineligible.",
            actions=[],
            nl_assertions=[
                "The agent informed the customer that luxury vehicles require the driver to be at least 25 years old.",
                "The agent suggested alternative vehicle categories that the customer is eligible for.",
            ],
            reward_basis=["NL_ASSERTION"],
        ))

    return tasks


def gen_expired_license(db, ix, n):
    """Customer with expired license tries to make a reservation."""
    tasks = []
    pool = list(ix.customers_expired_license)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        cid = pool[i]
        name = customer_name(db, cid)
        cust = db["customers"][cid]
        track_use(cid)

        tasks.append(make_task(
            task_id=f"expired_license_{i+1}",
            purpose="Customer with expired license tries to book — should be denied",
            relevant_policies="Valid driver's license required. Must not expire before pickup.",
            notes=f"{name}'s license expired {cust['license_expiry']}. Booking should fail.",
            persona=pick_easy_persona().label,
            task_instructions=(
                f"You are {name}. You want to book a car. You might not realize "
                f"your license has expired."
            ),
            reason_for_call="I'd like to book a compact car for next week.",
            known_info=f"Your name is {name}. You want a compact car for next week.",
            unknown_info="You don't know your license has expired.",
            ticket=f"{name} has expired license — cannot book.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
            ],
            nl_assertions=[
                "The agent informed the customer that their driver's license has expired and they cannot create a reservation until it is renewed.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_cancel_already_cancelled(db, ix, n):
    """Customer tries to cancel an already-cancelled reservation."""
    tasks = []
    pool = list(ix.cancelled_reservations)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        rid = pool[i]
        res = db["reservations"][rid]
        cid = res["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        tasks.append(make_task(
            task_id=f"cancel_already_{i+1}",
            purpose="Cancel already-cancelled reservation — explain status",
            relevant_policies="Cannot cancel already cancelled or completed reservations.",
            notes=f"{name} tries to cancel {rid} which is already cancelled.",
            persona=pick_easy_persona().label,
            task_instructions=(
                f"You are {name}. You want to cancel a reservation but it's "
                f"already been cancelled. Accept the explanation."
            ),
            reason_for_call="I need to cancel my reservation. I don't think I need the car anymore.",
            known_info=f"Your name is {name}. You think you have a reservation to cancel.",
            unknown_info="You don't know it was already cancelled.",
            ticket=f"{name} tries to cancel already-cancelled reservation.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
            ],
            nl_assertions=[
                "The agent informed the customer that the reservation has already been cancelled.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_modify_active_reservation(db, ix, n):
    """Customer tries to modify an active (picked up) reservation — should explain limitation."""
    tasks = []
    pool = list(ix.active_reservations)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        rid = pool[i]
        res = db["reservations"][rid]
        cid = res["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        tasks.append(make_task(
            task_id=f"modify_active_{i+1}",
            purpose="Modify active (picked-up) reservation — explain can't modify",
            relevant_policies="Insurance and categories can only be changed on confirmed reservations. Active rentals only allow extras changes.",
            notes=f"{name} tries to modify active reservation {rid}.",
            persona=pick_easy_persona().label,
            task_instructions=(
                f"You are {name}. You want to change the insurance on your rental "
                f"but you've already picked up the car."
            ),
            reason_for_call="I want to add insurance to my current rental. Can you change that?",
            known_info=f"Your name is {name}. You currently have an active rental.",
            unknown_info="You don't know that modifications can't be made to active rentals.",
            ticket=f"{name} tries to modify active rental.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
            ],
            nl_assertions=[
                "The agent explained that insurance and other reservation details (except extras) cannot be changed once the rental is active.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_credit_over_limit(db, ix, n):
    """Customer asks for credit above $200 limit — should transfer to human."""
    tasks = []
    pool = list(ix.all_customers)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        cid = pool[i]
        name = customer_name(db, cid)
        track_use(cid)

        tasks.append(make_task(
            task_id=f"credit_over_limit_{i+1}",
            purpose="Credit request over $200 — must transfer to human agent",
            relevant_policies="Max credit $200 per incident. Higher requires manager approval.",
            notes=f"{name} wants $300 credit — over limit, needs human agent.",
            persona=pick_hard_persona().label,
            task_instructions=(
                f"You are {name}. You had a major issue with a rental and want "
                f"$300 in compensation. Be firm about the amount."
            ),
            reason_for_call=(
                "I had a horrible experience — the car broke down, ruined my trip. "
                "I want at least $300 in compensation."
            ),
            known_info=f"Your name is {name}. You want $300 credit.",
            unknown_info="You don't know the $200 limit.",
            ticket=f"{name} wants $300 credit — over $200 limit.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("transfer_1", "transfer_to_human_agents", {
                    "summary": f"Customer {name} requests $300 credit for service failure, exceeds $200 agent limit.",
                }, "Transfer to human for high credit",
                       compare_args=[]),
            ],
            nl_assertions=[
                "The agent explained that credits above $200 require manager approval and transferred the customer to a human agent.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_dispute_invoice(db, ix, n):
    """Customer disputes an invoice charge — agent reviews and escalates."""
    tasks = []
    pool = list(ix.disputed_invoices)
    random.shuffle(pool)

    for i in range(min(n, len(pool))):
        iid = pool[i]
        inv = db["invoices"][iid]
        cid = inv["customer_id"]
        name = customer_name(db, cid)
        track_use(cid)

        total = inv["total"]
        damage_items = [li for li in inv["line_items"] if li["category"] == "damage"]
        has_damage = len(damage_items) > 0

        dispute_reason = (
            "I'm disputing the damage charge — I didn't cause any damage"
            if has_damage
            else "I think I was overcharged for my rental"
        )

        tasks.append(make_task(
            task_id=f"dispute_invoice_{i+1}",
            purpose="Customer disputes invoice — review and escalate",
            relevant_policies="Agent cannot adjust invoices directly. Disputes should be escalated.",
            notes=f"{name} disputes invoice {iid} (${total:.2f}). {'Has damage charge.' if has_damage else 'General overcharge claim.'}",
            persona=pick_hard_persona().label,
            task_instructions=(
                f"You are {name}. You're upset about charges on your invoice. "
                f"You want an explanation and resolution."
            ),
            reason_for_call=f"{dispute_reason}. My total was ${total:.2f} and that seems too high.",
            known_info=f"Your name is {name}. You're disputing a charge of ${total:.2f}.",
            unknown_info="You don't know the invoice ID or line item details.",
            ticket=f"{name} disputes invoice ${total:.2f}.",
            actions=[
                action("find_1", "find_customer_by_name", {"name": name},
                       f"Look up {name}", compare_args=[]),
                action("transfer_1", "transfer_to_human_agents", {
                    "summary": f"Customer {name} disputes invoice {iid} (${total:.2f}). {dispute_reason}.",
                }, "Transfer to billing team",
                       compare_args=[]),
            ],
            nl_assertions=[
                "The agent reviewed the invoice with the customer and explained the charges before transferring.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_transfer_scenarios(db, ix, n):
    """Various scenarios requiring human agent transfer."""
    tasks = []
    pool = list(ix.all_customers)
    random.shuffle(pool)

    scenarios = [
        (
            "accident_report",
            "I was in an accident with my rental car",
            "Rental car accident — customer needs claims process. Must transfer to human.",
            "The agent cannot handle accident claims directly. Should be transferred to a human agent.",
        ),
        (
            "legal_question",
            "I got a parking ticket in the rental car and want to know my legal obligations",
            "Legal question about parking ticket during rental. Agent cannot give legal advice.",
            "The agent cannot provide legal advice. Should explain this and transfer to human.",
        ),
        (
            "insurance_claim",
            "Someone hit my rental car in a parking lot. How do I file an insurance claim?",
            "Insurance claim for third-party damage. Agent cannot process claims.",
            "The agent should explain that insurance claims need to be handled by a specialist and transfer.",
        ),
        (
            "corporate_account",
            "I need to set up a corporate account for my company's fleet needs",
            "Corporate account setup — not available via regular customer service.",
            "The agent cannot set up corporate accounts. Should transfer to business services.",
        ),
    ]

    for i in range(min(n, len(pool), len(scenarios))):
        cid = pool[i]
        name = customer_name(db, cid)
        track_use(cid)

        scenario_id, reason, notes, nl_check = scenarios[i % len(scenarios)]

        tasks.append(make_task(
            task_id=f"transfer_{scenario_id}_{i+1}",
            purpose=f"Transfer scenario: {scenario_id}",
            relevant_policies="Agent cannot handle accidents, legal, insurance claims, or corporate setup.",
            notes=notes,
            persona=pick_easy_persona().label,
            task_instructions=(
                f"You are {name}. {reason}. Cooperate with the transfer."
            ),
            reason_for_call=reason,
            known_info=f"Your name is {name}.",
            unknown_info="You don't know the process for this type of request.",
            ticket=f"{name}: {scenario_id} — needs human agent.",
            actions=[
                action("transfer_1", "transfer_to_human_agents", {
                    "summary": f"Customer {name}: {reason}",
                }, f"Transfer for {scenario_id}",
                       compare_args=[]),
            ],
            nl_assertions=[nl_check],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_find_by_email(db, ix, n):
    """Look up customer by email and check reservation."""
    tasks = []
    pool = list(ix.confirmed_reservations)
    random.shuffle(pool)
    used_customers = set()

    for rid in pool:
        if len(tasks) >= n:
            break
        res = db["reservations"][rid]
        cid = res["customer_id"]
        if cid in used_customers:
            continue
        used_customers.add(cid)

        name = customer_name(db, cid)
        email = db["customers"][cid]["email"]
        track_use(cid)

        tasks.append(make_task(
            task_id=f"find_by_email_{len(tasks)+1}",
            purpose="Look up customer by email and check reservation",
            relevant_policies="Customers can be looked up by email.",
            notes=f"{name} provides email {email} to check reservation.",
            persona=pick_easy_persona().label,
            task_instructions=(
                f"You are {name}. Provide your email address ({email}) to look up "
                f"your account and check your reservation."
            ),
            reason_for_call=f"I'd like to check on my reservation. My email is {email}.",
            known_info=f"Your name is {name}. Your email is {email}.",
            unknown_info="You don't know your customer ID.",
            ticket=f"{name} looks up account by email {email}.",
            actions=[
                action("find_1", "find_customer_by_email", {"email": email},
                       f"Look up by email {email}",
                       compare_args=["email"]),
            ],
            nl_assertions=[
                "The agent found the customer's account and provided reservation details.",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


# ── Main ────────────────────────────────────────────────────────

def generate_all(db):
    ix = build_indexes(db)

    all_tasks = []

    # ── Tier 1: Simple Single-Action (~80 tasks) ──
    tier1 = [
        ("create_reservation", gen_create_reservation, 12),
        ("cancel_reservation", gen_cancel_reservation, 6),
        ("modify_dates", gen_modify_reservation_dates, 5),
        ("modify_insurance", gen_modify_insurance, 5),
        ("apply_loyalty", gen_apply_loyalty_points, 5),
        ("extend_rental", gen_extend_rental, 5),
        ("report_damage", gen_report_damage, 5),
    ]

    # ── Tier 2: Information & Search (~32 tasks) ──
    tier2 = [
        ("search_vehicles", gen_search_vehicles, 5),
        ("check_reservation", gen_check_reservation, 4),
        ("list_extras", gen_list_extras, 4),
        ("check_invoice", gen_check_invoice, 4),
    ]

    # ── Tier 3: Moderate Multi-Step (~50 tasks) ──
    tier3 = [
        ("res_ins_extras", gen_reservation_with_insurance_and_extras, 5),
        ("one_way", gen_one_way_rental, 5),
        ("upgrade_category", gen_modify_category_upgrade, 5),
        ("roadside", gen_roadside_assistance, 5),
        ("issue_credit", gen_issue_credit, 5),
    ]

    # ── Tier 4: Complex Multi-Step (~30 tasks) ──
    tier4 = [
        ("cancel_rebook", gen_cancel_and_rebook, 4),
        ("extend_add_extras", gen_extend_and_add_extras, 4),
        ("loyalty_booking", gen_loyalty_booking, 4),
    ]

    # ── Tier 5: Edge Cases & Policy (~35 tasks) ──
    tier5 = [
        ("luxury_underage", gen_luxury_underage, 3),
        ("expired_license", gen_expired_license, 4),
        ("cancel_already", gen_cancel_already_cancelled, 3),
        ("modify_active", gen_modify_active_reservation, 4),
        ("credit_over_limit", gen_credit_over_limit, 3),
        ("dispute_invoice", gen_dispute_invoice, 4),
        ("transfer", gen_transfer_scenarios, 4),
        ("find_by_email", gen_find_by_email, 4),
    ]

    for tier_name, tier_gens in [
        ("Tier 1", tier1), ("Tier 2", tier2), ("Tier 3", tier3),
        ("Tier 4", tier4), ("Tier 5", tier5),
    ]:
        tier_tasks = []
        for gen_name, gen_fn, base_n in tier_gens:
            tasks = gen_fn(db, ix, base_n)
            tier_tasks.extend(tasks)
        all_tasks.extend(tier_tasks)
        print(f"  {tier_name}: {len(tier_tasks)} tasks")

    return all_tasks


if __name__ == "__main__":
    db = load_db()
    tasks = generate_all(db)

    # Check for duplicate IDs
    ids = [t["id"] for t in tasks]
    dups = [tid for tid in ids if ids.count(tid) > 1]
    if dups:
        print(f"WARNING: Duplicate task IDs: {set(dups)}")

    print(f"\nTotal tasks: {len(tasks)}")

    # Difficulty distribution
    easy = [t for t in tasks if t["id"].endswith("a")]
    hard = [t for t in tasks if t["id"].endswith("b")]
    single = [t for t in tasks if not t["id"].endswith("a") and not t["id"].endswith("b")]
    print(f"  Easy (a): {len(easy)}")
    print(f"  Hard (b): {len(hard)}")
    print(f"  Single variant: {len(single)}")

    # Reward basis distribution
    rb_counts = {}
    for t in tasks:
        key = tuple(sorted(t["evaluation_criteria"]["reward_basis"]))
        rb_counts[key] = rb_counts.get(key, 0) + 1
    print(f"\n  Reward basis distribution:")
    for key, count in sorted(rb_counts.items()):
        print(f"    {key}: {count}")

    # Write tasks
    with open(TASKS_PATH, "w") as f:
        json.dump(tasks, f, indent=2)
    print(f"\nWrote {len(tasks)} tasks to {TASKS_PATH}")

    # Write splits
    all_ids = [t["id"] for t in tasks]
    easy_ids = [t["id"] for t in easy] + [t["id"] for t in single]
    hard_ids = [t["id"] for t in hard]

    splits = {
        "base": all_ids,
        "easy": easy_ids,
        "hard": hard_ids,
    }
    with open(SPLIT_PATH, "w") as f:
        json.dump(splits, f, indent=2)
    print(f"Wrote splits to {SPLIT_PATH}")
    print(f"  base: {len(all_ids)}, easy: {len(easy_ids)}, hard: {len(hard_ids)}")
