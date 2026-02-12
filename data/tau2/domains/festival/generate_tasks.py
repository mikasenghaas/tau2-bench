#!/usr/bin/env python3
"""Procedurally generate ~200 festival domain tasks from db.json.

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
FESTIVAL_START = "2025-10-24"
FESTIVAL_END = "2025-10-26"

DB_PATH = Path(__file__).parent / "db.json"
TASKS_PATH = Path(__file__).parent / "tasks.json"
SPLIT_TASKS_PATH = Path(__file__).parent / "split_tasks.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_db() -> dict:
    with open(DB_PATH) as f:
        return json.load(f)


def attendee_name(db: dict, aid: str) -> str:
    return db["attendees"][aid]["name"]


def ticket_type_label(ttype: str) -> str:
    return {
        "day_pass": "day pass",
        "weekend": "weekend pass",
        "vip": "VIP pass",
        "artist": "artist pass",
    }.get(ttype, ttype)


# ---------------------------------------------------------------------------
# Entity Indexes
# ---------------------------------------------------------------------------


@dataclass
class EntityIndexes:
    # Attendees
    attendees_with_valid_tickets: list = field(default_factory=list)
    attendees_without_tickets: list = field(default_factory=list)
    attendees_with_camping: list = field(default_factory=list)
    attendees_with_accessibility: list = field(default_factory=list)
    attendees_age_verified: list = field(default_factory=list)
    attendees_not_age_verified: list = field(default_factory=list)

    # Tickets
    valid_tickets: list = field(default_factory=list)
    valid_day_passes: list = field(default_factory=list)
    valid_weekend_passes: list = field(default_factory=list)
    valid_vip_tickets: list = field(default_factory=list)
    refunded_tickets: list = field(default_factory=list)
    transferred_tickets: list = field(default_factory=list)

    # Upgradeable tickets (day_pass -> weekend/vip, weekend -> vip)
    upgradeable_day_passes: list = field(default_factory=list)
    upgradeable_weekend_passes: list = field(default_factory=list)

    # Camping
    reserved_camping: list = field(default_factory=list)
    checked_in_camping: list = field(default_factory=list)
    cancelled_camping: list = field(default_factory=list)
    modifiable_camping: list = field(default_factory=list)
    non_vip_camping: list = field(default_factory=list)

    # Lost items
    unclaimed_items: list = field(default_factory=list)
    claimed_items: list = field(default_factory=list)

    # Performances
    age_restricted_performances: list = field(default_factory=list)
    all_ages_performances: list = field(default_factory=list)
    fri_performances: list = field(default_factory=list)
    sat_performances: list = field(default_factory=list)
    sun_performances: list = field(default_factory=list)

    # For transfer targets: attendees registered but different from ticket holder
    transfer_targets: dict = field(
        default_factory=dict
    )  # ticket_id -> eligible recipient aid


def build_indexes(db: dict) -> EntityIndexes:
    ix = EntityIndexes()

    # Ambiguous names check
    _name_counts: dict[str, list[str]] = {}
    for aid, a in db["attendees"].items():
        _name_counts.setdefault(a["name"], []).append(aid)
    _ambiguous: set[str] = set()
    for _aids in _name_counts.values():
        if len(_aids) > 1:
            _ambiguous.update(_aids)

    for aid, a in db["attendees"].items():
        if aid in _ambiguous:
            continue
        if a["ticket_ids"]:
            ix.attendees_with_valid_tickets.append(aid)
        else:
            ix.attendees_without_tickets.append(aid)
        if a["camping_reservation_id"]:
            ix.attendees_with_camping.append(aid)
        if a["accessibility_needs"]:
            ix.attendees_with_accessibility.append(aid)
        if a["age_verified"]:
            ix.attendees_age_verified.append(aid)
        else:
            ix.attendees_not_age_verified.append(aid)

    # Collect attendees who already have VIP or artist tickets
    _has_vip_or_artist: set[str] = set()
    for t in db["tickets"].values():
        if t["status"] == "valid" and t["type"] in ("vip", "artist"):
            _has_vip_or_artist.add(t["attendee_id"])

    for tid, t in db["tickets"].items():
        if t["attendee_id"] in _ambiguous:
            continue
        if t["status"] == "valid":
            ix.valid_tickets.append(tid)
            if t["type"] == "day_pass":
                ix.valid_day_passes.append(tid)
                # Only upgradeable if attendee doesn't already have VIP/artist
                if t["attendee_id"] not in _has_vip_or_artist:
                    ix.upgradeable_day_passes.append(tid)
            elif t["type"] == "weekend":
                ix.valid_weekend_passes.append(tid)
                if t["attendee_id"] not in _has_vip_or_artist:
                    ix.upgradeable_weekend_passes.append(tid)
            elif t["type"] == "vip":
                ix.valid_vip_tickets.append(tid)
        elif t["status"] == "refunded":
            ix.refunded_tickets.append(tid)
        elif t["status"] == "transferred":
            ix.transferred_tickets.append(tid)

    for crid, cr in db["camping_reservations"].items():
        if cr["attendee_id"] in _ambiguous:
            continue
        if cr["status"] == "reserved":
            ix.reserved_camping.append(crid)
            ix.modifiable_camping.append(crid)
            if cr["zone"] != "vip":
                ix.non_vip_camping.append(crid)
        elif cr["status"] == "checked_in":
            ix.checked_in_camping.append(crid)
            ix.modifiable_camping.append(crid)
        elif cr["status"] == "cancelled":
            ix.cancelled_camping.append(crid)

    for iid, item in db["lost_items"].items():
        if item["status"] == "unclaimed":
            ix.unclaimed_items.append(iid)
        elif item["status"] == "claimed":
            ix.claimed_items.append(iid)

    for pid, p in db["performances"].items():
        if p["age_restriction"]:
            ix.age_restricted_performances.append(pid)
        else:
            ix.all_ages_performances.append(pid)
        if p["day"] == "fri":
            ix.fri_performances.append(pid)
        elif p["day"] == "sat":
            ix.sat_performances.append(pid)
        elif p["day"] == "sun":
            ix.sun_performances.append(pid)

    # Build transfer targets: for each valid ticket, find a different attendee
    non_ambig_attendees = [aid for aid in db["attendees"] if aid not in _ambiguous]
    for tid in ix.valid_tickets:
        t = db["tickets"][tid]
        candidates = [aid for aid in non_ambig_attendees if aid != t["attendee_id"]]
        if candidates:
            ix.transfer_targets[tid] = random.choice(candidates)

    return ix


# ---------------------------------------------------------------------------
# Persona System
# ---------------------------------------------------------------------------


@dataclass
class Persona:
    label: str
    instructions: str
    auth: str  # "name" or "email"
    difficulty: str


EASY_PERSONAS = [
    Persona(
        "Friendly and direct",
        "Provide all requested information promptly and clearly. Be cooperative and concise.",
        "name",
        "easy",
    ),
    Persona(
        "Excited first-timer",
        "You're excited about the festival! Provide details quickly. Be enthusiastic but cooperative.",
        "name",
        "easy",
    ),
]

MEDIUM_PERSONAS = [
    Persona(
        "Casual, provides info gradually",
        "Don't volunteer all information at once. Wait for the agent to ask for specific details before providing them.",
        "name",
        "medium",
    ),
    Persona(
        "Group organizer",
        "You're managing logistics for a group. Be organized but brief. Reference 'my group' or 'my friends' frequently.",
        "name",
        "medium",
    ),
    Persona(
        "Busy professional",
        "You have limited time. Be terse and direct. Give short answers. Omit details you assume the agent can figure out.",
        "name",
        "medium",
    ),
]

HARD_PERSONAS = [
    Persona(
        "Vague and uncertain",
        "You don't remember exact details. Describe things from memory using approximate descriptions. Say things like 'I think it was...' or 'something like...'. You're not sure about specifics.",
        "name",
        "hard",
    ),
    Persona(
        "Chatty and digressive",
        "You are very chatty and go off-topic. Share anecdotes or small talk before answering. Bury your actual request in longer statements.",
        "name",
        "hard",
    ),
    Persona(
        "Frustrated attendee",
        "You had a bad experience at the festival. You are frustrated and vent before giving details. Your responses are curt.",
        "name",
        "hard",
    ),
    Persona(
        "Anxious parent with teens",
        "You're worried about your teenagers at the festival. Ask lots of safety-related questions. Mention concerns about age restrictions frequently.",
        "name",
        "hard",
    ),
    Persona(
        "VIP who expects premium treatment",
        "You paid for VIP and expect top-tier service. Be impatient. Reference your VIP status repeatedly.",
        "name",
        "hard",
    ),
]

ALL_EASY_MEDIUM = EASY_PERSONAS + MEDIUM_PERSONAS


def pick_easy_persona() -> Persona:
    return random.choice(ALL_EASY_MEDIUM)


def pick_hard_persona() -> Persona:
    return random.choice(HARD_PERSONAS)


# ---------------------------------------------------------------------------
# Vague descriptions for items/artists
# ---------------------------------------------------------------------------

VAGUE_ARTIST_DESCRIPTIONS = {
    "Aurora Waves": "that indie pop band, something about waves",
    "Ironclad": "a rock band, I think they're called something metal-ish",
    "Midnight Sun": "a rock group, name had something to do with the sun at night",
    "Neon Pulse": "electronic act, neon something",
    "Velvet Dusk": "a soul singer, name sounded really smooth",
    "DJ Nova": "a DJ, nova or supernova or something",
    "Folk Remedy": "a folk band, something about remedies or medicine",
    "Golden Hour": "a pop act, named after that time of day with the nice light",
    "Thunder Road": "a rock band, thunder something",
    "Phoenix Rising": "a big rock band, something about a phoenix",
    "Crystal Echoes": "dreamy sounding music, crystal something",
    "Solar Flare": "a funky band, sun-related name",
    "River Song": "a folk artist, name was about rivers",
    "Circuit Breaker": "electronic music, something technical sounding",
    "Daybreak": "an indie pop band, named after morning",
    "Steel Horizon": "rock band, had something to do with horizons",
    "Starfall Collective": "a rock collective, star-related name",
    "Pastel Dreams": "dream pop, something pastel",
    "Brass Monkey": "a funky band with a funny animal name",
    "Timber Folk": "folk music, something about trees",
}


def vague_artist(artist_name: str) -> str:
    return VAGUE_ARTIST_DESCRIPTIONS.get(
        artist_name, f"a band called something like '{artist_name}'"
    )


VAGUE_ITEM_DESCRIPTIONS = {
    "Black iPhone 14 with cracked screen protector": "my phone, a black iPhone",
    "Blue backpack with water bottle pocket": "my blue backpack",
    "Red sunglasses, Ray-Ban style": "my red sunglasses",
    "Silver car keys with BMW keychain": "my car keys with a BMW keychain",
    "Denim jacket with patches": "my denim jacket, it had patches on it",
    "White AirPods Pro case": "my AirPods case, white",
    "Brown leather wallet": "my brown wallet",
    "Canon camera with strap": "my camera, a Canon",
    "Samsung Galaxy phone, blue case": "my Samsung phone, blue case",
    "Portable phone charger, Anker brand": "my phone charger, an Anker one",
    "Polaroid camera, white": "my Polaroid camera",
    "Bluetooth speaker, JBL": "my JBL speaker",
}


def vague_item(description: str) -> str:
    return VAGUE_ITEM_DESCRIPTIONS.get(description, f"something like: {description}")


# ---------------------------------------------------------------------------
# Task builder helpers
# ---------------------------------------------------------------------------

PAYMENT_METHODS = ["credit_card", "festival_credits"]

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
                "domain": "festival",
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


# =========================================================================
# Tier 1: Simple Single-Action Generators
# =========================================================================


def gen_ticket_upgrade_day_to_weekend(db, ix, n=6):
    """Upgrade day pass to weekend. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.upgradeable_day_passes)
    random.shuffle(eligible)

    for i, tid in enumerate(eligible[:n]):
        t = db["tickets"][tid]
        aid = t["attendee_id"]
        name = attendee_name(db, aid)
        pmid = t["payment_method_id"]
        track_use(aid)
        track_use(tid)

        acts = [
            action(
                "upgrade_1",
                "upgrade_ticket",
                {"ticket_id": tid, "new_type": "weekend", "payment_method_id": pmid},
                f"Upgrade {tid} from day pass to weekend",
                compare_args=["ticket_id", "new_type"],
            )
        ]
        asserts = [
            env_assert(
                "assert_ticket_type", {"ticket_id": tid, "expected_type": "weekend"}
            ),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"upgrade_day_weekend_{i + 1}a",
                "Test day pass to weekend upgrade",
                "Upgrades allowed to higher tier. Price difference charged.",
                f"Attendee {name} upgrades day pass to weekend.",
                pa.label,
                f"You are {name}. You want to upgrade your festival ticket. {pa.instructions}",
                f"I have a day pass and I'd like to upgrade to a weekend pass.",
                f"Your name is {name}. You have a day pass.",
                "You don't know the ticket ID or exact price difference.",
                f"Attendee {name} wants to upgrade day pass {tid} to weekend.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"upgrade_day_weekend_{i + 1}b",
                "Test day pass upgrade with vague request",
                "Upgrades allowed to higher tier. Price difference charged.",
                f"Attendee {name} vaguely asks about staying longer.",
                pb.label,
                f"You are {name}. You're at the festival and want to stay longer. {pb.instructions}",
                f"I bought a ticket for just one day but I'm having so much fun... is there a way I could stay for the whole weekend?",
                f"Your name is {name}. You have a single-day ticket.",
                "You don't know upgrade options, pricing, or your ticket ID.",
                f"Attendee {name} vaguely asks about extending stay. Agent should identify upgrade path.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_ticket_upgrade_to_vip(db, ix, n=5):
    """Upgrade day/weekend pass to VIP. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.upgradeable_day_passes[:3]) + list(
        ix.upgradeable_weekend_passes[:3]
    )
    random.shuffle(eligible)

    for i, tid in enumerate(eligible[:n]):
        t = db["tickets"][tid]
        aid = t["attendee_id"]
        name = attendee_name(db, aid)
        pmid = t["payment_method_id"]
        old_type = t["type"]
        track_use(aid)
        track_use(tid)

        acts = [
            action(
                "upgrade_1",
                "upgrade_ticket",
                {"ticket_id": tid, "new_type": "vip", "payment_method_id": pmid},
                f"Upgrade {tid} from {old_type} to VIP",
                compare_args=["ticket_id", "new_type"],
            )
        ]
        asserts = [
            env_assert(
                "assert_ticket_type", {"ticket_id": tid, "expected_type": "vip"}
            ),
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"upgrade_vip_{i + 1}a",
                f"Test {old_type} to VIP upgrade",
                "Upgrades to VIP subject to availability. Price difference charged.",
                f"Attendee {name} upgrades {old_type} to VIP.",
                pa.label,
                f"You are {name}. You want the VIP experience. {pa.instructions}",
                f"I want to upgrade my {ticket_type_label(old_type)} to VIP. What's the cost difference?",
                f"Your name is {name}. You have a {ticket_type_label(old_type)}.",
                "You don't know your ticket ID or exact pricing.",
                f"Attendee {name} wants VIP upgrade from {old_type} ticket {tid}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"upgrade_vip_{i + 1}b",
                f"Test VIP upgrade with demanding patron",
                "Upgrades to VIP subject to availability. Price difference charged.",
                f"Attendee {name} demands VIP treatment.",
                pb.label,
                f"You are {name}. You want to upgrade to VIP. {pb.instructions}",
                f"I want the best experience possible at this festival. What's the top tier?",
                f"Your name is {name}. You have a {ticket_type_label(old_type)}.",
                "You don't know specific tiers or pricing.",
                f"Attendee {name} wants premium upgrade. Agent should identify VIP option.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_ticket_refund(db, ix, n=5):
    """Refund a valid ticket. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.valid_tickets)
    random.shuffle(eligible)

    for i, tid in enumerate(eligible[:n]):
        t = db["tickets"][tid]
        aid = t["attendee_id"]
        name = attendee_name(db, aid)
        ttype = t["type"]
        track_use(aid)
        track_use(tid)

        acts = [
            action(
                "refund_1",
                "refund_ticket",
                {"ticket_id": tid, "reason": "Cannot attend"},
                f"Refund ticket {tid}",
                compare_args=["ticket_id"],
            )
        ]
        asserts = [
            env_assert(
                "assert_ticket_status",
                {"ticket_id": tid, "expected_status": "refunded"},
            ),
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"ticket_refund_{i + 1}a",
                "Test ticket refund within refund window",
                "14+ days: full refund. 7-13 days: 50%. <7 days: none.",
                f"Attendee {name} requests refund of {ttype} ticket.",
                pa.label,
                f"You are {name}. You can't make it to the festival. {pa.instructions}",
                f"I need to cancel my {ticket_type_label(ttype)} and get a refund. Something came up and I can't attend.",
                f"Your name is {name}. You have a {ticket_type_label(ttype)}.",
                "You don't know your ticket ID or the refund policy details.",
                f"Attendee {name} wants refund on {ttype} ticket {tid}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"ticket_refund_{i + 1}b",
                "Test ticket refund with difficult interaction",
                "14+ days: full refund. 7-13 days: 50%. <7 days: none.",
                f"Attendee {name} upset about needing refund.",
                pb.label,
                f"You are {name}. You're unhappy you can't attend. {pb.instructions}",
                f"I bought a ticket but now I can't go... is there any way to get my money back?",
                f"Your name is {name}.",
                "You don't know refund policy, ticket ID, or what percentage you'll get back.",
                f"Attendee {name} vaguely asks about getting money back. Agent should find ticket and process refund.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_ticket_transfer(db, ix, n=5):
    """Transfer ticket to another attendee. n bases -> 2n tasks."""
    tasks = []
    eligible = [tid for tid in ix.valid_tickets if tid in ix.transfer_targets]
    random.shuffle(eligible)

    for i, tid in enumerate(eligible[:n]):
        t = db["tickets"][tid]
        aid = t["attendee_id"]
        name = attendee_name(db, aid)
        target_aid = ix.transfer_targets[tid]
        target_email = db["attendees"][target_aid]["email"]
        target_name = attendee_name(db, target_aid)
        track_use(aid)
        track_use(tid)

        acts = [
            action(
                "transfer_1",
                "transfer_ticket",
                {"ticket_id": tid, "new_attendee_email": target_email},
                f"Transfer {tid} to {target_name}",
                compare_args=["ticket_id", "new_attendee_email"],
            )
        ]
        asserts = [
            env_assert(
                "assert_ticket_status",
                {"ticket_id": tid, "expected_status": "transferred"},
            ),
            env_assert(
                "assert_ticket_attendee",
                {"ticket_id": tid, "expected_attendee_id": target_aid},
            ),
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"ticket_transfer_{i + 1}a",
                "Test ticket transfer to registered attendee",
                "Transfers allowed once per ticket. Both parties must be registered.",
                f"Attendee {name} transfers ticket to {target_name}.",
                pa.label,
                f"You are {name}. You want to give your ticket to a friend. {pa.instructions}",
                f"I'd like to transfer my ticket to my friend {target_name}. Their email is {target_email}.",
                f"Your name is {name}. Your friend is {target_name} ({target_email}).",
                "You don't know your ticket ID.",
                f"Attendee {name} transfers ticket {tid} to {target_name} ({target_email}).",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"ticket_transfer_{i + 1}b",
                "Test ticket transfer with incomplete info",
                "Transfers allowed once per ticket. Both parties must be registered.",
                f"Attendee {name} wants to give ticket away but is vague.",
                pb.label,
                f"You are {name}. You can't attend and want your friend to go instead. {pb.instructions}",
                f"I can't make it to the festival... can I give my ticket to someone else?",
                f"Your name is {name}. When asked, your friend's email is {target_email}.",
                "You don't initially mention the friend's name or email. Share when asked.",
                f"Attendee {name} wants to transfer. Agent must ask for recipient info.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_cancel_camping(db, ix, n=4):
    """Cancel camping reservation. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.reserved_camping)
    random.shuffle(eligible)

    for i, crid in enumerate(eligible[:n]):
        cr = db["camping_reservations"][crid]
        aid = cr["attendee_id"]
        name = attendee_name(db, aid)
        zone = cr["zone"]
        track_use(aid)
        track_use(crid)

        acts = [
            action(
                "cancel_camp_1",
                "cancel_camping",
                {"reservation_id": crid},
                f"Cancel camping {crid}",
            )
        ]
        asserts = [
            env_assert(
                "assert_camping_status",
                {"reservation_id": crid, "expected_status": "cancelled"},
            ),
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"cancel_camping_{i + 1}a",
                "Test camping cancellation",
                "Camping reservations can be cancelled if reserved or checked in.",
                f"Attendee {name} cancels {zone} camping.",
                pa.label,
                f"You are {name}. You want to cancel your camping reservation. {pa.instructions}",
                f"I need to cancel my camping reservation. I'll be staying at a hotel instead.",
                f"Your name is {name}. You have a camping spot in the {zone} zone.",
                "You don't know your reservation ID.",
                f"Attendee {name} wants to cancel camping {crid} ({zone} zone).",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"cancel_camping_{i + 1}b",
                "Test camping cancellation with vague request",
                "Camping reservations can be cancelled if reserved or checked in.",
                f"Attendee {name} vaguely mentions not needing camping.",
                pb.label,
                f"You are {name}. You changed your plans about camping. {pb.instructions}",
                f"I don't think I'll be camping after all... my friend has a spare room.",
                f"Your name is {name}.",
                "You don't know your reservation details or cancellation process.",
                f"Attendee {name} vaguely wants to cancel camping. Agent should find and cancel.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_modify_camping_zone(db, ix, n=4):
    """Modify camping zone. n bases -> 2n tasks."""
    tasks = []
    eligible = list(ix.non_vip_camping)
    random.shuffle(eligible)

    zone_changes = {"general": "quiet", "quiet": "general", "family": "quiet"}

    for i, crid in enumerate(eligible[:n]):
        cr = db["camping_reservations"][crid]
        aid = cr["attendee_id"]
        name = attendee_name(db, aid)
        old_zone = cr["zone"]
        new_zone = zone_changes.get(old_zone, "quiet")
        track_use(aid)
        track_use(crid)

        acts = [
            action(
                "modify_camp_1",
                "modify_camping",
                {"reservation_id": crid, "zone": new_zone},
                f"Change camping zone from {old_zone} to {new_zone}",
                compare_args=["reservation_id", "zone"],
            )
        ]
        asserts = [
            env_assert(
                "assert_camping_zone",
                {"reservation_id": crid, "expected_zone": new_zone},
            ),
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"modify_camping_zone_{i + 1}a",
                "Test camping zone modification",
                "Camping can be modified if reserved or checked in. VIP requires VIP ticket.",
                f"Attendee {name} changes from {old_zone} to {new_zone} camping.",
                pa.label,
                f"You are {name}. You want to change your camping zone. {pa.instructions}",
                f"I'd like to switch my camping zone from {old_zone} to {new_zone}.",
                f"Your name is {name}. You're currently in the {old_zone} zone. You want {new_zone}.",
                "You don't know your reservation ID.",
                f"Attendee {name} wants to change camping from {old_zone} to {new_zone} ({crid}).",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        zone_reasons = {
            "quiet": "it's too loud where I am",
            "general": "the quiet zone is too strict for us",
            "family": "I need somewhere more family-friendly",
        }
        reason = zone_reasons.get(new_zone, "I want a different camping area")
        tasks.append(
            make_task(
                f"modify_camping_zone_{i + 1}b",
                "Test camping zone change with indirect request",
                "Camping can be modified if reserved or checked in. VIP requires VIP ticket.",
                f"Attendee {name} indirectly requests zone change.",
                pb.label,
                f"You are {name}. You're not happy with your camping zone. {pb.instructions}",
                f"Hey, {reason}... is there another camping option?",
                f"Your name is {name}. When asked, you'd prefer the {new_zone} zone.",
                "You don't know zone names well. Describe your preference and agree when agent suggests {new_zone}.",
                f"Attendee {name} wants to move camping. Agent should identify and change to {new_zone}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_report_lost_item(db, ix, n=5):
    """Report a lost item. Single variant (inherently interactive)."""
    tasks = []
    eligible = list(ix.attendees_with_valid_tickets)
    random.shuffle(eligible)

    lost_descriptions = [
        ("phone", "black iPhone with a cracked case", "Near Main Stage"),
        ("wallet", "brown leather wallet with ID inside", "Food Court area"),
        ("sunglasses", "prescription sunglasses in a blue case", "Sunset Stage"),
        ("keys", "car keys with a Subaru keychain", "Parking shuttle stop"),
        ("jacket", "green rain jacket with hood", "The Grove"),
        ("camera", "small digital camera, silver, Sony", "Acoustic Garden"),
        ("backpack", "gray backpack with laptop inside", "Near Electronic Tent"),
        ("water bottle", "purple Nalgene water bottle with stickers", "Near camping"),
    ]

    for i, aid in enumerate(eligible[:n]):
        name = attendee_name(db, aid)
        desc_label, desc, location = lost_descriptions[i % len(lost_descriptions)]
        track_use(aid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"report_lost_{i + 1}",
                "Test lost item reporting",
                "Attendees can report lost items with description and location.",
                f"Attendee {name} lost their {desc_label}.",
                pa.label,
                f"You are {name}. You lost something at the festival. {pa.instructions}",
                f"I lost my {desc_label}! I think I left it {location.lower()}.",
                f"Your name is {name}. You lost: {desc}. Last seen: {location}.",
                "You're not sure of the exact time you lost it.",
                f"Attendee {name} reports lost {desc_label} near {location}.",
                [
                    action(
                        "report_1",
                        "report_lost_item",
                        {
                            "attendee_id": aid,
                            "description": desc,
                            "last_seen_location": location,
                        },
                        f"Report lost {desc_label}",
                        compare_args=["attendee_id"],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_claim_lost_item(db, ix, n=4):
    """Claim a found item. n bases -> 2n tasks."""
    tasks = []
    unclaimed = list(ix.unclaimed_items)
    random.shuffle(unclaimed)
    eligible_attendees = list(ix.attendees_with_valid_tickets)
    random.shuffle(eligible_attendees)

    for i, iid in enumerate(unclaimed[:n]):
        item = db["lost_items"][iid]
        aid = eligible_attendees[i % len(eligible_attendees)]
        name = attendee_name(db, aid)
        desc = item["description"]
        vdesc = vague_item(desc)
        track_use(aid)
        track_use(iid)

        acts = [
            action(
                "search_1",
                "search_lost_items",
                {"description": desc},
                f"Search for '{desc}'",
                compare_args=[],
            ),
            action(
                "claim_1",
                "claim_lost_item",
                {"item_id": iid, "attendee_id": aid},
                f"Claim item {iid}",
                compare_args=["item_id", "attendee_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_lost_item_status",
                {"item_id": iid, "expected_status": "claimed"},
            ),
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"claim_lost_{i + 1}a",
                "Test claiming a found item",
                "Items unclaimed for 30 days are donated. Only registered attendees can claim.",
                f"Attendee {name} claims found {desc}.",
                pa.label,
                f"You are {name}. You lost something and want to check if it was found. {pa.instructions}",
                f"I lost a {desc.lower()} and I'm wondering if it was turned in to lost and found.",
                f"Your name is {name}. You lost a {desc.lower()}.",
                "You don't know the item ID.",
                f"Attendee {name} asks about {desc}. Agent should search and claim {iid}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"claim_lost_{i + 1}b",
                "Test lost item claim with vague description",
                "Items unclaimed for 30 days are donated. Only registered attendees can claim.",
                f"Attendee {name} vaguely describes lost item.",
                pb.label,
                f"You are {name}. You lost something at the festival. {pb.instructions}",
                f"I think I lost something... {vdesc}. I'm not sure where exactly.",
                f"Your name is {name}. You lost: {vdesc}.",
                "You don't remember exactly where or when you lost it.",
                f"Attendee {name} vaguely describes item matching '{desc}'. Agent should search and claim.",
                [
                    action(
                        "claim_1",
                        "claim_lost_item",
                        {"item_id": iid, "attendee_id": aid},
                        f"Claim item {iid}",
                        compare_args=["item_id", "attendee_id"],
                    )
                ],
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_add_accessibility(db, ix, n=4):
    """Add accessibility needs. Single variant."""
    tasks = []
    # Pick attendees without accessibility notes
    eligible = [
        aid
        for aid in ix.attendees_with_valid_tickets
        if not db["attendees"][aid]["accessibility_needs"]
    ]
    random.shuffle(eligible)

    needs_list = [
        (
            "wheelchair",
            "I use a wheelchair and need accessible viewing areas and paths",
        ),
        (
            "hearing",
            "I'm hearing impaired and would like ASL interpreter info for performances",
        ),
        (
            "mobility",
            "I have limited mobility and need close parking and accessible routes",
        ),
        ("visual", "I have a visual impairment and may need guided assistance"),
    ]

    for i, aid in enumerate(eligible[:n]):
        name = attendee_name(db, aid)
        need_label, need_desc = needs_list[i % len(needs_list)]
        track_use(aid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"add_accessibility_{i + 1}",
                "Test recording accessibility needs",
                "Festival offers accessible areas, ASL interpreters, accessible camping. Record on profile.",
                f"Attendee {name} needs {need_label} accommodations.",
                pa.label,
                f"You are {name}. You have accessibility needs for the festival. {pa.instructions}",
                f"{need_desc}.",
                f"Your name is {name}. Your need: {need_desc}.",
                "You don't know what accommodations are available.",
                f"Attendee {name} needs {need_label} accommodation recorded.",
                [
                    action(
                        "accessibility_1",
                        "add_accessibility_note",
                        {"attendee_id": aid, "needs": need_desc},
                        f"Record {need_label} needs",
                        compare_args=["attendee_id"],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_issue_credits(db, ix, n=4):
    """Issue festival credits. Single variant."""
    tasks = []
    eligible = list(ix.attendees_with_valid_tickets)
    random.shuffle(eligible)

    complaints = [
        (25.0, "Sound system failure during performance I was waiting hours for"),
        (15.0, "Vendor overcharged me for food and couldn't fix it"),
        (30.0, "VIP area was closed for an hour during my visit"),
        (20.0, "Shuttle was severely delayed, missed first hour of festival"),
        (50.0, "Camping area flooded and had to relocate"),
    ]

    for i, aid in enumerate(eligible[:n]):
        name = attendee_name(db, aid)
        amount, reason = complaints[i % len(complaints)]
        track_use(aid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"issue_credits_{i + 1}",
                "Test issuing festival credits for service issue",
                "Max $50 per incident. Non-transferable.",
                f"Attendee {name} compensated ${amount:.2f} for: {reason}.",
                pa.label,
                f"You are {name}. You had a bad experience. {pa.instructions}",
                f"{reason}. I think I deserve some compensation.",
                f"Your name is {name}. Your complaint: {reason}.",
                "You don't know how much you'll receive or the credit system.",
                f"Attendee {name} complains about: {reason}. Issue ${amount:.2f} credits.",
                [
                    action(
                        "credits_1",
                        "issue_festival_credits",
                        {"attendee_id": aid, "amount": amount, "reason": reason},
                        f"Issue ${amount:.2f} credits",
                        compare_args=["attendee_id"],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


# =========================================================================
# Tier 2: Information & Search Generators
# =========================================================================


def gen_schedule_by_day(db, ix, n=3):
    """Look up schedule by day. n bases -> 2n tasks."""
    tasks = []
    days = [("fri", "Friday"), ("sat", "Saturday"), ("sun", "Sunday")]

    for i in range(min(n, len(days))):
        day_code, day_label = days[i]

        acts = [
            action(
                "schedule_1",
                "get_schedule",
                {"day": day_code},
                f"Get {day_label} schedule",
                compare_args=["day"],
            )
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"schedule_day_{i + 1}a",
                f"Test schedule lookup for {day_label}",
                "get_schedule supports filtering by day, stage, genre.",
                f"Attendee asks for {day_label} lineup.",
                pa.label,
                f"You are a festival attendee checking the schedule. {pa.instructions}",
                f"Can you show me the full lineup for {day_label}?",
                f"You want to see {day_label}'s performances.",
                "You don't know artist names or stage assignments.",
                f"Attendee asks for {day_label} schedule.",
                acts,
                reward_basis=["ACTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"schedule_day_{i + 1}b",
                f"Test schedule lookup with vague day reference",
                "get_schedule supports filtering by day, stage, genre.",
                f"Attendee vaguely asks about {day_label}.",
                pb.label,
                f"You are a festival attendee. {pb.instructions}",
                f"What's happening on the {'first' if i == 0 else 'second' if i == 1 else 'last'} day of the festival?",
                f"You want {day_label}'s schedule but refer to it as the {'first' if i == 0 else 'second' if i == 1 else 'last'} day.",
                "You don't know it's called {day_label} specifically.",
                f"Attendee asks about {'first' if i == 0 else 'second' if i == 1 else 'last'} day. Agent should map to {day_code}.",
                acts,
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_schedule_by_genre(db, ix, n=4):
    """Look up schedule by genre. Single variant."""
    tasks = []
    genres = ["electronic", "rock", "folk", "jazz"]

    for i, genre in enumerate(genres[:n]):
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"schedule_genre_{i + 1}",
                f"Test schedule search by genre ({genre})",
                "get_schedule supports filtering by genre.",
                f"Attendee searches for {genre} performances.",
                pa.label,
                f"You are a festival attendee who loves {genre} music. {pa.instructions}",
                f"I'm mainly into {genre}. What {genre} acts are playing this weekend?",
                f"You want to see all {genre} performances.",
                "You don't know specific artist names.",
                f"Attendee asks about {genre} acts.",
                [
                    action(
                        "schedule_1",
                        "get_schedule",
                        {"genre": genre},
                        f"Search {genre} performances",
                        compare_args=["genre"],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_vendor_search(db, ix, n=3):
    """Search vendors by type. Single variant."""
    tasks = []
    types_with_labels = [("food", "food"), ("merch", "merchandise"), ("art", "art")]

    for i, (vtype, vlabel) in enumerate(types_with_labels[:n]):
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"vendor_search_{i + 1}",
                f"Test vendor search for {vlabel}",
                "list_vendors supports type filtering.",
                f"Attendee looks for {vlabel} vendors.",
                pa.label,
                f"You are a festival attendee looking for {vlabel}. {pa.instructions}",
                f"Where can I find {vlabel} vendors at the festival?",
                f"You want {vlabel} vendor locations.",
                "You don't know specific vendor names.",
                f"Attendee asks about {vlabel} vendors.",
                [
                    action(
                        "vendors_1",
                        "list_vendors",
                        {"type": vtype},
                        f"List {vlabel} vendors",
                        compare_args=["type"],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_shuttle_info(db, ix, n=3):
    """Get shuttle schedule info. Single variant."""
    tasks = []
    routes = ["Downtown", "Airport", "Parking"]

    for i, route_keyword in enumerate(routes[:n]):
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"shuttle_info_{i + 1}",
                f"Test shuttle schedule lookup ({route_keyword})",
                "get_shuttle_schedule supports route filtering.",
                f"Attendee asks about {route_keyword} shuttle.",
                pa.label,
                f"You are a festival attendee needing transportation. {pa.instructions}",
                f"What times does the {route_keyword.lower()} shuttle run?",
                f"You want {route_keyword} shuttle schedule.",
                "You don't know specific departure times.",
                f"Attendee asks about {route_keyword} shuttle times.",
                [
                    action(
                        "shuttle_1",
                        "get_shuttle_schedule",
                        {"route": route_keyword.lower()},
                        f"Get {route_keyword} shuttle schedule",
                        compare_args=["route"],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_check_ticket_availability(db, ix, n=3):
    """Check ticket availability. n bases -> 2n tasks."""
    tasks = []
    queries = [
        ("day_pass", "sat", "Saturday day pass"),
        ("weekend", "all", "weekend pass"),
        ("vip", "all", "VIP pass"),
    ]

    for i, (ttype, day, label) in enumerate(queries[:n]):
        acts = [
            action(
                "avail_1",
                "check_ticket_availability",
                {"type": ttype, "day": day},
                f"Check {label} availability",
                compare_args=["type", "day"],
            )
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"ticket_avail_{i + 1}a",
                f"Test ticket availability check for {label}",
                "check_ticket_availability shows remaining tickets by type and day.",
                f"Attendee checks if {label} tickets are still available.",
                pa.label,
                f"You are someone interested in the festival. {pa.instructions}",
                f"Are there still {label} tickets available?",
                f"You want to know about {label} availability.",
                "You don't know current capacity or how many are sold.",
                f"Attendee checks {label} availability.",
                acts,
                reward_basis=["ACTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"ticket_avail_{i + 1}b",
                f"Test ticket availability with vague request",
                "check_ticket_availability shows remaining tickets by type and day.",
                f"Attendee vaguely asks about {label}.",
                pb.label,
                f"You are someone considering attending. {pb.instructions}",
                f"Is it too late to get tickets for the festival? I was thinking about the {label}...",
                f"You want {label} but aren't sure what's available.",
                "You don't know ticket types, pricing, or availability.",
                f"Attendee vaguely asks about tickets. Agent should check {ttype}/{day} availability.",
                acts,
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_list_attendee_tickets(db, ix, n=3):
    """List an attendee's tickets. n bases -> 2n tasks."""
    tasks = []
    eligible = [
        aid
        for aid in ix.attendees_with_valid_tickets
        if len(db["attendees"][aid]["ticket_ids"]) >= 1
    ]
    random.shuffle(eligible)

    for i, aid in enumerate(eligible[:n]):
        name = attendee_name(db, aid)
        n_tickets = len(db["attendees"][aid]["ticket_ids"])
        track_use(aid)

        acts = [
            action(
                "find_1",
                "find_attendee_by_name",
                {"name": name},
                f"Find attendee {name}",
                compare_args=[],
            ),
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"list_tickets_{i + 1}a",
                "Test listing attendee's tickets",
                "Find attendee and display ticket information.",
                f"Attendee {name} asks about their tickets.",
                pa.label,
                f"You are {name}. You want to check your ticket details. {pa.instructions}",
                "I want to see what tickets I have for the festival.",
                f"Your name is {name}.",
                "You don't know your ticket IDs or exact ticket type.",
                f"Attendee {name} wants to see their {n_tickets} ticket(s).",
                acts,
                nl_assertions=[
                    f"The agent provided information about the attendee's {n_tickets} ticket(s)"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"list_tickets_{i + 1}b",
                "Test listing tickets with vague request",
                "Find attendee and display ticket information.",
                f"Attendee {name} vaguely asks about their account.",
                pb.label,
                f"You are {name}. {pb.instructions}",
                "Can you pull up my festival account? I need to check something about my tickets.",
                f"Your name is {name}.",
                "You don't know your attendee ID or ticket details.",
                f"Attendee {name} vaguely asks about account. Agent should find and show tickets.",
                acts,
                nl_assertions=[
                    f"The agent provided information about the attendee's {n_tickets} ticket(s)"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


# =========================================================================
# Tier 3: Multi-step Generators
# =========================================================================


def gen_upgrade_and_modify_camping(db, ix, n=3):
    """Upgrade to VIP + modify camping to VIP zone. n bases -> 2n tasks."""
    tasks = []
    # Find attendees with non-VIP tickets and camping
    eligible = []
    for crid in ix.non_vip_camping:
        cr = db["camping_reservations"][crid]
        aid = cr["attendee_id"]
        # Find an upgradeable ticket for this attendee
        for tid in db["attendees"][aid].get("ticket_ids", []):
            if (
                tid in db["tickets"]
                and db["tickets"][tid]["status"] == "valid"
                and db["tickets"][tid]["type"] in ("day_pass", "weekend")
            ):
                eligible.append((tid, crid, aid))
                break
    random.shuffle(eligible)

    for i, (tid, crid, aid) in enumerate(eligible[:n]):
        t = db["tickets"][tid]
        name = attendee_name(db, aid)
        pmid = t["payment_method_id"]
        old_type = t["type"]
        old_zone = db["camping_reservations"][crid]["zone"]
        track_use(aid)
        track_use(tid)
        track_use(crid)

        acts = [
            action(
                "upgrade_1",
                "upgrade_ticket",
                {"ticket_id": tid, "new_type": "vip", "payment_method_id": pmid},
                f"Upgrade to VIP",
                compare_args=["ticket_id", "new_type"],
            ),
            action(
                "modify_camp_1",
                "modify_camping",
                {"reservation_id": crid, "zone": "vip"},
                f"Move camping to VIP zone",
                compare_args=["reservation_id", "zone"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_ticket_type", {"ticket_id": tid, "expected_type": "vip"}
            ),
            env_assert(
                "assert_camping_zone", {"reservation_id": crid, "expected_zone": "vip"}
            ),
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"upgrade_vip_camping_{i + 1}a",
                "Test VIP upgrade + camping zone change (multi-step)",
                "VIP camping requires VIP ticket. Must upgrade ticket first.",
                f"Attendee {name} wants full VIP experience: ticket + camping.",
                pa.label,
                f"You are {name}. You want to go all-in on VIP. {pa.instructions}",
                f"I want to upgrade to VIP and also move my camping to the VIP zone.",
                f"Your name is {name}. You have a {ticket_type_label(old_type)} and {old_zone} camping.",
                "You don't know IDs or that VIP camping requires VIP ticket.",
                f"Attendee {name} wants VIP upgrade + VIP camping. Agent must do both.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"upgrade_vip_camping_{i + 1}b",
                "Test VIP upgrade + camping with vague request",
                "VIP camping requires VIP ticket. Must upgrade ticket first.",
                f"Attendee {name} vaguely wants 'the best of everything'.",
                pb.label,
                f"You are {name}. You want the premium experience. {pb.instructions}",
                f"I want the best experience you have... VIP everything. What do I need to do?",
                f"Your name is {name}.",
                "You don't know what VIP includes or what steps are needed.",
                f"Attendee {name} wants premium upgrade. Agent should upgrade ticket + move camping.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_search_and_claim_lost(db, ix, n=4):
    """Search lost items then claim. Reuses gen_claim_lost_item above — this is
    for the multi-step index that includes the search action."""
    # Already covered by claim_lost tasks which include search action
    return []


def gen_refund_and_cancel_camping(db, ix, n=3):
    """Refund ticket + cancel camping. n bases -> 2n tasks."""
    tasks = []
    # Find attendees with both valid ticket and camping
    eligible = []
    for crid in ix.reserved_camping:
        cr = db["camping_reservations"][crid]
        aid = cr["attendee_id"]
        for tid in db["attendees"][aid].get("ticket_ids", []):
            if tid in db["tickets"] and db["tickets"][tid]["status"] == "valid":
                eligible.append((tid, crid, aid))
                break
    random.shuffle(eligible)

    for i, (tid, crid, aid) in enumerate(eligible[:n]):
        name = attendee_name(db, aid)
        ttype = db["tickets"][tid]["type"]
        zone = db["camping_reservations"][crid]["zone"]
        track_use(aid)
        track_use(tid)
        track_use(crid)

        acts = [
            action(
                "refund_1",
                "refund_ticket",
                {"ticket_id": tid, "reason": "Cannot attend"},
                f"Refund ticket {tid}",
                compare_args=["ticket_id"],
            ),
            action(
                "cancel_camp_1",
                "cancel_camping",
                {"reservation_id": crid},
                f"Cancel camping {crid}",
            ),
        ]
        asserts = [
            env_assert(
                "assert_ticket_status",
                {"ticket_id": tid, "expected_status": "refunded"},
            ),
            env_assert(
                "assert_camping_status",
                {"reservation_id": crid, "expected_status": "cancelled"},
            ),
        ]

        # Variant A
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"refund_and_cancel_{i + 1}a",
                "Test ticket refund + camping cancellation (multi-step)",
                "Refund policy: 14+ days full, 7-13 days 50%, <7 none. Camping follows same.",
                f"Attendee {name} can't attend — needs full cancellation.",
                pa.label,
                f"You are {name}. You can no longer attend. {pa.instructions}",
                f"I need to cancel everything — my ticket and my camping reservation. Something came up.",
                f"Your name is {name}. You have a {ticket_type_label(ttype)} and {zone} zone camping.",
                "You don't know IDs or refund amounts.",
                f"Attendee {name} needs full cancellation: ticket {tid} + camping {crid}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"refund_and_cancel_{i + 1}b",
                "Test full cancellation with emotional interaction",
                "Refund policy: 14+ days full, 7-13 days 50%, <7 none.",
                f"Attendee {name} upset about needing to cancel.",
                pb.label,
                f"You are {name}. Something went wrong and you can't attend. {pb.instructions}",
                f"I can't go anymore... I need everything cancelled. My ticket, my campsite, everything.",
                f"Your name is {name}.",
                "You're emotional and don't provide organized details. Agent must piece it together.",
                f"Attendee {name} wants full cancellation. Agent should refund ticket + cancel camping.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_transfer_and_credits(db, ix, n=3):
    """Transfer ticket + issue credits for inconvenience. n bases -> tasks."""
    tasks = []
    eligible = [tid for tid in ix.valid_tickets if tid in ix.transfer_targets]
    random.shuffle(eligible)

    for i, tid in enumerate(eligible[:n]):
        t = db["tickets"][tid]
        aid = t["attendee_id"]
        name = attendee_name(db, aid)
        target_aid = ix.transfer_targets[tid]
        target_email = db["attendees"][target_aid]["email"]
        target_name = attendee_name(db, target_aid)
        track_use(aid)
        track_use(tid)

        acts = [
            action(
                "transfer_1",
                "transfer_ticket",
                {"ticket_id": tid, "new_attendee_email": target_email},
                f"Transfer ticket to {target_name}",
                compare_args=["ticket_id", "new_attendee_email"],
            ),
            action(
                "credits_1",
                "issue_festival_credits",
                {
                    "attendee_id": aid,
                    "amount": 20.0,
                    "reason": "Vendor equipment malfunction",
                },
                f"Issue credits for vendor equipment failure",
                compare_args=["attendee_id"],
            ),
        ]

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"transfer_credits_{i + 1}",
                "Test ticket transfer + credits for service issue",
                "Transfers: once per ticket, both registered. Credits: max $50, non-transferable.",
                f"Attendee {name} transfers ticket and receives compensation.",
                pa.label,
                f"You are {name}. You need to transfer your ticket because a vendor issue ruined your experience. {pa.instructions}",
                f"I need to transfer my ticket to {target_name} ({target_email}). Also, there was a vendor equipment malfunction at the festival that affected me — can I get some compensation for that?",
                f"Your name is {name}. Friend: {target_name} ({target_email}). You experienced a vendor equipment failure.",
                "You don't know your ticket ID or the credit policy.",
                f"Transfer ticket {tid} to {target_name}, then issue $20 credits for vendor equipment failure.",
                acts,
                reward_basis=["ACTION"],
            )
        )
    return tasks


# =========================================================================
# Tier 4: Complex Multi-step
# =========================================================================


def gen_upgrade_transfer_camping(db, ix, n=2):
    """Upgrade + transfer old ticket + modify camping. Complex multi-step."""
    # This is the most complex scenario — handled by the multi-step above
    return []


# =========================================================================
# Tier 5: Edge Cases & Policy Violations
# =========================================================================


def gen_refund_too_late(db, ix, n=3):
    """Attempt refund too close to festival. Should be denied."""
    # Festival starts 2025-10-24, today is 2025-10-15 = 9 days away
    # So we're in the 50% window (7-13 days). These refunds should succeed at 50%.
    # For true denials, we'd need to be < 7 days. Instead, test the policy explanation.
    tasks = []
    eligible = list(ix.valid_tickets)
    random.shuffle(eligible)

    for i, tid in enumerate(eligible[:n]):
        t = db["tickets"][tid]
        aid = t["attendee_id"]
        name = attendee_name(db, aid)
        ttype = t["type"]
        track_use(aid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"refund_policy_info_{i + 1}",
                "Test refund with explanation of partial refund policy",
                "14+ days: full. 7-13 days: 50%. <7: none. Today is 9 days before.",
                f"Attendee {name} asks about refund. Should be told 50% refund.",
                pa.label,
                f"You are {name}. You want a refund but want to know how much you'll get back. {pa.instructions}",
                f"I need to cancel my {ticket_type_label(ttype)}. How much of a refund will I get?",
                f"Your name is {name}. You have a {ticket_type_label(ttype)}.",
                "You want to know the refund amount before proceeding.",
                f"Attendee asks about refund amount. Festival is 9 days away — 50% refund applies.",
                [
                    action(
                        "refund_1",
                        "refund_ticket",
                        {"ticket_id": tid, "reason": "Cannot attend"},
                        f"Refund ticket {tid} at 50%",
                        compare_args=["ticket_id"],
                    )
                ],
                nl_assertions=[
                    "The agent informed the attendee that they will receive a 50% refund (since the festival is 7-13 days away)"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_transfer_already_transferred(db, ix, n=2):
    """Attempt to transfer an already-transferred ticket. Should be denied."""
    tasks = []
    eligible = list(ix.transferred_tickets)
    random.shuffle(eligible)

    for i, tid in enumerate(eligible[:n]):
        t = db["tickets"][tid]
        aid = t["attendee_id"]
        name = attendee_name(db, aid)
        track_use(aid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"transfer_denied_{i + 1}",
                "Test transfer denial for already-transferred ticket",
                "Each ticket can only be transferred once.",
                f"Attendee {name} tries to transfer already-transferred ticket.",
                pa.label,
                f"You are {name}. You received a transferred ticket and want to pass it on. {pa.instructions}",
                f"I got a ticket transferred to me, but now I can't go either. Can I transfer it to someone else?",
                f"Your name is {name}. Your ticket was already transferred to you.",
                "You don't know the one-transfer limit.",
                f"Ticket {tid} already transferred. Agent should explain one-transfer policy.",
                [],
                nl_assertions=[
                    "The agent explained that tickets can only be transferred once and this ticket has already been transferred"
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_upgrade_artist_denied(db, ix, n=2):
    """Attempt to upgrade to artist pass. Should be denied."""
    tasks = []
    eligible = list(ix.valid_tickets)
    random.shuffle(eligible)

    for i, tid in enumerate(eligible[:n]):
        t = db["tickets"][tid]
        aid = t["attendee_id"]
        name = attendee_name(db, aid)
        track_use(aid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"upgrade_artist_denied_{i + 1}",
                "Test denial of upgrade to artist pass",
                "Artist passes are by invitation only, not available for purchase.",
                f"Attendee {name} wants artist pass.",
                pa.label,
                f"You are {name}. You want the ultimate festival experience. {pa.instructions}",
                f"I want to upgrade to an artist pass. What would that cost?",
                f"Your name is {name}.",
                "You don't know artist passes aren't purchasable.",
                f"Attendee wants artist pass. Agent should explain it's invitation-only.",
                [],
                nl_assertions=[
                    "The agent explained that artist passes are by invitation only and cannot be purchased or upgraded to"
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_wristband_issue(db, ix, n=2):
    """Wristband issue — must transfer to human. n tasks."""
    tasks = []
    eligible = list(ix.attendees_with_valid_tickets)
    random.shuffle(eligible)

    for i, aid in enumerate(eligible[:n]):
        name = attendee_name(db, aid)
        track_use(aid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"wristband_issue_{i + 1}",
                "Test wristband issue escalation to human agent",
                "Wristband issues must be escalated — agent cannot replace/reissue.",
                f"Attendee {name} has a wristband problem.",
                pa.label,
                f"You are {name}. Your wristband isn't working. {pa.instructions}",
                f"My wristband stopped scanning at the gate. Can you fix it?",
                f"Your name is {name}. Your wristband doesn't work.",
                "You don't know the wristband policy.",
                f"Attendee {name} has wristband issue. Agent should transfer to human.",
                [
                    action(
                        "transfer_1",
                        "transfer_to_human_agents",
                        {
                            "summary": f"Attendee {name} has a non-functioning wristband that needs replacement."
                        },
                        "Transfer to human for wristband issue",
                        compare_args=[],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_age_restriction_info(db, ix, n=3):
    """Ask about age-restricted performances. n bases -> 2n tasks."""
    tasks = []
    restricted = list(ix.age_restricted_performances)
    random.shuffle(restricted)

    for i, pid in enumerate(restricted[:n]):
        perf = db["performances"][pid]
        artist = perf["artist_name"]
        restriction = perf["age_restriction"]
        day = perf["day"]

        acts = [
            action(
                "schedule_1",
                "get_schedule",
                {"day": day},
                f"Get {day} schedule",
                compare_args=[],
            ),
        ]

        # Variant A: Direct question about specific artist
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"age_restriction_{i + 1}a",
                "Test age restriction information for specific performance",
                "Age-restricted shows require ID verification at venue. Agent can't verify age.",
                f"Attendee asks about {artist}'s age restriction ({restriction}).",
                pa.label,
                f"You are a festival attendee. You're interested in {artist}. {pa.instructions}",
                f"Is {artist}'s show age-restricted? My teenager wants to go.",
                f"You want to know about age restrictions for {artist}.",
                "You don't know the restriction level or verification process.",
                f"Attendee asks about {artist} ({restriction}). Agent should inform about restriction and ID check at entrance.",
                acts,
                nl_assertions=[
                    f"The agent informed the attendee that {artist}'s performance is {restriction} and requires ID verification at the venue"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )

        # Variant B: Vague question about safe shows for teens
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"age_restriction_{i + 1}b",
                "Test age restriction query with worried parent",
                "Age-restricted shows require ID verification at venue. Agent can't verify age.",
                f"Parent asks about which shows are safe for teens.",
                pb.label,
                f"You are a parent attending with your 16-year-old. {pb.instructions}",
                f"I'm here with my teenager and I want to make sure we don't end up at a show that's not appropriate. Which ones on {day} should we avoid?",
                f"You have a 16-year-old and want to know about age-restricted shows on {day}.",
                "You don't know which shows are restricted or the restriction types.",
                f"Parent asks about {day} age restrictions. Agent should list restricted shows.",
                acts,
                nl_assertions=[
                    f"The agent provided information about age-restricted performances on {day}"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_vip_camping_denied(db, ix, n=2):
    """Attempt VIP camping without VIP ticket. Should be denied."""
    tasks = []
    # Find non-VIP attendees with camping
    eligible = []
    for crid in ix.non_vip_camping:
        cr = db["camping_reservations"][crid]
        aid = cr["attendee_id"]
        has_vip = any(
            db["tickets"][tid]["type"] == "vip"
            for tid in db["attendees"][aid].get("ticket_ids", [])
            if tid in db["tickets"]
        )
        if not has_vip:
            eligible.append((crid, aid))
    random.shuffle(eligible)

    for i, (crid, aid) in enumerate(eligible[:n]):
        name = attendee_name(db, aid)
        track_use(aid)

        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"vip_camping_denied_{i + 1}",
                "Test VIP camping denial without VIP ticket",
                "VIP camping zone requires VIP ticket.",
                f"Attendee {name} wants VIP camping but doesn't have VIP ticket.",
                pa.label,
                f"You are {name}. You want the VIP camping experience. {pa.instructions}",
                f"Can I switch my camping to the VIP zone?",
                f"Your name is {name}. You have a non-VIP ticket.",
                "You don't know VIP camping requires a VIP ticket.",
                f"Attendee {name} wants VIP camping but lacks VIP ticket. Agent should explain requirement.",
                [],
                nl_assertions=[
                    "The agent explained that VIP camping requires a VIP ticket"
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_weather_cancellation(db, ix, n=2):
    """Ask about weather cancellation policy. Should explain org handles it."""
    tasks = []
    eligible = list(ix.attendees_with_valid_tickets)
    random.shuffle(eligible)

    for i, aid in enumerate(eligible[:n]):
        name = attendee_name(db, aid)
        track_use(aid)

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"weather_policy_{i + 1}",
                "Test weather cancellation policy explanation",
                "Weather cancellations handled by org, not agent.",
                f"Attendee {name} worried about weather.",
                pb.label,
                f"You are {name}. You're worried about rain at the festival. {pb.instructions}",
                f"What happens if the festival gets rained out? Do I get a refund?",
                f"Your name is {name}.",
                "You don't know the weather policy.",
                f"Attendee asks about weather policy. Agent should explain org handles it.",
                [],
                nl_assertions=[
                    "The agent explained that weather cancellations are handled by the festival organization"
                ],
                reward_basis=["NL_ASSERTION"],
            )
        )
    return tasks


def gen_credits_over_limit(db, ix, n=2):
    """Request credits over $50 limit. Should be denied or capped."""
    tasks = []
    eligible = list(ix.attendees_with_valid_tickets)
    random.shuffle(eligible)

    for i, aid in enumerate(eligible[:n]):
        name = attendee_name(db, aid)
        track_use(aid)

        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"credits_over_limit_{i + 1}",
                "Test festival credits over $50 limit",
                "Max $50 per incident. Agent should explain limit.",
                f"Attendee {name} demands excessive credits.",
                pb.label,
                f"You are {name}. You had a terrible experience. {pb.instructions}",
                f"I want $100 in festival credits! The sound system ruined the entire show I was most excited about!",
                f"Your name is {name}. You want $100 in credits.",
                "You don't know the $50 limit. When told, reluctantly accept $50.",
                f"Attendee wants $100 credits. Agent should explain $50 max, issue $50.",
                [
                    action(
                        "credits_1",
                        "issue_festival_credits",
                        {
                            "attendee_id": aid,
                            "amount": 50.0,
                            "reason": "Sound system failure during performance",
                        },
                        "Issue maximum $50 credits",
                        compare_args=["attendee_id"],
                    )
                ],
                nl_assertions=[
                    "The agent explained that the maximum festival credit per incident is $50"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


# =========================================================================
# Generate All Tasks
# =========================================================================


def generate_all(db: dict) -> list[dict]:
    random.seed(SEED)
    ix = build_indexes(db)
    tasks = []

    # Tier 1: Simple single-action (~95 tasks)
    tasks += gen_ticket_upgrade_day_to_weekend(db, ix, n=8)  # 16
    tasks += gen_ticket_upgrade_to_vip(db, ix, n=5)  # 10
    tasks += gen_ticket_refund(db, ix, n=8)  # 16
    tasks += gen_ticket_transfer(db, ix, n=7)  # 14
    tasks += gen_cancel_camping(db, ix, n=6)  # 12
    tasks += gen_modify_camping_zone(db, ix, n=5)  # 10
    tasks += gen_report_lost_item(db, ix, n=7)  # 7
    tasks += gen_claim_lost_item(db, ix, n=5)  # 10

    # Tier 2: Info & search (~48 tasks)
    tasks += gen_schedule_by_day(db, ix, n=3)  # 6
    tasks += gen_schedule_by_genre(db, ix, n=4)  # 4
    tasks += gen_vendor_search(db, ix, n=3)  # 3
    tasks += gen_shuttle_info(db, ix, n=3)  # 3
    tasks += gen_check_ticket_availability(db, ix, n=3)  # 6
    tasks += gen_list_attendee_tickets(db, ix, n=5)  # 10
    tasks += gen_add_accessibility(db, ix, n=4)  # 4
    tasks += gen_issue_credits(db, ix, n=5)  # 5

    # Tier 3: Multi-step (~25 tasks)
    tasks += gen_upgrade_and_modify_camping(db, ix, n=3)  # 6
    tasks += gen_refund_and_cancel_camping(db, ix, n=4)  # 8
    tasks += gen_transfer_and_credits(db, ix, n=5)  # 5

    # Tier 5: Edge cases & policy violations (~35 tasks)
    tasks += gen_refund_too_late(db, ix, n=4)  # 4
    tasks += gen_transfer_already_transferred(db, ix, n=3)  # 3
    tasks += gen_upgrade_artist_denied(db, ix, n=3)  # 3
    tasks += gen_wristband_issue(db, ix, n=3)  # 3
    tasks += gen_age_restriction_info(db, ix, n=4)  # 8
    tasks += gen_vip_camping_denied(db, ix, n=2)  # 2
    tasks += gen_weather_cancellation(db, ix, n=3)  # 3
    tasks += gen_credits_over_limit(db, ix, n=3)  # 3

    return tasks


def write_splits(tasks: list[dict]) -> dict:
    all_ids = [t["id"] for t in tasks]
    easy_ids = [
        tid
        for tid in all_ids
        if tid.endswith("a") or not any(tid.endswith(c) for c in "ab")
    ]
    hard_ids = [tid for tid in all_ids if tid.endswith("b")]

    splits = {
        "base": all_ids,
        "easy": easy_ids,
        "hard": hard_ids,
    }
    return splits


if __name__ == "__main__":
    import sys

    db = load_db()
    tasks = generate_all(db)

    # Stats
    print(f"\nTotal tasks: {len(tasks)}")

    tier_counts = {"tier1": 0, "tier2": 0, "tier3": 0, "tier5": 0}
    for t in tasks:
        tid = t["id"]
        if any(
            tid.startswith(p)
            for p in [
                "upgrade_day",
                "upgrade_vip_",
                "ticket_refund",
                "ticket_transfer",
                "cancel_camping",
                "modify_camping",
                "report_lost",
                "claim_lost",
            ]
        ):
            tier_counts["tier1"] += 1
        elif any(
            tid.startswith(p)
            for p in [
                "schedule_",
                "vendor_",
                "shuttle_",
                "ticket_avail",
                "list_tickets",
                "add_accessibility",
                "issue_credits",
            ]
        ):
            tier_counts["tier2"] += 1
        elif any(
            tid.startswith(p)
            for p in ["upgrade_vip_camping", "refund_and_cancel", "transfer_credits"]
        ):
            tier_counts["tier3"] += 1
        else:
            tier_counts["tier5"] += 1

    for tier, cnt in tier_counts.items():
        print(f"  {tier}: {cnt}")

    easy = [
        t
        for t in tasks
        if t["id"].endswith("a") or not any(t["id"].endswith(c) for c in "ab")
    ]
    hard = [t for t in tasks if t["id"].endswith("b")]
    print(f"\nEasy/single variants: {len(easy)}")
    print(f"Hard variants: {len(hard)}")

    reward_types = {"ACTION": 0, "ENV_ASSERTION": 0, "NL_ASSERTION": 0}
    for t in tasks:
        for rb in t["evaluation_criteria"]["reward_basis"]:
            reward_types[rb] += 1
    print(f"\nReward basis usage:")
    for rb, cnt in reward_types.items():
        print(f"  {rb}: {cnt}")

    if "--stats" in sys.argv:
        sys.exit(0)

    # Write tasks
    with open(TASKS_PATH, "w") as f:
        json.dump(tasks, f, indent=2)
    print(f"\nWritten {len(tasks)} tasks to {TASKS_PATH}")

    # Write splits
    splits = write_splits(tasks)
    with open(SPLIT_TASKS_PATH, "w") as f:
        json.dump(splits, f, indent=2)
    print(f"Written splits to {SPLIT_TASKS_PATH}")
    for split_name, ids in splits.items():
        print(f"  {split_name}: {len(ids)} tasks")
