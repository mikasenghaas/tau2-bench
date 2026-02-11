#!/usr/bin/env python3
"""Procedurally generate ~200 library domain tasks from db.json.

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
FINE_CHECKOUT_BLOCK_THRESHOLD = 10.0
MAX_RENEWALS_STANDARD = 2
MAX_RENEWALS_STUDENT = 3

DB_PATH = Path(__file__).parent / "db.json"
TASKS_PATH = Path(__file__).parent / "tasks.json"
SPLIT_TASKS_PATH = Path(__file__).parent / "split_tasks.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_db() -> dict:
    with open(DB_PATH) as f:
        return json.load(f)


def patron_name(db: dict, pid: str) -> str:
    return db["patrons"][pid]["name"]


def book_title(db: dict, bid: str) -> str:
    return db["books"][bid]["title"]


def branch_name(db: dict, brid: str) -> str:
    return db["branches"][brid]["name"]


def copy_book_id(db: dict, cid: str) -> str:
    return db["copies"][cid]["book_id"]


def copy_branch_id(db: dict, cid: str) -> str:
    return db["copies"][cid]["branch_id"]


def max_renewals(db: dict, patron_id: str) -> int:
    mtype = db["patrons"][patron_id]["membership_type"]
    return MAX_RENEWALS_STUDENT if mtype == "student" else MAX_RENEWALS_STANDARD


def book_has_pending_hold(db: dict, book_id: str) -> bool:
    return any(
        h["book_id"] == book_id and h["status"] == "pending"
        for h in db["holds"].values()
    )


def patron_is_active(db: dict, pid: str) -> bool:
    return db["patrons"][pid]["membership_expiry"] >= TODAY


def patron_can_checkout(db: dict, pid: str) -> bool:
    p = db["patrons"][pid]
    return (
        p["membership_expiry"] >= TODAY
        and p["fines_owed"] <= FINE_CHECKOUT_BLOCK_THRESHOLD
        and len(p["active_loans"]) < p["borrowing_limit"]
    )


# ---------------------------------------------------------------------------
# Entity Indexes
# ---------------------------------------------------------------------------


@dataclass
class EntityIndexes:
    active_patrons: list = field(default_factory=list)
    expired_patrons: list = field(default_factory=list)
    patrons_with_fines_blocking: list = field(default_factory=list)
    patrons_with_outstanding_fines: list = field(default_factory=list)
    patrons_at_limit: list = field(default_factory=list)
    patrons_below_limit: list = field(default_factory=list)
    patrons_no_fines_active: list = field(default_factory=list)

    available_copies: list = field(default_factory=list)
    checked_out_copies: list = field(default_factory=list)
    unavailable_copies: list = field(default_factory=list)

    active_loans: list = field(default_factory=list)
    overdue_active_loans: list = field(default_factory=list)
    not_overdue_active_loans: list = field(default_factory=list)
    renewable_loans: list = field(default_factory=list)
    max_renewal_loans: list = field(default_factory=list)
    hold_blocked_loans: list = field(default_factory=list)

    pending_holds: list = field(default_factory=list)
    ready_holds: list = field(default_factory=list)
    cancellable_holds: list = field(default_factory=list)

    outstanding_fines: list = field(default_factory=list)
    waiver_eligible_fines: list = field(default_factory=list)
    waiver_ineligible_fines: list = field(default_factory=list)

    upcoming_events_with_capacity: list = field(default_factory=list)
    full_events: list = field(default_factory=list)
    cancelled_events: list = field(default_factory=list)
    completed_events: list = field(default_factory=list)

    books_all_out_at_branch: dict = field(default_factory=dict)
    available_copies_by_book_branch: dict = field(default_factory=dict)


def build_indexes(db: dict) -> EntityIndexes:
    ix = EntityIndexes()

    for pid, p in db["patrons"].items():
        if p["membership_expiry"] >= TODAY:
            ix.active_patrons.append(pid)
            if len(p["active_loans"]) >= p["borrowing_limit"]:
                ix.patrons_at_limit.append(pid)
            else:
                ix.patrons_below_limit.append(pid)
            if p["fines_owed"] == 0.0:
                ix.patrons_no_fines_active.append(pid)
        else:
            ix.expired_patrons.append(pid)

        if p["fines_owed"] > FINE_CHECKOUT_BLOCK_THRESHOLD:
            ix.patrons_with_fines_blocking.append(pid)
        if 0 < p["fines_owed"] <= FINE_CHECKOUT_BLOCK_THRESHOLD:
            ix.patrons_with_outstanding_fines.append(pid)

    for cid, c in db["copies"].items():
        if c["status"] == "available":
            ix.available_copies.append(cid)
        elif c["status"] == "checked_out":
            ix.checked_out_copies.append(cid)
        else:
            ix.unavailable_copies.append(cid)

    for lid, loan in db["loans"].items():
        if loan["return_date"] is not None:
            continue
        ix.active_loans.append(lid)
        if loan["due_date"] < TODAY:
            ix.overdue_active_loans.append(lid)
        else:
            ix.not_overdue_active_loans.append(lid)

        patron_id = loan["patron_id"]
        copy = db["copies"][loan["copy_id"]]
        book_id = copy["book_id"]
        mr = max_renewals(db, patron_id)
        has_hold = book_has_pending_hold(db, book_id)

        if loan["renewals_count"] >= mr:
            ix.max_renewal_loans.append(lid)
        elif has_hold:
            ix.hold_blocked_loans.append(lid)
        else:
            ix.renewable_loans.append(lid)

    for hid, h in db["holds"].items():
        if h["status"] == "pending":
            ix.pending_holds.append(hid)
            ix.cancellable_holds.append(hid)
        elif h["status"] == "ready":
            ix.ready_holds.append(hid)
            ix.cancellable_holds.append(hid)

    for fid, f in db["fines"].items():
        if f["status"] != "outstanding":
            continue
        ix.outstanding_fines.append(fid)
        other = [
            f2
            for f2 in db["fines"].values()
            if f2["patron_id"] == f["patron_id"] and f2["fine_id"] != fid
        ]
        if not other:
            ix.waiver_eligible_fines.append(fid)
        else:
            ix.waiver_ineligible_fines.append(fid)

    for eid, e in db["events"].items():
        if e["status"] == "upcoming" and len(e["registered_patrons"]) < e["capacity"]:
            ix.upcoming_events_with_capacity.append(eid)
        elif e["status"] == "full":
            ix.full_events.append(eid)
        elif e["status"] == "cancelled":
            ix.cancelled_events.append(eid)
        elif e["status"] == "completed":
            ix.completed_events.append(eid)

    # Book-branch availability
    for book_id, book in db["books"].items():
        by_br: dict[str, list] = {}
        for cid in book["copies"]:
            c = db["copies"][cid]
            by_br.setdefault(c["branch_id"], []).append(c)
        for br, copies in by_br.items():
            avail = [c for c in copies if c["status"] == "available"]
            if avail:
                ix.available_copies_by_book_branch[(book_id, br)] = [
                    c["copy_id"] for c in avail
                ]
            else:
                ix.books_all_out_at_branch[(book_id, br)] = True

    # Filter out patrons with ambiguous (duplicate) names.
    _name_counts: dict[str, list[str]] = {}
    for pid, p in db["patrons"].items():
        _name_counts.setdefault(p["name"], []).append(pid)
    _ambiguous: set[str] = set()
    for _pids in _name_counts.values():
        if len(_pids) > 1:
            _ambiguous.update(_pids)

    def _remove_ambiguous(pids: list) -> list:
        return [pid for pid in pids if pid not in _ambiguous]

    ix.active_patrons = _remove_ambiguous(ix.active_patrons)
    ix.expired_patrons = _remove_ambiguous(ix.expired_patrons)
    ix.patrons_with_fines_blocking = _remove_ambiguous(ix.patrons_with_fines_blocking)
    ix.patrons_with_outstanding_fines = _remove_ambiguous(
        ix.patrons_with_outstanding_fines
    )
    ix.patrons_at_limit = _remove_ambiguous(ix.patrons_at_limit)
    ix.patrons_below_limit = _remove_ambiguous(ix.patrons_below_limit)
    ix.patrons_no_fines_active = _remove_ambiguous(ix.patrons_no_fines_active)

    def _loan_patron(lid):
        return db["loans"][lid]["patron_id"]

    def _fine_patron(fid):
        return db["fines"][fid]["patron_id"]

    def _hold_patron(hid):
        return db["holds"][hid]["patron_id"]

    # Filter out loans where the patron has multiple active loans of the same
    # book.  When a patron has 2+ copies of the same title checked out the
    # agent can't deterministically pick the "right" copy to return/renew,
    # leading to false negatives.
    from collections import Counter as _Counter

    _dup_book_loans: set[str] = set()
    for pid, p in db["patrons"].items():
        book_counts: dict[str, list[str]] = {}
        for lid in p["active_loans"]:
            loan = db["loans"][lid]
            bid = db["copies"][loan["copy_id"]]["book_id"]
            book_counts.setdefault(bid, []).append(lid)
        for bid, lids in book_counts.items():
            if len(lids) > 1:
                _dup_book_loans.update(lids)

    def _is_clean_loan(lid):
        return _loan_patron(lid) not in _ambiguous and lid not in _dup_book_loans

    ix.active_loans = [lid for lid in ix.active_loans if _is_clean_loan(lid)]
    ix.overdue_active_loans = [
        lid for lid in ix.overdue_active_loans if _is_clean_loan(lid)
    ]
    ix.not_overdue_active_loans = [
        lid for lid in ix.not_overdue_active_loans if _is_clean_loan(lid)
    ]
    ix.renewable_loans = [
        lid for lid in ix.renewable_loans if _is_clean_loan(lid)
    ]
    ix.max_renewal_loans = [
        lid for lid in ix.max_renewal_loans if _is_clean_loan(lid)
    ]
    ix.hold_blocked_loans = [
        lid for lid in ix.hold_blocked_loans if _is_clean_loan(lid)
    ]

    ix.outstanding_fines = [
        fid for fid in ix.outstanding_fines if _fine_patron(fid) not in _ambiguous
    ]
    ix.waiver_eligible_fines = [
        fid for fid in ix.waiver_eligible_fines if _fine_patron(fid) not in _ambiguous
    ]
    ix.waiver_ineligible_fines = [
        fid for fid in ix.waiver_ineligible_fines if _fine_patron(fid) not in _ambiguous
    ]

    ix.pending_holds = [
        hid for hid in ix.pending_holds if _hold_patron(hid) not in _ambiguous
    ]
    ix.ready_holds = [
        hid for hid in ix.ready_holds if _hold_patron(hid) not in _ambiguous
    ]
    ix.cancellable_holds = [
        hid for hid in ix.cancellable_holds if _hold_patron(hid) not in _ambiguous
    ]

    return ix


# ---------------------------------------------------------------------------
# Persona System (structured, difficulty-aware)
# ---------------------------------------------------------------------------


@dataclass
class Persona:
    label: str
    instructions: str
    auth: str  # "name" or "card"
    difficulty: str  # "easy", "medium", "hard"


EASY_PERSONAS = [
    Persona(
        "Friendly and direct",
        "Provide all requested information promptly and clearly. Be cooperative and concise.",
        "name",
        "easy",
    ),
    Persona(
        "Polite regular patron",
        "You know the library system well. Provide information concisely and politely.",
        "name",
        "easy",
    ),
]

MEDIUM_PERSONAS = [
    Persona(
        "Casual, provides info gradually",
        "Don't volunteer all information at once. Wait for the agent to ask for specific details before providing them. Answer one question at a time.",
        "name",
        "medium",
    ),
    Persona(
        "Busy professional",
        "You have limited time. Be terse and direct. Give short answers. Omit details you assume the agent can figure out.",
        "name",
        "medium",
    ),
    Persona(
        "Distracted parent",
        "You have kids in the background. Your responses may be slightly scattered. You might answer a question, then go back to add something you forgot.",
        "name",
        "medium",
    ),
]

HARD_PERSONAS = [
    Persona(
        "Vague and uncertain",
        "You don't remember exact titles or details. Describe things from memory using approximate descriptions. Say things like 'I think it was called...' or 'something about...'. You're not sure which branch you want.",
        "name",
        "hard",
    ),
    Persona(
        "Chatty and digressive",
        "You are very chatty and go off-topic. Before answering questions, share anecdotes or small talk. Bury your actual requests in longer statements. The agent needs to extract key information from your chatter.",
        "name",
        "hard",
    ),
    Persona(
        "Frustrated patron",
        "You are frustrated about a previous bad experience. Vent before giving details. Your responses are curt. The agent may need to ask clarifying questions multiple times.",
        "name",
        "hard",
    ),
    Persona(
        "Elderly, unfamiliar with system",
        "You are not very familiar with library terminology or procedures. You might confuse terms (say 'reserve' when you mean 'check out'). You need patient guidance.",
        "name",
        "hard",
    ),
    Persona(
        "Nervous first-timer",
        "You are a nervous first-time library user. You're unsure about procedures and ask the agent to walk you through each step. Express uncertainty frequently.",
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
# Vague book descriptions (for hard variants)
# ---------------------------------------------------------------------------

VAGUE_BOOK_DESCRIPTIONS = {
    "the_great_gatsby": "a classic novel set in the 1920s, about the American Dream and a mysterious wealthy man",
    "to_kill_a_mockingbird": "that famous book about a lawyer in the South defending someone in a trial, told from a child's perspective",
    "pride_and_prejudice": "a Jane Austen novel, the one with Mr. Darcy and Elizabeth",
    "nineteen_eighty_four": "a dystopian novel about surveillance and Big Brother",
    "the_catcher_in_the_rye": "a novel about a teenager wandering around New York City, I think his name was Holden",
    "brave_new_world": "a book about a future society where everyone is controlled, something about soma",
    "the_road": "a really dark novel about a father and son traveling after the world ends",
    "beloved": "a Toni Morrison novel dealing with slavery and its aftermath",
    "intro_to_algorithms": "a big algorithms textbook, I think it's by Cormen or something",
    "organic_chemistry": "an organic chemistry textbook, a thick one",
    "thinking_fast_and_slow": "a book about psychology and decision-making, by Kahneman I think",
    "sapiens": "that popular nonfiction book about the history of humankind",
    "the_elements_of_style": "a writing guide, I think by Strunk and White",
    "a_brief_history_of_time": "a Stephen Hawking book about the universe and black holes",
    "the_selfish_gene": "a biology book by Richard Dawkins about evolution",
    "quantum_computing": "a book about quantum computers, fairly technical",
    "cosmos": "the Carl Sagan book about space and the universe",
    "charlottes_web": "a children's book about a pig and a spider who are friends",
    "goodnight_moon": "that children's bedtime story book with the bunny",
    "where_the_wild_things_are": "a picture book about a boy who sails to an island with monsters",
    "the_very_hungry_caterpillar": "the kids' book about a caterpillar eating through everything",
    "gone_girl": "a thriller about a woman who goes missing, by Gillian Flynn I think",
    "the_girl_with_the_dragon_tattoo": "a Swedish mystery novel about a hacker girl",
    "the_hound_of_the_baskervilles": "a Sherlock Holmes mystery, the one with the scary dog",
    "a_peoples_history": "Howard Zinn's alternative history of America",
    "the_guns_of_august": "a history book about the start of World War I",
    "team_of_rivals": "that book about Abraham Lincoln and his cabinet",
    "steve_jobs": "the Steve Jobs biography by Walter Isaacson",
    "the_diary_of_a_young_girl": "Anne Frank's diary",
    "merriams_dictionary": "a big dictionary, Merriam-Webster I think",
}


def vague_book(bid: str, title: str) -> str:
    return VAGUE_BOOK_DESCRIPTIONS.get(bid, f"a book called something like '{title}'")


# ---------------------------------------------------------------------------
# Payment, entity tracking, task builder
# ---------------------------------------------------------------------------

PAYMENT_METHODS = ["cash", "credit_card", "debit_card"]


def pick_payment() -> str:
    return random.choice(PAYMENT_METHODS)


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
                "domain": "library",
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


def gen_simple_checkout(db, ix, n=8):
    """Simple checkout. n base scenarios → 2n tasks (easy+hard variants)."""
    tasks = []
    eligible = list(
        set(pid for pid in ix.patrons_below_limit if patron_can_checkout(db, pid))
    )
    random.shuffle(eligible)
    # Use book/branch copy lists so we pick the first available copy the model
    # will see from get_book_availability (avoids copy_id mismatch).
    avail_combos = list(ix.available_copies_by_book_branch.items())
    random.shuffle(avail_combos)

    count = 0
    combo_idx = 0
    for pid in eligible:
        if count >= n or combo_idx >= len(avail_combos):
            break
        (bid, brid), copy_ids = avail_combos[combo_idx]
        combo_idx += 1
        cid = copy_ids[0]  # first available copy at this branch
        track_use(pid)
        track_use(cid)
        p = db["patrons"][pid]
        title = book_title(db, bid)
        br = branch_name(db, brid)
        name = p["name"]
        lc = len(p["active_loans"])
        vdesc = vague_book(bid, title)

        acts = [
            action(
                "checkout_1",
                "checkout_book",
                {"patron_id": pid, "copy_id": cid},
                f"Check out {cid} ('{title}') to {name}",
                compare_args=["patron_id", "copy_id"],
            )
        ]
        asserts = [
            env_assert(
                "assert_copy_status", {"copy_id": cid, "expected_status": "checked_out"}
            ),
            env_assert(
                "assert_patron_loan_count", {"patron_id": pid, "expected": lc + 1}
            ),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"simple_checkout_{count + 1}a",
                "Test simple book checkout with eligible patron",
                "Patron must have active membership, fines <= $10, and be below borrowing limit.",
                f"Patron {name} checks out '{title}' at {br}. Straightforward checkout.",
                pa.label,
                f"You are {name}. You want to check out a book from the library. {pa.instructions}",
                f"You'd like to check out '{title}' at the {br}.",
                f"Your name is {name}. You want '{title}' at the {br}.",
                "You don't know the copy ID or your patron ID.",
                f"Patron {name} wants to check out '{title}' at {br}. Patron is eligible.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"simple_checkout_{count + 1}b",
                "Test simple checkout with vague patron request",
                "Patron must have active membership, fines <= $10, and be below borrowing limit.",
                f"Patron {name} vaguely describes '{title}'. Agent must identify the book and process checkout.",
                pb.label,
                f"You are {name}. You want to check out a book. {pb.instructions}",
                f"You're looking for {vdesc}. You're not sure which branch has it.",
                f"Your name is {name}. You vaguely remember the book as {vdesc}.",
                "You don't know the exact title, copy ID, or which branch has it.",
                f"Patron {name} vaguely describes '{title}' as '{vdesc}'. Agent should identify the book, find a copy, and checkout.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
        count += 1
    return tasks


def gen_simple_return(db, ix, n=6):
    """Simple return (not overdue). n bases → 2n tasks."""
    tasks = []
    not_overdue = list(ix.not_overdue_active_loans)
    random.shuffle(not_overdue)

    for i, lid in enumerate(not_overdue[:n]):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        vdesc = vague_book(bid, title)
        track_use(pid)
        track_use(cid)

        acts = [
            action(
                "return_1", "return_book", {"copy_id": cid}, f"Return {cid} ('{title}')"
            )
        ]
        asserts = [
            env_assert(
                "assert_copy_status", {"copy_id": cid, "expected_status": "available"}
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"simple_return_{i + 1}a",
                "Test simple book return (not overdue)",
                "Copy must be checked out. Return processes the loan and makes the copy available.",
                f"Patron {name} returns '{title}'. Not overdue.",
                pa.label,
                f"You are {name}. You want to return a book you borrowed. {pa.instructions}",
                f"You want to return '{title}'.",
                f"Your name is {name}. You have '{title}' checked out.",
                "You don't know the copy ID. The agent should look up your loans.",
                f"Patron {name} wants to return '{title}' (copy {cid}). Not overdue.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"simple_return_{i + 1}b",
                "Test simple return with vague book description",
                "Copy must be checked out. Return processes the loan and makes the copy available.",
                f"Patron {name} vaguely describes '{title}' for return.",
                pb.label,
                f"You are {name}. You want to return a book. {pb.instructions}",
                f"You want to return a book — {vdesc}.",
                f"Your name is {name}. You have a book checked out that you'd describe as {vdesc}.",
                "You don't remember the exact title or copy ID.",
                f"Patron {name} describes '{title}' vaguely as '{vdesc}'. Agent should identify the loan and process return.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_overdue_return(db, ix, n=5):
    """Return overdue book. n bases → 2n tasks."""
    tasks = []
    overdue = list(ix.overdue_active_loans)
    random.shuffle(overdue)

    for i, lid in enumerate(overdue[:n]):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        vdesc = vague_book(bid, title)
        track_use(pid)
        track_use(cid)

        acts = [
            action(
                "return_1",
                "return_book",
                {"copy_id": cid},
                f"Return overdue {cid} ('{title}')",
            )
        ]
        asserts = [
            env_assert(
                "assert_copy_status", {"copy_id": cid, "expected_status": "available"}
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"overdue_return_{i + 1}a",
                "Test return of overdue book (fine generated)",
                "Overdue returns generate fines at $0.25/day, capped at $25.",
                f"Patron {name} returns overdue '{title}' (due {loan['due_date']}).",
                pa.label,
                f"You are {name}. You need to return a book that's overdue. {pa.instructions}",
                f"You want to return '{title}'. You think it might be overdue.",
                f"Your name is {name}. You have '{title}' checked out.",
                "You're not sure exactly how overdue it is or what the fine will be.",
                f"Patron {name} returns overdue '{title}' (copy {cid}, due {loan['due_date']}).",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"overdue_return_{i + 1}b",
                "Test overdue return with vague description",
                "Overdue returns generate fines at $0.25/day, capped at $25.",
                f"Patron {name} vaguely describes overdue '{title}'.",
                pb.label,
                f"You are {name}. You need to return a book that might be overdue. {pb.instructions}",
                f"You have a book to return, something like {vdesc}. You think it might be late.",
                f"Your name is {name}. You have a book that's {vdesc}.",
                "You don't remember the exact title or how overdue it is.",
                f"Patron {name} vaguely describes overdue '{title}' as '{vdesc}'. Agent should identify and return.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_renew_loan(db, ix, n=5):
    """Renew eligible loan. n bases → 2n tasks."""
    tasks = []
    renewable = list(ix.renewable_loans)
    random.shuffle(renewable)

    for i, lid in enumerate(renewable[:n]):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        vdesc = vague_book(bid, title)
        track_use(pid)

        acts = [
            action(
                "renew_1",
                "renew_loan",
                {"loan_id": lid},
                f"Renew loan {lid} for '{title}'",
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"renew_loan_{i + 1}a",
                "Test loan renewal for eligible loan",
                "Loans can be renewed if under max renewals and no pending holds on the book.",
                f"Patron {name} renews '{title}' (renewals: {loan['renewals_count']}).",
                pa.label,
                f"You are {name}. You want to renew a book. {pa.instructions}",
                f"You'd like to renew '{title}' — you need more time with it.",
                f"Your name is {name}. You have '{title}' checked out.",
                "You don't know your loan ID.",
                f"Patron {name} wants to renew '{title}' (loan {lid}). Eligible.",
                acts,
                reward_basis=["ACTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"renew_loan_{i + 1}b",
                "Test loan renewal with vague book reference",
                "Loans can be renewed if under max renewals and no pending holds on the book.",
                f"Patron {name} vaguely describes '{title}' for renewal.",
                pb.label,
                f"You are {name}. You want to keep a library book longer. {pb.instructions}",
                f"You have a book checked out, {vdesc}, and you need more time with it.",
                f"Your name is {name}. You have a book, {vdesc}.",
                "You don't remember the exact title or loan details.",
                f"Patron {name} vaguely describes '{title}' for renewal. Agent should identify loan and renew.",
                acts,
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_pay_fine_full(db, ix, n=4):
    """Pay fine in full. n bases → 2n tasks."""
    tasks = []
    fines = [fid for fid in ix.outstanding_fines if db["fines"][fid]["amount"] <= 10.0]
    random.shuffle(fines)

    for i, fid in enumerate(fines[:n]):
        fine = db["fines"][fid]
        pid = fine["patron_id"]
        name = patron_name(db, pid)
        amount = fine["amount"]
        payment = pick_payment()
        track_use(pid)

        acts = [
            action(
                "pay_fine_1",
                "pay_fine",
                {"fine_id": fid, "amount": amount, "payment_method": payment},
                f"Pay ${amount:.2f} on {fid}",
                compare_args=["fine_id"],
            )
        ]
        asserts = [
            env_assert(
                "assert_fine_status", {"fine_id": fid, "expected_status": "paid"}
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"pay_fine_full_{i + 1}a",
                "Test full fine payment",
                "Fines can be paid in full or partially. Payment reduces patron's fines_owed.",
                f"Patron {name} pays fine {fid} (${amount:.2f}) via {payment}.",
                pa.label,
                f"You are {name}. You want to pay off a fine. {pa.instructions}",
                f"You want to pay your library fine in full.",
                f"Your name is {name}. You know you have a fine to pay.",
                f"You don't know the exact fine amount. When told, pay the full ${amount:.2f} using {payment}.",
                f"Patron {name} pays fine {fid} (${amount:.2f}) via {payment}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"pay_fine_full_{i + 1}b",
                "Test fine payment with difficult patron interaction",
                "Fines can be paid in full or partially. Payment reduces patron's fines_owed.",
                f"Patron {name} pays fine {fid} (${amount:.2f}) after difficult interaction.",
                pb.label,
                f"You are {name}. You have a library fine. {pb.instructions}",
                f"You think you might have some kind of fee or charge on your account.",
                f"Your name is {name}.",
                f"You're not sure what the fine is for or the amount. When the agent tells you, agree to pay ${amount:.2f} using {payment}.",
                f"Patron {name} vaguely asks about charges. Fine {fid} (${amount:.2f}). Agent should look up and process payment.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_cancel_hold(db, ix, n=3):
    """Cancel a hold. Single variant only."""
    tasks = []
    holds = list(ix.cancellable_holds)
    random.shuffle(holds)

    for i, hid in enumerate(holds[:n]):
        hold = db["holds"][hid]
        pid = hold["patron_id"]
        bid = hold["book_id"]
        title = book_title(db, bid)
        name = patron_name(db, pid)
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"cancel_hold_{i + 1}",
                "Test hold cancellation",
                "Pending or ready holds can be cancelled.",
                f"Patron {name} cancels hold on '{title}' (hold {hid}).",
                pa.label,
                f"You are {name}. You want to cancel a hold you placed. {pa.instructions}",
                f"You want to cancel your hold on '{title}'. You no longer need it.",
                f"Your name is {name}. You placed a hold on '{title}'.",
                "You don't know the hold ID.",
                f"Patron {name} wants to cancel hold {hid} on '{title}'.",
                [
                    action(
                        "cancel_hold_1",
                        "cancel_hold",
                        {"hold_id": hid},
                        f"Cancel hold {hid} on '{title}'",
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_renew_membership(db, ix, n=3):
    """Renew expired membership. Single variant only."""
    tasks = []
    expired = list(ix.expired_patrons)
    random.shuffle(expired)

    for i, pid in enumerate(expired[:n]):
        name = patron_name(db, pid)
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"renew_membership_{i + 1}",
                "Test membership renewal",
                "Expired memberships can be renewed for one year.",
                f"Patron {name} has expired membership ({db['patrons'][pid]['membership_expiry']}).",
                pa.label,
                f"You are {name}. Your library membership has expired. {pa.instructions}",
                "You want to renew your library membership.",
                f"Your name is {name}.",
                "You're not sure when your membership expired.",
                f"Patron {name} wants to renew expired membership.",
                [
                    action(
                        "renew_1",
                        "renew_membership",
                        {"patron_id": pid},
                        f"Renew membership for {name}",
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Tier 2: Information & Search Generators
# ---------------------------------------------------------------------------


def gen_search_by_title(db, ix, n=3):
    """Search catalog by title. n bases → 2n tasks."""
    tasks = []
    books = list(db["books"].keys())
    random.shuffle(books)

    for i, bid in enumerate(books[:n]):
        title = book_title(db, bid)
        vdesc = vague_book(bid, title)

        # Variant A: Easy — exact title
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"search_title_{i + 1}a",
                "Test catalog search by title",
                "search_catalog supports partial, case-insensitive title search.",
                f"Patron searches for '{title}'.",
                pa.label,
                f"You are a library patron looking for a specific book. {pa.instructions}",
                f"You're looking for a book called '{title}'. Can you check if the library has it?",
                f"You know the book title: '{title}'.",
                "You don't know the book ID or availability.",
                f"Patron asks about '{title}'. Agent should search the catalog.",
                [
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search catalog for '{title}'",
                        compare_args=["title"],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )

        # Variant B: Hard — vague description
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"search_title_{i + 1}b",
                "Test catalog search with vague book description",
                "search_catalog supports partial, case-insensitive title search.",
                f"Patron vaguely describes '{title}'.",
                pb.label,
                f"You are a library patron looking for a book. {pb.instructions}",
                f"You're looking for {vdesc}. You can't remember the exact title.",
                f"You vaguely remember the book as {vdesc}.",
                "You don't know the exact title or book ID.",
                f"Patron vaguely describes '{title}' as '{vdesc}'. Agent should search catalog.",
                [
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search catalog for '{title}'",
                        compare_args=["title"],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_search_by_author(db, ix, n=4):
    """Search catalog by author or category. Single variant."""
    tasks = []
    books = list(db["books"].values())
    random.shuffle(books)

    for i, book in enumerate(books[:n]):
        pa = pick_easy_persona()
        if i % 2 == 0:
            search_arg = {"author": book["author"]}
            query_desc = f"author '{book['author']}'"
            reason = f"You're looking for books by {book['author']}."
            known = f"You want books by {book['author']}."
        else:
            search_arg = {"category": book["category"]}
            query_desc = f"category '{book['category']}'"
            reason = f"You're looking for {book['category']} books."
            known = f"You want {book['category']} books."

        tasks.append(
            make_task(
                f"search_author_category_{i + 1}",
                f"Test catalog search by {query_desc}",
                "search_catalog supports author and category search.",
                f"Patron searches by {query_desc}.",
                pa.label,
                f"You are a library patron looking for books. {pa.instructions}",
                reason,
                known,
                "You don't know specific book IDs.",
                f"Patron asks about books by {query_desc}. Agent should search catalog.",
                [
                    action(
                        "search_1",
                        "search_catalog",
                        search_arg,
                        f"Search catalog by {query_desc}",
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_check_availability(db, ix, n=3):
    """Check availability. n bases → 2n tasks."""
    tasks = []
    books = list(db["books"].keys())
    random.shuffle(books)
    branches = list(db["branches"].keys())

    for i in range(min(n, len(books))):
        bid = books[i]
        brid = random.choice(branches)
        title = book_title(db, bid)
        br = branch_name(db, brid)
        vdesc = vague_book(bid, title)

        acts = [
            action(
                "search_1",
                "search_catalog",
                {"title": title},
                f"Search for '{title}'",
                compare_args=["title"],
            ),
            action(
                "availability_1",
                "get_book_availability",
                {"book_id": bid, "branch_id": brid},
                f"Check availability at {br}",
                compare_args=["book_id"],
            ),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"check_availability_{i + 1}a",
                "Test checking book availability at a branch",
                "Use search_catalog to find the book, then get_book_availability.",
                f"Patron asks about '{title}' at {br}.",
                pa.label,
                f"You are a library patron checking availability. {pa.instructions}",
                f"You want to know if '{title}' is available at the {br}.",
                f"You want '{title}' at the {br}.",
                "You don't know if there are copies available.",
                f"Patron asks about '{title}' at {br}. Agent should search and check availability.",
                acts,
                reward_basis=["ACTION"],
            )
        )

        # Variant B: Hard — vague
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"check_availability_{i + 1}b",
                "Test availability check with vague description",
                "Use search_catalog to find the book, then get_book_availability.",
                f"Patron vaguely describes '{title}' for availability check.",
                pb.label,
                f"You are a library patron. {pb.instructions}",
                f"You're wondering if the library has {vdesc}. You'd like to pick it up if it's available.",
                f"You vaguely remember: {vdesc}.",
                "You don't know the exact title, which branch, or availability.",
                f"Patron vaguely describes '{title}'. Agent should identify book and check availability.",
                [
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search for '{title}'",
                        compare_args=["title"],
                    )
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_list_loans(db, ix, n=3):
    """List patron's loans. n bases → 2n tasks."""
    tasks = []
    with_loans = [
        pid for pid in ix.active_patrons if db["patrons"][pid]["active_loans"]
    ]
    random.shuffle(with_loans)

    for i, pid in enumerate(with_loans[:n]):
        name = patron_name(db, pid)
        track_use(pid)
        loan_count = len(db["patrons"][pid]["active_loans"])

        acts = [
            action(
                "find_1",
                "find_patron_by_name",
                {"name": name},
                f"Find patron {name}",
                compare_args=[],
            ),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"list_loans_{i + 1}a",
                "Test listing patron's active loans",
                "Find patron and provide loan information.",
                f"Patron {name} asks to see current loans.",
                pa.label,
                f"You are {name}. You want to see what books you have out. {pa.instructions}",
                "You want to know what books you currently have checked out.",
                f"Your name is {name}.",
                "You don't remember exactly which books you have.",
                f"Patron {name} wants to see active loans. Agent should look up and list.",
                acts,
                nl_assertions=[
                    f"The agent provided information about the patron's {loan_count} active loan(s)"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )

        # Variant B: Hard — vague request
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"list_loans_{i + 1}b",
                "Test listing loans with vague request",
                "Find patron and provide loan information.",
                f"Patron {name} vaguely asks about account status.",
                pb.label,
                f"You are {name}. {pb.instructions}",
                "You want to check on your library account — like what you have borrowed or when things are due.",
                f"Your name is {name}.",
                "You don't know your patron ID or what's on your account.",
                f"Patron {name} vaguely asks about account. Agent should find patron and list loans.",
                acts,
                nl_assertions=[
                    f"The agent provided information about the patron's {loan_count} active loan(s)"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_list_fines(db, ix, n=3):
    """List patron's fines. n bases → 2n tasks."""
    tasks = []
    with_fines = [
        pid for pid in ix.active_patrons if db["patrons"][pid]["fines_owed"] > 0
    ]
    random.shuffle(with_fines)

    for i, pid in enumerate(with_fines[:n]):
        name = patron_name(db, pid)
        fines_owed = db["patrons"][pid]["fines_owed"]
        track_use(pid)

        acts = [
            action(
                "find_1",
                "find_patron_by_name",
                {"name": name},
                f"Find patron {name}",
                compare_args=[],
            ),
            action(
                "list_fines_1",
                "list_patron_fines",
                {"patron_id": pid},
                f"List fines for {name}",
            ),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"list_fines_{i + 1}a",
                "Test listing patron's outstanding fines",
                "Use find_patron_by_name then list_patron_fines.",
                f"Patron {name} (fines: ${fines_owed:.2f}) asks about fines.",
                pa.label,
                f"You are {name}. You want to check your fines. {pa.instructions}",
                "You want to know if you have any outstanding library fines.",
                f"Your name is {name}.",
                "You don't know your exact fine balance.",
                f"Patron {name} wants to check fines. Agent should look up and list.",
                acts,
                reward_basis=["ACTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"list_fines_{i + 1}b",
                "Test listing fines with vague inquiry",
                "Use find_patron_by_name then list_patron_fines.",
                f"Patron {name} vaguely asks about charges.",
                pb.label,
                f"You are {name}. {pb.instructions}",
                "You think you might owe the library some money but you're not sure.",
                f"Your name is {name}.",
                "You have no idea about your fine situation.",
                f"Patron {name} vaguely asks about potential charges. Agent should find patron and list fines.",
                acts,
                nl_assertions=[
                    f"The agent informed the patron about their outstanding balance of ${fines_owed:.2f}"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Tier 3: Moderate Multi-Step Generators
# ---------------------------------------------------------------------------


def gen_checkout_blocked_by_fines(db, ix, n=3):
    """Fines block checkout → pay → checkout. n bases → 2n tasks."""
    tasks = []
    blocking = [
        pid
        for pid in ix.patrons_with_fines_blocking
        if patron_is_active(db, pid)
        and len(db["patrons"][pid]["active_loans"])
        < db["patrons"][pid]["borrowing_limit"]
    ]
    avail_combos = list(ix.available_copies_by_book_branch.items())
    random.shuffle(avail_combos)
    combo_idx = 0

    for i, pid in enumerate(blocking):
        if i >= n or combo_idx >= len(avail_combos):
            break
        p = db["patrons"][pid]
        name = p["name"]
        track_use(pid)

        patron_fines = [
            f
            for f in db["fines"].values()
            if f["patron_id"] == pid and f["status"] == "outstanding"
        ]
        if not patron_fines:
            continue
        fine = patron_fines[0]
        fid = fine["fine_id"]
        excess = p["fines_owed"] - FINE_CHECKOUT_BLOCK_THRESHOLD
        pay_amount = min(round(excess + 0.50, 2), fine["amount"])
        payment = pick_payment()

        (bid, brid), copy_ids = avail_combos[combo_idx]
        combo_idx += 1
        cid = copy_ids[0]
        title = book_title(db, bid)
        br = branch_name(db, brid)
        lc = len(p["active_loans"])
        vdesc = vague_book(bid, title)

        acts = [
            action(
                "pay_fine_1",
                "pay_fine",
                {"fine_id": fid, "amount": pay_amount, "payment_method": payment},
                f"Pay ${pay_amount:.2f} toward {fid}",
                compare_args=["fine_id"],
            ),
            action(
                "checkout_1",
                "checkout_book",
                {"patron_id": pid, "copy_id": cid},
                f"Check out {cid} ('{title}') to {name}",
                compare_args=["patron_id", "copy_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_copy_status", {"copy_id": cid, "expected_status": "checked_out"}
            ),
            env_assert(
                "assert_patron_loan_count", {"patron_id": pid, "expected": lc + 1}
            ),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"checkout_with_fines_{i + 1}a",
                "Test checkout blocked by fines, requiring payment first",
                f"Fines > ${FINE_CHECKOUT_BLOCK_THRESHOLD:.2f} block checkouts.",
                f"Patron {name} has ${p['fines_owed']:.2f} in fines. Needs to pay before checkout.",
                pa.label,
                f"You are {name}. You want to check out a book but may have fines. {pa.instructions}",
                f"You want to check out '{title}' at the {br}. You know you have some overdue fines.",
                f"Your name is {name}. You want '{title}' at the {br}.",
                f"You don't know the exact fine amount. When told about the block, agree to pay ${pay_amount:.2f} via {payment}.",
                f"Patron {name}: ${p['fines_owed']:.2f} fines block checkout. Agent must collect payment then checkout.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"checkout_with_fines_{i + 1}b",
                "Test checkout blocked by fines with difficult patron",
                f"Fines > ${FINE_CHECKOUT_BLOCK_THRESHOLD:.2f} block checkouts.",
                f"Patron {name} vaguely requests '{title}' while having blocking fines.",
                pb.label,
                f"You are {name}. You want a book from the library. {pb.instructions}",
                f"You're looking for {vdesc}. You're not sure if you owe anything.",
                f"Your name is {name}. You want {vdesc}.",
                f"You don't know your fine balance or that it blocks checkout. When told, agree to pay ${pay_amount:.2f} via {payment}.",
                f"Patron {name} vaguely describes '{title}' while having ${p['fines_owed']:.2f} blocking fines.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_checkout_blocked_by_membership(db, ix, n=3):
    """Expired membership → renew → checkout. n bases → 2n tasks."""
    tasks = []
    expired_eligible = [
        pid
        for pid in ix.expired_patrons
        if db["patrons"][pid]["fines_owed"] <= FINE_CHECKOUT_BLOCK_THRESHOLD
        and len(db["patrons"][pid]["active_loans"])
        < db["patrons"][pid]["borrowing_limit"]
    ]
    avail_combos = list(ix.available_copies_by_book_branch.items())
    random.shuffle(avail_combos)
    random.shuffle(expired_eligible)

    combo_idx = 0
    for i, pid in enumerate(expired_eligible):
        if i >= n or combo_idx >= len(avail_combos):
            break
        p = db["patrons"][pid]
        name = p["name"]
        track_use(pid)

        (bid, brid), copy_ids = avail_combos[combo_idx]
        combo_idx += 1
        cid = copy_ids[0]
        title = book_title(db, bid)
        br = branch_name(db, brid)
        lc = len(p["active_loans"])
        vdesc = vague_book(bid, title)

        acts = [
            action(
                "renew_membership_1",
                "renew_membership",
                {"patron_id": pid},
                f"Renew membership for {name}",
            ),
            action(
                "checkout_1",
                "checkout_book",
                {"patron_id": pid, "copy_id": cid},
                f"Check out {cid} ('{title}') to {name}",
                compare_args=["patron_id", "copy_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_copy_status", {"copy_id": cid, "expected_status": "checked_out"}
            ),
            env_assert(
                "assert_patron_loan_count", {"patron_id": pid, "expected": lc + 1}
            ),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"checkout_expired_membership_{i + 1}a",
                "Test checkout blocked by expired membership",
                "Membership must be active for checkout. Expired can be renewed for one year.",
                f"Patron {name} has expired membership ({p['membership_expiry']}). Must renew first.",
                pa.label,
                f"You are {name}. You want to check out a book. {pa.instructions}",
                f"You want to check out '{title}' at the {br}.",
                f"Your name is {name}. You want '{title}' at the {br}.",
                "You're not sure if your membership is valid. If expired, agree to renew.",
                f"Patron {name}: expired membership. Agent must renew then checkout.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"checkout_expired_membership_{i + 1}b",
                "Test checkout with expired membership and vague request",
                "Membership must be active for checkout. Expired can be renewed for one year.",
                f"Patron {name} vaguely requests '{title}' with expired membership.",
                pb.label,
                f"You are {name}. You want a book. {pb.instructions}",
                f"You're looking for {vdesc}.",
                f"Your name is {name}. You want something like {vdesc}.",
                "You're not sure about your membership status. If expired, agree to renew.",
                f"Patron {name} vaguely describes '{title}'. Membership expired. Agent must renew then checkout.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_place_hold(db, ix, n=4):
    """Place hold on unavailable book. n bases → 2n tasks."""
    tasks = []
    combos = list(ix.books_all_out_at_branch.keys())
    random.shuffle(combos)
    eligible = [pid for pid in ix.active_patrons if pid not in ix.patrons_at_limit]
    random.shuffle(eligible)

    count = 0
    pidx = 0
    for book_id, branch_id in combos:
        if count >= n or pidx >= len(eligible):
            break
        pid = eligible[pidx]
        pidx += 1
        name = patron_name(db, pid)
        title = book_title(db, book_id)
        br = branch_name(db, branch_id)
        vdesc = vague_book(book_id, title)
        track_use(pid)

        hold_act = action(
            "place_hold_1",
            "place_hold",
            {"patron_id": pid, "book_id": book_id, "branch_id": branch_id},
            f"Place hold on '{title}' at {br}",
            compare_args=["patron_id", "book_id", "branch_id"],
        )

        # Variant A: Easy — full search+availability+hold sequence
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"place_hold_{count + 1}a",
                "Test placing a hold on an unavailable book",
                "Holds can be placed when no copies are available at the requested branch.",
                f"Patron {name} wants '{title}' at {br} — unavailable. Should place hold.",
                pa.label,
                f"You are {name}. You want a book that might not be available. {pa.instructions}",
                f"You'd like to get '{title}' from the {br}.",
                f"Your name is {name}. You want '{title}' at the {br}.",
                "You don't know if the book is available. If not, ask for a hold.",
                f"Patron {name} wants '{title}' at {br}. Unavailable. Agent should place hold.",
                [
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search for '{title}'",
                        compare_args=["title"],
                    ),
                    action(
                        "availability_1",
                        "get_book_availability",
                        {"book_id": book_id, "branch_id": branch_id},
                        f"Check availability at {br}",
                        compare_args=["book_id"],
                    ),
                    hold_act,
                ],
                reward_basis=["ACTION"],
            )
        )

        # Variant B: Hard — vague description, core action only
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"place_hold_{count + 1}b",
                "Test placing hold with vague book description",
                "Holds can be placed when no copies are available at the requested branch.",
                f"Patron {name} vaguely describes '{title}' and needs a hold.",
                pb.label,
                f"You are {name}. You want a specific book. {pb.instructions}",
                f"You're looking for {vdesc}. You'd like to pick it up at a library if it's available.",
                f"Your name is {name}. You want {vdesc}.",
                "You don't know the title, availability, or branch. If unavailable, ask for a hold.",
                f"Patron {name} vaguely describes '{title}'. Unavailable at {br}. Agent should place hold.",
                [hold_act],
                reward_basis=["ACTION"],
            )
        )
        count += 1
    return tasks


def gen_register_event(db, ix, n=4):
    """Register for event. n bases → 2n tasks."""
    tasks = []
    events = list(ix.upcoming_events_with_capacity)
    eligible = list(ix.active_patrons)
    random.shuffle(eligible)
    random.shuffle(events)

    count = 0
    pidx = 0
    for eid in events:
        if count >= n or pidx >= len(eligible):
            break
        event = db["events"][eid]
        brid = event["branch_id"]
        br = branch_name(db, brid)

        while pidx < len(eligible):
            pid = eligible[pidx]
            pidx += 1
            if pid not in event["registered_patrons"]:
                break
        else:
            continue

        name = patron_name(db, pid)
        track_use(pid)

        reg_act = action(
            "register_1",
            "register_for_event",
            {"patron_id": pid, "event_id": eid},
            f"Register {name} for '{event['title']}'",
            compare_args=["patron_id", "event_id"],
        )

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"register_event_{count + 1}a",
                "Test event registration",
                "Patron must have active membership. Event must have capacity.",
                f"Patron {name} registers for '{event['title']}' at {br}.",
                pa.label,
                f"You are {name}. You want to sign up for a library event. {pa.instructions}",
                f"You heard about '{event['title']}' at the {br} and want to sign up.",
                f"Your name is {name}. You want '{event['title']}' at the {br}.",
                "You don't know the event ID or if there's still space.",
                f"Patron {name} registers for '{event['title']}' ({eid}) at {br}.",
                [
                    action(
                        "find_branch_1",
                        "find_branch_by_name",
                        {"name": br},
                        f"Find branch {br}",
                        compare_args=[],
                    ),
                    action(
                        "list_events_1",
                        "list_events",
                        {"branch_id": brid},
                        f"List events at {br}",
                        compare_args=[],
                    ),
                    reg_act,
                ],
                reward_basis=["ACTION"],
            )
        )

        # Variant B: Hard — vague event description
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"register_event_{count + 1}b",
                "Test event registration with vague request",
                "Patron must have active membership. Event must have capacity.",
                f"Patron {name} vaguely describes '{event['title']}' event.",
                pb.label,
                f"You are {name}. You want to attend something at the library. {pb.instructions}",
                f"You heard the library has some kind of event — maybe something like '{event['title'].split(':')[0].strip()}'? You'd like to sign up.",
                f"Your name is {name}. You're interested in a library event.",
                "You don't remember the exact event name, date, or which branch.",
                f"Patron {name} vaguely asks about '{event['title']}'. Agent should find event and register.",
                [reg_act],
                reward_basis=["ACTION"],
            )
        )
        count += 1
    return tasks


def gen_pay_fine_partial(db, ix, n=3):
    """Partial fine payment. Single variant."""
    tasks = []
    fines = [fid for fid in ix.outstanding_fines if db["fines"][fid]["amount"] > 2.0]
    random.shuffle(fines)

    for i, fid in enumerate(fines[:n]):
        fine = db["fines"][fid]
        pid = fine["patron_id"]
        name = patron_name(db, pid)
        pay_amount = round(fine["amount"] / 2, 2)
        if pay_amount <= 0:
            pay_amount = 1.0
        payment = pick_payment()
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"pay_fine_partial_{i + 1}",
                "Test partial fine payment",
                "Fines can be paid partially. Remaining balance stays outstanding.",
                f"Patron {name} pays ${pay_amount:.2f} of ${fine['amount']:.2f} fine ({fid}).",
                pa.label,
                f"You are {name}. You want to make a partial payment on a fine. {pa.instructions}",
                "You want to pay some of your library fine but not all right now.",
                f"Your name is {name}.",
                f"You don't know the exact amount. When told, pay ${pay_amount:.2f} using {payment}.",
                f"Patron {name} pays ${pay_amount:.2f} toward fine {fid} (${fine['amount']:.2f}) via {payment}.",
                [
                    action(
                        "find_1",
                        "find_patron_by_name",
                        {"name": name},
                        f"Find patron {name}",
                        compare_args=[],
                    ),
                    action(
                        "list_fines_1",
                        "list_patron_fines",
                        {"patron_id": pid},
                        f"List fines for {name}",
                    ),
                    action(
                        "pay_fine_1",
                        "pay_fine",
                        {
                            "fine_id": fid,
                            "amount": pay_amount,
                            "payment_method": payment,
                        },
                        f"Pay ${pay_amount:.2f} on {fid}",
                        compare_args=["fine_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_interlibrary_loan(db, ix, n=3):
    """Interlibrary loan request. Single variant."""
    tasks = []
    eligible = list(ix.active_patrons)
    random.shuffle(eligible)
    books = list(db["books"].keys())
    random.shuffle(books)

    for i in range(min(n, len(eligible), len(books))):
        pid = eligible[i]
        bid = books[i]
        name = patron_name(db, pid)
        title = book_title(db, bid)
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"interlibrary_loan_{i + 1}",
                "Test interlibrary loan request",
                "Active membership required. ILL for books unavailable locally.",
                f"Patron {name} requests ILL for '{title}'.",
                pa.label,
                f"You are {name}. You want an interlibrary loan. {pa.instructions}",
                f"You've been looking for '{title}' but can't find it. You'd like to request it from another library.",
                f"Your name is {name}. You want '{title}'.",
                "You're not sure how the interlibrary loan process works.",
                f"Patron {name} requests ILL for '{title}'.",
                [
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search for '{title}'",
                        compare_args=["title"],
                    ),
                    action(
                        "ill_1",
                        "request_interlibrary_loan",
                        {"patron_id": pid, "book_id": bid},
                        f"Request ILL for '{title}'",
                        compare_args=["patron_id", "book_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_waive_fine_eligible(db, ix, n=3):
    """Waive fine (eligible — first offense). n bases → 2n tasks."""
    tasks = []
    eligible = [
        fid for fid in ix.waiver_eligible_fines if db["fines"][fid]["amount"] <= 10.0
    ]
    random.shuffle(eligible)

    for i, fid in enumerate(eligible[:n]):
        fine = db["fines"][fid]
        pid = fine["patron_id"]
        name = patron_name(db, pid)
        track_use(pid)

        acts = [
            action(
                "list_fines_1",
                "list_patron_fines",
                {"patron_id": pid},
                f"List fines for {name}",
            ),
            action(
                "waive_1",
                "waive_fine",
                {"fine_id": fid, "reason": "first_offense"},
                f"Waive fine {fid}",
                compare_args=["fine_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_fine_status", {"fine_id": fid, "expected_status": "waived"}
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"waive_fine_{i + 1}a",
                "Test fine waiver for eligible patron (first offense)",
                "Fine waivers only for first offense (no other fines on record).",
                f"Patron {name} has one fine ({fid}, ${fine['amount']:.2f}) — eligible.",
                pa.label,
                f"You are {name}. You want to ask about getting a fine waived. {pa.instructions}",
                "You have a library fine and you'd like to ask if it can be waived. This is your first time having a fine.",
                f"Your name is {name}. You have a fine you'd like waived.",
                "You don't know if you're eligible. Mention it's your first offense when asked.",
                f"Patron {name} requests waiver of {fid}. First offense — eligible.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"waive_fine_{i + 1}b",
                "Test fine waiver with difficult patron interaction",
                "Fine waivers only for first offense (no other fines on record).",
                f"Patron {name} asks about charges and wants them removed.",
                pb.label,
                f"You are {name}. {pb.instructions}",
                "You have some kind of charge on your account and you want it removed. You've never had any issues before.",
                f"Your name is {name}.",
                "You don't know the details of the fine. Mention it's your first time having a problem when prompted.",
                f"Patron {name} vaguely asks about charges. Fine {fid} eligible for waiver.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_search_availability_checkout(db, ix, n=4):
    """Search → availability → checkout (full flow). n bases → 2n tasks."""
    tasks = []
    eligible = [pid for pid in ix.patrons_below_limit if patron_can_checkout(db, pid)]
    random.shuffle(eligible)
    avail_combos = list(ix.available_copies_by_book_branch.items())
    random.shuffle(avail_combos)

    count = 0
    pidx = 0
    for (book_id, branch_id), copy_ids in avail_combos:
        if count >= n or pidx >= len(eligible):
            break
        pid = eligible[pidx]
        pidx += 1
        cid = copy_ids[0]
        name = patron_name(db, pid)
        title = book_title(db, book_id)
        br = branch_name(db, branch_id)
        lc = len(db["patrons"][pid]["active_loans"])
        vdesc = vague_book(book_id, title)
        track_use(pid)
        track_use(cid)

        checkout_act = action(
            "checkout_1",
            "checkout_book",
            {"patron_id": pid, "copy_id": cid},
            f"Check out {cid} to {name}",
            compare_args=["patron_id", "copy_id"],
        )
        asserts = [
            env_assert(
                "assert_copy_status", {"copy_id": cid, "expected_status": "checked_out"}
            ),
            env_assert(
                "assert_patron_loan_count", {"patron_id": pid, "expected": lc + 1}
            ),
        ]

        # Variant A: Easy — full flow
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"search_checkout_{count + 1}a",
                "Test full flow: search → availability → checkout",
                "Agent should search catalog, verify availability, then checkout.",
                f"Patron {name} wants '{title}' at {br}. Copy {cid} available.",
                pa.label,
                f"You are {name}. You want to find and borrow a book. {pa.instructions}",
                f"You're looking for '{title}' at the {br} and want to borrow it.",
                f"Your name is {name}. You want '{title}' at the {br}.",
                "You don't know if it's available.",
                f"Patron {name} wants '{title}' at {br}. Agent should search, check, checkout.",
                [
                    action(
                        "search_1",
                        "search_catalog",
                        {"title": title},
                        f"Search for '{title}'",
                        compare_args=["title"],
                    ),
                    action(
                        "availability_1",
                        "get_book_availability",
                        {"book_id": book_id, "branch_id": branch_id},
                        f"Check availability at {br}",
                        compare_args=["book_id"],
                    ),
                    checkout_act,
                ],
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard — vague
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"search_checkout_{count + 1}b",
                "Test search-to-checkout with vague book description",
                "Agent should search catalog, verify availability, then checkout.",
                f"Patron {name} vaguely describes '{title}' for checkout.",
                pb.label,
                f"You are {name}. You want a book from the library. {pb.instructions}",
                f"You're looking for {vdesc}. You'd like to borrow it if it's available.",
                f"Your name is {name}. You want {vdesc}.",
                "You don't know the exact title, branch, or availability.",
                f"Patron {name} vaguely describes '{title}'. Agent should find and checkout copy {cid}.",
                [checkout_act],
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
        count += 1
    return tasks


# ---------------------------------------------------------------------------
# Tier 4: Complex Multi-Step Generators
# ---------------------------------------------------------------------------


def gen_return_then_checkout(db, ix, n=4):
    """Return a book then checkout a new one. n bases → 2n tasks."""
    tasks = []
    candidates = []
    for lid in ix.active_loans:
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        p = db["patrons"][pid]
        if (
            p["membership_expiry"] >= TODAY
            and p["fines_owed"] <= FINE_CHECKOUT_BLOCK_THRESHOLD
        ):
            candidates.append(lid)
    random.shuffle(candidates)
    avail_combos = list(ix.available_copies_by_book_branch.items())
    random.shuffle(avail_combos)

    count = 0
    combo_idx = 0
    for lid in candidates:
        if count >= n or combo_idx >= len(avail_combos):
            break
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        ret_cid = loan["copy_id"]
        ret_bid = copy_book_id(db, ret_cid)
        ret_title = book_title(db, ret_bid)

        (new_bid, new_brid), copy_ids = avail_combos[combo_idx]
        combo_idx += 1
        if new_bid == ret_bid:
            continue
        new_cid = copy_ids[0]
        new_title = book_title(db, new_bid)
        new_br = branch_name(db, new_brid)
        vdesc = vague_book(new_bid, new_title)

        name = patron_name(db, pid)
        final_lc = len(db["patrons"][pid]["active_loans"])
        track_use(pid)

        acts = [
            action(
                "return_1",
                "return_book",
                {"copy_id": ret_cid},
                f"Return {ret_cid} ('{ret_title}')",
            ),
            action(
                "checkout_1",
                "checkout_book",
                {"patron_id": pid, "copy_id": new_cid},
                f"Check out {new_cid} ('{new_title}') to {name}",
                compare_args=["patron_id", "copy_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_copy_status",
                {"copy_id": ret_cid, "expected_status": "available"},
            ),
            env_assert(
                "assert_copy_status",
                {"copy_id": new_cid, "expected_status": "checked_out"},
            ),
            env_assert(
                "assert_patron_loan_count", {"patron_id": pid, "expected": final_lc}
            ),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"return_checkout_{count + 1}a",
                "Test return followed by checkout",
                "Return processes loan. Checkout requires eligibility.",
                f"Patron {name} returns '{ret_title}' and checks out '{new_title}' at {new_br}.",
                pa.label,
                f"You are {name}. You want to return a book and borrow a different one. {pa.instructions}",
                f"You want to return '{ret_title}' and check out '{new_title}' at the {new_br}.",
                f"Your name is {name}. You have '{ret_title}' to return. You want '{new_title}' at the {new_br}.",
                "You don't know the copy IDs.",
                f"Patron {name} returns '{ret_title}' then checks out '{new_title}' at {new_br}.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"return_checkout_{count + 1}b",
                "Test return+checkout with vague new book description",
                "Return processes loan. Checkout requires eligibility.",
                f"Patron {name} returns '{ret_title}' and vaguely describes '{new_title}'.",
                pb.label,
                f"You are {name}. You want to return a book and get a new one. {pb.instructions}",
                f"You want to return '{ret_title}' and you're also looking for {vdesc}.",
                f"Your name is {name}. You have '{ret_title}' to return. You also want {vdesc}.",
                "You don't know the exact new title or copy IDs.",
                f"Patron {name} returns '{ret_title}' and vaguely describes '{new_title}'. Agent should handle both.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
        count += 1
    return tasks


def gen_renew_membership_register_event(db, ix, n=3):
    """Renew expired membership + register for event. Single variant."""
    tasks = []
    expired = list(ix.expired_patrons)
    events = list(ix.upcoming_events_with_capacity)
    random.shuffle(expired)
    random.shuffle(events)

    for i in range(min(n, len(expired), len(events))):
        pid = expired[i]
        eid = events[i % len(events)]
        event = db["events"][eid]
        if pid in event["registered_patrons"]:
            continue
        name = patron_name(db, pid)
        brid = event["branch_id"]
        br = branch_name(db, brid)
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"renew_register_event_{i + 1}",
                "Test membership renewal followed by event registration",
                "Membership must be active for event registration.",
                f"Patron {name}: expired membership. Renew then register for '{event['title']}' at {br}.",
                pa.label,
                f"You are {name}. You want to sign up for a library event. {pa.instructions}",
                f"You want to attend '{event['title']}' at the {br}.",
                f"Your name is {name}. You want '{event['title']}' at the {br}.",
                "You're not sure if your membership is current. If expired, agree to renew.",
                f"Patron {name}: expired. Agent must renew then register for '{event['title']}'.",
                [
                    action(
                        "renew_1",
                        "renew_membership",
                        {"patron_id": pid},
                        f"Renew membership for {name}",
                    ),
                    action(
                        "register_1",
                        "register_for_event",
                        {"patron_id": pid, "event_id": eid},
                        f"Register {name} for '{event['title']}'",
                        compare_args=["patron_id", "event_id"],
                    ),
                ],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_pay_multiple_fines(db, ix, n=3):
    """Pay multiple fines for same patron. Single variant."""
    tasks = []
    patron_fines: dict[str, list] = {}
    for fid in ix.outstanding_fines:
        fine = db["fines"][fid]
        patron_fines.setdefault(fine["patron_id"], []).append(fid)
    multi = [(pid, fids) for pid, fids in patron_fines.items() if len(fids) >= 2]
    random.shuffle(multi)

    for i, (pid, fids) in enumerate(multi[:n]):
        name = patron_name(db, pid)
        payment = pick_payment()
        track_use(pid)
        pa = pick_easy_persona()

        fine_acts = []
        fine_asserts = []
        total = 0.0
        for j, fid in enumerate(fids):
            fine = db["fines"][fid]
            total += fine["amount"]
            fine_acts.append(
                action(
                    f"pay_fine_{j + 1}",
                    "pay_fine",
                    {
                        "fine_id": fid,
                        "amount": fine["amount"],
                        "payment_method": payment,
                    },
                    f"Pay ${fine['amount']:.2f} on {fid}",
                    compare_args=["fine_id"],
                )
            )
            fine_asserts.append(
                env_assert(
                    "assert_fine_status", {"fine_id": fid, "expected_status": "paid"}
                )
            )

        tasks.append(
            make_task(
                f"pay_multiple_fines_{i + 1}",
                "Test paying multiple outstanding fines",
                "Each fine can be paid individually.",
                f"Patron {name} pays {len(fids)} fines totaling ${total:.2f}.",
                pa.label,
                f"You are {name}. You want to pay all your fines. {pa.instructions}",
                "You want to pay all your outstanding library fines.",
                f"Your name is {name}. You want to pay all fines.",
                f"You don't know how many fines you have. Pay all using {payment}.",
                f"Patron {name}: {len(fids)} fines, ${total:.2f}. Agent should list and process each.",
                fine_acts,
                fine_asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
    return tasks


def gen_return_overdue_pay_fine(db, ix, n=3):
    """Return overdue + pay resulting fine. n bases → 2n tasks."""
    tasks = []
    overdue = list(ix.overdue_active_loans)
    random.shuffle(overdue)

    for i, lid in enumerate(overdue[:n]):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        vdesc = vague_book(bid, title)
        payment = pick_payment()
        track_use(pid)

        acts = [
            action(
                "return_1",
                "return_book",
                {"copy_id": cid},
                f"Return overdue {cid} ('{title}')",
            )
        ]
        asserts = [
            env_assert(
                "assert_copy_status", {"copy_id": cid, "expected_status": "available"}
            )
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"return_overdue_pay_{i + 1}a",
                "Test returning overdue book and paying fine",
                "Overdue returns generate fines ($0.25/day). Patron wants to pay immediately.",
                f"Patron {name} returns overdue '{title}' (due {loan['due_date']}) and pays fine.",
                pa.label,
                f"You are {name}. You want to return an overdue book and pay any fines. {pa.instructions}",
                f"You want to return '{title}' — it's overdue. You'd like to pay any fine immediately.",
                f"Your name is {name}. You have '{title}' checked out and it's overdue.",
                f"You don't know the fine amount. After returning, pay the full fine using {payment}.",
                f"Patron {name} returns overdue '{title}' and pays fine via {payment}.",
                acts,
                asserts,
                nl_assertions=[
                    "The agent informed the patron about the overdue fine",
                    "The agent processed or offered to process the fine payment",
                ],
                reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"return_overdue_pay_{i + 1}b",
                "Test overdue return+pay with vague description",
                "Overdue returns generate fines ($0.25/day).",
                f"Patron {name} vaguely describes overdue '{title}' and wants to settle up.",
                pb.label,
                f"You are {name}. You need to return a library book and deal with any fees. {pb.instructions}",
                f"You have a book to return — {vdesc}. You think it might be late. You want to settle everything.",
                f"Your name is {name}. You have a book — {vdesc}.",
                f"You're not sure of the title or fine. After returning, pay using {payment}.",
                f"Patron {name} vaguely describes overdue '{title}'. Agent should return and handle fine.",
                acts,
                asserts,
                nl_assertions=["The agent informed the patron about the overdue fine"],
                reward_basis=["ACTION", "ENV_ASSERTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_hold_plus_checkout_different(db, ix, n=2):
    """Hold on unavailable + checkout a different book. n bases → 2n tasks."""
    tasks = []
    combos = list(ix.books_all_out_at_branch.keys())
    random.shuffle(combos)
    eligible = [pid for pid in ix.patrons_below_limit if patron_can_checkout(db, pid)]
    random.shuffle(eligible)
    avail_combos = list(ix.available_copies_by_book_branch.items())
    random.shuffle(avail_combos)

    count = 0
    pidx = 0
    combo_idx = 0
    for book_id, branch_id in combos:
        if count >= n or pidx >= len(eligible) or combo_idx >= len(avail_combos):
            break
        pid = eligible[pidx]
        pidx += 1

        # Find an available copy for a *different* book
        new_cid = None
        while combo_idx < len(avail_combos):
            (cb_bid, cb_brid), copy_ids = avail_combos[combo_idx]
            combo_idx += 1
            if cb_bid != book_id:
                new_cid = copy_ids[0]
                new_bid = cb_bid
                new_brid = cb_brid
                break
        if new_cid is None:
            continue

        name = patron_name(db, pid)
        hold_title = book_title(db, book_id)
        br = branch_name(db, branch_id)
        new_title = book_title(db, new_bid)
        new_br = branch_name(db, new_brid)
        vdesc_hold = vague_book(book_id, hold_title)
        vdesc_new = vague_book(new_bid, new_title)
        lc = len(db["patrons"][pid]["active_loans"])
        track_use(pid)

        acts = [
            action(
                "place_hold_1",
                "place_hold",
                {"patron_id": pid, "book_id": book_id, "branch_id": branch_id},
                f"Place hold on '{hold_title}' at {br}",
                compare_args=["patron_id", "book_id", "branch_id"],
            ),
            action(
                "checkout_1",
                "checkout_book",
                {"patron_id": pid, "copy_id": new_cid},
                f"Check out {new_cid} ('{new_title}') to {name}",
                compare_args=["patron_id", "copy_id"],
            ),
        ]
        asserts = [
            env_assert(
                "assert_copy_status",
                {"copy_id": new_cid, "expected_status": "checked_out"},
            ),
            env_assert(
                "assert_patron_loan_count", {"patron_id": pid, "expected": lc + 1}
            ),
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"hold_and_checkout_{count + 1}a",
                "Test placing hold + checking out a different book",
                "Holds placed when unavailable. Checkouts require eligibility.",
                f"Patron {name}: hold '{hold_title}' at {br}, checkout '{new_title}' at {new_br}.",
                pa.label,
                f"You are {name}. You want two books. {pa.instructions}",
                f"You want '{hold_title}' from the {br} and also '{new_title}' from the {new_br}.",
                f"Your name is {name}. You want '{hold_title}' at {br} and '{new_title}' at {new_br}.",
                f"You don't know availability. If '{hold_title}' isn't available, ask for a hold.",
                f"Patron {name}: '{hold_title}' unavailable (hold), '{new_title}' available (checkout).",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"hold_and_checkout_{count + 1}b",
                "Test hold+checkout with vague descriptions",
                "Holds placed when unavailable. Checkouts require eligibility.",
                f"Patron {name} vaguely describes two books.",
                pb.label,
                f"You are {name}. You're looking for a couple of books. {pb.instructions}",
                f"You want {vdesc_hold} and also {vdesc_new}.",
                f"Your name is {name}. You want {vdesc_hold} and {vdesc_new}.",
                "You don't know titles or availability. If one isn't available, ask for a hold.",
                f"Patron {name} vaguely describes '{hold_title}' and '{new_title}'. Agent should hold+checkout.",
                acts,
                asserts,
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
        count += 1
    return tasks


# ---------------------------------------------------------------------------
# Tier 5: Edge Cases & Policy Generators
# ---------------------------------------------------------------------------


def gen_checkout_at_limit(db, ix, n=3):
    """Patron at borrowing limit tries to checkout. n bases → 2n tasks."""
    tasks = []
    at_limit = list(ix.patrons_at_limit)
    random.shuffle(at_limit)
    avail = list(ix.available_copies)
    random.shuffle(avail)

    for i, pid in enumerate(at_limit[:n]):
        if not avail:
            break
        cid = avail[i % len(avail)]
        name = patron_name(db, pid)
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        br = branch_name(db, copy_branch_id(db, cid))
        limit = db["patrons"][pid]["borrowing_limit"]
        vdesc = vague_book(bid, title)
        track_use(pid)

        nl = [
            f"The agent informed the patron they have reached the borrowing limit of {limit} books",
            "The agent suggested returning a book to free up a slot",
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"checkout_at_limit_{i + 1}a",
                "Test checkout when patron is at borrowing limit",
                f"Patrons cannot exceed borrowing limit of {limit} books.",
                f"Patron {name} at limit ({limit}). Checkout should fail.",
                pa.label,
                f"You are {name}. You want to check out another book. {pa.instructions}",
                f"You want to check out '{title}' at the {br}.",
                f"Your name is {name}. You want '{title}' at the {br}.",
                "You don't realize you've hit your borrowing limit.",
                f"Patron {name} at limit ({limit}). Agent should inform and suggest returning a book.",
                [],
                nl_assertions=nl,
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"checkout_at_limit_{i + 1}b",
                "Test checkout at limit with vague request",
                f"Patrons cannot exceed borrowing limit of {limit} books.",
                f"Patron {name} vaguely requests '{title}' while at limit.",
                pb.label,
                f"You are {name}. You want a book. {pb.instructions}",
                f"You're looking for {vdesc}.",
                f"Your name is {name}. You want {vdesc}.",
                "You have no idea about your borrowing limit.",
                f"Patron {name} at limit, vaguely requests '{title}'. Agent should inform of limit.",
                [],
                nl_assertions=nl,
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_renewal_at_max(db, ix, n=4):
    """Renewal at max renewals. Single variant."""
    tasks = []
    max_loans = list(ix.max_renewal_loans)
    random.shuffle(max_loans)

    for i, lid in enumerate(max_loans[:n]):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        cid = loan["copy_id"]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        name = patron_name(db, pid)
        mr = max_renewals(db, pid)
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"renewal_max_{i + 1}",
                "Test renewal when maximum renewals reached",
                f"Maximum {mr} renewals allowed.",
                f"Patron {name} tries to renew '{title}' ({loan['renewals_count']}/{mr} used).",
                pa.label,
                f"You are {name}. You want to renew a book. {pa.instructions}",
                f"You'd like to renew '{title}'.",
                f"Your name is {name}. You have '{title}' checked out.",
                "You don't know you've used all renewals.",
                f"Patron {name}: max renewals reached for '{title}'. Agent should inform.",
                [],
                nl_assertions=[
                    f"The agent informed the patron that maximum renewals ({mr}) have been reached",
                    "The agent explained the patron cannot renew further",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_renewal_blocked_by_hold(db, ix, n=4):
    """Renewal blocked by pending hold. Single variant."""
    tasks = []
    blocked = list(ix.hold_blocked_loans)
    random.shuffle(blocked)

    for i, lid in enumerate(blocked[:n]):
        loan = db["loans"][lid]
        pid = loan["patron_id"]
        title = book_title(db, copy_book_id(db, loan["copy_id"]))
        name = patron_name(db, pid)
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"renewal_hold_blocked_{i + 1}",
                "Test renewal blocked by pending hold",
                "Loans cannot be renewed if another patron has a pending hold.",
                f"Patron {name} tries to renew '{title}' but hold exists.",
                pa.label,
                f"You are {name}. You want to renew a book. {pa.instructions}",
                f"You'd like to renew '{title}'.",
                f"Your name is {name}. You have '{title}' checked out.",
                "You don't know another patron has a hold.",
                f"Patron {name}: hold blocks renewal of '{title}'. Agent should inform.",
                [],
                nl_assertions=[
                    "The agent informed the patron that the book cannot be renewed because another patron has placed a hold"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_event_full(db, ix, n=3):
    """Register for full event. Single variant."""
    tasks = []
    full = list(ix.full_events)
    random.shuffle(full)
    eligible = list(ix.active_patrons)
    random.shuffle(eligible)

    for i in range(min(n, len(full), len(eligible))):
        eid = full[i % len(full)]
        pid = eligible[i]
        event = db["events"][eid]
        name = patron_name(db, pid)
        br = branch_name(db, event["branch_id"])
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"event_full_{i + 1}",
                "Test registration for a full event",
                "Events at capacity cannot accept registrations.",
                f"Patron {name} tries to register for full '{event['title']}'.",
                pa.label,
                f"You are {name}. You want to attend a library event. {pa.instructions}",
                f"You want to sign up for '{event['title']}' at the {br}.",
                f"Your name is {name}. You want '{event['title']}' at the {br}.",
                "You don't know the event is full.",
                f"Patron {name}: '{event['title']}' is full. Agent should inform.",
                [],
                nl_assertions=[
                    f"The agent informed the patron that '{event['title']}' is full"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_event_cancelled(db, ix, n=2):
    """Register for cancelled/completed event. Single variant."""
    tasks = []
    events = ix.cancelled_events + ix.completed_events
    random.shuffle(events)
    eligible = list(ix.active_patrons)
    random.shuffle(eligible)

    for i in range(min(n, len(events), len(eligible))):
        eid = events[i]
        pid = eligible[i]
        event = db["events"][eid]
        name = patron_name(db, pid)
        br = branch_name(db, event["branch_id"])
        status = event["status"]
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"event_{status}_{i + 1}",
                f"Test registration for a {status} event",
                f"Events that are {status} cannot accept registrations.",
                f"Patron {name} tries to register for {status} '{event['title']}'.",
                pa.label,
                f"You are {name}. You want to attend a library event. {pa.instructions}",
                f"You want to sign up for '{event['title']}' at the {br}.",
                f"Your name is {name}. You want '{event['title']}' at the {br}.",
                f"You don't know the event is {status}.",
                f"Patron {name}: '{event['title']}' is {status}. Agent should inform.",
                [],
                nl_assertions=[
                    f"The agent informed the patron that '{event['title']}' is {status}"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_hold_unnecessary(db, ix, n=3):
    """Patron asks for hold when copy available. Single variant."""
    tasks = []
    avail_combos = list(ix.available_copies_by_book_branch.keys())
    random.shuffle(avail_combos)
    eligible = list(ix.active_patrons)
    random.shuffle(eligible)

    for i in range(min(n, len(avail_combos), len(eligible))):
        book_id, branch_id = avail_combos[i]
        pid = eligible[i]
        name = patron_name(db, pid)
        title = book_title(db, book_id)
        br = branch_name(db, branch_id)
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"hold_unnecessary_{i + 1}",
                "Test patron requesting hold when book is actually available",
                "Holds cannot be placed when copies are available. Suggest checkout instead.",
                f"Patron {name} asks for hold on '{title}' at {br}, but copies available.",
                pa.label,
                f"You are {name}. You want to place a hold on a book. {pa.instructions}",
                f"You'd like to place a hold on '{title}' at the {br}. You assume it's not available.",
                f"Your name is {name}. You want to hold '{title}' at the {br}.",
                "You don't realize the book is actually available.",
                f"Patron {name}: '{title}' available at {br}. Agent should suggest checkout instead.",
                [],
                nl_assertions=[
                    f"The agent informed the patron that a copy of '{title}' is available at the {br}",
                    "The agent suggested checking out the book instead of placing a hold",
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_waive_fine_ineligible(db, ix, n=3):
    """Waiver denied (prior fines). n bases → 2n tasks."""
    tasks = []
    ineligible = [
        fid for fid in ix.waiver_ineligible_fines if db["fines"][fid]["amount"] <= 10.0
    ]
    random.shuffle(ineligible)

    for i, fid in enumerate(ineligible[:n]):
        fine = db["fines"][fid]
        pid = fine["patron_id"]
        name = patron_name(db, pid)
        track_use(pid)

        nl = [
            "The agent informed the patron that the fine waiver is not eligible because they have prior fines",
            "The agent explained the waiver policy (first offense only)",
        ]

        # Variant A: Easy
        pa = pick_easy_persona()
        tasks.append(
            make_task(
                f"waive_ineligible_{i + 1}a",
                "Test fine waiver denial for patron with prior fines",
                "Fine waivers are only for first offense.",
                f"Patron {name}: {fid} waiver denied, prior fines.",
                pa.label,
                f"You are {name}. You want to ask about a fine waiver. {pa.instructions}",
                "You have a library fine and want to see if it can be waived.",
                f"Your name is {name}.",
                "You don't know you're ineligible due to prior fines.",
                f"Patron {name}: waiver of {fid} denied (prior fines). Agent should explain policy.",
                [],
                nl_assertions=nl,
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )

        # Variant B: Hard
        pb = pick_hard_persona()
        tasks.append(
            make_task(
                f"waive_ineligible_{i + 1}b",
                "Test waiver denial with difficult patron",
                "Fine waivers are only for first offense.",
                f"Patron {name} frustratedly asks about charges and removal.",
                pb.label,
                f"You are {name}. {pb.instructions}",
                "You have a charge on your account and you want it removed. You don't think it's fair.",
                f"Your name is {name}.",
                "You're not aware of your fine history or the waiver policy.",
                f"Patron {name}: waiver ineligible. Agent should deny and explain despite difficult interaction.",
                [],
                nl_assertions=nl,
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_checkout_unavailable_copy(db, ix, n=3):
    """Checkout attempt for damaged/lost/in-transit copy. Single variant."""
    tasks = []
    unavail = [
        cid
        for cid in ix.unavailable_copies
        if db["copies"][cid]["status"] in ("damaged", "lost", "in_transit")
    ]
    random.shuffle(unavail)
    eligible = list(ix.active_patrons)
    random.shuffle(eligible)

    for i in range(min(n, len(unavail), len(eligible))):
        cid = unavail[i]
        pid = eligible[i]
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        brid = copy_branch_id(db, cid)
        br = branch_name(db, brid)
        status = db["copies"][cid]["status"]
        name = patron_name(db, pid)
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"checkout_unavailable_{i + 1}",
                f"Test checkout attempt for {status} copy",
                f"Copies with status '{status}' cannot be checked out.",
                f"Patron {name} wants '{title}' at {br} but copy is {status}.",
                pa.label,
                f"You are {name}. You want a specific book. {pa.instructions}",
                f"You want '{title}' from the {br}.",
                f"Your name is {name}. You want '{title}' at the {br}.",
                f"You don't know the copy is {status}.",
                f"Patron {name}: '{title}' at {br} is {status}. Agent should inform.",
                [],
                nl_assertions=[
                    f"The agent informed the patron that the requested copy is not available (status: {status})"
                ],
                reward_basis=["ACTION", "NL_ASSERTION"],
            )
        )
    return tasks


def gen_transfer_scenarios(db, ix, n=4):
    """Transfer to human agent scenarios. Single variant."""
    tasks = []
    eligible = list(ix.active_patrons)
    random.shuffle(eligible)

    transfer_types = [
        {
            "suffix": "dispute_fine",
            "reason": "You want to dispute a fine. You believe it's an error and insist on speaking with someone who can investigate.",
            "known": "Your name is {name}. You have a fine you believe is incorrect.",
            "unknown": "Keep insisting until they transfer you.",
            "ticket": "Patron {name} disputes a fine. Agent should transfer to human.",
            "nl": ["The agent transferred the patron to a human agent"],
        },
        {
            "suffix": "change_info",
            "reason": "You want to update your address and phone number on your library account.",
            "known": "Your name is {name}. You recently moved.",
            "unknown": "If the agent can't update your info, ask to be transferred.",
            "ticket": "Patron {name} wants to update personal info. Agent should transfer to human.",
            "nl": [
                "The agent transferred the patron to a human agent for updating personal information"
            ],
        },
        {
            "suffix": "lost_book",
            "reason": "You lost a library book and want to report it.",
            "known": "Your name is {name}. You lost a book you had checked out.",
            "unknown": "You're not sure what happens when a book is lost.",
            "ticket": "Patron {name} reports lost book. Agent should transfer to human.",
            "nl": [
                "The agent transferred the patron to a human agent to handle the lost book report"
            ],
        },
        {
            "suffix": "meeting_room",
            "reason": "You want to reserve a meeting room at the library for a study group.",
            "known": "Your name is {name}. You want to book a meeting room.",
            "unknown": "You expect the library to have meeting rooms.",
            "ticket": "Patron {name} wants meeting room. Agent should transfer to human.",
            "nl": [
                "The agent transferred the patron to a human agent for meeting room reservation"
            ],
        },
    ]

    for i, scenario in enumerate(transfer_types[:n]):
        if i >= len(eligible):
            break
        pid = eligible[i]
        name = patron_name(db, pid)
        track_use(pid)
        pa = pick_easy_persona()

        tasks.append(
            make_task(
                f"transfer_{scenario['suffix']}",
                f"Test transfer to human agent ({scenario['suffix']})",
                "Agent should transfer to human when unable to resolve.",
                f"Patron {name}: {scenario['suffix']} scenario.",
                pa.label,
                f"You are {name}. {scenario['reason']} {pa.instructions}",
                scenario["reason"],
                scenario["known"].format(name=name),
                scenario["unknown"],
                scenario["ticket"].format(name=name),
                [
                    action(
                        "transfer_1",
                        "transfer_to_human_agents",
                        {"summary": f"Patron {name}: {scenario['suffix']}"},
                        "Transfer to human agent",
                        compare_args=[],
                    )
                ],
                nl_assertions=scenario["nl"],
                reward_basis=["ACTION"],
            )
        )
    return tasks


def gen_find_by_card(db, ix, n=3):
    """Patron identifies by card number. Single variant."""
    tasks = []
    eligible = [pid for pid in ix.active_patrons if patron_can_checkout(db, pid)]
    random.shuffle(eligible)
    avail = list(ix.available_copies)
    random.shuffle(avail)

    for i, pid in enumerate(eligible[:n]):
        if not avail:
            break
        cid = avail.pop()
        name = patron_name(db, pid)
        bid = copy_book_id(db, cid)
        title = book_title(db, bid)
        brid = copy_branch_id(db, cid)
        br = branch_name(db, brid)
        lc = len(db["patrons"][pid]["active_loans"])
        track_use(pid)

        tasks.append(
            make_task(
                f"find_by_card_{i + 1}",
                "Test patron lookup by card number",
                "find_patron_by_card accepts patron_id as library card number.",
                f"Patron {name} gives card number '{pid}'.",
                "Prepared card-holder",
                f"You are {name}. You prefer to identify by card number. You have your library card handy.",
                f"You want to check out '{title}' at the {br}.",
                f"Your library card number is {pid}. You want '{title}' at the {br}.",
                "You don't want to give your name — only your card number.",
                f"Patron gives card '{pid}'. Agent should use find_patron_by_card, then checkout.",
                [
                    action(
                        "find_1",
                        "find_patron_by_card",
                        {"card_number": pid},
                        f"Look up patron by card {pid}",
                        compare_args=[],
                    ),
                    action(
                        "checkout_1",
                        "checkout_book",
                        {"patron_id": pid, "copy_id": cid},
                        f"Check out {cid} to {name}",
                        compare_args=["patron_id", "copy_id"],
                    ),
                ],
                [
                    env_assert(
                        "assert_copy_status",
                        {"copy_id": cid, "expected_status": "checked_out"},
                    ),
                    env_assert(
                        "assert_patron_loan_count",
                        {"patron_id": pid, "expected": lc + 1},
                    ),
                ],
                reward_basis=["ACTION", "ENV_ASSERTION"],
            )
        )
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

    # n = number of base scenarios; generators with variants produce 2*n tasks
    generators_t1 = [
        ("simple_checkout", gen_simple_checkout, 9),
        ("simple_return", gen_simple_return, 6),
        ("overdue_return", gen_overdue_return, 6),
        ("renew_loan", gen_renew_loan, 5),
        ("pay_fine_full", gen_pay_fine_full, 4),
        ("cancel_hold", gen_cancel_hold, 3),
        ("renew_membership", gen_renew_membership, 3),
    ]

    generators_t2 = [
        ("search_title", gen_search_by_title, 3),
        ("search_author_category", gen_search_by_author, 4),
        ("check_availability", gen_check_availability, 3),
        ("list_loans", gen_list_loans, 3),
        ("list_fines", gen_list_fines, 3),
    ]

    generators_t3 = [
        ("checkout_with_fines", gen_checkout_blocked_by_fines, 3),
        ("checkout_expired_membership", gen_checkout_blocked_by_membership, 3),
        ("place_hold", gen_place_hold, 4),
        ("register_event", gen_register_event, 4),
        ("pay_fine_partial", gen_pay_fine_partial, 3),
        ("interlibrary_loan", gen_interlibrary_loan, 3),
        ("waive_fine", gen_waive_fine_eligible, 3),
        ("search_checkout", gen_search_availability_checkout, 4),
    ]

    generators_t4 = [
        ("return_checkout", gen_return_then_checkout, 4),
        ("renew_register_event", gen_renew_membership_register_event, 3),
        ("return_overdue_pay", gen_return_overdue_pay_fine, 3),
        ("hold_and_checkout", gen_hold_plus_checkout_different, 2),
    ]

    generators_t5 = [
        ("checkout_at_limit", gen_checkout_at_limit, 3),
        ("renewal_max", gen_renewal_at_max, 4),
        ("renewal_hold_blocked", gen_renewal_blocked_by_hold, 4),
        ("event_full", gen_event_full, 2),
        ("event_cancelled", gen_event_cancelled, 2),
        ("hold_unnecessary", gen_hold_unnecessary, 3),
        ("waive_ineligible", gen_waive_fine_ineligible, 3),
        ("checkout_unavailable", gen_checkout_unavailable_copy, 3),
        ("transfer", gen_transfer_scenarios, 4),
        ("find_by_card", gen_find_by_card, 3),
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
        t["id"]
        for t in all_tasks
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
