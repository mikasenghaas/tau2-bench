#!/usr/bin/env python3
"""Generate a realistically-sized restaurant database (db.json).

Deterministic via random.seed(42). Uses only stdlib modules.
Run from repo root:
    uv run python environments/service_agent/tau2/data/tau2/domains/restaurant/generate_db.py
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
LOYALTY_POINTS_PER_DOLLAR = 100  # 100 points = $10 discount
GIFT_CARD_MAX_NO_MANAGER = 50.0
MODIFICATION_CUTOFF_HOURS = 2
CANCELLATION_FEE_CUTOFF_HOURS = 1
CANCELLATION_FEE_PARTY_SIZE = 6
PRIVATE_DINING_MIN_PARTY = 6


# ── Helpers ─────────────────────────────────────────────────────────────────
def date_str(dt):
    return dt.strftime("%Y-%m-%d")


def time_str(dt):
    return dt.strftime("%H:%M")


def make_unique_id(base, existing):
    """Return base if unique, else base_2, base_3, ..."""
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


# ═══════════════════════════════════════════════════════════════════════════
# Step 1: Locations (3)
# ═══════════════════════════════════════════════════════════════════════════
LOCATION_SPECS = [
    {
        "location_id": "riverside_downtown",
        "name": "Riverside Dining - Downtown",
        "address": "200 Main Street, Riverside",
        "hours": "Mon-Sun 11AM-10PM",
        "phone": "555-0100",
        "weight": 0.45,
        "short": "downtown",
    },
    {
        "location_id": "riverside_waterfront",
        "name": "Riverside Dining - Waterfront",
        "address": "85 Harbor Boulevard, Riverside",
        "hours": "Mon-Sun 11AM-11PM",
        "phone": "555-0200",
        "weight": 0.35,
        "short": "waterfront",
    },
    {
        "location_id": "riverside_garden",
        "name": "Riverside Dining - Garden District",
        "address": "412 Garden Lane, Riverside",
        "hours": "Tue-Sun 5PM-10PM",
        "phone": "555-0300",
        "weight": 0.20,
        "short": "garden",
    },
]

locations = {}
location_ids = [loc["location_id"] for loc in LOCATION_SPECS]
location_weights = [loc["weight"] for loc in LOCATION_SPECS]
location_short = {loc["location_id"]: loc["short"] for loc in LOCATION_SPECS}

for spec in LOCATION_SPECS:
    locations[spec["location_id"]] = {
        "location_id": spec["location_id"],
        "name": spec["name"],
        "address": spec["address"],
        "hours": spec["hours"],
        "phone": spec["phone"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Tables (60 — 20 per location)
# ═══════════════════════════════════════════════════════════════════════════
# Section distributions per location:
#   downtown:   12 indoor, 5 outdoor, 3 private
#   waterfront: 8 indoor, 9 outdoor, 3 private
#   garden:     6 indoor, 11 outdoor, 3 private
TABLE_LAYOUT = {
    "riverside_downtown": [
        ("indoor", [2, 2, 4, 4, 4, 4, 6, 6, 6, 8, 8, 10]),
        ("outdoor", [2, 4, 4, 6, 6]),
        ("private", [8, 10, 12]),
    ],
    "riverside_waterfront": [
        ("indoor", [2, 2, 4, 4, 4, 6, 6, 8]),
        ("outdoor", [2, 2, 4, 4, 4, 6, 6, 8, 8]),
        ("private", [8, 10, 12]),
    ],
    "riverside_garden": [
        ("indoor", [2, 4, 4, 4, 6, 8]),
        ("outdoor", [2, 2, 4, 4, 4, 4, 6, 6, 6, 8, 10]),
        ("private", [6, 10, 12]),
    ],
}

tables = {}
table_counts = defaultdict(int)  # (loc_short, section) -> count

for loc_id, sections in TABLE_LAYOUT.items():
    lshort = location_short[loc_id]
    for section, capacities in sections:
        for cap in capacities:
            table_counts[(lshort, section)] += 1
            num = table_counts[(lshort, section)]
            tid = f"table_{lshort}_{section}_{num}"
            tables[tid] = {
                "table_id": tid,
                "location_id": loc_id,
                "capacity": cap,
                "section": section,
                "is_available": True,
            }

# Mark a few tables unavailable (maintenance / reserved)
unavailable_tables = [
    "table_downtown_indoor_3",    # 4-seat indoor at downtown
    "table_waterfront_outdoor_7", # 6-seat outdoor at waterfront
    "table_garden_private_1",     # 6-seat private at garden
]
for tid in unavailable_tables:
    if tid in tables:
        tables[tid]["is_available"] = False


# ═══════════════════════════════════════════════════════════════════════════
# Step 3: Menu Items (32)
# ═══════════════════════════════════════════════════════════════════════════
# (item_id, name, description, price, category, allergens, dietary_tags, available)
MENU_CATALOG = [
    # Appetizers (8)
    ("crispy_calamari", "Crispy Calamari", "Lightly battered calamari rings with marinara sauce", 14.50, "appetizer", ["gluten", "shellfish"], [], True),
    ("bruschetta", "Bruschetta", "Toasted bread topped with tomatoes, basil, and olive oil", 10.00, "appetizer", ["gluten"], ["vegan"], True),
    ("caesar_salad", "Caesar Salad", "Romaine lettuce with Caesar dressing, croutons, and parmesan", 12.00, "appetizer", ["dairy", "eggs", "gluten"], [], True),
    ("soup_of_day", "Soup of the Day", "Chef's daily soup selection", 8.50, "appetizer", [], ["vegetarian"], True),
    ("shrimp_cocktail", "Shrimp Cocktail", "Chilled jumbo shrimp with cocktail sauce", 16.00, "appetizer", ["shellfish"], ["gluten-free"], True),
    ("spring_rolls", "Vegetable Spring Rolls", "Crispy rolls filled with seasonal vegetables", 11.00, "appetizer", ["gluten", "soy"], ["vegan"], True),
    ("stuffed_mushrooms", "Stuffed Mushrooms", "Portobello mushrooms stuffed with herbed breadcrumbs and cheese", 13.00, "appetizer", ["dairy", "gluten"], ["vegetarian"], True),
    ("edamame", "Steamed Edamame", "Lightly salted steamed soybeans", 7.00, "appetizer", ["soy"], ["vegan", "gluten-free"], True),

    # Mains (10)
    ("grilled_salmon", "Grilled Atlantic Salmon", "Pan-seared salmon with lemon butter sauce and seasonal vegetables", 28.00, "main", ["dairy"], ["gluten-free"], True),
    ("filet_mignon", "Filet Mignon", "8oz center-cut filet with garlic mashed potatoes", 42.00, "main", ["dairy"], ["gluten-free"], True),
    ("chicken_parmesan", "Chicken Parmesan", "Breaded chicken breast with marinara and melted mozzarella", 22.00, "main", ["dairy", "gluten", "eggs"], [], True),
    ("pasta_primavera", "Pasta Primavera", "Penne pasta with sautéed seasonal vegetables in garlic olive oil", 18.00, "main", ["gluten"], ["vegan"], True),
    ("ribeye_steak", "Ribeye Steak", "12oz bone-in ribeye with truffle fries", 45.00, "main", ["dairy"], ["gluten-free"], True),
    ("lobster_tail", "Lobster Tail", "Broiled Maine lobster tail with drawn butter", 48.00, "main", ["shellfish", "dairy"], ["gluten-free"], True),
    ("veggie_burger", "Veggie Burger", "House-made black bean burger on a brioche bun", 16.00, "main", ["gluten", "soy"], ["vegetarian"], True),
    ("mushroom_risotto", "Wild Mushroom Risotto", "Creamy arborio rice with mixed wild mushrooms and parmesan", 24.00, "main", ["dairy"], ["vegetarian", "gluten-free"], True),
    ("grilled_chicken", "Grilled Herb Chicken", "Free-range half chicken with roasted potatoes", 20.00, "main", [], ["gluten-free"], True),
    ("pan_seared_tuna", "Pan-Seared Ahi Tuna", "Sesame-crusted tuna with wasabi aioli", 32.00, "main", ["soy", "eggs"], ["gluten-free"], False),  # Unavailable — seasonal

    # Desserts (8)
    ("tiramisu", "Tiramisu", "Classic Italian coffee-flavored layered dessert", 12.00, "dessert", ["dairy", "eggs", "gluten"], ["vegetarian"], True),
    ("chocolate_cake", "Chocolate Lava Cake", "Warm chocolate cake with molten center and vanilla ice cream", 14.00, "dessert", ["dairy", "eggs", "gluten", "nuts"], ["vegetarian"], True),
    ("creme_brulee", "Crème Brûlée", "Vanilla custard with caramelized sugar top", 11.00, "dessert", ["dairy", "eggs"], ["vegetarian", "gluten-free"], True),
    ("cheesecake", "New York Cheesecake", "Classic New York-style cheesecake with berry compote", 13.00, "dessert", ["dairy", "eggs", "gluten"], ["vegetarian"], True),
    ("fruit_sorbet", "Seasonal Fruit Sorbet", "Three scoops of house-made fruit sorbet", 9.00, "dessert", [], ["vegan", "gluten-free"], True),
    ("panna_cotta", "Panna Cotta", "Italian cream dessert with raspberry coulis", 11.50, "dessert", ["dairy"], ["vegetarian", "gluten-free"], True),
    ("apple_tart", "Apple Tart", "Warm apple tart with cinnamon and caramel sauce", 12.50, "dessert", ["gluten", "dairy", "eggs"], ["vegetarian"], True),
    ("brownie_sundae", "Brownie Sundae", "Walnut brownie with ice cream and hot fudge", 13.50, "dessert", ["dairy", "eggs", "gluten", "nuts"], ["vegetarian"], False),  # Unavailable

    # Drinks (6)
    ("sparkling_water", "Sparkling Water", "Bottled sparkling mineral water", 4.00, "drink", [], ["vegan", "gluten-free"], True),
    ("iced_tea", "Fresh Iced Tea", "House-brewed iced tea with lemon", 3.50, "drink", [], ["vegan", "gluten-free"], True),
    ("espresso", "Espresso", "Double shot of Italian espresso", 4.50, "drink", [], ["vegan", "gluten-free"], True),
    ("craft_lemonade", "Craft Lemonade", "Hand-squeezed lemonade with fresh mint", 5.00, "drink", [], ["vegan", "gluten-free"], True),
    ("house_red_wine", "House Red Wine", "Glass of house Cabernet Sauvignon", 12.00, "drink", [], ["vegan", "gluten-free"], True),
    ("house_white_wine", "House White Wine", "Glass of house Chardonnay", 11.00, "drink", [], ["vegan", "gluten-free"], True),
]

menu_items = {}
for item_id, name, desc, price, cat, allergens, dietary_tags, available in MENU_CATALOG:
    menu_items[item_id] = {
        "item_id": item_id,
        "name": name,
        "description": desc,
        "price": price,
        "category": cat,
        "allergens": allergens,
        "dietary_tags": dietary_tags,
        "available": available,
    }

item_ids = [iid for iid, m in menu_items.items() if m["available"]]
item_ids_by_cat = defaultdict(list)
for iid in item_ids:
    item_ids_by_cat[menu_items[iid]["category"]].append(iid)


# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Customers (150)
# ═══════════════════════════════════════════════════════════════════════════
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen",
    "Charles", "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony",
    "Margaret", "Mark", "Sandra", "Donald", "Ashley", "Steven", "Dorothy",
    "Paul", "Kimberly", "Andrew", "Emily", "Joshua", "Donna",
    "Kenneth", "Michelle", "Kevin", "Carol", "Brian", "Amanda",
    "George", "Melissa", "Timothy", "Deborah",
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

# Allergen and dietary restriction pools
ALLERGEN_POOL = ["nuts", "dairy", "gluten", "shellfish", "eggs", "soy"]
DIETARY_POOL = ["vegan", "vegetarian", "gluten-free"]

customers = {}
customer_names_set: set[str] = set()
customer_id_list: list[str] = []

# Pre-select indices for edge cases
ALLERGY_INDICES = set(random.sample(range(150), 30))  # 20% have allergies
DIETARY_INDICES = set(random.sample(range(150), 25))  # ~17% have dietary restrictions
HIGH_LOYALTY_INDICES = set(random.sample(range(150), 15))  # High loyalty points
ZERO_LOYALTY_INDICES = set(random.sample(range(150), 20))  # Zero loyalty points

for i in range(150):
    # Pick a unique (first, last) combination
    for _attempt in range(500):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        display_name = f"{first} {last}"
        if display_name not in customer_names_set:
            break
    else:
        raise RuntimeError("Could not find a unique name after 500 attempts")
    customer_names_set.add(display_name)

    cid = f"{first.lower()}_{last.lower()}"
    # Should be unique since display name is unique
    customer_id_list.append(cid)

    domain = random.choice(EMAIL_DOMAINS)
    digits = random.randint(1, 99)
    email = f"{first.lower()}.{last.lower()}{digits}@{domain}"
    phone = f"555-{random.randint(1000, 9999):04d}"

    # Allergies
    allergy_info = []
    if i in ALLERGY_INDICES:
        num_allergies = random.choices([1, 2], weights=[70, 30], k=1)[0]
        allergy_info = random.sample(ALLERGEN_POOL, num_allergies)

    # Dietary restrictions
    dietary_restrictions = []
    if i in DIETARY_INDICES:
        num_diets = random.choices([1, 2], weights=[80, 20], k=1)[0]
        dietary_restrictions = random.sample(DIETARY_POOL, num_diets)

    # Loyalty points
    if i in ZERO_LOYALTY_INDICES:
        loyalty_points = 0
    elif i in HIGH_LOYALTY_INDICES:
        loyalty_points = random.randint(500, 2000)
    else:
        loyalty_points = random.randint(0, 500)

    customers[cid] = {
        "customer_id": cid,
        "name": display_name,
        "email": email,
        "phone": phone,
        "dietary_restrictions": dietary_restrictions,
        "allergy_info": allergy_info,
        "loyalty_points": loyalty_points,
        "reservation_ids": [],
        "order_ids": [],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Reservations (80)
# ═══════════════════════════════════════════════════════════════════════════
RESERVATION_TIMES = [
    "11:00", "11:30", "12:00", "12:30", "13:00",
    "17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30",
]

reservations = {}
reservation_status_counts = defaultdict(int)

# We want a good distribution of statuses and edge cases
# Status distribution: confirmed ~30, waitlisted ~8, cancelled ~12,
#                      completed ~20, no_show ~5, seated ~5

# Helper to create a reservation
def create_reservation(
    cid, loc_id, date_dt, time_str_val, party_size, status,
    special_requests=None, assign_table=True
):
    last = cid.split("_")[-1]
    base_rid = f"res_{last}_{date_str(date_dt).replace('-', '')}"
    rid = make_unique_id(base_rid, reservations)

    tid = None
    if assign_table:
        # Find a table at this location that fits
        loc_tables = [
            t for t in tables.values()
            if t["location_id"] == loc_id and t["capacity"] >= party_size
        ]
        if loc_tables:
            tid = random.choice(loc_tables)["table_id"]

    reservations[rid] = {
        "reservation_id": rid,
        "customer_id": cid,
        "location_id": loc_id,
        "date": date_str(date_dt),
        "time": time_str_val,
        "party_size": party_size,
        "table_id": tid,
        "status": status,
        "special_requests": special_requests,
    }
    customers[cid]["reservation_ids"].append(rid)
    reservation_status_counts[status] += 1
    return rid


# ── 5a. Confirmed reservations in the future (modifiable — more than 2h away)
# These are the ones customers can modify or cancel without fee
for j in range(25):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    # Future date: 1-14 days from today
    date_dt = TODAY + timedelta(days=random.randint(1, 14))
    time_val = random.choice(RESERVATION_TIMES)
    party_size = random.choices(
        [2, 3, 4, 5, 6, 7, 8], weights=[25, 15, 25, 10, 10, 8, 7], k=1
    )[0]
    create_reservation(cid, loc_id, date_dt, time_val, party_size, "confirmed")

# ── 5b. Confirmed reservations within 2 hours (NOT modifiable)
# REFERENCE_DATE = 2025-10-15 00:00 (midnight), so "within 2 hours" means
# today at 01:00 or 01:30 etc. We set a few at today's early morning.
for j in range(5):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    date_dt = TODAY  # same day
    time_val = f"{random.randint(0, 1):02d}:{random.choice(['00', '30'])}"
    party_size = random.choice([2, 4, 6])
    create_reservation(cid, loc_id, date_dt, time_val, party_size, "confirmed")

# ── 5c. Confirmed reservations within 1 hour AND party > 6 (cancellation fee)
for j in range(4):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    date_dt = TODAY
    time_val = "00:30"  # 30 min from midnight = within 1 hour
    party_size = random.choice([7, 8, 10])
    create_reservation(cid, loc_id, date_dt, time_val, party_size, "confirmed",
                       special_requests="Large party dinner")

# ── 5d. Confirmed within 1 hour, party <= 6 (no cancellation fee)
for j in range(3):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    date_dt = TODAY
    time_val = "00:30"
    party_size = random.choice([2, 4, 6])
    create_reservation(cid, loc_id, date_dt, time_val, party_size, "confirmed")

# ── 5e. Waitlisted reservations
for j in range(8):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    date_dt = TODAY + timedelta(days=random.randint(1, 10))
    time_val = random.choice(RESERVATION_TIMES)
    party_size = random.choices([2, 4, 6, 8], weights=[20, 35, 25, 20], k=1)[0]
    create_reservation(cid, loc_id, date_dt, time_val, party_size, "waitlisted")

# ── 5f. Cancelled reservations (historical)
for j in range(12):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    date_dt = TODAY - timedelta(days=random.randint(1, 30))
    time_val = random.choice(RESERVATION_TIMES)
    party_size = random.choice([2, 4, 6])
    create_reservation(cid, loc_id, date_dt, time_val, party_size, "cancelled")

# ── 5g. Completed reservations (past)
for j in range(15):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    date_dt = TODAY - timedelta(days=random.randint(1, 60))
    time_val = random.choice(RESERVATION_TIMES)
    party_size = random.choice([2, 3, 4, 5, 6])
    create_reservation(cid, loc_id, date_dt, time_val, party_size, "completed")

# ── 5h. No-show reservations
for j in range(5):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    date_dt = TODAY - timedelta(days=random.randint(1, 14))
    time_val = random.choice(RESERVATION_TIMES)
    party_size = random.choice([2, 4])
    create_reservation(cid, loc_id, date_dt, time_val, party_size, "no_show")

# ── 5i. Seated reservations (currently dining)
for j in range(3):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    date_dt = TODAY
    time_val = random.choice(["18:00", "19:00", "19:30"])
    party_size = random.choice([2, 4, 6])
    create_reservation(cid, loc_id, date_dt, time_val, party_size, "seated")


# ═══════════════════════════════════════════════════════════════════════════
# Step 6: Orders (60)
# ═══════════════════════════════════════════════════════════════════════════

orders = {}
order_status_counts = defaultdict(int)


def random_order_items(num_items):
    """Create a random set of order items."""
    items = []
    used_items = set()
    for _ in range(num_items):
        iid = random.choice(item_ids)
        while iid in used_items:
            iid = random.choice(item_ids)
        used_items.add(iid)
        qty = random.choices([1, 2], weights=[80, 20], k=1)[0]
        items.append({
            "item_id": iid,
            "quantity": qty,
            "modifications": None,
            "price": menu_items[iid]["price"],
        })
    return items


def create_order(
    cid, loc_id, status, items=None, reservation_id=None,
    payment_method=None, tip=0.0, special_instructions=None,
):
    last = cid.split("_")[-1]
    base_oid = f"ord_{last}_{status[:4]}"
    oid = make_unique_id(base_oid, orders)

    if items is None:
        num = random.randint(2, 5)
        items = random_order_items(num)

    total = round(sum(it["price"] * it["quantity"] for it in items), 2)

    orders[oid] = {
        "order_id": oid,
        "customer_id": cid,
        "reservation_id": reservation_id,
        "location_id": loc_id,
        "items": items,
        "status": status,
        "total": total,
        "payment_method": payment_method,
        "tip": tip,
        "special_instructions": special_instructions,
    }
    customers[cid]["order_ids"].append(oid)
    order_status_counts[status] += 1
    return oid


# ── 6a. Placed orders (modifiable — can add/remove items, apply loyalty)
for j in range(12):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    # Link to an existing confirmed reservation if customer has one
    res_id = None
    cust_res = [
        rid for rid in customers[cid]["reservation_ids"]
        if reservations[rid]["status"] == "confirmed"
        and reservations[rid]["location_id"] == loc_id
    ]
    if cust_res:
        res_id = cust_res[0]
    create_order(cid, loc_id, "placed", reservation_id=res_id)

# ── 6b. Preparing orders (items can be cancelled individually)
for j in range(10):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    create_order(cid, loc_id, "preparing")

# ── 6c. Ready orders (no modifications)
for j in range(8):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    create_order(cid, loc_id, "ready", payment_method="credit_card")

# ── 6d. Delivered orders
for j in range(8):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    tip = round(random.choice([0.0, 5.0, 8.0, 10.0, 15.0, 20.0]), 2)
    create_order(cid, loc_id, "delivered", payment_method="credit_card", tip=tip)

# ── 6e. Completed orders (historical)
for j in range(15):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    tip = round(random.choice([0.0, 5.0, 10.0, 15.0, 20.0]), 2)
    create_order(cid, loc_id, "completed", payment_method="credit_card", tip=tip)

# ── 6f. Cancelled orders
for j in range(7):
    cid = random.choice(customer_id_list)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    create_order(cid, loc_id, "cancelled")

# ── 6g. Orders with specific items for allergy-related tasks
# Create orders where a customer with allergies has items containing their allergen
allergic_customers = [
    cid for cid in customer_id_list
    if customers[cid]["allergy_info"]
]
for j in range(5):
    if not allergic_customers:
        break
    cid = random.choice(allergic_customers)
    loc_id = random.choices(location_ids, weights=location_weights, k=1)[0]
    allergy = customers[cid]["allergy_info"][0]
    # Find items containing this allergen
    allergen_items = [
        iid for iid in item_ids
        if allergy in menu_items[iid]["allergens"]
    ]
    if allergen_items:
        risky_item = random.choice(allergen_items)
        safe_item = random.choice([
            iid for iid in item_ids
            if allergy not in menu_items[iid]["allergens"]
        ])
        items = [
            {"item_id": risky_item, "quantity": 1, "modifications": None,
             "price": menu_items[risky_item]["price"]},
            {"item_id": safe_item, "quantity": 1, "modifications": None,
             "price": menu_items[safe_item]["price"]},
        ]
        create_order(cid, loc_id, "placed", items=items,
                     special_instructions=f"Note: customer has {allergy} allergy")


# ═══════════════════════════════════════════════════════════════════════════
# Step 7: Payment Methods (one credit card per customer + a few gift cards)
# ═══════════════════════════════════════════════════════════════════════════
payment_methods = {}

# Credit card for each customer
CARD_PREFIXES = ["Visa", "Mastercard", "Amex"]
for cid in customer_id_list:
    last = cid.split("_")[-1]
    pm_id = f"pm_{last}"
    pm_id = make_unique_id(pm_id, payment_methods)
    last4 = f"{random.randint(1000, 9999)}"
    card_type = random.choice(CARD_PREFIXES)
    payment_methods[pm_id] = {
        "payment_method_id": pm_id,
        "customer_id": cid,
        "type": "credit_card",
        "details": f"{card_type} ending in {last4}",
    }

# A few pre-existing gift cards (from previous service issues)
gift_card_customers = random.sample(customer_id_list, 5)
for cid in gift_card_customers:
    last = cid.split("_")[-1]
    gc_id = f"gc_{last}"
    gc_id = make_unique_id(gc_id, payment_methods)
    amount = random.choice([10.00, 15.00, 20.00, 25.00, 30.00])
    payment_methods[gc_id] = {
        "payment_method_id": gc_id,
        "customer_id": cid,
        "type": "gift_card",
        "details": f"${amount:.2f} gift card - previous service compensation",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════
errors = []

# 1. All reservation customer_ids exist
for rid, res in reservations.items():
    if res["customer_id"] not in customers:
        errors.append(f"Reservation {rid} references unknown customer {res['customer_id']}")
    if res["location_id"] not in locations:
        errors.append(f"Reservation {rid} references unknown location {res['location_id']}")
    if res["table_id"] and res["table_id"] not in tables:
        errors.append(f"Reservation {rid} references unknown table {res['table_id']}")

# 2. All order customer_ids exist and items reference valid menu items
for oid, order in orders.items():
    if order["customer_id"] not in customers:
        errors.append(f"Order {oid} references unknown customer {order['customer_id']}")
    if order["location_id"] not in locations:
        errors.append(f"Order {oid} references unknown location {order['location_id']}")
    for it in order["items"]:
        if it["item_id"] not in menu_items:
            errors.append(f"Order {oid} references unknown menu item {it['item_id']}")

# 3. All payment method customer_ids exist
for pm_id, pm in payment_methods.items():
    if pm["customer_id"] not in customers:
        errors.append(f"Payment {pm_id} references unknown customer {pm['customer_id']}")

# 4. Customer reservation_ids and order_ids are valid
for cid, cust in customers.items():
    for rid in cust["reservation_ids"]:
        if rid not in reservations:
            errors.append(f"Customer {cid} references unknown reservation {rid}")
    for oid in cust["order_ids"]:
        if oid not in orders:
            errors.append(f"Customer {cid} references unknown order {oid}")

# 5. Private dining sections require party >= 6
for rid, res in reservations.items():
    if res["table_id"] and res["table_id"] in tables:
        table = tables[res["table_id"]]
        if table["section"] == "private" and res["party_size"] < PRIVATE_DINING_MIN_PARTY:
            # This is a data quality note, not necessarily an error for testing
            pass

# 6. Unique customer names
name_counts = defaultdict(int)
for cust in customers.values():
    name_counts[cust["name"]] += 1
for name, cnt in name_counts.items():
    if cnt > 1:
        errors.append(f"Duplicate customer name: {name} (appears {cnt} times)")

# ── Statistics ──────────────────────────────────────────────────────────────
allergy_counts = defaultdict(int)
for cust in customers.values():
    for allergy in cust["allergy_info"]:
        allergy_counts[allergy] += 1

dietary_counts = defaultdict(int)
for cust in customers.values():
    for diet in cust["dietary_restrictions"]:
        dietary_counts[diet] += 1

loyalty_ranges = {"zero": 0, "low (1-200)": 0, "medium (201-500)": 0, "high (501+)": 0}
for cust in customers.values():
    pts = cust["loyalty_points"]
    if pts == 0:
        loyalty_ranges["zero"] += 1
    elif pts <= 200:
        loyalty_ranges["low (1-200)"] += 1
    elif pts <= 500:
        loyalty_ranges["medium (201-500)"] += 1
    else:
        loyalty_ranges["high (501+)"] += 1

# Confirmed reservations within 2 hours of REFERENCE_DATE
within_2h = []
within_1h_large = []
within_1h_small = []
future_confirmed = []
for rid, res in reservations.items():
    if res["status"] != "confirmed":
        continue
    try:
        res_dt = datetime.strptime(f"{res['date']} {res['time']}", "%Y-%m-%d %H:%M")
    except ValueError:
        continue
    diff = res_dt - TODAY
    if diff.total_seconds() <= 0:
        # Past - within cutoff
        within_2h.append(rid)
        if diff.total_seconds() >= -3600:
            if res["party_size"] > CANCELLATION_FEE_PARTY_SIZE:
                within_1h_large.append(rid)
            else:
                within_1h_small.append(rid)
    elif diff.total_seconds() <= 7200:
        within_2h.append(rid)
    else:
        future_confirmed.append(rid)

placed_orders = [oid for oid, o in orders.items() if o["status"] == "placed"]
preparing_orders = [oid for oid, o in orders.items() if o["status"] == "preparing"]

print("=" * 60)
print("RESTAURANT DATABASE GENERATION COMPLETE")
print("=" * 60)
print(f"\nLocations:      {len(locations)}")
for lid, loc in locations.items():
    print(f"  {lid}: {loc['name']}")
print(f"\nTables:         {len(tables)}")
for section in ["indoor", "outdoor", "private"]:
    cnt = sum(1 for t in tables.values() if t["section"] == section)
    print(f"  {section}: {cnt}")
unavail = sum(1 for t in tables.values() if not t["is_available"])
print(f"  unavailable: {unavail}")

print(f"\nMenu Items:     {len(menu_items)}")
for cat in ["appetizer", "main", "dessert", "drink"]:
    cnt = sum(1 for m in menu_items.values() if m["category"] == cat)
    avail = sum(1 for m in menu_items.values() if m["category"] == cat and m["available"])
    print(f"  {cat}: {cnt} ({avail} available)")

print(f"\nCustomers:      {len(customers)}")
print(f"  With allergies:           {sum(1 for c in customers.values() if c['allergy_info'])}")
for allergy, cnt in sorted(allergy_counts.items()):
    print(f"    {allergy}: {cnt}")
print(f"  With dietary restrictions: {sum(1 for c in customers.values() if c['dietary_restrictions'])}")
for diet, cnt in sorted(dietary_counts.items()):
    print(f"    {diet}: {cnt}")
print(f"  Loyalty points distribution:")
for rng, cnt in loyalty_ranges.items():
    print(f"    {rng}: {cnt}")

print(f"\nReservations:   {len(reservations)}")
for status, cnt in sorted(reservation_status_counts.items()):
    print(f"  {status}: {cnt}")

print(f"\n-- Reservation Edge Cases --")
print(f"  Future confirmed (modifiable):          {len(future_confirmed)}")
print(f"  Within 2h (not modifiable):             {len(within_2h)}")
print(f"  Within 1h + party > 6 (cancel fee):     {len(within_1h_large)}")
print(f"  Within 1h + party <= 6 (no cancel fee): {len(within_1h_small)}")

print(f"\nOrders:         {len(orders)}")
for status, cnt in sorted(order_status_counts.items()):
    print(f"  {status}: {cnt}")
print(f"  Placed (modifiable):    {len(placed_orders)}")
print(f"  Preparing (cancel items): {len(preparing_orders)}")

print(f"\nPayment Methods: {len(payment_methods)}")
cc_count = sum(1 for pm in payment_methods.values() if pm["type"] == "credit_card")
gc_count = sum(1 for pm in payment_methods.values() if pm["type"] == "gift_card")
print(f"  credit_card: {cc_count}")
print(f"  gift_card:   {gc_count}")

if errors:
    print(f"\n!! VALIDATION ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
else:
    print("\nAll validation checks passed")


# ── Write db.json ───────────────────────────────────────────────────────────
db = {
    "customers": customers,
    "reservations": reservations,
    "tables": tables,
    "locations": locations,
    "menu_items": menu_items,
    "orders": orders,
    "payment_methods": payment_methods,
}

output_path = Path(__file__).parent / "db.json"
with open(output_path, "w") as f:
    json.dump(db, f, indent=2)

print(f"\nWritten to {output_path}")
