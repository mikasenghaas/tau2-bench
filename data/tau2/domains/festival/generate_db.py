#!/usr/bin/env python3
"""Generate festival database (db.json).

Standalone script (stdlib only). Deterministic via random.seed(42).

Usage:
    python generate_db.py
"""

import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

# ── Reference date ──────────────────────────────────────────────────────────
TODAY = datetime(2025, 10, 15)
FESTIVAL_FRI = datetime(2025, 10, 24)
FESTIVAL_SAT = datetime(2025, 10, 25)
FESTIVAL_SUN = datetime(2025, 10, 26)


def date_str(dt):
    return dt.strftime("%Y-%m-%d")


def make_unique_id(base, existing):
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


# ═══════════════════════════════════════════════════════════════════════════
# Step 1: Stages (5)
# ═══════════════════════════════════════════════════════════════════════════
STAGE_SPECS = [
    {
        "stage_id": "main_stage",
        "name": "Main Stage",
        "capacity": 5000,
        "location_description": "Central field, largest stage with full production setup",
    },
    {
        "stage_id": "sunset_stage",
        "name": "Sunset Stage",
        "capacity": 2000,
        "location_description": "West hill overlooking the valley, known for golden hour sets",
    },
    {
        "stage_id": "grove_stage",
        "name": "The Grove",
        "capacity": 800,
        "location_description": "Intimate wooded area with natural acoustics",
    },
    {
        "stage_id": "electronic_tent",
        "name": "Electronic Tent",
        "capacity": 1500,
        "location_description": "Covered tent near the east entrance, full LED setup",
    },
    {
        "stage_id": "acoustic_garden",
        "name": "Acoustic Garden",
        "capacity": 300,
        "location_description": "Quiet garden area for unplugged performances",
    },
]

stages = {}
for spec in STAGE_SPECS:
    stages[spec["stage_id"]] = {
        "stage_id": spec["stage_id"],
        "name": spec["name"],
        "capacity": spec["capacity"],
        "location_description": spec["location_description"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Performances (45 — 15 per day)
# ═══════════════════════════════════════════════════════════════════════════
PERFORMANCE_CATALOG = [
    # Friday
    (
        "perf_aurora_fri",
        "Aurora Waves",
        "main_stage",
        "fri",
        "12:00",
        "13:30",
        "indie_pop",
        None,
    ),
    (
        "perf_ironclad_fri",
        "Ironclad",
        "main_stage",
        "fri",
        "15:00",
        "16:30",
        "rock",
        None,
    ),
    (
        "perf_midnight_sun_fri",
        "Midnight Sun",
        "main_stage",
        "fri",
        "19:00",
        "21:00",
        "rock",
        None,
    ),
    (
        "perf_neon_pulse_fri",
        "Neon Pulse",
        "sunset_stage",
        "fri",
        "13:00",
        "14:30",
        "electronic",
        None,
    ),
    (
        "perf_velvet_dusk_fri",
        "Velvet Dusk",
        "sunset_stage",
        "fri",
        "17:00",
        "18:30",
        "soul",
        None,
    ),
    (
        "perf_dj_nova_fri",
        "DJ Nova",
        "sunset_stage",
        "fri",
        "20:00",
        "22:00",
        "electronic",
        "18+",
    ),
    (
        "perf_folk_remedy_fri",
        "Folk Remedy",
        "grove_stage",
        "fri",
        "14:00",
        "15:30",
        "folk",
        None,
    ),
    (
        "perf_wanderlust_fri",
        "Wanderlust",
        "grove_stage",
        "fri",
        "17:00",
        "18:30",
        "indie_folk",
        None,
    ),
    (
        "perf_cosmic_bass_fri",
        "Cosmic Bass",
        "electronic_tent",
        "fri",
        "16:00",
        "18:00",
        "electronic",
        None,
    ),
    (
        "perf_synth_lords_fri",
        "Synth Lords",
        "electronic_tent",
        "fri",
        "21:00",
        "23:00",
        "electronic",
        "18+",
    ),
    (
        "perf_willow_strings_fri",
        "Willow & Strings",
        "acoustic_garden",
        "fri",
        "12:00",
        "13:00",
        "acoustic",
        None,
    ),
    (
        "perf_quiet_storm_fri",
        "Quiet Storm",
        "acoustic_garden",
        "fri",
        "15:00",
        "16:00",
        "jazz",
        None,
    ),
    (
        "perf_luna_moth_fri",
        "Luna Moth",
        "acoustic_garden",
        "fri",
        "18:00",
        "19:00",
        "acoustic",
        None,
    ),
    (
        "perf_bass_tribe_fri",
        "Bass Tribe",
        "electronic_tent",
        "fri",
        "23:30",
        "01:30",
        "electronic",
        "21+",
    ),
    (
        "perf_skyline_fri",
        "Skyline",
        "grove_stage",
        "fri",
        "20:00",
        "21:30",
        "indie_rock",
        None,
    ),
    # Saturday
    (
        "perf_golden_hour_sat",
        "Golden Hour",
        "main_stage",
        "sat",
        "12:00",
        "13:30",
        "pop",
        None,
    ),
    (
        "perf_thunder_road_sat",
        "Thunder Road",
        "main_stage",
        "sat",
        "15:00",
        "16:30",
        "rock",
        None,
    ),
    (
        "perf_phoenix_rising_sat",
        "Phoenix Rising",
        "main_stage",
        "sat",
        "19:00",
        "21:00",
        "rock",
        None,
    ),
    (
        "perf_crystal_echoes_sat",
        "Crystal Echoes",
        "sunset_stage",
        "sat",
        "13:00",
        "14:30",
        "dream_pop",
        None,
    ),
    (
        "perf_solar_flare_sat",
        "Solar Flare",
        "sunset_stage",
        "sat",
        "17:00",
        "18:30",
        "funk",
        None,
    ),
    (
        "perf_night_frequency_sat",
        "Night Frequency",
        "sunset_stage",
        "sat",
        "20:00",
        "22:00",
        "electronic",
        "18+",
    ),
    (
        "perf_river_song_sat",
        "River Song",
        "grove_stage",
        "sat",
        "14:00",
        "15:30",
        "folk",
        None,
    ),
    (
        "perf_ember_glow_sat",
        "Ember Glow",
        "grove_stage",
        "sat",
        "17:00",
        "18:30",
        "indie_folk",
        None,
    ),
    (
        "perf_circuit_breaker_sat",
        "Circuit Breaker",
        "electronic_tent",
        "sat",
        "16:00",
        "18:00",
        "electronic",
        None,
    ),
    (
        "perf_afterdark_sat",
        "Afterdark",
        "electronic_tent",
        "sat",
        "21:00",
        "23:00",
        "electronic",
        "18+",
    ),
    (
        "perf_morning_dew_sat",
        "Morning Dew",
        "acoustic_garden",
        "sat",
        "12:00",
        "13:00",
        "acoustic",
        None,
    ),
    (
        "perf_blue_note_sat",
        "Blue Note Trio",
        "acoustic_garden",
        "sat",
        "15:00",
        "16:00",
        "jazz",
        None,
    ),
    (
        "perf_heartstrings_sat",
        "Heartstrings",
        "acoustic_garden",
        "sat",
        "18:00",
        "19:00",
        "acoustic",
        None,
    ),
    (
        "perf_deep_space_sat",
        "Deep Space",
        "electronic_tent",
        "sat",
        "23:30",
        "01:30",
        "electronic",
        "21+",
    ),
    (
        "perf_wildfire_sat",
        "Wildfire",
        "grove_stage",
        "sat",
        "20:00",
        "21:30",
        "indie_rock",
        None,
    ),
    # Sunday
    (
        "perf_daybreak_sun",
        "Daybreak",
        "main_stage",
        "sun",
        "12:00",
        "13:30",
        "indie_pop",
        None,
    ),
    (
        "perf_steel_horizon_sun",
        "Steel Horizon",
        "main_stage",
        "sun",
        "15:00",
        "16:30",
        "rock",
        None,
    ),
    (
        "perf_starfall_sun",
        "Starfall Collective",
        "main_stage",
        "sun",
        "19:00",
        "21:00",
        "rock",
        None,
    ),
    (
        "perf_pastel_dreams_sun",
        "Pastel Dreams",
        "sunset_stage",
        "sun",
        "13:00",
        "14:30",
        "dream_pop",
        None,
    ),
    (
        "perf_brass_monkey_sun",
        "Brass Monkey",
        "sunset_stage",
        "sun",
        "17:00",
        "18:30",
        "funk",
        None,
    ),
    (
        "perf_electric_soul_sun",
        "Electric Soul",
        "sunset_stage",
        "sun",
        "20:00",
        "22:00",
        "soul",
        "18+",
    ),
    (
        "perf_timber_folk_sun",
        "Timber Folk",
        "grove_stage",
        "sun",
        "14:00",
        "15:30",
        "folk",
        None,
    ),
    (
        "perf_moss_garden_sun",
        "Moss & Garden",
        "grove_stage",
        "sun",
        "17:00",
        "18:30",
        "indie_folk",
        None,
    ),
    (
        "perf_voltage_sun",
        "Voltage",
        "electronic_tent",
        "sun",
        "16:00",
        "18:00",
        "electronic",
        None,
    ),
    (
        "perf_final_transmission_sun",
        "Final Transmission",
        "electronic_tent",
        "sun",
        "21:00",
        "23:00",
        "electronic",
        "18+",
    ),
    (
        "perf_gentle_tide_sun",
        "Gentle Tide",
        "acoustic_garden",
        "sun",
        "12:00",
        "13:00",
        "acoustic",
        None,
    ),
    (
        "perf_ivory_keys_sun",
        "Ivory Keys",
        "acoustic_garden",
        "sun",
        "15:00",
        "16:00",
        "jazz",
        None,
    ),
    (
        "perf_last_light_sun",
        "Last Light",
        "acoustic_garden",
        "sun",
        "18:00",
        "19:00",
        "acoustic",
        None,
    ),
    (
        "perf_rave_cave_sun",
        "Rave Cave",
        "electronic_tent",
        "sun",
        "23:30",
        "01:30",
        "electronic",
        "21+",
    ),
    (
        "perf_echo_chamber_sun",
        "Echo Chamber",
        "grove_stage",
        "sun",
        "20:00",
        "21:30",
        "indie_rock",
        None,
    ),
]

performances = {}
for pid, artist, stage, day, start, end, genre, age_restriction in PERFORMANCE_CATALOG:
    performances[pid] = {
        "performance_id": pid,
        "artist_name": artist,
        "stage_id": stage,
        "day": day,
        "start_time": start,
        "end_time": end,
        "genre": genre,
        "age_restriction": age_restriction,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 3: Vendors (15)
# ═══════════════════════════════════════════════════════════════════════════
VENDOR_SPECS = [
    (
        "vendor_burger_barn",
        "Burger Barn",
        "food",
        "Near Main Stage entrance",
        "11:00 AM - 1:00 AM",
    ),
    (
        "vendor_taco_truck",
        "Taco Fiesta",
        "food",
        "Food Court Row A",
        "11:00 AM - 12:00 AM",
    ),
    (
        "vendor_pizza_wagon",
        "Wood Fire Pizza Wagon",
        "food",
        "Food Court Row A",
        "12:00 PM - 11:00 PM",
    ),
    (
        "vendor_smoothie_shack",
        "Smoothie Shack",
        "food",
        "Near Acoustic Garden",
        "9:00 AM - 8:00 PM",
    ),
    (
        "vendor_bbq_pit",
        "Smokey's BBQ Pit",
        "food",
        "Food Court Row B",
        "11:00 AM - 10:00 PM",
    ),
    (
        "vendor_vegan_bites",
        "Green Bites (Vegan)",
        "food",
        "Food Court Row B",
        "10:00 AM - 10:00 PM",
    ),
    (
        "vendor_coffee_cart",
        "Bean There Coffee",
        "food",
        "Near camping entrance",
        "6:00 AM - 4:00 PM",
    ),
    (
        "vendor_merch_official",
        "Official Festival Merch",
        "merch",
        "Main entrance plaza",
        "10:00 AM - 11:00 PM",
    ),
    (
        "vendor_vinyl_records",
        "Vinyl Revival",
        "merch",
        "Near Sunset Stage",
        "11:00 AM - 9:00 PM",
    ),
    (
        "vendor_handmade_jewelry",
        "Luna Crafts Jewelry",
        "art",
        "Art Market Row",
        "10:00 AM - 8:00 PM",
    ),
    (
        "vendor_festival_prints",
        "Festival Prints & Posters",
        "art",
        "Art Market Row",
        "10:00 AM - 9:00 PM",
    ),
    (
        "vendor_face_paint",
        "Face Paint Station",
        "art",
        "Near The Grove",
        "11:00 AM - 7:00 PM",
    ),
    (
        "vendor_tshirt_press",
        "Custom T-Shirt Press",
        "merch",
        "Art Market Row",
        "10:00 AM - 8:00 PM",
    ),
    (
        "vendor_hat_shack",
        "Hat Shack",
        "merch",
        "Near Electronic Tent",
        "10:00 AM - 10:00 PM",
    ),
    (
        "vendor_ice_cream",
        "Frosty Scoops",
        "food",
        "Near family camping",
        "12:00 PM - 10:00 PM",
    ),
]

vendors = {}
for vid, name, vtype, loc, hours in VENDOR_SPECS:
    vendors[vid] = {
        "vendor_id": vid,
        "name": name,
        "type": vtype,
        "location": loc,
        "hours": hours,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Shuttles (4)
# ═══════════════════════════════════════════════════════════════════════════
SHUTTLE_SPECS = [
    {
        "shuttle_id": "shuttle_downtown",
        "route": "Downtown Express",
        "departure_times": [
            "09:00",
            "10:00",
            "11:00",
            "13:00",
            "15:00",
            "17:00",
            "19:00",
            "22:00",
            "00:00",
        ],
        "pickup_location": "Downtown Transit Center, 100 Main St",
        "dropoff_location": "Festival Main Gate",
        "capacity": 45,
    },
    {
        "shuttle_id": "shuttle_airport",
        "route": "Airport Shuttle",
        "departure_times": ["08:00", "11:00", "14:00", "17:00", "21:00"],
        "pickup_location": "Springfield Regional Airport, Terminal B",
        "dropoff_location": "Festival Main Gate",
        "capacity": 30,
    },
    {
        "shuttle_id": "shuttle_parking_a",
        "route": "Parking Lot A Loop",
        "departure_times": [
            "09:00",
            "09:30",
            "10:00",
            "10:30",
            "11:00",
            "11:30",
            "12:00",
            "13:00",
            "14:00",
            "15:00",
            "16:00",
            "17:00",
            "18:00",
            "19:00",
            "20:00",
            "21:00",
            "22:00",
            "23:00",
            "00:00",
        ],
        "pickup_location": "Parking Lot A, Highway 7 entrance",
        "dropoff_location": "Festival East Gate",
        "capacity": 50,
    },
    {
        "shuttle_id": "shuttle_hotel_zone",
        "route": "Hotel Zone Connector",
        "departure_times": [
            "09:00",
            "10:30",
            "12:00",
            "14:00",
            "16:00",
            "18:00",
            "20:00",
            "23:00",
        ],
        "pickup_location": "Hotel Row, Convention Blvd",
        "dropoff_location": "Festival Main Gate",
        "capacity": 40,
    },
]

shuttles = {}
for spec in SHUTTLE_SPECS:
    shuttles[spec["shuttle_id"]] = spec


# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Attendees (200)
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
    "Jason",
    "Stephanie",
    "Edward",
    "Rebecca",
    "Ryan",
    "Sharon",
    "Jacob",
    "Laura",
    "Gary",
    "Cynthia",
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

EMAIL_DOMAINS = ["email.com", "mail.com", "inbox.com", "webmail.net", "fastmail.org"]
EMERGENCY_CONTACTS = [
    "Mom: 555-{:04d}",
    "Dad: 555-{:04d}",
    "Partner: 555-{:04d}",
    "Spouse: 555-{:04d}",
    "Friend: 555-{:04d}",
    "Sister: 555-{:04d}",
    "Brother: 555-{:04d}",
]

attendees = {}
attendee_names_set: set[str] = set()

for i in range(200):
    for _attempt in range(500):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        display_name = f"{first} {last}"
        if display_name not in attendee_names_set:
            break
    else:
        raise RuntimeError("Could not find a unique name after 500 attempts")
    attendee_names_set.add(display_name)
    aid = f"{first.lower()}_{last.lower()}"

    digits = random.randint(1, 99)
    email = f"{first.lower()}.{last.lower()}{digits}@{random.choice(EMAIL_DOMAINS)}"
    phone = f"555-{random.randint(1000, 9999):04d}"
    ec_template = random.choice(EMERGENCY_CONTACTS)
    emergency_contact = ec_template.format(random.randint(1000, 9999))

    # ~15% have accessibility needs
    accessibility = None
    if random.random() < 0.15:
        accessibility = random.choice(
            [
                "Wheelchair user — needs accessible viewing areas and paths",
                "Hearing impaired — needs ASL interpreter for performances",
                "Visual impairment — needs guided assistance",
                "Mobility limited — needs close parking and accessible routes",
                "Service animal accommodation required",
            ]
        )

    # ~70% are age-verified (21+)
    age_verified = random.random() < 0.70

    attendees[aid] = {
        "attendee_id": aid,
        "name": display_name,
        "email": email,
        "phone": phone,
        "emergency_contact": emergency_contact,
        "ticket_ids": [],
        "camping_reservation_id": None,
        "accessibility_needs": accessibility,
        "wristband_id": f"WB-{random.randint(10000, 99999)}",
        "age_verified": age_verified,
    }

all_attendee_ids = list(attendees.keys())


# ═══════════════════════════════════════════════════════════════════════════
# Step 6: Payment Methods (200 — one per attendee)
# ═══════════════════════════════════════════════════════════════════════════
payment_methods = {}
for aid in all_attendee_ids:
    pmid = f"pm_{aid}"
    if random.random() < 0.85:
        pm_type = "credit_card"
        last4 = f"{random.randint(1000, 9999)}"
        details = f"Visa ending in {last4}"
    else:
        pm_type = "festival_credits"
        details = f"Festival credit balance"

    payment_methods[pmid] = {
        "payment_method_id": pmid,
        "type": pm_type,
        "details": details,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 7: Tickets (250)
# ═══════════════════════════════════════════════════════════════════════════
# Distribution: ~120 day passes, ~80 weekend, ~40 VIP, ~10 artist
tickets = {}
ticket_id_set = set()

TICKET_PRICES = {
    "day_pass": 75.0,
    "weekend": 180.0,
    "vip": 350.0,
    "artist": 0.0,
}

TICKET_DISTRIBUTION = [
    ("day_pass", 120),
    ("weekend", 80),
    ("vip", 40),
    ("artist", 10),
]

# Shuffle attendees for ticket assignment
shuffled_attendees = list(all_attendee_ids)
random.shuffle(shuffled_attendees)
attendee_idx = 0

for ttype, count in TICKET_DISTRIBUTION:
    for j in range(count):
        aid = shuffled_attendees[attendee_idx % len(shuffled_attendees)]
        attendee_idx += 1
        last = attendees[aid]["name"].split()[-1].lower()

        if ttype == "day_pass":
            day = random.choice(["fri", "sat", "sun"])
        else:
            day = "all"

        purchase_date = TODAY - timedelta(days=random.randint(14, 90))
        pmid = f"pm_{aid}"

        base_tid = f"ticket_{last}_{ttype}"
        tid = make_unique_id(base_tid, ticket_id_set)
        ticket_id_set.add(tid)

        # Status: 90% valid, 5% refunded, 3% transferred, 2% cancelled
        r = random.random()
        if r < 0.90:
            status = "valid"
        elif r < 0.95:
            status = "refunded"
        elif r < 0.98:
            status = "transferred"
        else:
            status = "cancelled"

        tickets[tid] = {
            "ticket_id": tid,
            "attendee_id": aid,
            "type": ttype,
            "day": day,
            "status": status,
            "purchase_date": date_str(purchase_date),
            "price": TICKET_PRICES[ttype],
            "payment_method_id": pmid,
        }

        if status == "valid":
            attendees[aid]["ticket_ids"].append(tid)


# ═══════════════════════════════════════════════════════════════════════════
# Step 8: Camping Reservations (80)
# ═══════════════════════════════════════════════════════════════════════════
camping_reservations = {}
camping_id_set = set()

CAMPING_ZONES = ["general", "quiet", "family", "vip"]
CAMPING_ZONE_WEIGHTS = [50, 20, 15, 15]
SPOTS_PER_ZONE = {"general": 200, "quiet": 50, "family": 40, "vip": 30}
spot_counters = defaultdict(int)

# Only attendees with valid tickets get camping
eligible_campers = [aid for aid in all_attendee_ids if attendees[aid]["ticket_ids"]]
random.shuffle(eligible_campers)

for i in range(min(80, len(eligible_campers))):
    aid = eligible_campers[i]
    last = attendees[aid]["name"].split()[-1].lower()

    zone = random.choices(CAMPING_ZONES, weights=CAMPING_ZONE_WEIGHTS, k=1)[0]

    # VIP zone requires VIP ticket
    has_vip = any(
        tickets[tid]["type"] == "vip"
        for tid in attendees[aid]["ticket_ids"]
        if tid in tickets
    )
    if zone == "vip" and not has_vip:
        zone = "general"

    spot_counters[zone] += 1
    spot_number = spot_counters[zone]

    check_in = FESTIVAL_FRI
    check_out = FESTIVAL_SUN + timedelta(days=1)  # Monday

    base_cid = f"camp_{last}_{zone}"
    crid = make_unique_id(base_cid, camping_id_set)
    camping_id_set.add(crid)

    # Status: 85% reserved, 10% cancelled, 5% checked_in
    r = random.random()
    if r < 0.85:
        status = "reserved"
    elif r < 0.95:
        status = "cancelled"
    else:
        status = "checked_in"

    vehicle_pass = random.random() < 0.40

    camping_reservations[crid] = {
        "reservation_id": crid,
        "attendee_id": aid,
        "zone": zone,
        "spot_number": spot_number,
        "check_in_date": date_str(check_in),
        "check_out_date": date_str(check_out),
        "status": status,
        "vehicle_pass": vehicle_pass,
    }

    if status in ("reserved", "checked_in"):
        attendees[aid]["camping_reservation_id"] = crid


# ═══════════════════════════════════════════════════════════════════════════
# Step 9: Lost Items (25)
# ═══════════════════════════════════════════════════════════════════════════
LOST_ITEM_TEMPLATES = [
    ("Black iPhone 14 with cracked screen protector", "Near Main Stage"),
    ("Blue backpack with water bottle pocket", "Near Food Court Row A"),
    ("Red sunglasses, Ray-Ban style", "Sunset Stage viewing area"),
    ("Silver car keys with BMW keychain", "Parking Lot A shuttle stop"),
    ("Denim jacket with patches", "The Grove seating area"),
    ("White AirPods Pro case", "Electronic Tent entrance"),
    ("Brown leather wallet", "Near official merch booth"),
    ("Green camping chair", "General camping zone B"),
    ("Canon camera with strap", "Acoustic Garden"),
    ("Pink hydroflask water bottle", "Food Court Row B"),
    ("Black fanny pack with festival map", "Main Gate"),
    ("Prescription glasses, black frames", "Sunset Stage"),
    ("Gold bracelet with charms", "Art Market Row"),
    ("Samsung Galaxy phone, blue case", "Near Burger Barn"),
    ("Portable phone charger, Anker brand", "Electronic Tent"),
    ("Straw hat with flower band", "Near camping entrance"),
    ("Small blue cooler bag", "Family camping zone"),
    ("Tie-dye t-shirt, size L", "The Grove stage"),
    ("Leather sandals, size 9", "Near Smoothie Shack"),
    ("Polaroid camera, white", "Sunset Stage VIP area"),
    ("Bluetooth speaker, JBL", "Quiet camping zone"),
    ("Rain poncho, clear plastic", "Main Stage area"),
    ("Skateboard, Element brand", "East Gate area"),
    ("Tote bag with festival logo", "Vinyl Revival booth"),
    ("Reading glasses in a red case", "Bean There Coffee"),
]

lost_items = {}
found_dates = [FESTIVAL_FRI, FESTIVAL_SAT, FESTIVAL_SUN]

for i, (desc, loc) in enumerate(LOST_ITEM_TEMPLATES):
    day = random.choice(found_dates)
    hour = random.randint(10, 23)
    minute = random.choice([0, 15, 30, 45])
    found_time = f"{date_str(day)} {hour:02d}:{minute:02d}"

    slug = desc.lower().replace(" ", "_").replace(",", "")[:25]
    item_id = f"lost_{slug}_{i + 1}"

    # Status: 60% unclaimed, 25% claimed, 15% donated
    r = random.random()
    if r < 0.60:
        status = "unclaimed"
        claimed_by = None
    elif r < 0.85:
        status = "claimed"
        claimed_by = random.choice(all_attendee_ids)
    else:
        status = "donated"
        claimed_by = None

    lost_items[item_id] = {
        "item_id": item_id,
        "description": desc,
        "found_location": loc,
        "found_time": found_time,
        "status": status,
        "claimed_by": claimed_by,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 10: Validation
# ═══════════════════════════════════════════════════════════════════════════
errors = []

# FK: tickets -> attendees, payment_methods
for tid, t in tickets.items():
    if t["attendee_id"] not in attendees:
        errors.append(f"Ticket {tid}: attendee {t['attendee_id']} not found")
    if t["payment_method_id"] not in payment_methods:
        errors.append(
            f"Ticket {tid}: payment method {t['payment_method_id']} not found"
        )

# FK: camping -> attendees
for crid, cr in camping_reservations.items():
    if cr["attendee_id"] not in attendees:
        errors.append(f"Camping {crid}: attendee {cr['attendee_id']} not found")

# FK: performances -> stages
for pid, p in performances.items():
    if p["stage_id"] not in stages:
        errors.append(f"Performance {pid}: stage {p['stage_id']} not found")

# FK: lost_items claimed_by -> attendees
for iid, item in lost_items.items():
    if item["claimed_by"] and item["claimed_by"] not in attendees:
        errors.append(f"Lost item {iid}: claimed_by {item['claimed_by']} not found")

# Verify attendee ticket back-references
for aid, a in attendees.items():
    for tid in a["ticket_ids"]:
        if tid not in tickets:
            errors.append(f"Attendee {aid}: ticket {tid} not found")
        elif tickets[tid]["status"] != "valid":
            errors.append(f"Attendee {aid}: ticket {tid} is {tickets[tid]['status']}")

# Verify camping back-references
for aid, a in attendees.items():
    crid = a["camping_reservation_id"]
    if crid and crid not in camping_reservations:
        errors.append(f"Attendee {aid}: camping {crid} not found")


# ═══════════════════════════════════════════════════════════════════════════
# Statistics
# ═══════════════════════════════════════════════════════════════════════════
ticket_types = defaultdict(int)
ticket_statuses = defaultdict(int)
for t in tickets.values():
    ticket_types[t["type"]] += 1
    ticket_statuses[t["status"]] += 1

camping_zones = defaultdict(int)
camping_statuses = defaultdict(int)
for cr in camping_reservations.values():
    camping_zones[cr["zone"]] += 1
    camping_statuses[cr["status"]] += 1

perf_by_day = defaultdict(int)
perf_age_restricted = 0
for p in performances.values():
    perf_by_day[p["day"]] += 1
    if p["age_restriction"]:
        perf_age_restricted += 1

lost_statuses = defaultdict(int)
for item in lost_items.values():
    lost_statuses[item["status"]] += 1

attendees_with_accessibility = sum(
    1 for a in attendees.values() if a["accessibility_needs"]
)
attendees_age_verified = sum(1 for a in attendees.values() if a["age_verified"])
attendees_with_tickets = sum(1 for a in attendees.values() if a["ticket_ids"])
attendees_with_camping = sum(
    1 for a in attendees.values() if a["camping_reservation_id"]
)

print("=" * 60)
print("FESTIVAL DATABASE GENERATION COMPLETE")
print("=" * 60)
print(f"\nAttendees:     {len(attendees)}")
print(f"  With tickets:  {attendees_with_tickets}")
print(f"  With camping:  {attendees_with_camping}")
print(f"  Age verified:  {attendees_age_verified}")
print(f"  Accessibility: {attendees_with_accessibility}")
print(f"\nTickets:       {len(tickets)}")
for tt, cnt in sorted(ticket_types.items()):
    print(f"  {tt}: {cnt}")
print(f"  Statuses:")
for ts, cnt in sorted(ticket_statuses.items()):
    print(f"    {ts}: {cnt}")
print(f"\nCamping:       {len(camping_reservations)}")
for z, cnt in sorted(camping_zones.items()):
    print(f"  {z}: {cnt}")
for cs, cnt in sorted(camping_statuses.items()):
    print(f"    {cs}: {cnt}")
print(f"\nStages:        {len(stages)}")
print(f"Performances:  {len(performances)}")
for d, cnt in sorted(perf_by_day.items()):
    print(f"  {d}: {cnt}")
print(f"  Age-restricted: {perf_age_restricted}")
print(f"\nVendors:       {len(vendors)}")
print(f"Shuttles:      {len(shuttles)}")
print(f"\nLost Items:    {len(lost_items)}")
for ls, cnt in sorted(lost_statuses.items()):
    print(f"  {ls}: {cnt}")
print(f"\nPayment Methods: {len(payment_methods)}")

if errors:
    print(f"\n!! VALIDATION ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
else:
    print("\nAll validation checks passed")


# ═══════════════════════════════════════════════════════════════════════════
# Write db.json
# ═══════════════════════════════════════════════════════════════════════════
db = {
    "attendees": attendees,
    "tickets": tickets,
    "camping_reservations": camping_reservations,
    "stages": stages,
    "performances": performances,
    "lost_items": lost_items,
    "vendors": vendors,
    "shuttles": shuttles,
    "payment_methods": payment_methods,
}

output_path = Path(__file__).parent / "db.json"
with open(output_path, "w") as f:
    json.dump(db, f, indent=2)

print(f"\nWritten to {output_path}")
