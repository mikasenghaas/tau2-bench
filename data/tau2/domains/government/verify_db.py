#!/usr/bin/env python3
"""Verify government database integrity."""
import json
import sys
from pathlib import Path


def verify(db):
    errors = []

    citizens = db["citizens"]
    households = db["households"]
    permits = db["permits"]
    licenses = db["licenses"]
    tax_accounts = db["tax_accounts"]
    cases = db["cases"]
    departments = db["departments"]

    # Foreign key: citizen -> household
    for cid, c in citizens.items():
        if c["household_id"] not in households:
            errors.append(f"Citizen {cid}: household {c['household_id']} not found")

    # Foreign key: citizen -> tax_accounts
    for cid, c in citizens.items():
        for aid in c["tax_account_ids"]:
            if aid not in tax_accounts:
                errors.append(f"Citizen {cid}: tax account {aid} not found")

    # Foreign key: citizen -> permits
    for cid, c in citizens.items():
        for pid in c["permit_ids"]:
            if pid not in permits:
                errors.append(f"Citizen {cid}: permit {pid} not found")

    # Foreign key: citizen -> licenses
    for cid, c in citizens.items():
        for lid in c["license_ids"]:
            if lid not in licenses:
                errors.append(f"Citizen {cid}: license {lid} not found")

    # Foreign key: citizen -> cases
    for cid, c in citizens.items():
        for caseid in c["case_ids"]:
            if caseid not in cases:
                errors.append(f"Citizen {cid}: case {caseid} not found")

    # Foreign key: household -> members
    for hid, h in households.items():
        for member in h["members"]:
            if member not in citizens:
                errors.append(f"Household {hid}: member {member} not found")

    # Foreign key: household -> property tax account
    for hid, h in households.items():
        if h["property_tax_account_id"] and h["property_tax_account_id"] not in tax_accounts:
            errors.append(
                f"Household {hid}: tax account {h['property_tax_account_id']} not found"
            )

    # Reverse FK: permits -> citizens
    for pid, p in permits.items():
        if p["citizen_id"] not in citizens:
            errors.append(f"Permit {pid}: citizen {p['citizen_id']} not found")

    # Reverse FK: licenses -> citizens
    for lid, l in licenses.items():
        if l["citizen_id"] not in citizens:
            errors.append(f"License {lid}: citizen {l['citizen_id']} not found")

    # Reverse FK: tax accounts -> citizens
    for aid, a in tax_accounts.items():
        if a["citizen_id"] not in citizens:
            errors.append(f"Tax account {aid}: citizen {a['citizen_id']} not found")

    # Reverse FK: cases -> citizens
    for caseid, c in cases.items():
        if c["citizen_id"] not in citizens:
            errors.append(f"Case {caseid}: citizen {c['citizen_id']} not found")

    # Zoning consistency: no business permits in residential zones
    for pid, p in permits.items():
        if p["type"] == "business":
            cid = p["citizen_id"]
            if cid in citizens:
                hid = citizens[cid]["household_id"]
                if hid in households and households[hid]["zoning_type"] == "residential":
                    errors.append(
                        f"Permit {pid}: business permit for citizen in residential zone"
                    )

    # Status consistency: suspended/revoked licenses should not be renewal_eligible
    for lid, l in licenses.items():
        if l["status"] in ("suspended", "revoked") and l["renewal_eligible"]:
            errors.append(
                f"License {lid}: {l['status']} but renewal_eligible=True"
            )

    # Payment plan consistency
    for aid, a in tax_accounts.items():
        if a["payment_plan_active"] and a["installments_remaining"] <= 0:
            errors.append(
                f"Tax account {aid}: payment plan active but 0 installments remaining"
            )
        if not a["payment_plan_active"] and a["installments_remaining"] > 0:
            errors.append(
                f"Tax account {aid}: payment plan inactive but {a['installments_remaining']} installments remaining"
            )

    # Cases: assigned_department should be valid
    for caseid, c in cases.items():
        if c["assigned_department"] and c["assigned_department"] not in departments:
            errors.append(
                f"Case {caseid}: department {c['assigned_department']} not found"
            )

    # No duplicate citizen names
    names = [c["name"] for c in citizens.values()]
    seen = set()
    for name in names:
        if name in seen:
            errors.append(f"Duplicate citizen name: {name}")
        seen.add(name)

    return errors


if __name__ == "__main__":
    db = json.loads((Path(__file__).parent / "db.json").read_text())
    errors = verify(db)
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print(f"\n{len(errors)} error(s) found")
        sys.exit(1)
    else:
        print("All verification checks passed")
        sys.exit(0)
