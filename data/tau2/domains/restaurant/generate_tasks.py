#!/usr/bin/env python3
"""Procedurally generate ~200 restaurant domain tasks from db.json.

Standalone script (stdlib only: json, random, pathlib).
Deterministic via random.seed(42).

Uses structured personas and variant generation:
- Easy (a) variants: full info, direct persona
- Hard (b) variants: vague info, challenging persona

Usage:
    python generate_tasks.py            # writes tasks.json + split_tasks.json
    python generate_tasks.py --stats    # print stats only, don't write
"""

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
TODAY = "2025-10-15"
TODAY_DT = datetime(2025, 10, 15)

# Policy constants (mirror tools.py)
MODIFICATION_CUTOFF_HOURS = 2
CANCELLATION_FEE_CUTOFF_HOURS = 1
CANCELLATION_FEE_PARTY_SIZE = 6
LOYALTY_POINTS_PER_DOLLAR = 100
GIFT_CARD_MAX_NO_MANAGER = 50.0

DB_PATH = Path(__file__).parent / "db.json"
TASKS_PATH = Path(__file__).parent / "tasks.json"
SPLIT_TASKS_PATH = Path(__file__).parent / "split_tasks.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_db():
    with open(DB_PATH) as f:
        return json.load(f)


def cust_name(db, cid):
    return db["customers"][cid]["name"]


def loc_name(db, lid):
    return db["locations"][lid]["name"]


def item_name(db, iid):
    return db["menu_items"][iid]["name"]


def res_datetime(res):
    return datetime.strptime(f"{res['date']} {res['time']}", "%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Entity Indexes
# ---------------------------------------------------------------------------


@dataclass
class EntityIndexes:
    confirmed_future: list = field(default_factory=list)
    confirmed_within_2h: list = field(default_factory=list)
    confirmed_within_1h_large: list = field(default_factory=list)
    confirmed_within_1h_small: list = field(default_factory=list)
    waitlisted: list = field(default_factory=list)

    placed_orders: list = field(default_factory=list)
    preparing_orders: list = field(default_factory=list)
    immutable_orders: list = field(default_factory=list)

    all_customers: list = field(default_factory=list)
    customers_with_allergies: list = field(default_factory=list)
    customers_with_diet: list = field(default_factory=list)
    customers_high_loyalty: list = field(default_factory=list)
    customers_moderate_loyalty: list = field(default_factory=list)
    customers_zero_loyalty: list = field(default_factory=list)

    available_items: list = field(default_factory=list)
    unavailable_items: list = field(default_factory=list)
    items_by_allergen: dict = field(default_factory=dict)
    items_by_dietary: dict = field(default_factory=dict)


def build_indexes(db):
    ix = EntityIndexes()

    # Ambiguous names
    nc = defaultdict(list)
    for cid, c in db["customers"].items():
        nc[c["name"]].append(cid)
    ambiguous = set()
    for cids in nc.values():
        if len(cids) > 1:
            ambiguous.update(cids)

    def clean(cid):
        return cid not in ambiguous

    # Reservations
    for rid, res in db["reservations"].items():
        if not clean(res["customer_id"]):
            continue
        if res["status"] == "confirmed":
            try:
                rdt = res_datetime(res)
            except ValueError:
                continue
            cm = rdt - timedelta(hours=MODIFICATION_CUTOFF_HOURS)
            cc = rdt - timedelta(hours=CANCELLATION_FEE_CUTOFF_HOURS)
            if TODAY_DT >= cm:
                ix.confirmed_within_2h.append(rid)
                if TODAY_DT >= cc:
                    if res["party_size"] > CANCELLATION_FEE_PARTY_SIZE:
                        ix.confirmed_within_1h_large.append(rid)
                    else:
                        ix.confirmed_within_1h_small.append(rid)
            else:
                ix.confirmed_future.append(rid)
        elif res["status"] == "waitlisted":
            ix.waitlisted.append(rid)

    # Orders
    for oid, order in db["orders"].items():
        if not clean(order["customer_id"]):
            continue
        if order["status"] == "placed":
            ix.placed_orders.append(oid)
        elif order["status"] == "preparing":
            ix.preparing_orders.append(oid)
        elif order["status"] in ("ready", "delivered", "completed", "cancelled"):
            ix.immutable_orders.append(oid)

    # Customers
    for cid, cust in db["customers"].items():
        if not clean(cid):
            continue
        ix.all_customers.append(cid)
        if cust["allergy_info"]:
            ix.customers_with_allergies.append(cid)
        if cust["dietary_restrictions"]:
            ix.customers_with_diet.append(cid)
        pts = cust["loyalty_points"]
        if pts >= 500:
            ix.customers_high_loyalty.append(cid)
        elif pts > 0:
            ix.customers_moderate_loyalty.append(cid)
        else:
            ix.customers_zero_loyalty.append(cid)

    # Menu
    for iid, item in db["menu_items"].items():
        if item["available"]:
            ix.available_items.append(iid)
            for a in item["allergens"]:
                ix.items_by_allergen.setdefault(a, []).append(iid)
            for t in item["dietary_tags"]:
                ix.items_by_dietary.setdefault(t, []).append(iid)
        else:
            ix.unavailable_items.append(iid)

    return ix


# ---------------------------------------------------------------------------
# Persona System
# ---------------------------------------------------------------------------


@dataclass
class Persona:
    label: str
    instructions: str
    difficulty: str


EASY_PERSONAS = [
    Persona("Friendly and direct",
            "Provide all requested information promptly and clearly. Be cooperative and concise.",
            "easy"),
    Persona("Polite regular customer",
            "You know the restaurant well. Provide information concisely and politely.",
            "easy"),
]

MEDIUM_PERSONAS = [
    Persona("Casual, provides info gradually",
            "Don't volunteer all information at once. Wait for the agent to ask for specific details.",
            "medium"),
    Persona("Busy professional",
            "You have limited time. Be terse and direct. Give short answers.",
            "medium"),
    Persona("Indecisive diner",
            "You're not entirely sure what you want. You may ask for recommendations before deciding.",
            "medium"),
]

HARD_PERSONAS = [
    Persona("Vague and uncertain",
            "You don't remember exact details. Describe things from memory using approximate descriptions. Say 'I think...' or 'something like...'.",
            "hard"),
    Persona("Chatty and digressive",
            "You are very chatty. Before answering questions, share anecdotes. Bury your actual requests in longer statements.",
            "hard"),
    Persona("Frustrated customer",
            "You are frustrated about a previous bad experience. Vent before giving details. Your responses are curt.",
            "hard"),
    Persona("Elderly, unfamiliar with process",
            "You are not very familiar with restaurant reservation systems. You might confuse terms or need patient guidance.",
            "hard"),
    Persona("Nervous about allergies",
            "You are very worried about food allergies. You ask multiple times about allergens and want extra confirmation.",
            "hard"),
]

ALL_EASY_MEDIUM = EASY_PERSONAS + MEDIUM_PERSONAS


def pick_easy():
    return random.choice(ALL_EASY_MEDIUM)


def pick_hard():
    return random.choice(HARD_PERSONAS)


# ---------------------------------------------------------------------------
# Vague Descriptions (for hard variants)
# ---------------------------------------------------------------------------

VAGUE_LOCATIONS = {
    "riverside_downtown": "the downtown location, the one on Main Street",
    "riverside_waterfront": "the one by the water, near the harbor",
    "riverside_garden": "the Garden District restaurant, the cozy one",
}

VAGUE_MENU_ITEMS = {
    "crispy_calamari": "the calamari appetizer",
    "bruschetta": "that tomato bread appetizer",
    "caesar_salad": "the Caesar salad",
    "soup_of_day": "whatever soup you have today",
    "shrimp_cocktail": "the shrimp appetizer, the cold one",
    "spring_rolls": "those veggie spring rolls",
    "stuffed_mushrooms": "the stuffed mushroom thing",
    "edamame": "the edamame",
    "grilled_salmon": "the salmon dish",
    "filet_mignon": "the filet, the fancy steak",
    "chicken_parmesan": "the chicken parm",
    "pasta_primavera": "the vegetable pasta",
    "ribeye_steak": "the big ribeye",
    "lobster_tail": "the lobster",
    "veggie_burger": "the veggie burger",
    "mushroom_risotto": "the mushroom risotto",
    "grilled_chicken": "the grilled chicken",
    "tiramisu": "tiramisu",
    "chocolate_cake": "the chocolate lava cake",
    "creme_brulee": "the crème brûlée",
    "cheesecake": "the cheesecake",
    "fruit_sorbet": "the fruit sorbet",
    "panna_cotta": "the panna cotta",
    "apple_tart": "the apple dessert",
    "sparkling_water": "sparkling water",
    "iced_tea": "iced tea",
    "espresso": "an espresso",
    "craft_lemonade": "the lemonade",
    "house_red_wine": "a glass of red",
    "house_white_wine": "a glass of white wine",
}


def vague_loc(lid):
    return VAGUE_LOCATIONS.get(lid, lid)


def vague_item(iid):
    return VAGUE_MENU_ITEMS.get(iid, iid)


# ---------------------------------------------------------------------------
# Entity Usage Tracking
# ---------------------------------------------------------------------------

_entity_usage: dict[str, int] = {}


def track_use(eid):
    _entity_usage[eid] = _entity_usage.get(eid, 0) + 1


def sort_by_usage(ids):
    return sorted(ids, key=lambda x: _entity_usage.get(x, 0))


def sample_diverse(ids, n):
    ordered = sort_by_usage(list(ids))
    chosen = ordered[:n]
    for c in chosen:
        track_use(c)
    return chosen


# ---------------------------------------------------------------------------
# Task Builder
# ---------------------------------------------------------------------------


def make_task(
    task_id, purpose, relevant_policies, notes,
    persona, task_instructions, reason_for_call,
    known_info, unknown_info, ticket,
    actions, env_assertions=None, nl_assertions=None,
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
                "domain": "restaurant",
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
    return {"env_type": "assistant", "func_name": func_name, "arguments": arguments}


# ---------------------------------------------------------------------------
# Tier 1: Simple Single-Action Generators
# ---------------------------------------------------------------------------


def gen_create_reservation(db, ix, n=8):
    """Create a new reservation. n bases -> 2n tasks (a/b)."""
    tasks = []
    eligible = list(ix.all_customers)
    random.shuffle(eligible)
    future_dates = [
        (TODAY_DT + timedelta(days=d)).strftime("%Y-%m-%d")
        for d in range(2, 15)
    ]
    times = ["17:00", "18:00", "18:30", "19:00", "19:30", "20:00"]

    for i, cid in enumerate(eligible[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        lid = random.choice(list(db["locations"].keys()))
        lname = loc_name(db, lid)
        date = random.choice(future_dates)
        time = random.choice(times)
        party = random.choice([2, 3, 4, 5, 6])
        orig_res_count = len(db["customers"][cid]["reservation_ids"])

        acts = [action(
            "create_res_1", "create_reservation",
            {"customer_id": cid, "location_id": lid, "date": date,
             "time": time, "party_size": party},
            f"Create reservation for {name} at {lname}",
            compare_args=["customer_id", "location_id", "date", "time", "party_size"],
        )]
        asserts = [env_assert(
            "assert_customer_reservation_count",
            {"customer_id": cid, "expected_count": orig_res_count + 1},
        )]

        # Variant A
        pa = pick_easy()
        tasks.append(make_task(
            f"create_res_{i+1}a",
            "Test simple reservation creation",
            "Reservations require customer, location, date, time, party size.",
            f"{name} books at {lname} on {date} at {time} for {party}.",
            pa.label,
            f"You are {name}. You want to make a dinner reservation. {pa.instructions}",
            f"I'd like to make a reservation for {party} at {lname} on {date} at {time}.",
            f"Your name is {name}. You want {party} guests at {lname}, {date} at {time}.",
            "You don't know your customer ID.",
            f"{name} wants reservation for {party} at {lname} on {date} at {time}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        # Variant B
        pb = pick_hard()
        vloc = vague_loc(lid)
        tasks.append(make_task(
            f"create_res_{i+1}b",
            "Test reservation creation with vague customer",
            "Reservations require customer, location, date, time, party size.",
            f"{name} vaguely requests reservation at {lname}. Agent must clarify details.",
            pb.label,
            f"You are {name}. You want to make a dinner reservation. {pb.instructions}",
            f"I'd like to book a table... for about {party} of us at {vloc}.",
            f"Your name is {name}. You want {party} guests at {vloc}. Date: {date}, around {time}.",
            "You don't remember the exact location name or your customer ID.",
            f"{name} vaguely describes {lname}. Agent should identify location and create reservation.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_cancel_reservation(db, ix, n=6):
    """Cancel a future reservation (no fee). n bases -> 2n tasks."""
    tasks = []
    candidates = list(ix.confirmed_future)
    random.shuffle(candidates)

    for i, rid in enumerate(candidates[:n]):
        res = db["reservations"][rid]
        cid = res["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)
        lname = loc_name(db, res["location_id"])

        acts = [action(
            "cancel_res_1", "cancel_reservation",
            {"reservation_id": rid, "reason": "Customer requested cancellation"},
            f"Cancel reservation {rid} for {name}",
            compare_args=["reservation_id"],
        )]
        asserts = [env_assert(
            "assert_reservation_status",
            {"reservation_id": rid, "expected_status": "cancelled"},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"cancel_res_{i+1}a",
            "Test simple reservation cancellation (no fee)",
            "Cancellations well in advance incur no fee.",
            f"{name} cancels reservation {rid} at {lname}. No cancellation fee.",
            pa.label,
            f"You are {name}. You need to cancel your reservation. {pa.instructions}",
            f"I need to cancel my reservation at {lname} on {res['date']} at {res['time']}.",
            f"Your name is {name}. Reservation at {lname} on {res['date']} at {res['time']}.",
            "You don't know your reservation ID.",
            f"{name} cancels reservation {rid}. Well in advance, no fee.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"cancel_res_{i+1}b",
            "Test reservation cancellation with vague customer",
            "Cancellations well in advance incur no fee.",
            f"{name} vaguely asks to cancel at {lname}.",
            pb.label,
            f"You are {name}. You need to cancel your upcoming dinner. {pb.instructions}",
            f"I need to cancel my dinner plans... the one coming up at {vague_loc(res['location_id'])}.",
            f"Your name is {name}. You have a reservation at {lname} on {res['date']}.",
            "You don't remember the exact date or reservation ID.",
            f"{name} vaguely describes reservation. Agent should find and cancel {rid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_cancel_order_item(db, ix, n=5):
    """Cancel an item from a placed or preparing order. n bases -> 2n tasks."""
    tasks = []
    candidates = list(ix.placed_orders + ix.preparing_orders)
    # Only use orders with >= 2 items
    candidates = [oid for oid in candidates if len(db["orders"][oid]["items"]) >= 2]
    random.shuffle(candidates)

    for i, oid in enumerate(candidates[:n]):
        order = db["orders"][oid]
        cid = order["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)
        # Pick the first item to cancel
        cancel_item = order["items"][0]
        iid = cancel_item["item_id"]
        iname = item_name(db, iid)
        orig_count = len(order["items"])

        acts = [action(
            "cancel_item_1", "cancel_order_item",
            {"order_id": oid, "item_id": iid, "reason": "Customer changed mind"},
            f"Remove {iname} from order {oid}",
            compare_args=["order_id", "item_id"],
        )]
        asserts = [env_assert(
            "assert_order_item_count",
            {"order_id": oid, "expected_count": orig_count - 1},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"cancel_item_{i+1}a",
            "Test cancelling an item from an order",
            "Items can be cancelled from placed or preparing orders.",
            f"{name} removes {iname} from order {oid}.",
            pa.label,
            f"You are {name}. You want to remove an item from your order. {pa.instructions}",
            f"I'd like to remove the {iname} from my order.",
            f"Your name is {name}. You want to remove {iname} from your current order.",
            "You don't know the order ID or item ID.",
            f"{name} wants to remove {iname} from order {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"cancel_item_{i+1}b",
            "Test cancelling item with vague description",
            "Items can be cancelled from placed or preparing orders.",
            f"{name} vaguely describes removing {iname}.",
            pb.label,
            f"You are {name}. You want to take something off your order. {pb.instructions}",
            f"Actually, can you take off {vague_item(iid)}? I changed my mind.",
            f"Your name is {name}. You want to remove {vague_item(iid)} from your order.",
            "You don't know the order or item ID.",
            f"{name} vaguely requests removing {iname} from order {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_modify_order_add(db, ix, n=5):
    """Add an item to a placed order. n bases -> 2n tasks."""
    tasks = []
    placed = list(ix.placed_orders)
    random.shuffle(placed)

    for i, oid in enumerate(placed[:n]):
        order = db["orders"][oid]
        cid = order["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)
        # Pick an item not already in the order
        existing_ids = {it["item_id"] for it in order["items"]}
        new_candidates = [iid for iid in ix.available_items if iid not in existing_ids]
        if not new_candidates:
            continue
        new_iid = random.choice(new_candidates)
        new_iname = item_name(db, new_iid)
        orig_count = len(order["items"])

        acts = [action(
            "modify_ord_1", "modify_order",
            {"order_id": oid,
             "add_items": [{"item_id": new_iid, "quantity": 1}]},
            f"Add {new_iname} to order {oid}",
            compare_args=["order_id"],
        )]
        asserts = [env_assert(
            "assert_order_item_count",
            {"order_id": oid, "expected_count": orig_count + 1},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"add_item_{i+1}a",
            "Test adding an item to an order",
            "Orders with status 'placed' can be modified.",
            f"{name} adds {new_iname} to order {oid}.",
            pa.label,
            f"You are {name}. You want to add something to your order. {pa.instructions}",
            f"Can I also get the {new_iname} added to my order?",
            f"Your name is {name}. You want to add {new_iname} to your current order.",
            "You don't know the order ID or item ID.",
            f"{name} wants to add {new_iname} to order {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"add_item_{i+1}b",
            "Test adding item with vague description",
            "Orders with status 'placed' can be modified.",
            f"{name} vaguely asks to add {new_iname}.",
            pb.label,
            f"You are {name}. You want to add something to your order. {pb.instructions}",
            f"Oh, can I also get {vague_item(new_iid)}?",
            f"Your name is {name}. You want to add {vague_item(new_iid)} to your order.",
            "You don't know the order or item IDs.",
            f"{name} vaguely requests adding {new_iname} to order {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_modify_reservation(db, ix, n=5):
    """Modify a future reservation (party size). n bases -> 2n tasks."""
    tasks = []
    candidates = list(ix.confirmed_future)
    random.shuffle(candidates)

    for i, rid in enumerate(candidates[:n]):
        res = db["reservations"][rid]
        cid = res["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)
        lname = loc_name(db, res["location_id"])
        old_party = res["party_size"]
        # Change party size
        new_party = old_party + random.choice([-1, 1, 2])
        new_party = max(2, min(new_party, 8))
        if new_party == old_party:
            new_party = old_party + 1

        acts = [action(
            "modify_res_1", "modify_reservation",
            {"reservation_id": rid, "party_size": new_party},
            f"Modify reservation {rid} party size to {new_party}",
            compare_args=["reservation_id", "party_size"],
        )]
        asserts = [env_assert(
            "assert_reservation_party_size",
            {"reservation_id": rid, "expected_party_size": new_party},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"modify_res_{i+1}a",
            "Test modifying reservation party size",
            "Reservations can be modified up to 2 hours before reserved time.",
            f"{name} changes party size from {old_party} to {new_party} for {rid}.",
            pa.label,
            f"You are {name}. You need to change your reservation. {pa.instructions}",
            f"I need to change my reservation at {lname} on {res['date']} — we'll be {new_party} instead of {old_party}.",
            f"Your name is {name}. Reservation at {lname} on {res['date']} at {res['time']}. Change to {new_party} guests.",
            "You don't know your reservation ID.",
            f"{name} changes reservation {rid} from {old_party} to {new_party} guests.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"modify_res_{i+1}b",
            "Test modifying reservation with vague customer",
            "Reservations can be modified up to 2 hours before reserved time.",
            f"{name} vaguely requests party size change for {rid}.",
            pb.label,
            f"You are {name}. You need to update your dinner plans. {pb.instructions}",
            f"My dinner reservation... we have more people coming. It should be {new_party} total now.",
            f"Your name is {name}. You have a reservation at {vague_loc(res['location_id'])}. Need {new_party} guests.",
            "You don't remember exact date or reservation ID.",
            f"{name} vaguely describes changing reservation {rid} to {new_party} guests.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


# ---------------------------------------------------------------------------
# Tier 2: Information & Search
# ---------------------------------------------------------------------------


def gen_menu_lookup(db, ix, n=3):
    """Customer asks about the menu. n bases -> 2n tasks."""
    tasks = []
    lids = list(db["locations"].keys())
    random.shuffle(lids)

    for i, lid in enumerate(lids[:n]):
        lname = loc_name(db, lid)
        cid = random.choice(ix.all_customers)
        track_use(cid)
        name = cust_name(db, cid)

        acts = [action(
            "get_menu_1", "get_menu",
            {"location_id": lid},
            f"Get menu for {lname}",
            compare_args=["location_id"],
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"menu_lookup_{i+1}a",
            "Test menu lookup",
            "Menu is available per location with allergen and dietary info.",
            f"{name} asks for the menu at {lname}.",
            pa.label,
            f"You are {name}. You want to see the menu. {pa.instructions}",
            f"Can I see the menu for {lname}?",
            f"Your name is {name}. You want the menu at {lname}.",
            "You don't know the location ID.",
            f"{name} requests menu at {lname}.",
            acts, nl_assertions=["The agent provided menu information to the customer"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"menu_lookup_{i+1}b",
            "Test menu lookup with vague location",
            "Menu is available per location with allergen and dietary info.",
            f"{name} vaguely asks about the menu at {lname}.",
            pb.label,
            f"You are {name}. You want to see what's on the menu. {pb.instructions}",
            f"What do you guys have at {vague_loc(lid)}?",
            f"Your name is {name}. You want the menu at {vague_loc(lid)}.",
            "You don't know the location name exactly.",
            f"{name} vaguely asks for menu at {lname}.",
            acts, nl_assertions=["The agent provided menu information to the customer"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_dietary_menu(db, ix, n=4):
    """Customer asks about dietary-filtered menu. n bases -> 2n tasks."""
    tasks = []
    queries = [
        ("vegan", None), ("vegetarian", None), ("gluten-free", None),
        (None, "nuts"), (None, "dairy"), (None, "shellfish"),
        ("vegan", "nuts"), ("gluten-free", "dairy"),
    ]
    random.shuffle(queries)

    for i, (tag, allergen) in enumerate(queries[:n]):
        lid = random.choice(list(db["locations"].keys()))
        lname = loc_name(db, lid)
        cid = random.choice(ix.all_customers)
        track_use(cid)
        name = cust_name(db, cid)

        args = {"location_id": lid}
        if tag:
            args["dietary_tag"] = tag
        if allergen:
            args["exclude_allergen"] = allergen

        desc_parts = []
        if tag:
            desc_parts.append(f"{tag} options")
        if allergen:
            desc_parts.append(f"no {allergen}")
        desc = " and ".join(desc_parts)

        acts = [action(
            "dietary_menu_1", "get_dietary_menu", args,
            f"Get {desc} menu at {lname}",
            compare_args=list(args.keys()),
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"dietary_menu_{i+1}a",
            f"Test dietary menu filter ({desc})",
            "Allergen and dietary info must be checked and communicated.",
            f"{name} asks for {desc} at {lname}.",
            pa.label,
            f"You are {name}. You have dietary needs. {pa.instructions}",
            f"I'm looking for {desc} at {lname}.",
            f"Your name is {name}. You want {desc} options at {lname}.",
            "You don't know the location or menu item IDs.",
            f"{name} asks for {desc} menu at {lname}.",
            acts, nl_assertions=[f"The agent provided {desc} menu options"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"dietary_menu_{i+1}b",
            f"Test dietary menu filter with vague request ({desc})",
            "Allergen and dietary info must be checked and communicated.",
            f"{name} vaguely asks for {desc} at {lname}.",
            pb.label,
            f"You are {name}. You have dietary needs. {pb.instructions}",
            f"What can I eat at {vague_loc(lid)}? I need {desc}.",
            f"Your name is {name}. You need {desc} at {vague_loc(lid)}.",
            "You don't know exact location name.",
            f"{name} vaguely asks for {desc} at {lname}.",
            acts, nl_assertions=[f"The agent provided {desc} menu options"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_search_availability(db, ix, n=4):
    """Search table availability. n bases -> 2n tasks."""
    tasks = []
    future_dates = [
        (TODAY_DT + timedelta(days=d)).strftime("%Y-%m-%d")
        for d in range(2, 10)
    ]
    times = ["18:00", "19:00", "19:30", "20:00"]
    sizes = [2, 4, 6, 8]

    for i in range(n):
        lid = random.choice(list(db["locations"].keys()))
        lname = loc_name(db, lid)
        cid = random.choice(ix.all_customers)
        track_use(cid)
        name = cust_name(db, cid)
        date = random.choice(future_dates)
        time = random.choice(times)
        party = random.choice(sizes)

        acts = [action(
            "search_avail_1", "search_availability",
            {"location_id": lid, "date": date, "time": time, "party_size": party},
            f"Search availability at {lname} for {party} on {date} at {time}",
            compare_args=["location_id", "date", "time", "party_size"],
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"search_avail_{i+1}a",
            "Test table availability search",
            "Tables can be searched by location, date, time, and party size.",
            f"{name} checks availability at {lname}.",
            pa.label,
            f"You are {name}. You want to check if there's a table available. {pa.instructions}",
            f"Do you have a table for {party} at {lname} on {date} at {time}?",
            f"Your name is {name}. Checking {lname} for {party} on {date} at {time}.",
            "You don't know the location ID.",
            f"{name} checks availability: {lname}, {party} guests, {date} at {time}.",
            acts, nl_assertions=["The agent communicated table availability to the customer"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"search_avail_{i+1}b",
            "Test availability search with vague request",
            "Tables can be searched by location, date, time, and party size.",
            f"{name} vaguely asks about availability at {lname}.",
            pb.label,
            f"You are {name}. You want to check table availability. {pb.instructions}",
            f"Is there room for {party} at {vague_loc(lid)} on {date}... around dinner time?",
            f"Your name is {name}. Looking for {party} at {vague_loc(lid)} on {date} around {time}.",
            "You don't remember the exact restaurant name.",
            f"{name} vaguely asks availability at {lname}.",
            acts, nl_assertions=["The agent communicated table availability to the customer"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_reservation_info(db, ix, n=3):
    """Customer asks about their reservation details. n bases -> 2n tasks."""
    tasks = []
    candidates = list(ix.confirmed_future)
    random.shuffle(candidates)

    for i, rid in enumerate(candidates[:n]):
        res = db["reservations"][rid]
        cid = res["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)

        acts = [action(
            "get_res_1", "get_reservation",
            {"reservation_id": rid},
            f"Get reservation {rid} details",
            compare_args=[],
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"res_info_{i+1}a",
            "Test reservation info lookup",
            "Customer should be able to check reservation details.",
            f"{name} asks about reservation {rid}.",
            pa.label,
            f"You are {name}. You want to check your reservation details. {pa.instructions}",
            f"Can you check my upcoming reservation? I think it's at {loc_name(db, res['location_id'])}.",
            f"Your name is {name}. You have a reservation coming up.",
            "You don't know your reservation ID.",
            f"{name} asks about reservation {rid}.",
            acts,
            nl_assertions=["The agent provided the reservation details including date, time, and party size"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"res_info_{i+1}b",
            "Test reservation info with vague request",
            "Customer should be able to check reservation details.",
            f"{name} vaguely asks about reservation.",
            pb.label,
            f"You are {name}. You want to check on your dinner plans. {pb.instructions}",
            f"I have a dinner coming up... can you look it up?",
            f"Your name is {name}. You have a reservation but don't remember details.",
            "You don't know the date, time, location, or reservation ID.",
            f"{name} vaguely asks about reservation {rid}.",
            acts,
            nl_assertions=["The agent provided the reservation details including date, time, and party size"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


# ---------------------------------------------------------------------------
# Tier 3: Moderate Multi-Step
# ---------------------------------------------------------------------------


def gen_apply_loyalty(db, ix, n=5):
    """Apply loyalty discount to a placed order. n bases -> 2n tasks."""
    tasks = []
    # Find placed orders whose customer has sufficient points
    pairs = []
    for oid in ix.placed_orders:
        order = db["orders"][oid]
        cid = order["customer_id"]
        cust = db["customers"][cid]
        if cust["loyalty_points"] >= 100:
            max_discount = round(cust["loyalty_points"] / LOYALTY_POINTS_PER_DOLLAR * 10, 2)
            if max_discount <= order["total"]:
                pairs.append((oid, cid, cust["loyalty_points"]))
            else:
                # Use a smaller amount of points
                safe_points = int(order["total"] / 10 * LOYALTY_POINTS_PER_DOLLAR)
                safe_points = max(100, (safe_points // 100) * 100)
                if safe_points <= cust["loyalty_points"]:
                    pairs.append((oid, cid, safe_points))
    random.shuffle(pairs)

    for i, (oid, cid, points) in enumerate(pairs[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        order = db["orders"][oid]
        cust = db["customers"][cid]
        discount = round(points / LOYALTY_POINTS_PER_DOLLAR * 10, 2)
        remaining = cust["loyalty_points"] - points

        acts = [action(
            "apply_loyalty_1", "apply_loyalty_discount",
            {"order_id": oid, "points": points},
            f"Apply {points} loyalty points (${discount:.2f} off) to order {oid}",
            compare_args=["order_id", "points"],
        )]
        asserts = [env_assert(
            "assert_customer_loyalty_points",
            {"customer_id": cid, "expected_points": remaining},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"apply_loyalty_{i+1}a",
            "Test applying loyalty discount",
            "100 points = $10 discount. Points can only be applied to placed/preparing orders.",
            f"{name} applies {points} points (${discount:.2f}) to order {oid}.",
            pa.label,
            f"You are {name}. You want to use your loyalty points. {pa.instructions}",
            f"I'd like to use {points} of my loyalty points on my current order.",
            f"Your name is {name}. You have {cust['loyalty_points']} loyalty points. You want to use {points}.",
            "You don't know your order ID.",
            f"{name} wants to apply {points} points to order {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"apply_loyalty_{i+1}b",
            "Test loyalty discount with vague request",
            "100 points = $10 discount. Points can only be applied to placed/preparing orders.",
            f"{name} vaguely asks to use points.",
            pb.label,
            f"You are {name}. You want to use your loyalty points. {pb.instructions}",
            f"Can I use some of my points? I think I have a bunch saved up.",
            f"Your name is {name}. You want to use {points} points on your order. You have {cust['loyalty_points']} total.",
            "You don't know exact point balance or order ID.",
            f"{name} wants to apply {points} points to order {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_issue_gift_card(db, ix, n=4):
    """Issue gift card for service failure. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.all_customers)
    random.shuffle(eligible)

    service_failures = [
        ("wrong order delivered", 25.00),
        ("excessive wait time of over 1 hour", 20.00),
        ("food quality issue — undercooked steak", 30.00),
        ("wrong order and cold food", 40.00),
        ("missing items from order", 15.00),
        ("rude staff experience", 25.00),
    ]
    random.shuffle(service_failures)

    for i, cid in enumerate(eligible[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        reason, amount = service_failures[i % len(service_failures)]

        acts = [action(
            "issue_gc_1", "issue_gift_card",
            {"customer_id": cid, "amount": amount, "reason": reason},
            f"Issue ${amount:.2f} gift card to {name} for {reason}",
            compare_args=["customer_id", "amount"],
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"issue_gc_{i+1}a",
            "Test gift card issuance for service failure",
            "Gift cards only for service failures. Max $50 without manager.",
            f"{name} reports {reason}. Agent issues ${amount:.2f} gift card.",
            pa.label,
            f"You are {name}. You had a bad experience. {pa.instructions}",
            f"I had a terrible experience — {reason}. I'd like some compensation.",
            f"Your name is {name}. You experienced: {reason}.",
            "You don't know what compensation is available.",
            f"{name} reports {reason}. Agent should issue ${amount:.2f} gift card.",
            acts,
            nl_assertions=[f"The agent issued a gift card to the customer as compensation"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"issue_gc_{i+1}b",
            "Test gift card issuance with frustrated customer",
            "Gift cards only for service failures. Max $50 without manager.",
            f"{name} is upset about {reason}.",
            pb.label,
            f"You are {name}. You had a terrible experience. {pb.instructions}",
            f"I'm really upset about what happened. {reason.capitalize()}. This is unacceptable.",
            f"Your name is {name}. Your complaint: {reason}.",
            "You want compensation but aren't sure what form it should take.",
            f"{name} complains about {reason}. Agent should issue ${amount:.2f} gift card.",
            acts,
            nl_assertions=[f"The agent issued a gift card to the customer as compensation"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_modify_add_remove(db, ix, n=4):
    """Add and remove items in one order modification. n bases -> 2n tasks."""
    tasks = []
    placed = [oid for oid in ix.placed_orders if len(db["orders"][oid]["items"]) >= 2]
    random.shuffle(placed)

    for i, oid in enumerate(placed[:n]):
        order = db["orders"][oid]
        cid = order["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)
        # Remove first item, add a new one
        rm_item = order["items"][0]
        rm_iid = rm_item["item_id"]
        rm_iname = item_name(db, rm_iid)
        existing = {it["item_id"] for it in order["items"]}
        new_options = [iid for iid in ix.available_items if iid not in existing]
        if not new_options:
            continue
        add_iid = random.choice(new_options)
        add_iname = item_name(db, add_iid)

        acts = [action(
            "modify_ord_1", "modify_order",
            {"order_id": oid,
             "add_items": [{"item_id": add_iid, "quantity": 1}],
             "remove_items": [rm_iid]},
            f"Remove {rm_iname}, add {add_iname} on order {oid}",
            compare_args=["order_id"],
        )]
        # Item count stays the same (remove 1, add 1)
        asserts = [env_assert(
            "assert_order_item_count",
            {"order_id": oid, "expected_count": len(order["items"])},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"modify_add_rm_{i+1}a",
            "Test order modification (add + remove)",
            "Placed orders can have items added or removed.",
            f"{name} swaps {rm_iname} for {add_iname} on {oid}.",
            pa.label,
            f"You are {name}. You want to change items on your order. {pa.instructions}",
            f"I'd like to swap the {rm_iname} for {add_iname} on my order.",
            f"Your name is {name}. Remove {rm_iname}, add {add_iname}.",
            "You don't know order or item IDs.",
            f"{name} swaps {rm_iname} for {add_iname} on order {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"modify_add_rm_{i+1}b",
            "Test order modification with vague request",
            "Placed orders can have items added or removed.",
            f"{name} vaguely asks to swap items on {oid}.",
            pb.label,
            f"You are {name}. You changed your mind about your order. {pb.instructions}",
            f"Actually... instead of {vague_item(rm_iid)}, can I get {vague_item(add_iid)}?",
            f"Your name is {name}. You want {vague_item(add_iid)} instead of {vague_item(rm_iid)}.",
            "You don't know the IDs.",
            f"{name} vaguely swaps {rm_iname} for {add_iname} on {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_cancel_rebook(db, ix, n=3):
    """Cancel reservation and make a new one. n bases -> 2n tasks."""
    tasks = []
    candidates = list(ix.confirmed_future)
    random.shuffle(candidates)

    for i, rid in enumerate(candidates[:n]):
        res = db["reservations"][rid]
        cid = res["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)
        lid = res["location_id"]
        lname = loc_name(db, lid)
        new_date = (TODAY_DT + timedelta(days=random.randint(3, 14))).strftime("%Y-%m-%d")
        new_time = random.choice(["18:00", "19:00", "19:30", "20:00"])
        party = res["party_size"]
        orig_count = len(db["customers"][cid]["reservation_ids"])

        acts = [
            action("cancel_1", "cancel_reservation",
                   {"reservation_id": rid, "reason": "Rescheduling"},
                   f"Cancel reservation {rid}", compare_args=["reservation_id"]),
            action("create_1", "create_reservation",
                   {"customer_id": cid, "location_id": lid, "date": new_date,
                    "time": new_time, "party_size": party},
                   f"Create new reservation at {lname}",
                   compare_args=["customer_id", "location_id", "date", "time", "party_size"]),
        ]
        asserts = [
            env_assert("assert_reservation_status",
                       {"reservation_id": rid, "expected_status": "cancelled"}),
        ]

        pa = pick_easy()
        tasks.append(make_task(
            f"cancel_rebook_{i+1}a",
            "Test cancel and rebook reservation",
            "Cancellations and new reservations follow standard policy.",
            f"{name} reschedules reservation {rid} to {new_date} at {new_time}.",
            pa.label,
            f"You are {name}. You need to reschedule your reservation. {pa.instructions}",
            f"I need to reschedule my reservation at {lname} from {res['date']} to {new_date} at {new_time}.",
            f"Your name is {name}. Current: {lname} on {res['date']}. New: {new_date} at {new_time}, {party} guests.",
            "You don't know your reservation ID.",
            f"{name} reschedules {rid} to {new_date} at {new_time}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"cancel_rebook_{i+1}b",
            "Test cancel and rebook with vague request",
            "Cancellations and new reservations follow standard policy.",
            f"{name} vaguely asks to reschedule at {lname}.",
            pb.label,
            f"You are {name}. Something came up and you need to change your plans. {pb.instructions}",
            f"I can't make it to dinner at {vague_loc(lid)} on {res['date']}. Can we move it to {new_date} around {new_time}?",
            f"Your name is {name}. Move from {res['date']} to {new_date} at {new_time}. Same location and party size.",
            "You don't remember exact details.",
            f"{name} reschedules {rid} to {new_date} at {new_time}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_dietary_reservation(db, ix, n=3):
    """Customer with dietary needs creates reservation and checks menu. n bases -> 2n tasks."""
    tasks = []
    diet_custs = list(ix.customers_with_diet)
    random.shuffle(diet_custs)

    for i, cid in enumerate(diet_custs[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        cust = db["customers"][cid]
        diet = cust["dietary_restrictions"][0]
        lid = random.choice(list(db["locations"].keys()))
        lname = loc_name(db, lid)
        date = (TODAY_DT + timedelta(days=random.randint(2, 10))).strftime("%Y-%m-%d")
        time = random.choice(["18:00", "19:00", "19:30"])
        party = random.choice([2, 4])
        orig_count = len(cust["reservation_ids"])

        acts = [
            action("dietary_1", "get_dietary_menu",
                   {"location_id": lid, "dietary_tag": diet},
                   f"Check {diet} menu at {lname}",
                   compare_args=["location_id", "dietary_tag"]),
            action("create_1", "create_reservation",
                   {"customer_id": cid, "location_id": lid, "date": date,
                    "time": time, "party_size": party},
                   f"Create reservation for {name}",
                   compare_args=["customer_id", "location_id", "date", "time", "party_size"]),
        ]
        asserts = [env_assert(
            "assert_customer_reservation_count",
            {"customer_id": cid, "expected_count": orig_count + 1},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"diet_res_{i+1}a",
            "Test dietary check then reservation",
            "Dietary info should be checked. Reservations require standard info.",
            f"{name} ({diet}) checks menu then books at {lname}.",
            pa.label,
            f"You are {name}. You are {diet} and want to dine out. {pa.instructions}",
            f"I'm {diet}. Do you have options at {lname}? If so, I'd like a table for {party} on {date} at {time}.",
            f"Your name is {name}. You are {diet}. Want to book at {lname}, {date} at {time}, {party} guests.",
            "You don't know menu item or customer IDs.",
            f"{name} ({diet}) checks menu then books at {lname}.",
            acts, asserts,
            nl_assertions=[f"The agent provided {diet} menu options"],
            reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"diet_res_{i+1}b",
            "Test dietary reservation with vague request",
            "Dietary info should be checked. Reservations require standard info.",
            f"{name} ({diet}) vaguely asks about dining at {lname}.",
            pb.label,
            f"You are {name}. You have dietary needs and want to eat out. {pb.instructions}",
            f"I'm {diet} and I want to have dinner at {vague_loc(lid)}... maybe for {party}?",
            f"Your name is {name}. You are {diet}. Want {party} guests at {vague_loc(lid)} on {date} around {time}.",
            "You don't know exact details.",
            f"{name} ({diet}) vaguely asks to dine at {lname}.",
            acts, asserts,
            nl_assertions=[f"The agent provided {diet} menu options"],
            reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_allergy_modify(db, ix, n=3):
    """Customer with allergy modifies order — agent should check allergens. n bases -> 2n tasks."""
    tasks = []
    allergy_custs = list(ix.customers_with_allergies)
    random.shuffle(allergy_custs)

    for i, cid in enumerate(allergy_custs[:n]):
        cust = db["customers"][cid]
        allergy = cust["allergy_info"][0]
        # Find a placed order for this customer
        cust_placed = [oid for oid in cust["order_ids"]
                       if oid in db["orders"] and db["orders"][oid]["status"] == "placed"]
        if not cust_placed:
            # Use any placed order and pretend
            if not ix.placed_orders:
                continue
            oid = random.choice(ix.placed_orders)
            cid = db["orders"][oid]["customer_id"]
            cust = db["customers"][cid]
            if not cust["allergy_info"]:
                continue
            allergy = cust["allergy_info"][0]
        else:
            oid = cust_placed[0]

        track_use(cid)
        name = cust_name(db, cid)
        # Find a safe item to add (no allergen)
        safe_items = [iid for iid in ix.available_items
                      if allergy not in db["menu_items"][iid]["allergens"]]
        if not safe_items:
            continue
        safe_iid = random.choice(safe_items)
        safe_iname = item_name(db, safe_iid)
        orig_count = len(db["orders"][oid]["items"])

        acts = [action(
            "modify_1", "modify_order",
            {"order_id": oid, "add_items": [{"item_id": safe_iid, "quantity": 1}]},
            f"Add {safe_iname} (safe for {allergy} allergy) to order {oid}",
            compare_args=["order_id"],
        )]
        asserts = [env_assert(
            "assert_order_item_count",
            {"order_id": oid, "expected_count": orig_count + 1},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"allergy_modify_{i+1}a",
            "Test allergen-aware order modification",
            "Agent must check allergens before modifying orders for allergic customers.",
            f"{name} (allergic to {allergy}) adds {safe_iname} to order.",
            pa.label,
            f"You are {name}. You have a {allergy} allergy. You want to add to your order. {pa.instructions}",
            f"I'd like to add {safe_iname} to my order. Just to confirm, I'm allergic to {allergy}.",
            f"Your name is {name}. You are allergic to {allergy}. You want {safe_iname} added.",
            "You don't know the IDs. You expect the agent to verify allergens.",
            f"{name} ({allergy} allergy) adds {safe_iname} to {oid}. Agent should verify allergens.",
            acts, asserts,
            nl_assertions=["The agent confirmed the item is safe for the customer's allergy"],
            reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"allergy_modify_{i+1}b",
            "Test allergen-aware modification with vague request",
            "Agent must check allergens before modifying orders for allergic customers.",
            f"{name} ({allergy} allergy) vaguely adds to order.",
            pb.label,
            f"You are {name}. You have a {allergy} allergy. {pb.instructions}",
            f"Can I add something to my order? Maybe {vague_item(safe_iid)}. I'm really worried about {allergy}.",
            f"Your name is {name}. Allergic to {allergy}. Want {vague_item(safe_iid)}.",
            "You don't know IDs. You're worried about allergens.",
            f"{name} ({allergy} allergy) vaguely requests {safe_iname} for {oid}.",
            acts, asserts,
            nl_assertions=["The agent confirmed the item is safe for the customer's allergy"],
            reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
        ))

    return tasks


# ---------------------------------------------------------------------------
# Tier 4: Complex Multi-Step
# ---------------------------------------------------------------------------


def gen_loyalty_then_modify(db, ix, n=3):
    """Apply loyalty discount then add item. n bases -> 2n tasks."""
    tasks = []
    pairs = []
    for oid in ix.placed_orders:
        order = db["orders"][oid]
        cid = order["customer_id"]
        cust = db["customers"][cid]
        if cust["loyalty_points"] >= 200 and order["total"] >= 30:
            pairs.append((oid, cid))
    random.shuffle(pairs)

    for i, (oid, cid) in enumerate(pairs[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        cust = db["customers"][cid]
        order = db["orders"][oid]
        points = 200
        discount = round(points / LOYALTY_POINTS_PER_DOLLAR * 10, 2)
        remaining = cust["loyalty_points"] - points
        existing = {it["item_id"] for it in order["items"]}
        new_options = [iid for iid in ix.available_items if iid not in existing]
        if not new_options:
            continue
        add_iid = random.choice(new_options)
        add_iname = item_name(db, add_iid)

        acts = [
            action("loyalty_1", "apply_loyalty_discount",
                   {"order_id": oid, "points": points},
                   f"Apply {points} points", compare_args=["order_id", "points"]),
            action("modify_1", "modify_order",
                   {"order_id": oid, "add_items": [{"item_id": add_iid, "quantity": 1}]},
                   f"Add {add_iname}", compare_args=["order_id"]),
        ]
        asserts = [env_assert(
            "assert_customer_loyalty_points",
            {"customer_id": cid, "expected_points": remaining},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"loyalty_modify_{i+1}a",
            "Test loyalty discount then add item",
            "Loyalty: 100pts = $10. Orders can be modified while placed.",
            f"{name} applies {points} points then adds {add_iname}.",
            pa.label,
            f"You are {name}. You want to use points and add an item. {pa.instructions}",
            f"I'd like to use {points} loyalty points on my order, and also add {add_iname}.",
            f"Your name is {name}. Use {points} points and add {add_iname}.",
            "You don't know your order ID.",
            f"{name}: apply {points} points then add {add_iname} to {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"loyalty_modify_{i+1}b",
            "Test loyalty + modify with vague request",
            "Loyalty: 100pts = $10. Orders can be modified while placed.",
            f"{name} vaguely asks to use points and add item.",
            pb.label,
            f"You are {name}. You want to use points and change your order. {pb.instructions}",
            f"Can I use some points — maybe {points} — and throw in {vague_item(add_iid)} too?",
            f"Your name is {name}. Use {points} points. Add {vague_item(add_iid)}.",
            "You don't know IDs or exact point balance.",
            f"{name}: apply {points} points then add {add_iname} to {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_cancel_rebook_diff_loc(db, ix, n=3):
    """Cancel reservation at one location, rebook at another. n bases -> 2n tasks."""
    tasks = []
    candidates = list(ix.confirmed_future)
    random.shuffle(candidates)

    for i, rid in enumerate(candidates[:n]):
        res = db["reservations"][rid]
        cid = res["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)
        old_lid = res["location_id"]
        other_lids = [lid for lid in db["locations"] if lid != old_lid]
        new_lid = random.choice(other_lids)
        new_lname = loc_name(db, new_lid)
        old_lname = loc_name(db, old_lid)
        new_date = (TODAY_DT + timedelta(days=random.randint(3, 10))).strftime("%Y-%m-%d")
        new_time = random.choice(["18:00", "19:00", "19:30"])
        party = res["party_size"]

        acts = [
            action("cancel_1", "cancel_reservation",
                   {"reservation_id": rid, "reason": "Switching location"},
                   f"Cancel at {old_lname}", compare_args=["reservation_id"]),
            action("create_1", "create_reservation",
                   {"customer_id": cid, "location_id": new_lid, "date": new_date,
                    "time": new_time, "party_size": party},
                   f"Rebook at {new_lname}",
                   compare_args=["customer_id", "location_id", "date", "time", "party_size"]),
        ]
        asserts = [env_assert(
            "assert_reservation_status",
            {"reservation_id": rid, "expected_status": "cancelled"},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"rebook_diff_{i+1}a",
            "Test cancel and rebook at different location",
            "Reservations can be cancelled and recreated at different locations.",
            f"{name} moves from {old_lname} to {new_lname}.",
            pa.label,
            f"You are {name}. You want to move your reservation to a different location. {pa.instructions}",
            f"I'd like to move my reservation from {old_lname} to {new_lname}, {new_date} at {new_time}.",
            f"Your name is {name}. Cancel at {old_lname}, rebook at {new_lname} on {new_date} at {new_time}, {party} guests.",
            "You don't know your reservation ID.",
            f"{name} moves reservation from {old_lname} to {new_lname}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"rebook_diff_{i+1}b",
            "Test rebook different location with vague request",
            "Reservations can be cancelled and recreated at different locations.",
            f"{name} vaguely asks to switch locations.",
            pb.label,
            f"You are {name}. You want to switch restaurants. {pb.instructions}",
            f"Actually, can we go to {vague_loc(new_lid)} instead? Move my reservation there for {new_date}.",
            f"Your name is {name}. Switch to {vague_loc(new_lid)} on {new_date} at {new_time}, {party} guests.",
            "You don't know exact location names or IDs.",
            f"{name} switches from {old_lname} to {new_lname}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_allergy_full_order(db, ix, n=3):
    """Full allergen-aware order workflow. n bases -> 2n tasks."""
    tasks = []
    allergy_custs = list(ix.customers_with_allergies)
    random.shuffle(allergy_custs)

    for i, cid in enumerate(allergy_custs[:n]):
        cust = db["customers"][cid]
        allergy = cust["allergy_info"][0]
        track_use(cid)
        name = cust_name(db, cid)
        lid = random.choice(list(db["locations"].keys()))
        lname = loc_name(db, lid)

        # Find safe items
        safe_items = [iid for iid in ix.available_items
                      if allergy not in db["menu_items"][iid]["allergens"]]

        acts = [
            action("dietary_1", "get_dietary_menu",
                   {"location_id": lid, "exclude_allergen": allergy},
                   f"Get menu excluding {allergy} at {lname}",
                   compare_args=["location_id", "exclude_allergen"]),
        ]

        pa = pick_easy()
        tasks.append(make_task(
            f"allergy_order_{i+1}a",
            "Test full allergen-aware order workflow",
            "Allergen info must always be checked. Agent must flag allergens proactively.",
            f"{name} ({allergy} allergy) orders at {lname}.",
            pa.label,
            f"You are {name}. You have a severe {allergy} allergy. You want to order food. {pa.instructions}",
            f"I have a {allergy} allergy. What can I safely eat at {lname}?",
            f"Your name is {name}. Severe {allergy} allergy. Want to see safe menu options at {lname}.",
            "You don't know which items are safe.",
            f"{name} ({allergy} allergy) needs safe menu at {lname}.",
            acts,
            nl_assertions=[
                f"The agent checked allergen information and provided {allergy}-free options",
                f"The agent confirmed food safety for the customer's {allergy} allergy",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"allergy_order_{i+1}b",
            "Test allergen order with nervous customer",
            "Allergen info must always be checked. Agent must flag allergens proactively.",
            f"{name} ({allergy} allergy) nervously orders at {lname}.",
            pb.label,
            f"You are {name}. You are very anxious about your {allergy} allergy. {pb.instructions}",
            f"I'm really worried... I have a {allergy} allergy. Is anything safe at {vague_loc(lid)}?",
            f"Your name is {name}. Very worried about {allergy}. Want safe options at {vague_loc(lid)}.",
            "You're not sure which items are safe and need reassurance.",
            f"{name} ({allergy} allergy) anxiously asks about {lname}.",
            acts,
            nl_assertions=[
                f"The agent checked allergen information and provided {allergy}-free options",
                f"The agent confirmed food safety for the customer's {allergy} allergy",
            ],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_reservation_and_order(db, ix, n=3):
    """Create reservation, then modify existing order. n bases -> 2n tasks."""
    tasks = []
    # Find customers with placed orders
    pairs = []
    for oid in ix.placed_orders:
        order = db["orders"][oid]
        cid = order["customer_id"]
        pairs.append((oid, cid))
    random.shuffle(pairs)

    for i, (oid, cid) in enumerate(pairs[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        order = db["orders"][oid]
        lid = order["location_id"]
        lname = loc_name(db, lid)
        date = (TODAY_DT + timedelta(days=random.randint(2, 10))).strftime("%Y-%m-%d")
        time = random.choice(["18:00", "19:00"])
        party = random.choice([2, 4])
        orig_res_count = len(db["customers"][cid]["reservation_ids"])
        # Add an item
        existing = {it["item_id"] for it in order["items"]}
        new_options = [iid for iid in ix.available_items if iid not in existing]
        if not new_options:
            continue
        add_iid = random.choice(new_options)
        add_iname = item_name(db, add_iid)

        acts = [
            action("create_1", "create_reservation",
                   {"customer_id": cid, "location_id": lid, "date": date,
                    "time": time, "party_size": party},
                   f"Book reservation",
                   compare_args=["customer_id", "location_id", "date", "time", "party_size"]),
            action("modify_1", "modify_order",
                   {"order_id": oid, "add_items": [{"item_id": add_iid, "quantity": 1}]},
                   f"Add {add_iname} to order",
                   compare_args=["order_id"]),
        ]
        asserts = [env_assert(
            "assert_customer_reservation_count",
            {"customer_id": cid, "expected_count": orig_res_count + 1},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"res_and_order_{i+1}a",
            "Test reservation creation plus order modification",
            "Reservations and order modifications follow standard policy.",
            f"{name} books at {lname} and adds {add_iname}.",
            pa.label,
            f"You are {name}. You need a reservation and want to add to your order. {pa.instructions}",
            f"I'd like a table for {party} at {lname} on {date} at {time}. Also, add {add_iname} to my current order.",
            f"Your name is {name}. Book {party} at {lname} on {date} at {time}. Also add {add_iname}.",
            "You don't know your customer or order IDs.",
            f"{name}: book table and add {add_iname} to order {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"res_and_order_{i+1}b",
            "Test reservation + order modification with vague request",
            "Reservations and order modifications follow standard policy.",
            f"{name} vaguely asks to book and modify order.",
            pb.label,
            f"You are {name}. You need a few things done. {pb.instructions}",
            f"I need to book a table at {vague_loc(lid)} and also add something to my order.",
            f"Your name is {name}. Book {party} at {vague_loc(lid)} on {date} at {time}. Add {vague_item(add_iid)}.",
            "You don't know IDs.",
            f"{name}: book table at {lname} and add {add_iname} to {oid}.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


# ---------------------------------------------------------------------------
# Tier 5: Edge Cases & Policy
# ---------------------------------------------------------------------------


def gen_modify_res_denied(db, ix, n=4):
    """Modification denied — within 2h cutoff. Single variant."""
    tasks = []
    candidates = list(ix.confirmed_within_2h)
    random.shuffle(candidates)

    for i, rid in enumerate(candidates[:n]):
        res = db["reservations"][rid]
        cid = res["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)

        pa = pick_easy()
        tasks.append(make_task(
            f"mod_res_denied_{i+1}",
            "Test reservation modification denied (within 2h cutoff)",
            "Reservations can only be modified up to 2 hours before reserved time.",
            f"{name} tries to modify {rid} but it's within 2 hours. Should be denied.",
            pa.label,
            f"You are {name}. You want to change your reservation. {pa.instructions}",
            f"I need to change the party size for my reservation to 5 people.",
            f"Your name is {name}. You have reservation on {res['date']} at {res['time']}.",
            "You don't realize it's too late to modify.",
            f"{name} tries to modify {rid} — within 2h cutoff. Agent should explain policy.",
            [],
            nl_assertions=["The agent explained that the reservation cannot be modified within 2 hours of the reserved time"],
            reward_basis=["NL_ASSERTION"],
        ))

    return tasks


def gen_cancel_fee(db, ix, n=4):
    """Late cancellation with fee (party > 6). Single variant."""
    tasks = []
    candidates = list(ix.confirmed_within_1h_large)
    random.shuffle(candidates)

    for i, rid in enumerate(candidates[:n]):
        res = db["reservations"][rid]
        cid = res["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)

        acts = [action(
            "cancel_1", "cancel_reservation",
            {"reservation_id": rid, "reason": "Customer requested cancellation"},
            f"Cancel {rid} with late fee",
            compare_args=["reservation_id"],
        )]
        asserts = [env_assert(
            "assert_reservation_status",
            {"reservation_id": rid, "expected_status": "cancelled"},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"cancel_fee_{i+1}",
            "Test late cancellation with fee (party > 6)",
            "Cancellations within 1 hour for parties > 6 incur a cancellation fee.",
            f"{name} cancels {rid} within 1h, party {res['party_size']}. Fee applies.",
            pa.label,
            f"You are {name}. You need to cancel your reservation urgently. {pa.instructions}",
            f"I need to cancel my dinner reservation right away. Party of {res['party_size']}.",
            f"Your name is {name}. Reservation on {res['date']} at {res['time']}, party of {res['party_size']}.",
            "You don't know about the cancellation fee.",
            f"{name} cancels {rid}. Late + party > 6 = fee. Agent should warn about fee.",
            acts, asserts,
            nl_assertions=["The agent informed the customer about the late cancellation fee"],
            reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_cancel_no_fee(db, ix, n=3):
    """Late cancellation without fee (party <= 6). Single variant."""
    tasks = []
    candidates = list(ix.confirmed_within_1h_small)
    random.shuffle(candidates)

    for i, rid in enumerate(candidates[:n]):
        res = db["reservations"][rid]
        cid = res["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)

        acts = [action(
            "cancel_1", "cancel_reservation",
            {"reservation_id": rid, "reason": "Customer requested cancellation"},
            f"Cancel {rid} (no fee)",
            compare_args=["reservation_id"],
        )]
        asserts = [env_assert(
            "assert_reservation_status",
            {"reservation_id": rid, "expected_status": "cancelled"},
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"cancel_no_fee_{i+1}",
            "Test late cancellation without fee (party <= 6)",
            "No fee for parties of 6 or fewer, even within 1 hour.",
            f"{name} cancels {rid} within 1h, party {res['party_size']}. No fee.",
            pa.label,
            f"You are {name}. You need to cancel your dinner. {pa.instructions}",
            f"I need to cancel my reservation for tonight.",
            f"Your name is {name}. Reservation on {res['date']} at {res['time']}, party of {res['party_size']}.",
            "You don't know about cancellation policies.",
            f"{name} cancels {rid}. Within 1h but party <= 6 = no fee.",
            acts, asserts, reward_basis=["ACTION", "ENV_ASSERTION"],
        ))

    return tasks


def gen_modify_order_denied(db, ix, n=4):
    """Order modification denied — not in placed status. Single variant."""
    tasks = []
    candidates = list(ix.immutable_orders)
    random.shuffle(candidates)

    for i, oid in enumerate(candidates[:n]):
        order = db["orders"][oid]
        cid = order["customer_id"]
        track_use(cid)
        name = cust_name(db, cid)

        pa = pick_easy()
        tasks.append(make_task(
            f"mod_order_denied_{i+1}",
            f"Test order modification denied (status: {order['status']})",
            "Only 'placed' orders can be modified. 'placed'/'preparing' can have items cancelled.",
            f"{name} tries to modify order {oid} (status: {order['status']}). Denied.",
            pa.label,
            f"You are {name}. You want to change your order. {pa.instructions}",
            f"Can I add a dessert to my order?",
            f"Your name is {name}. You have an order (you don't know the status).",
            "You don't know the order can't be modified.",
            f"{name} tries to modify {oid} (status: {order['status']}). Agent should explain policy.",
            [],
            nl_assertions=[f"The agent explained that the order cannot be modified because its status is {order['status']}"],
            reward_basis=["NL_ASSERTION"],
        ))

    return tasks


def gen_loyalty_insufficient(db, ix, n=3):
    """Customer has insufficient loyalty points. Single variant."""
    tasks = []
    pairs = []
    for oid in ix.placed_orders:
        order = db["orders"][oid]
        cid = order["customer_id"]
        cust = db["customers"][cid]
        if 0 < cust["loyalty_points"] < 100:
            pairs.append((oid, cid))
    # Also add zero-loyalty customers with placed orders
    for cid in ix.customers_zero_loyalty:
        cust_orders = [oid for oid in db["customers"][cid]["order_ids"]
                       if oid in db["orders"] and db["orders"][oid]["status"] == "placed"]
        if cust_orders:
            pairs.append((cust_orders[0], cid))
    random.shuffle(pairs)

    for i, (oid, cid) in enumerate(pairs[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        cust = db["customers"][cid]
        pts = cust["loyalty_points"]

        pa = pick_easy()
        tasks.append(make_task(
            f"loyalty_insuff_{i+1}",
            "Test loyalty discount denied (insufficient points)",
            "Customers cannot redeem more points than they have.",
            f"{name} has {pts} points, tries to redeem 500. Should be denied.",
            pa.label,
            f"You are {name}. You want to use loyalty points. {pa.instructions}",
            f"I'd like to use 500 of my loyalty points on my order.",
            f"Your name is {name}. You want to use 500 points. You have {pts}.",
            "You believe you have enough points.",
            f"{name} tries 500 points with only {pts}. Agent should explain.",
            [],
            nl_assertions=["The agent informed the customer they have insufficient loyalty points"],
            reward_basis=["NL_ASSERTION"],
        ))

    return tasks


def gen_loyalty_exceeds(db, ix, n=2):
    """Loyalty discount would exceed order total. Single variant."""
    tasks = []
    pairs = []
    for oid in ix.placed_orders:
        order = db["orders"][oid]
        cid = order["customer_id"]
        cust = db["customers"][cid]
        # Need customer with enough points that discount > total
        max_discount = round(cust["loyalty_points"] / LOYALTY_POINTS_PER_DOLLAR * 10, 2)
        if max_discount > order["total"] and cust["loyalty_points"] >= 100:
            pairs.append((oid, cid, cust["loyalty_points"]))
    random.shuffle(pairs)

    for i, (oid, cid, pts) in enumerate(pairs[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        total = db["orders"][oid]["total"]

        pa = pick_easy()
        tasks.append(make_task(
            f"loyalty_exceeds_{i+1}",
            "Test loyalty discount exceeds order total",
            "Discount cannot exceed the order total.",
            f"{name} tries to use all {pts} points on ${total:.2f} order. Discount would exceed total.",
            pa.label,
            f"You are {name}. You want to apply all your loyalty points. {pa.instructions}",
            f"I'd like to use all my loyalty points on my current order.",
            f"Your name is {name}. You want to use all {pts} points.",
            "You don't realize the discount would be too much.",
            f"{name} tries all {pts} points on ${total:.2f} order. Agent should explain limit.",
            [],
            nl_assertions=["The agent explained that the discount would exceed the order total"],
            reward_basis=["NL_ASSERTION"],
        ))

    return tasks


def gen_gift_over_limit(db, ix, n=3):
    """Gift card over $50, transfer to manager. Single variant."""
    tasks = []
    eligible = list(ix.all_customers)
    random.shuffle(eligible)

    for i, cid in enumerate(eligible[:n]):
        track_use(cid)
        name = cust_name(db, cid)

        acts = [action(
            "transfer_1", "transfer_to_human_agents",
            {"summary": f"Customer {name} requesting gift card over $50 for service failure"},
            "Transfer to manager for gift card > $50",
            compare_args=[],
        )]

        pa = pick_easy()
        tasks.append(make_task(
            f"gift_over_limit_{i+1}",
            "Test gift card over $50 — transfer to manager",
            "Gift cards over $50 require manager approval.",
            f"{name} requests $75 gift card. Over limit, transfer needed.",
            pa.label,
            f"You are {name}. You had a terrible experience and want significant compensation. {pa.instructions}",
            f"I want a $75 gift card for the awful experience I had — wrong order, cold food, hour wait.",
            f"Your name is {name}. You want $75 compensation for service failure.",
            "You expect the agent to handle it directly.",
            f"{name} wants $75 gift card. Over $50 limit. Agent should transfer to manager.",
            acts,
            nl_assertions=["The agent explained that amounts over $50 require manager approval and transferred the customer"],
            reward_basis=["ACTION", "NL_ASSERTION"],
        ))

    return tasks


def gen_gift_non_service(db, ix, n=3):
    """Gift card for non-service issue — denied. Single variant."""
    tasks = []
    eligible = list(ix.all_customers)
    random.shuffle(eligible)

    non_service_reasons = [
        "I didn't like the taste of my meal",
        "The restaurant was too loud for my liking",
        "I changed my mind about what I ordered",
        "The portions were smaller than I expected",
    ]

    for i, cid in enumerate(eligible[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        reason = non_service_reasons[i % len(non_service_reasons)]

        pa = pick_easy()
        tasks.append(make_task(
            f"gift_non_service_{i+1}",
            "Test gift card denied for non-service issue",
            "Gift cards can only be issued for service failures, not preference changes.",
            f"{name} wants gift card for: {reason}. Not a service failure.",
            pa.label,
            f"You are {name}. You want compensation. {pa.instructions}",
            f"I'd like a gift card because: {reason}.",
            f"Your name is {name}. You want a gift card. Reason: {reason}.",
            "You think your reason qualifies for compensation.",
            f"{name} wants gift card for non-service reason. Agent should explain policy.",
            [],
            nl_assertions=["The agent explained that gift cards are only issued for service failures"],
            reward_basis=["NL_ASSERTION"],
        ))

    return tasks


def gen_allergy_warning(db, ix, n=3):
    """Customer with allergy ordering allergen item — agent must warn. n bases -> 2n tasks."""
    tasks = []
    pairs = []
    for cid in ix.customers_with_allergies:
        cust = db["customers"][cid]
        allergy = cust["allergy_info"][0]
        dangerous = ix.items_by_allergen.get(allergy, [])
        if dangerous:
            pairs.append((cid, allergy, dangerous))
    random.shuffle(pairs)

    for i, (cid, allergy, dangerous_items) in enumerate(pairs[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        bad_iid = random.choice(dangerous_items)
        bad_iname = item_name(db, bad_iid)

        pa = pick_easy()
        tasks.append(make_task(
            f"allergy_warn_{i+1}a",
            "Test allergen warning when customer orders dangerous item",
            "Agent must always check allergen info and flag items containing customer's allergens.",
            f"{name} ({allergy} allergy) tries to order {bad_iname} which contains {allergy}.",
            pa.label,
            f"You are {name}. You have a {allergy} allergy. {pa.instructions}",
            f"I'd like to order the {bad_iname}. Oh, and I should mention I'm allergic to {allergy}.",
            f"Your name is {name}. Allergic to {allergy}. You want {bad_iname}.",
            "You don't realize this item contains your allergen.",
            f"{name} ({allergy} allergy) orders {bad_iname} (contains {allergy}). Agent MUST warn.",
            [],
            nl_assertions=[
                f"The agent warned the customer that {bad_iname} contains {allergy}",
                "The agent did NOT place the order without warning about the allergen",
            ],
            reward_basis=["NL_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"allergy_warn_{i+1}b",
            "Test allergen warning with vague customer",
            "Agent must always check allergen info and flag items containing customer's allergens.",
            f"{name} ({allergy} allergy) vaguely orders {bad_iname}.",
            pb.label,
            f"You are {name}. You have a {allergy} allergy. {pb.instructions}",
            f"Can I get {vague_item(bad_iid)}? I'm allergic to {allergy} by the way.",
            f"Your name is {name}. Allergic to {allergy}. Want {vague_item(bad_iid)}.",
            "You don't realize this item is dangerous.",
            f"{name} ({allergy} allergy) vaguely orders {bad_iname} (contains {allergy}). Agent MUST warn.",
            [],
            nl_assertions=[
                f"The agent warned the customer that {bad_iname} contains {allergy}",
                "The agent did NOT place the order without warning about the allergen",
            ],
            reward_basis=["NL_ASSERTION"],
        ))

    return tasks


def gen_transfer_scenarios(db, ix, n=4):
    """Transfer to human agent. Single variant."""
    tasks = []
    eligible = list(ix.all_customers)
    random.shuffle(eligible)

    scenarios = [
        {
            "suffix": "billing_dispute",
            "reason": "You want to dispute a charge on your bill that you believe is incorrect.",
            "known": "Your name is {name}. You have a billing discrepancy.",
            "unknown": "Keep insisting until they transfer you.",
            "ticket": "{name} disputes billing. Agent should transfer to human.",
            "nl": ["The agent transferred the customer to a human agent"],
        },
        {
            "suffix": "special_event",
            "reason": "You want to book the restaurant for a private event of 30+ people.",
            "known": "Your name is {name}. You want to book for a large private event.",
            "unknown": "You expect them to handle large event bookings.",
            "ticket": "{name} wants private event. Agent should transfer to human.",
            "nl": ["The agent transferred the customer to a human agent for the private event booking"],
        },
        {
            "suffix": "complaint_escalation",
            "reason": "You had a severe food poisoning incident and want to speak with a manager immediately.",
            "known": "Your name is {name}. You got food poisoning from a recent meal.",
            "unknown": "You want to speak to a manager directly.",
            "ticket": "{name} reports food poisoning. Agent should transfer to human.",
            "nl": ["The agent transferred the customer to a human agent"],
        },
        {
            "suffix": "refund_request",
            "reason": "You want a full refund for a completed order you were extremely unhappy with.",
            "known": "Your name is {name}. You want a refund for a past order.",
            "unknown": "You don't know if refunds are possible through customer service.",
            "ticket": "{name} wants refund. Agent should transfer to human.",
            "nl": ["The agent transferred the customer to a human agent for the refund request"],
        },
    ]

    for i, scenario in enumerate(scenarios[:n]):
        if i >= len(eligible):
            break
        cid = eligible[i]
        track_use(cid)
        name = cust_name(db, cid)
        pa = pick_easy()

        tasks.append(make_task(
            f"transfer_{scenario['suffix']}",
            f"Test transfer to human agent ({scenario['suffix']})",
            "Agent should transfer to human when unable to resolve.",
            f"{name}: {scenario['suffix']} scenario.",
            pa.label,
            f"You are {name}. {scenario['reason']} {pa.instructions}",
            scenario["reason"],
            scenario["known"].format(name=name),
            scenario["unknown"],
            scenario["ticket"].format(name=name),
            [action("transfer_1", "transfer_to_human_agents",
                    {"summary": f"Customer {name}: {scenario['suffix']}"},
                    "Transfer to human agent", compare_args=[])],
            nl_assertions=scenario["nl"],
            reward_basis=["ACTION"],
        ))

    return tasks


def gen_unavailable_item(db, ix, n=3):
    """Customer tries to order unavailable item. Single variant."""
    tasks = []
    eligible = list(ix.all_customers)
    random.shuffle(eligible)

    for i in range(min(n, len(ix.unavailable_items))):
        cid = eligible[i]
        track_use(cid)
        name = cust_name(db, cid)
        iid = ix.unavailable_items[i % len(ix.unavailable_items)]
        iname = item_name(db, iid)

        pa = pick_easy()
        tasks.append(make_task(
            f"unavail_item_{i+1}",
            "Test ordering unavailable menu item",
            "Unavailable items cannot be ordered. Agent should inform customer.",
            f"{name} tries to order {iname} which is unavailable.",
            pa.label,
            f"You are {name}. You want to order. {pa.instructions}",
            f"I'd like the {iname}, please.",
            f"Your name is {name}. You want {iname}.",
            "You don't know it's unavailable.",
            f"{name} orders {iname} (unavailable). Agent should inform and suggest alternatives.",
            [],
            nl_assertions=[f"The agent informed the customer that {iname} is currently unavailable"],
            reward_basis=["NL_ASSERTION"],
        ))

    return tasks


def gen_private_dining_small(db, ix, n=2):
    """Private dining with party < 6. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.all_customers)
    random.shuffle(eligible)

    for i, cid in enumerate(eligible[:n]):
        track_use(cid)
        name = cust_name(db, cid)
        lid = random.choice(list(db["locations"].keys()))
        lname = loc_name(db, lid)
        date = (TODAY_DT + timedelta(days=random.randint(3, 10))).strftime("%Y-%m-%d")
        party = random.choice([2, 3, 4])

        pa = pick_easy()
        tasks.append(make_task(
            f"private_small_{i+1}a",
            "Test private dining request with small party",
            "Private dining requires minimum party size of 6.",
            f"{name} wants private dining for {party}. Below minimum.",
            pa.label,
            f"You are {name}. You want a private dining room. {pa.instructions}",
            f"I'd like to book the private dining room at {lname} for {party} on {date}.",
            f"Your name is {name}. Private room at {lname}, {party} guests, {date}.",
            "You don't know about the minimum party size.",
            f"{name} wants private dining for {party} (min is 6). Agent should explain policy.",
            [],
            nl_assertions=["The agent explained that private dining requires a minimum party size of 6"],
            reward_basis=["NL_ASSERTION"],
        ))

        pb = pick_hard()
        tasks.append(make_task(
            f"private_small_{i+1}b",
            "Test private dining small party with vague customer",
            "Private dining requires minimum party size of 6.",
            f"{name} vaguely asks for private dining for {party}.",
            pb.label,
            f"You are {name}. You want a private experience. {pb.instructions}",
            f"Do you have any private rooms? It's just {party} of us at {vague_loc(lid)}.",
            f"Your name is {name}. Want private room for {party} at {vague_loc(lid)} on {date}.",
            "You don't know about minimum requirements.",
            f"{name} wants private dining for {party} at {lname}. Agent should explain policy.",
            [],
            nl_assertions=["The agent explained that private dining requires a minimum party size of 6"],
            reward_basis=["NL_ASSERTION"],
        ))

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
        ("create_reservation", gen_create_reservation, 8),
        ("cancel_reservation", gen_cancel_reservation, 6),
        ("cancel_order_item", gen_cancel_order_item, 5),
        ("add_item_to_order", gen_modify_order_add, 6),
        ("modify_reservation", gen_modify_reservation, 5),
    ]

    generators_t2 = [
        ("menu_lookup", gen_menu_lookup, 3),
        ("dietary_menu", gen_dietary_menu, 4),
        ("search_availability", gen_search_availability, 4),
        ("reservation_info", gen_reservation_info, 3),
    ]

    generators_t3 = [
        ("apply_loyalty", gen_apply_loyalty, 5),
        ("issue_gift_card", gen_issue_gift_card, 4),
        ("modify_add_remove", gen_modify_add_remove, 4),
        ("cancel_rebook", gen_cancel_rebook, 3),
        ("dietary_reservation", gen_dietary_reservation, 3),
        ("allergy_modify", gen_allergy_modify, 3),
    ]

    generators_t4 = [
        ("loyalty_then_modify", gen_loyalty_then_modify, 3),
        ("rebook_diff_location", gen_cancel_rebook_diff_loc, 3),
        ("allergy_full_order", gen_allergy_full_order, 3),
        ("reservation_and_order", gen_reservation_and_order, 3),
    ]

    generators_t5 = [
        ("modify_res_denied", gen_modify_res_denied, 4),
        ("cancel_fee", gen_cancel_fee, 4),
        ("cancel_no_fee", gen_cancel_no_fee, 3),
        ("modify_order_denied", gen_modify_order_denied, 4),
        ("loyalty_insufficient", gen_loyalty_insufficient, 3),
        ("loyalty_exceeds", gen_loyalty_exceeds, 2),
        ("gift_over_limit", gen_gift_over_limit, 3),
        ("gift_non_service", gen_gift_non_service, 3),
        ("allergy_warning", gen_allergy_warning, 3),
        ("transfer", gen_transfer_scenarios, 4),
        ("unavailable_item", gen_unavailable_item, 2),
        ("private_dining_small", gen_private_dining_small, 3),
    ]

    tier_names = [
        ("Tier 1: Simple Single-Action", generators_t1),
        ("Tier 2: Information & Search", generators_t2),
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
        t["id"] for t in all_tasks
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
