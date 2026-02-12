#!/usr/bin/env python3
"""Generate car rental database.

Standalone script (stdlib only). Deterministic via random.seed(42).

Usage:
    python generate_db.py
"""
import json
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)
HERE = Path(__file__).parent

# Reference date: October 15, 2025
TODAY = datetime(2025, 10, 15)

# ── Name pools ──────────────────────────────────────────────────

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen",
    "Charles", "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony",
    "Margaret", "Mark", "Sandra", "Donald", "Ashley", "Steven", "Kimberly",
    "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle", "Kenneth",
    "Carol", "Kevin", "Amanda", "Brian", "Dorothy", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca",
    "Jason", "Sharon", "Jeffrey", "Laura", "Ryan", "Cynthia",
    "Jacob", "Kathleen", "Gary", "Amy", "Nicholas", "Angela",
    "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole",
    "Brandon", "Helen", "Benjamin", "Samantha", "Samuel", "Katherine",
    "Raymond", "Christine", "Gregory", "Debra", "Frank", "Rachel",
    "Alexander", "Carolyn", "Patrick", "Janet", "Jack", "Catherine",
    "Dennis", "Maria", "Jerry", "Heather", "Tyler", "Diane",
    "Aaron", "Ruth", "Jose", "Julie", "Adam", "Olivia",
    "Nathan", "Joyce", "Henry", "Virginia", "Peter", "Victoria",
    "Zachary", "Kelly", "Douglas", "Lauren", "Harold", "Christina",
    "Carl", "Joan", "Arthur", "Evelyn", "Gerald", "Judith",
    "Roger", "Megan", "Keith", "Andrea", "Jeremy", "Cheryl",
    "Terry", "Hannah", "Lawrence", "Jacqueline", "Sean", "Martha",
    "Christian", "Gloria", "Albert", "Teresa", "Joe", "Ann",
    "Ethan", "Sara", "Austin", "Madison", "Jesse", "Frances",
    "Willie", "Kathryn", "Billy", "Janice", "Bryan", "Jean",
    "Bruce", "Abigail", "Jordan", "Alice", "Ralph", "Judy",
    "Roy", "Sophia", "Noah", "Grace",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz",
    "Parker", "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris",
    "Morales", "Murphy", "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan",
    "Cooper", "Peterson", "Bailey", "Reed", "Kelly", "Howard", "Ramos",
    "Kim", "Cox", "Ward", "Richardson", "Watson", "Brooks", "Chavez",
    "Wood", "James", "Bennett", "Gray", "Mendoza", "Ruiz", "Hughes",
    "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers", "Long",
    "Ross", "Foster", "Jimenez", "Powell",
]

EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "proton.me", "aol.com", "mail.com",
]

# ── Vehicle catalog ──────────────────────────────────────────────

VEHICLE_CATALOG = {
    "economy": [
        ("Toyota", "Corolla", 2024),
        ("Honda", "Civic", 2024),
        ("Nissan", "Sentra", 2023),
        ("Hyundai", "Elantra", 2024),
        ("Kia", "Forte", 2023),
    ],
    "compact": [
        ("Volkswagen", "Jetta", 2024),
        ("Mazda", "Mazda3", 2024),
        ("Subaru", "Impreza", 2023),
        ("Toyota", "Camry", 2024),
        ("Honda", "Accord", 2023),
    ],
    "midsize": [
        ("Ford", "Fusion", 2024),
        ("Chevrolet", "Malibu", 2024),
        ("Hyundai", "Sonata", 2023),
        ("Nissan", "Altima", 2024),
        ("Kia", "K5", 2023),
    ],
    "suv": [
        ("Toyota", "RAV4", 2024),
        ("Honda", "CR-V", 2024),
        ("Ford", "Explorer", 2024),
        ("Chevrolet", "Equinox", 2023),
        ("Jeep", "Cherokee", 2024),
    ],
    "luxury": [
        ("BMW", "5 Series", 2024),
        ("Mercedes-Benz", "E-Class", 2024),
        ("Audi", "A6", 2024),
        ("Lexus", "ES", 2024),
        ("Tesla", "Model S", 2024),
    ],
    "van": [
        ("Chrysler", "Pacifica", 2024),
        ("Honda", "Odyssey", 2024),
        ("Toyota", "Sienna", 2023),
        ("Kia", "Carnival", 2024),
    ],
}

FUEL_TYPES_BY_CATEGORY = {
    "economy": ["gasoline", "gasoline", "gasoline", "hybrid"],
    "compact": ["gasoline", "gasoline", "gasoline", "hybrid"],
    "midsize": ["gasoline", "gasoline", "hybrid", "hybrid"],
    "suv": ["gasoline", "gasoline", "gasoline", "diesel", "hybrid"],
    "luxury": ["gasoline", "gasoline", "gasoline", "electric", "hybrid"],
    "van": ["gasoline", "gasoline", "hybrid"],
}

VEHICLE_FEATURES = [
    "gps", "bluetooth", "backup_camera", "cruise_control",
    "heated_seats", "sunroof", "apple_carplay", "android_auto",
    "lane_assist", "blind_spot_monitor",
]

# ── Locations ────────────────────────────────────────────────────

LOCATIONS_DATA = [
    {
        "location_id": "downtown",
        "name": "Downtown Office",
        "address": "123 Main St, Springfield, IL 62701",
        "airport_code": None,
        "hours": "Mon-Fri 7:00 AM - 9:00 PM, Sat-Sun 8:00 AM - 6:00 PM",
        "phone": "555-0101",
    },
    {
        "location_id": "airport",
        "name": "Springfield Airport",
        "address": "1200 Airport Dr, Springfield, IL 62707",
        "airport_code": "SPI",
        "hours": "Daily 5:00 AM - 11:00 PM",
        "phone": "555-0102",
    },
    {
        "location_id": "westside",
        "name": "Westside Branch",
        "address": "456 Oak Ave, Springfield, IL 62704",
        "airport_code": None,
        "hours": "Mon-Sat 8:00 AM - 7:00 PM, Sun Closed",
        "phone": "555-0103",
    },
    {
        "location_id": "northpark",
        "name": "North Park Location",
        "address": "789 Park Blvd, Springfield, IL 62702",
        "airport_code": None,
        "hours": "Mon-Fri 8:00 AM - 8:00 PM, Sat 9:00 AM - 5:00 PM, Sun Closed",
        "phone": "555-0104",
    },
    {
        "location_id": "east_mall",
        "name": "East Mall Office",
        "address": "321 Mall Rd, Springfield, IL 62703",
        "airport_code": None,
        "hours": "Mon-Sat 9:00 AM - 8:00 PM, Sun 10:00 AM - 5:00 PM",
        "phone": "555-0105",
    },
    {
        "location_id": "lakeside",
        "name": "Lakeside Terminal",
        "address": "555 Lakeshore Dr, Springfield, IL 62706",
        "airport_code": None,
        "hours": "Mon-Fri 7:00 AM - 8:00 PM, Sat-Sun 8:00 AM - 6:00 PM",
        "phone": "555-0106",
    },
    {
        "location_id": "capital_city_airport",
        "name": "Capital City Airport",
        "address": "900 Terminal Way, Capital City, IL 62708",
        "airport_code": "CCA",
        "hours": "Daily 6:00 AM - 12:00 AM",
        "phone": "555-0107",
    },
    {
        "location_id": "university",
        "name": "University District",
        "address": "200 College St, Springfield, IL 62705",
        "airport_code": None,
        "hours": "Mon-Fri 8:00 AM - 7:00 PM, Sat 9:00 AM - 4:00 PM, Sun Closed",
        "phone": "555-0108",
    },
]

# Location weights for vehicle distribution
LOCATION_WEIGHTS = {
    "airport": 0.25,
    "downtown": 0.20,
    "capital_city_airport": 0.15,
    "westside": 0.10,
    "northpark": 0.08,
    "east_mall": 0.08,
    "lakeside": 0.07,
    "university": 0.07,
}

# Category distribution weights
CATEGORY_WEIGHTS = {
    "economy": 0.25,
    "compact": 0.22,
    "midsize": 0.20,
    "suv": 0.18,
    "luxury": 0.08,
    "van": 0.07,
}

# ── Extras ───────────────────────────────────────────────────────

EXTRAS_DATA = [
    {"extra_id": "gps", "name": "GPS Navigation", "daily_rate": 12.0},
    {"extra_id": "child_seat", "name": "Child Seat", "daily_rate": 10.0},
    {"extra_id": "additional_driver", "name": "Additional Driver", "daily_rate": 15.0},
    {"extra_id": "roadside_pkg", "name": "Roadside Assistance Package", "daily_rate": 8.0},
    {"extra_id": "roof_rack", "name": "Roof Rack", "daily_rate": 7.0},
    {"extra_id": "ski_rack", "name": "Ski Rack", "daily_rate": 7.0},
    {"extra_id": "wifi_hotspot", "name": "WiFi Hotspot", "daily_rate": 10.0},
]


# ── Helpers ──────────────────────────────────────────────────────

def make_unique_id(base, existing):
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


def random_phone():
    return f"555-{random.randint(1000, 9999)}"


def random_license_plate():
    letters = "".join(random.choices(string.ascii_uppercase, k=3))
    numbers = "".join(random.choices(string.digits, k=4))
    return f"{letters}-{numbers}"


def random_license_number():
    return f"DL-{random.randint(100000, 999999)}"


def random_card_last_four():
    return f"{random.randint(1000, 9999)}"


# ── Generation Functions ─────────────────────────────────────────

def generate_locations():
    locations = {}
    for loc in LOCATIONS_DATA:
        locations[loc["location_id"]] = loc
    return locations


def generate_extras():
    extras = {}
    for ext in EXTRAS_DATA:
        extras[ext["extra_id"]] = ext
    return extras


def generate_vehicles(locations):
    """Generate ~200 vehicles distributed across locations and categories."""
    vehicles = {}
    target_count = 200

    # Distribute by category and location
    location_ids = list(locations.keys())
    loc_weights = [LOCATION_WEIGHTS[lid] for lid in location_ids]

    for category, cat_weight in CATEGORY_WEIGHTS.items():
        n_vehicles = max(2, round(target_count * cat_weight))
        catalog = VEHICLE_CATALOG[category]
        fuel_options = FUEL_TYPES_BY_CATEGORY[category]

        for i in range(n_vehicles):
            make, model, year = random.choice(catalog)
            loc_id = random.choices(location_ids, weights=loc_weights, k=1)[0]

            # Build vehicle ID: lowercase make_model_locationshort
            model_short = model.lower().replace(" ", "_").replace("-", "_")
            base_id = f"{make.lower()}_{model_short}_{loc_id}"
            vid = make_unique_id(base_id, vehicles)

            fuel = random.choice(fuel_options)

            # Features: 3-6 random features
            n_features = random.randint(3, 6)
            features = random.sample(VEHICLE_FEATURES, n_features)

            mileage = random.randint(5000, 80000)

            # Most vehicles are available, some rented/maintenance
            status_roll = random.random()
            if status_roll < 0.65:
                status = "available"
            elif status_roll < 0.85:
                status = "rented"
            elif status_roll < 0.95:
                status = "reserved"
            else:
                status = "maintenance"

            vehicles[vid] = {
                "vehicle_id": vid,
                "make": make,
                "model": model,
                "year": year,
                "category": category,
                "license_plate": random_license_plate(),
                "mileage": mileage,
                "status": status,
                "location_id": loc_id,
                "fuel_type": fuel,
                "features": features,
            }

    return vehicles


def generate_customers(num_customers=150):
    """Generate 150 customers with varied loyalty tiers."""
    customers = {}
    used_names = set()

    # Shuffle and pair names
    first_pool = list(FIRST_NAMES)
    last_pool = list(LAST_NAMES)
    random.shuffle(first_pool)
    random.shuffle(last_pool)

    for i in range(num_customers):
        first = first_pool[i % len(first_pool)]
        last = last_pool[i % len(last_pool)]

        full_name = f"{first} {last}"
        if full_name in used_names:
            # Skip duplicate names to avoid ambiguity
            continue
        used_names.add(full_name)

        cid = f"{first.lower()}_{last.lower()}"
        if cid in customers:
            continue

        # Age: 21-70
        age = random.randint(21, 70)
        dob = TODAY - timedelta(days=age * 365 + random.randint(0, 364))
        dob_str = dob.strftime("%Y-%m-%d")

        # License expiry: most valid, some expired
        if random.random() < 0.05:
            # Expired license
            license_exp = TODAY - timedelta(days=random.randint(1, 180))
        else:
            license_exp = TODAY + timedelta(days=random.randint(90, 1800))
        license_exp_str = license_exp.strftime("%Y-%m-%d")

        # Loyalty tier distribution
        tier_roll = random.random()
        if tier_roll < 0.50:
            loyalty_tier = "none"
            loyalty_points = random.randint(0, 500)
        elif tier_roll < 0.75:
            loyalty_tier = "silver"
            loyalty_points = random.randint(200, 2000)
        elif tier_roll < 0.92:
            loyalty_tier = "gold"
            loyalty_points = random.randint(500, 5000)
        else:
            loyalty_tier = "platinum"
            loyalty_points = random.randint(1000, 10000)

        email_domain = random.choice(EMAIL_DOMAINS)
        email = f"{first.lower()}.{last.lower()}@{email_domain}"

        # Payment methods: 1-2
        payment_methods = []
        n_cards = random.randint(1, 2)
        brands = ["Visa", "Mastercard", "American Express", "Discover"]
        for j in range(n_cards):
            pm_id = f"pm_{cid}_{j+1}"
            payment_methods.append({
                "payment_method_id": pm_id,
                "type": random.choice(["credit_card", "debit_card"]),
                "last_four": random_card_last_four(),
                "brand": random.choice(brands),
            })

        customers[cid] = {
            "customer_id": cid,
            "name": full_name,
            "email": email,
            "phone": random_phone(),
            "driver_license_number": random_license_number(),
            "license_expiry": license_exp_str,
            "dob": dob_str,
            "loyalty_tier": loyalty_tier,
            "loyalty_points": loyalty_points,
            "reservations": [],
            "payment_methods": payment_methods,
        }

    return customers


def generate_reservations_and_agreements(customers, vehicles, locations, extras):
    """Generate reservations, rental agreements, and invoices."""
    reservations = {}
    rental_agreements = {}
    invoices = {}

    customer_list = list(customers.values())
    location_ids = list(locations.keys())
    extra_ids = list(extras.keys())
    categories = ["economy", "compact", "midsize", "suv", "luxury", "van"]

    base_rates = {
        "economy": 35.0, "compact": 45.0, "midsize": 55.0,
        "suv": 75.0, "luxury": 120.0, "van": 85.0,
    }

    loyalty_discounts = {
        "none": 0.0, "silver": 0.10, "gold": 0.15, "platinum": 0.20,
    }

    # ── Phase A: Completed reservations (historical) ──
    n_completed = 180
    for _ in range(n_completed):
        cust = random.choice(customer_list)
        cid = cust["customer_id"]
        last = cid.split("_")[-1]

        category = random.choices(
            categories,
            weights=[0.25, 0.22, 0.20, 0.18, 0.08, 0.07],
            k=1,
        )[0]

        # Luxury age check
        dob = datetime.strptime(cust["dob"], "%Y-%m-%d")
        age = (TODAY - dob).days // 365
        if category == "luxury" and age < 25:
            category = "midsize"

        pickup_loc = random.choice(location_ids)
        dropoff_loc = (
            pickup_loc
            if random.random() < 0.80
            else random.choice(location_ids)
        )

        # Past dates: 1-180 days ago
        days_ago = random.randint(7, 180)
        pickup_dt = TODAY - timedelta(days=days_ago)
        rental_days = random.randint(1, 14)
        dropoff_dt = pickup_dt + timedelta(days=rental_days)

        pickup_hour = random.randint(7, 18)
        dropoff_hour = random.randint(7, 18)
        pickup_str = pickup_dt.strftime(f"%Y-%m-%d {pickup_hour:02d}:00")
        dropoff_str = dropoff_dt.strftime(f"%Y-%m-%d {dropoff_hour:02d}:00")

        # Insurance
        ins_roll = random.random()
        if ins_roll < 0.30:
            insurance = "none"
        elif ins_roll < 0.70:
            insurance = "basic"
        else:
            insurance = "premium"

        # Extras
        n_extras = random.choices([0, 1, 2, 3], weights=[0.4, 0.3, 0.2, 0.1], k=1)[0]
        chosen_extras = random.sample(extra_ids, min(n_extras, len(extra_ids)))

        # Find a matching vehicle (any status is fine for completed)
        matching = [
            v for v in vehicles.values()
            if v["category"] == category and v["location_id"] == pickup_loc
        ]
        if not matching:
            matching = [v for v in vehicles.values() if v["category"] == category]
        if not matching:
            continue
        vehicle = random.choice(matching)

        # Pricing
        discount = loyalty_discounts.get(cust["loyalty_tier"], 0.0)
        daily = round(base_rates[category] * (1 - discount), 2)
        rental_cost = daily * rental_days
        ins_cost = (15.0 if insurance == "basic" else 30.0 if insurance == "premium" else 0.0) * rental_days
        extras_cost = sum(extras[eid]["daily_rate"] * rental_days for eid in chosen_extras)
        one_way = 75.0 if pickup_loc != dropoff_loc else 0.0
        subtotal = rental_cost + ins_cost + extras_cost + one_way
        total_estimate = round(subtotal, 2)

        # Create reservation
        date_str = pickup_dt.strftime("%Y%m%d")
        res_base = f"res_{last}_{date_str}"
        res_id = make_unique_id(res_base, reservations)

        reservations[res_id] = {
            "reservation_id": res_id,
            "customer_id": cid,
            "vehicle_category": category,
            "pickup_location_id": pickup_loc,
            "dropoff_location_id": dropoff_loc,
            "pickup_datetime": pickup_str,
            "dropoff_datetime": dropoff_str,
            "vehicle_id": vehicle["vehicle_id"],
            "status": "completed",
            "insurance_type": insurance,
            "extras": chosen_extras,
            "daily_rate": daily,
            "total_estimate": total_estimate,
        }
        customers[cid]["reservations"].append(res_id)

        # Create rental agreement
        agr_base = f"agr_{last}_{date_str}"
        agr_id = make_unique_id(agr_base, rental_agreements)

        fuel_out = round(random.uniform(0.85, 1.0), 2)
        fuel_in = round(random.uniform(0.3, 1.0), 2)
        mileage_out = vehicle["mileage"] - random.randint(100, 5000)
        mileage_in = mileage_out + random.randint(50, 2000)

        # Damage on ~5% of completed rentals
        damage = None
        damage_cost = 0.0
        if random.random() < 0.05:
            damage_descriptions = [
                "Minor scratch on front bumper",
                "Small dent on driver side door",
                "Windshield chip",
                "Scratch on rear fender",
                "Curb rash on front right wheel",
            ]
            damage = random.choice(damage_descriptions)
            damage_cost = round(random.uniform(150, 800), 2)

        # Late fee on ~10% of completed rentals
        late_fee = 0.0
        if random.random() < 0.10:
            late_fee = daily  # one extra day

        # Fuel refill cost
        fuel_cost = 0.0
        if fuel_in < fuel_out - 0.05:
            gallons = round((fuel_out - fuel_in) * 15, 1)  # ~15 gallon tank
            fuel_cost = round(gallons * 8.0, 2)

        final_subtotal = subtotal + damage_cost + late_fee + fuel_cost
        taxes = round(final_subtotal * 0.12, 2)
        final_total = round(final_subtotal + taxes, 2)

        rental_agreements[agr_id] = {
            "agreement_id": agr_id,
            "reservation_id": res_id,
            "customer_id": cid,
            "vehicle_id": vehicle["vehicle_id"],
            "actual_pickup": pickup_str,
            "actual_dropoff": dropoff_str,
            "fuel_level_out": fuel_out,
            "fuel_level_in": fuel_in,
            "mileage_out": mileage_out,
            "mileage_in": mileage_in,
            "damage_report": damage,
            "final_total": final_total,
        }

        # Create invoice
        inv_base = f"inv_{last}_{date_str}"
        inv_id = make_unique_id(inv_base, invoices)

        line_items = [
            {"description": f"{category.title()} rental - {rental_days} days", "amount": rental_cost, "category": "rental"},
        ]
        if ins_cost > 0:
            line_items.append({"description": f"{insurance.title()} insurance - {rental_days} days", "amount": ins_cost, "category": "insurance"})
        for eid in chosen_extras:
            line_items.append({"description": f"{extras[eid]['name']} - {rental_days} days", "amount": extras[eid]["daily_rate"] * rental_days, "category": "extra"})
        if one_way > 0:
            line_items.append({"description": "One-way surcharge", "amount": one_way, "category": "one_way"})
        if fuel_cost > 0:
            line_items.append({"description": "Fuel refill charge", "amount": fuel_cost, "category": "fuel"})
        if late_fee > 0:
            line_items.append({"description": "Late return fee (1 extra day)", "amount": late_fee, "category": "late_fee"})
        if damage_cost > 0:
            line_items.append({"description": f"Damage: {damage}", "amount": damage_cost, "category": "damage"})

        # Status: most paid, some disputed
        inv_status = "paid" if random.random() < 0.92 else "disputed"

        pm_id = cust["payment_methods"][0]["payment_method_id"] if cust["payment_methods"] else None

        invoices[inv_id] = {
            "invoice_id": inv_id,
            "customer_id": cid,
            "agreement_id": agr_id,
            "line_items": line_items,
            "subtotal": round(final_subtotal, 2),
            "taxes": taxes,
            "total": final_total,
            "status": inv_status,
            "payment_method_id": pm_id,
        }

    # ── Phase B: Active rentals (ongoing) ──
    n_active = 25
    # Find vehicles currently marked as "rented"
    rented_vehicles = [v for v in vehicles.values() if v["status"] == "rented"]
    active_customers = random.sample(customer_list, min(n_active, len(customer_list)))

    for idx, cust in enumerate(active_customers[:n_active]):
        if idx >= len(rented_vehicles):
            break

        cid = cust["customer_id"]
        last = cid.split("_")[-1]
        vehicle = rented_vehicles[idx]
        category = vehicle["category"]

        # Luxury age check
        dob = datetime.strptime(cust["dob"], "%Y-%m-%d")
        age = (TODAY - dob).days // 365
        if category == "luxury" and age < 25:
            continue

        pickup_loc = vehicle["location_id"]
        dropoff_loc = pickup_loc if random.random() < 0.80 else random.choice(location_ids)

        # Pickup: 1-7 days ago
        days_ago = random.randint(1, 7)
        pickup_dt = TODAY - timedelta(days=days_ago)
        rental_days = random.randint(3, 10)
        dropoff_dt = pickup_dt + timedelta(days=rental_days)

        pickup_hour = random.randint(7, 18)
        dropoff_hour = random.randint(7, 18)
        pickup_str = pickup_dt.strftime(f"%Y-%m-%d {pickup_hour:02d}:00")
        dropoff_str = dropoff_dt.strftime(f"%Y-%m-%d {dropoff_hour:02d}:00")

        ins_roll = random.random()
        insurance = "none" if ins_roll < 0.30 else "basic" if ins_roll < 0.70 else "premium"

        n_extras = random.choices([0, 1, 2], weights=[0.4, 0.35, 0.25], k=1)[0]
        chosen_extras = random.sample(extra_ids, min(n_extras, len(extra_ids)))

        discount = loyalty_discounts.get(cust["loyalty_tier"], 0.0)
        daily = round(base_rates[category] * (1 - discount), 2)
        rental_cost = daily * rental_days
        ins_cost = (15.0 if insurance == "basic" else 30.0 if insurance == "premium" else 0.0) * rental_days
        extras_cost = sum(extras[eid]["daily_rate"] * rental_days for eid in chosen_extras)
        one_way = 75.0 if pickup_loc != dropoff_loc else 0.0
        total_estimate = round(rental_cost + ins_cost + extras_cost + one_way, 2)

        date_str = pickup_dt.strftime("%Y%m%d")
        res_base = f"res_{last}_{date_str}"
        res_id = make_unique_id(res_base, reservations)

        reservations[res_id] = {
            "reservation_id": res_id,
            "customer_id": cid,
            "vehicle_category": category,
            "pickup_location_id": pickup_loc,
            "dropoff_location_id": dropoff_loc,
            "pickup_datetime": pickup_str,
            "dropoff_datetime": dropoff_str,
            "vehicle_id": vehicle["vehicle_id"],
            "status": "active",
            "insurance_type": insurance,
            "extras": chosen_extras,
            "daily_rate": daily,
            "total_estimate": total_estimate,
        }
        customers[cid]["reservations"].append(res_id)

        agr_base = f"agr_{last}_{date_str}"
        agr_id = make_unique_id(agr_base, rental_agreements)

        fuel_out = round(random.uniform(0.85, 1.0), 2)
        mileage_out = vehicle["mileage"]

        rental_agreements[agr_id] = {
            "agreement_id": agr_id,
            "reservation_id": res_id,
            "customer_id": cid,
            "vehicle_id": vehicle["vehicle_id"],
            "actual_pickup": pickup_str,
            "actual_dropoff": None,
            "fuel_level_out": fuel_out,
            "fuel_level_in": None,
            "mileage_out": mileage_out,
            "mileage_in": None,
            "damage_report": None,
            "final_total": None,
        }

    # ── Phase C: Confirmed (future) reservations ──
    n_confirmed = 50
    for _ in range(n_confirmed):
        cust = random.choice(customer_list)
        cid = cust["customer_id"]
        last = cid.split("_")[-1]

        category = random.choices(
            categories,
            weights=[0.25, 0.22, 0.20, 0.18, 0.08, 0.07],
            k=1,
        )[0]

        dob = datetime.strptime(cust["dob"], "%Y-%m-%d")
        age = (TODAY - dob).days // 365
        if category == "luxury" and age < 25:
            category = "midsize"

        pickup_loc = random.choice(location_ids)
        dropoff_loc = pickup_loc if random.random() < 0.80 else random.choice(location_ids)

        # Future: 1-60 days from now
        days_ahead = random.randint(1, 60)
        pickup_dt = TODAY + timedelta(days=days_ahead)
        rental_days = random.randint(1, 14)
        dropoff_dt = pickup_dt + timedelta(days=rental_days)

        pickup_hour = random.randint(7, 18)
        dropoff_hour = random.randint(7, 18)
        pickup_str = pickup_dt.strftime(f"%Y-%m-%d {pickup_hour:02d}:00")
        dropoff_str = dropoff_dt.strftime(f"%Y-%m-%d {dropoff_hour:02d}:00")

        ins_roll = random.random()
        insurance = "none" if ins_roll < 0.30 else "basic" if ins_roll < 0.70 else "premium"

        n_extras = random.choices([0, 1, 2, 3], weights=[0.35, 0.30, 0.25, 0.10], k=1)[0]
        chosen_extras = random.sample(extra_ids, min(n_extras, len(extra_ids)))

        # Find an available vehicle of this category at this location
        matching = [
            v for v in vehicles.values()
            if v["category"] == category
            and v["location_id"] == pickup_loc
            and v["status"] == "available"
        ]
        if not matching:
            matching = [
                v for v in vehicles.values()
                if v["category"] == category and v["status"] == "available"
            ]
        if not matching:
            continue
        vehicle = matching[0]

        discount = loyalty_discounts.get(cust["loyalty_tier"], 0.0)
        daily = round(base_rates[category] * (1 - discount), 2)
        rental_cost = daily * rental_days
        ins_cost = (15.0 if insurance == "basic" else 30.0 if insurance == "premium" else 0.0) * rental_days
        extras_cost = sum(extras[eid]["daily_rate"] * rental_days for eid in chosen_extras)
        one_way = 75.0 if pickup_loc != dropoff_loc else 0.0
        total_estimate = round(rental_cost + ins_cost + extras_cost + one_way, 2)

        date_str = pickup_dt.strftime("%Y%m%d")
        res_base = f"res_{last}_{date_str}"
        res_id = make_unique_id(res_base, reservations)

        reservations[res_id] = {
            "reservation_id": res_id,
            "customer_id": cid,
            "vehicle_category": category,
            "pickup_location_id": pickup_loc,
            "dropoff_location_id": dropoff_loc,
            "pickup_datetime": pickup_str,
            "dropoff_datetime": dropoff_str,
            "vehicle_id": vehicle["vehicle_id"],
            "status": "confirmed",
            "insurance_type": insurance,
            "extras": chosen_extras,
            "daily_rate": daily,
            "total_estimate": total_estimate,
        }
        customers[cid]["reservations"].append(res_id)

    # ── Phase D: Cancelled reservations ──
    n_cancelled = 20
    for _ in range(n_cancelled):
        cust = random.choice(customer_list)
        cid = cust["customer_id"]
        last = cid.split("_")[-1]

        category = random.choice(categories)

        dob = datetime.strptime(cust["dob"], "%Y-%m-%d")
        age = (TODAY - dob).days // 365
        if category == "luxury" and age < 25:
            category = "compact"

        pickup_loc = random.choice(location_ids)
        dropoff_loc = pickup_loc

        days_ago = random.randint(10, 90)
        pickup_dt = TODAY - timedelta(days=days_ago)
        rental_days = random.randint(1, 7)
        dropoff_dt = pickup_dt + timedelta(days=rental_days)

        pickup_str = pickup_dt.strftime("%Y-%m-%d 10:00")
        dropoff_str = dropoff_dt.strftime("%Y-%m-%d 10:00")

        discount = loyalty_discounts.get(cust["loyalty_tier"], 0.0)
        daily = round(base_rates[category] * (1 - discount), 2)

        date_str = pickup_dt.strftime("%Y%m%d")
        res_base = f"res_{last}_{date_str}"
        res_id = make_unique_id(res_base, reservations)

        reservations[res_id] = {
            "reservation_id": res_id,
            "customer_id": cid,
            "vehicle_category": category,
            "pickup_location_id": pickup_loc,
            "dropoff_location_id": dropoff_loc,
            "pickup_datetime": pickup_str,
            "dropoff_datetime": dropoff_str,
            "vehicle_id": None,
            "status": "cancelled",
            "insurance_type": "none",
            "extras": [],
            "daily_rate": daily,
            "total_estimate": round(daily * rental_days, 2),
        }
        customers[cid]["reservations"].append(res_id)

    # ── Phase E: No-show reservations ──
    n_noshow = 10
    for _ in range(n_noshow):
        cust = random.choice(customer_list)
        cid = cust["customer_id"]
        last = cid.split("_")[-1]

        category = random.choice(["economy", "compact", "midsize"])

        pickup_loc = random.choice(location_ids)

        days_ago = random.randint(3, 30)
        pickup_dt = TODAY - timedelta(days=days_ago)
        rental_days = random.randint(2, 5)
        dropoff_dt = pickup_dt + timedelta(days=rental_days)

        pickup_str = pickup_dt.strftime("%Y-%m-%d 09:00")
        dropoff_str = dropoff_dt.strftime("%Y-%m-%d 09:00")

        discount = loyalty_discounts.get(cust["loyalty_tier"], 0.0)
        daily = round(base_rates[category] * (1 - discount), 2)

        date_str = pickup_dt.strftime("%Y%m%d")
        res_base = f"res_{last}_{date_str}"
        res_id = make_unique_id(res_base, reservations)

        reservations[res_id] = {
            "reservation_id": res_id,
            "customer_id": cid,
            "vehicle_category": category,
            "pickup_location_id": pickup_loc,
            "dropoff_location_id": pickup_loc,
            "pickup_datetime": pickup_str,
            "dropoff_datetime": dropoff_str,
            "vehicle_id": None,
            "status": "no_show",
            "insurance_type": "none",
            "extras": [],
            "daily_rate": daily,
            "total_estimate": round(daily * rental_days, 2),
        }
        customers[cid]["reservations"].append(res_id)

    return reservations, rental_agreements, invoices


def generate():
    locations = generate_locations()
    extras = generate_extras()
    vehicles = generate_vehicles(locations)
    customers = generate_customers()
    reservations, rental_agreements, invoices = generate_reservations_and_agreements(
        customers, vehicles, locations, extras
    )

    db = {
        "customers": customers,
        "vehicles": vehicles,
        "locations": locations,
        "reservations": reservations,
        "rental_agreements": rental_agreements,
        "invoices": invoices,
        "extras": extras,
    }
    return db


if __name__ == "__main__":
    db = generate()
    with open(HERE / "db.json", "w") as f:
        json.dump(db, f, indent=2)

    # Print summary
    print("Car Rental Database Generated:")
    print(f"  Customers:         {len(db['customers'])}")
    print(f"  Vehicles:          {len(db['vehicles'])}")
    print(f"  Locations:         {len(db['locations'])}")
    print(f"  Reservations:      {len(db['reservations'])}")
    print(f"  Rental Agreements: {len(db['rental_agreements'])}")
    print(f"  Invoices:          {len(db['invoices'])}")
    print(f"  Extras:            {len(db['extras'])}")

    # Reservation status breakdown
    statuses = {}
    for r in db["reservations"].values():
        s = r["status"]
        statuses[s] = statuses.get(s, 0) + 1
    print(f"\n  Reservation statuses: {statuses}")

    # Loyalty tier breakdown
    tiers = {}
    for c in db["customers"].values():
        t = c["loyalty_tier"]
        tiers[t] = tiers.get(t, 0) + 1
    print(f"  Loyalty tiers: {tiers}")

    # Vehicle status breakdown
    vstatus = {}
    for v in db["vehicles"].values():
        s = v["status"]
        vstatus[s] = vstatus.get(s, 0) + 1
    print(f"  Vehicle statuses: {vstatus}")

    # Invoice status breakdown
    istatus = {}
    for inv in db["invoices"].values():
        s = inv["status"]
        istatus[s] = istatus.get(s, 0) + 1
    print(f"  Invoice statuses: {istatus}")
