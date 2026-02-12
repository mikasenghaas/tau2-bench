#!/usr/bin/env python3
"""Verify the restaurant database for referential integrity and edge-case coverage.

Run from repo root:
    uv run python environments/service_agent/tau2/data/tau2/domains/restaurant/verify_db.py
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

TODAY = datetime(2025, 10, 15)
MODIFICATION_CUTOFF_HOURS = 2
CANCELLATION_FEE_CUTOFF_HOURS = 1
CANCELLATION_FEE_PARTY_SIZE = 6

db_path = Path(__file__).parent / "db.json"
with open(db_path) as f:
    db = json.load(f)

customers = db["customers"]
reservations = db["reservations"]
tables = db["tables"]
locations = db["locations"]
menu_items = db["menu_items"]
orders = db["orders"]
payment_methods = db["payment_methods"]

errors = []
warnings = []


def check(condition, msg):
    if not condition:
        errors.append(msg)


def warn(condition, msg):
    if not condition:
        warnings.append(msg)


# ── Referential integrity ──────────────────────────────────────────────────
for rid, res in reservations.items():
    check(res["customer_id"] in customers,
          f"Reservation {rid}: unknown customer {res['customer_id']}")
    check(res["location_id"] in locations,
          f"Reservation {rid}: unknown location {res['location_id']}")
    if res["table_id"]:
        check(res["table_id"] in tables,
              f"Reservation {rid}: unknown table {res['table_id']}")

for oid, order in orders.items():
    check(order["customer_id"] in customers,
          f"Order {oid}: unknown customer {order['customer_id']}")
    check(order["location_id"] in locations,
          f"Order {oid}: unknown location {order['location_id']}")
    for item in order["items"]:
        check(item["item_id"] in menu_items,
              f"Order {oid}: unknown menu item {item['item_id']}")

for pm_id, pm in payment_methods.items():
    check(pm["customer_id"] in customers,
          f"Payment {pm_id}: unknown customer {pm['customer_id']}")

# ── Back-references ────────────────────────────────────────────────────────
for cid, cust in customers.items():
    for rid in cust["reservation_ids"]:
        check(rid in reservations,
              f"Customer {cid}: unknown reservation {rid}")
        if rid in reservations:
            check(reservations[rid]["customer_id"] == cid,
                  f"Customer {cid}: reservation {rid} belongs to {reservations[rid]['customer_id']}")
    for oid in cust["order_ids"]:
        check(oid in orders,
              f"Customer {cid}: unknown order {oid}")
        if oid in orders:
            check(orders[oid]["customer_id"] == cid,
                  f"Customer {cid}: order {oid} belongs to {orders[oid]['customer_id']}")

# ── Unique names ───────────────────────────────────────────────────────────
name_counts = defaultdict(int)
for cust in customers.values():
    name_counts[cust["name"]] += 1
for name, cnt in name_counts.items():
    check(cnt == 1, f"Duplicate customer name: {name} ({cnt} occurrences)")

# ── Order total consistency ────────────────────────────────────────────────
for oid, order in orders.items():
    expected = round(sum(it["price"] * it["quantity"] for it in order["items"]), 2)
    check(abs(order["total"] - expected) < 0.01,
          f"Order {oid}: total {order['total']} != computed {expected}")

# ── Edge case coverage ──────────────────────────────────────────────────────
confirmed_future = []
confirmed_within_2h = []
confirmed_within_1h_large_party = []
confirmed_within_1h_small_party = []
waitlisted = []

for rid, res in reservations.items():
    if res["status"] == "confirmed":
        try:
            res_dt = datetime.strptime(f"{res['date']} {res['time']}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        cutoff_mod = res_dt - timedelta(hours=MODIFICATION_CUTOFF_HOURS)
        cutoff_cancel = res_dt - timedelta(hours=CANCELLATION_FEE_CUTOFF_HOURS)
        if TODAY >= cutoff_mod:
            confirmed_within_2h.append(rid)
            if TODAY >= cutoff_cancel and res["party_size"] > CANCELLATION_FEE_PARTY_SIZE:
                confirmed_within_1h_large_party.append(rid)
            elif TODAY >= cutoff_cancel and res["party_size"] <= CANCELLATION_FEE_PARTY_SIZE:
                confirmed_within_1h_small_party.append(rid)
        else:
            confirmed_future.append(rid)
    elif res["status"] == "waitlisted":
        waitlisted.append(rid)

placed_orders = [oid for oid, o in orders.items() if o["status"] == "placed"]
preparing_orders = [oid for oid, o in orders.items() if o["status"] == "preparing"]
immutable_orders = [oid for oid, o in orders.items()
                    if o["status"] in ("ready", "delivered", "completed", "cancelled")]

customers_with_allergies = [cid for cid, c in customers.items() if c["allergy_info"]]
customers_with_diet = [cid for cid, c in customers.items() if c["dietary_restrictions"]]
high_loyalty = [cid for cid, c in customers.items() if c["loyalty_points"] >= 500]
zero_loyalty = [cid for cid, c in customers.items() if c["loyalty_points"] == 0]

warn(len(confirmed_future) >= 10,
     f"Need >=10 future confirmed reservations, have {len(confirmed_future)}")
warn(len(confirmed_within_2h) >= 3,
     f"Need >=3 within-2h confirmed reservations, have {len(confirmed_within_2h)}")
warn(len(confirmed_within_1h_large_party) >= 2,
     f"Need >=2 within-1h large-party reservations, have {len(confirmed_within_1h_large_party)}")
warn(len(confirmed_within_1h_small_party) >= 2,
     f"Need >=2 within-1h small-party reservations, have {len(confirmed_within_1h_small_party)}")
warn(len(waitlisted) >= 3,
     f"Need >=3 waitlisted reservations, have {len(waitlisted)}")
warn(len(placed_orders) >= 5,
     f"Need >=5 placed orders, have {len(placed_orders)}")
warn(len(preparing_orders) >= 5,
     f"Need >=5 preparing orders, have {len(preparing_orders)}")
warn(len(immutable_orders) >= 5,
     f"Need >=5 immutable orders, have {len(immutable_orders)}")
warn(len(customers_with_allergies) >= 10,
     f"Need >=10 customers with allergies, have {len(customers_with_allergies)}")
warn(len(customers_with_diet) >= 10,
     f"Need >=10 customers with dietary restrictions, have {len(customers_with_diet)}")
warn(len(high_loyalty) >= 5,
     f"Need >=5 high-loyalty customers, have {len(high_loyalty)}")
warn(len(zero_loyalty) >= 5,
     f"Need >=5 zero-loyalty customers, have {len(zero_loyalty)}")

# ── Report ──────────────────────────────────────────────────────────────────
print("=" * 60)
print("RESTAURANT DATABASE VERIFICATION")
print("=" * 60)
print(f"\nEntities: {len(customers)} customers, {len(reservations)} reservations, "
      f"{len(orders)} orders, {len(tables)} tables, {len(menu_items)} menu items, "
      f"{len(payment_methods)} payment methods")
print(f"\nEdge cases:")
print(f"  Future confirmed reservations:     {len(confirmed_future)}")
print(f"  Within-2h (not modifiable):        {len(confirmed_within_2h)}")
print(f"  Within-1h + party > 6 (fee):       {len(confirmed_within_1h_large_party)}")
print(f"  Within-1h + party <= 6 (no fee):   {len(confirmed_within_1h_small_party)}")
print(f"  Waitlisted:                        {len(waitlisted)}")
print(f"  Placed orders:                     {len(placed_orders)}")
print(f"  Preparing orders:                  {len(preparing_orders)}")
print(f"  Customers with allergies:          {len(customers_with_allergies)}")
print(f"  High-loyalty (500+):               {len(high_loyalty)}")
print(f"  Zero-loyalty:                      {len(zero_loyalty)}")

if errors:
    print(f"\n!! ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

if warnings:
    print(f"\n!! WARNINGS ({len(warnings)}):")
    for w in warnings:
        print(f"  - {w}")

print("\nAll checks passed" if not warnings else "\nPassed with warnings")
