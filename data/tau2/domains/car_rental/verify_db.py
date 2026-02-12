#!/usr/bin/env python3
"""Verify car rental database integrity."""
import json
import sys
from pathlib import Path


def verify(db):
    errors = []
    customers = db["customers"]
    vehicles = db["vehicles"]
    locations = db["locations"]
    reservations = db["reservations"]
    agreements = db["rental_agreements"]
    invoices = db["invoices"]
    extras = db["extras"]

    # Check reservation foreign keys
    for rid, res in reservations.items():
        if res["customer_id"] not in customers:
            errors.append(f"Reservation {rid}: customer {res['customer_id']} not found")
        if res["pickup_location_id"] not in locations:
            errors.append(f"Reservation {rid}: pickup location {res['pickup_location_id']} not found")
        if res["dropoff_location_id"] not in locations:
            errors.append(f"Reservation {rid}: dropoff location {res['dropoff_location_id']} not found")
        if res["vehicle_id"] and res["vehicle_id"] not in vehicles:
            errors.append(f"Reservation {rid}: vehicle {res['vehicle_id']} not found")
        for eid in res.get("extras", []):
            if eid not in extras:
                errors.append(f"Reservation {rid}: extra {eid} not found")
        # Status check
        if res["status"] not in ("confirmed", "active", "completed", "cancelled", "no_show"):
            errors.append(f"Reservation {rid}: invalid status {res['status']}")

    # Check agreement foreign keys
    for aid, agr in agreements.items():
        if agr["reservation_id"] not in reservations:
            errors.append(f"Agreement {aid}: reservation {agr['reservation_id']} not found")
        if agr["customer_id"] not in customers:
            errors.append(f"Agreement {aid}: customer {agr['customer_id']} not found")
        if agr["vehicle_id"] not in vehicles:
            errors.append(f"Agreement {aid}: vehicle {agr['vehicle_id']} not found")

    # Check invoice foreign keys
    for iid, inv in invoices.items():
        if inv["customer_id"] not in customers:
            errors.append(f"Invoice {iid}: customer {inv['customer_id']} not found")
        if inv["agreement_id"] not in agreements:
            errors.append(f"Invoice {iid}: agreement {inv['agreement_id']} not found")

    # Check customer reservation back-references
    for cid, cust in customers.items():
        for rid in cust["reservations"]:
            if rid not in reservations:
                errors.append(f"Customer {cid}: reservation {rid} not found")
            elif reservations[rid]["customer_id"] != cid:
                errors.append(f"Customer {cid}: reservation {rid} belongs to {reservations[rid]['customer_id']}")

    # Check vehicle statuses
    for vid, veh in vehicles.items():
        if veh["status"] not in ("available", "rented", "maintenance", "reserved"):
            errors.append(f"Vehicle {vid}: invalid status {veh['status']}")
        if veh["location_id"] not in locations:
            errors.append(f"Vehicle {vid}: location {veh['location_id']} not found")

    # Check no duplicate customer names
    names = [c["name"] for c in customers.values()]
    seen = set()
    for name in names:
        if name in seen:
            errors.append(f"Duplicate customer name: {name}")
        seen.add(name)

    # Check active reservations have matching active agreements
    active_res = [r for r in reservations.values() if r["status"] == "active"]
    active_agr_res_ids = {a["reservation_id"] for a in agreements.values() if a["actual_dropoff"] is None}
    for res in active_res:
        if res["reservation_id"] not in active_agr_res_ids:
            errors.append(f"Active reservation {res['reservation_id']} has no active agreement")

    return errors


if __name__ == "__main__":
    db = json.loads((Path(__file__).parent / "db.json").read_text())
    errors = verify(db)
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print(f"\n{len(errors)} errors found")
        sys.exit(1)
    else:
        print("Database verification passed. No errors found.")
        sys.exit(0)
