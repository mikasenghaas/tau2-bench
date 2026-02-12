# Car Rental Domain

A customer service benchmark domain for **DriveEasy Car Rentals**, featuring 194 tasks across 5 difficulty tiers. Agents must handle reservations, modifications, cancellations, roadside assistance, loyalty programs, damage reports, and policy edge cases.

## Domain Overview

| Property | Value |
|----------|-------|
| Customers | 150 |
| Vehicles | 200 (6 categories) |
| Locations | 8 (2 airport, 6 city) |
| Reservations | 285 |
| Rental Agreements | 205 |
| Invoices | 180 |
| Extras | 7 |
| Tools | 22 (12 READ, 8 WRITE, 2 GENERIC) |
| Tasks | 194 (121 easy, 73 hard) |

### Task Tiers

| Tier | Description | Tasks | Examples |
|------|-------------|-------|----------|
| 1 - Simple Single-Action | Basic CRUD operations | 76 | Create reservation, cancel, modify dates |
| 2 - Information & Search | Read-only lookups | 26 | Search vehicles, check invoice, list extras |
| 3 - Moderate Multi-Step | Multiple tools + reasoning | 41 | Reservation with insurance + extras, one-way rental |
| 4 - Complex Multi-Step | Chained operations | 22 | Cancel and rebook, extend rental + add extras |
| 5 - Edge Cases & Policy | Policy enforcement | 29 | Underage luxury, expired license, over-limit credit |

### Evaluation Criteria

| Reward Basis | Tasks |
|-------------|-------|
| ACTION + ENV_ASSERTION | 106 |
| ACTION + NL_ASSERTION | 52 |
| ACTION only | 33 |
| NL_ASSERTION only | 3 |

## Baseline Results

### v1 (Pre-Fix) — Qwen3-4B-Instruct

| Metric | Value |
|--------|-------|
| **Average Reward** | **0.273** (53/194 solved) |
| Avg Turns | 11.5 |
| Avg Errors | 3.3 |
| Avg Tool Calls | 6.3 |
| Avg Input Tokens | 57,980 |
| Avg Output Tokens | 1,068 |
| Total Time | 271s |

**Root cause analysis of failures (141/194):**

The v1 environment had several bugs that inflated the failure rate. An estimated ~95 of the 141 failures were caused by environment design issues rather than agent capability limitations:

1. **No `list_locations` tool** (~60-70 failures): Agents had no way to discover valid location IDs for `search_vehicles` and `create_reservation`. They would guess location names or hallucinate IDs, causing tool call failures.

2. **No agreement ID discovery path** (~25 failures): Tasks requiring `extend_rental`, `roadside_assistance`, or `report_damage` needed an `agreement_id`, but there was no tool to look up agreements from customer/reservation data.

3. **`extend_add_extras` impossible** (8 failures): `modify_reservation` rejected all changes on active reservations, but the `extend_add_extras` tasks required modifying extras on active rentals.

4. **Loose `issue_credit` compare_args**: Only checked `customer_id`, not `amount`, producing false positives.

5. **Grammar issues**: "a economy car", "a SUV", "1 days" in task text confused the user simulator.

### Changes Made (v1 → v2)

**Tools (tools.py):**
- Added `list_locations` READ tool — returns all rental locations with IDs and details
- Added `find_rental_agreements_by_customer` READ tool — looks up agreements by customer ID
- Fixed `modify_reservation` — active reservations now allow extras-only changes

**Task Generation (generate_tasks.py):**
- Fixed article grammar: "a economy" → "an economy", "a suv" → "an SUV"
- Fixed day pluralization: "1 days" → "1 day"
- Tightened `issue_credit` compare_args to check both `customer_id` and `amount`
- Updated `modify_active` NL assertion to reflect new active-reservation behavior

**Policy (policy.md):**
- Updated modification rules to document active rental extras changes

**Tests:**
- Added 7 new tests (68 total): `list_locations`, `find_rental_agreements_by_customer`, active extras modification

### v2 (Post-Fix) — Qwen3-4B-Instruct

| Metric | v1 | v2 | Delta |
|--------|----|----|-------|
| **Average Reward** | **0.273** (53/194) | **0.469** (91/194) | **+72%** |
| Avg Turns | 11.5 | 10.1 | -1.4 |
| Avg Errors | 3.3 | 0.9 | -2.4 |
| Avg Tool Calls | 6.3 | 5.1 | -1.2 |
| Avg Input Tokens | 57,980 | 57,127 | -853 |
| Avg Output Tokens | 1,068 | 1,282 | +214 |
| Total Time | 271s | 255s | -16s |

### Results by Task Type

| Task Type | v1 | v2 | Delta |
|-----------|----|----|-------|
| create_reservation | 0/24 | 17/24 | **+17** |
| search_vehicles | 1/10 | 9/10 | **+8** |
| res_ins_extras | 0/8 | 5/8 | **+5** |
| one_way | 1/8 | 5/8 | **+4** |
| modify_dates | 5/10 | 8/10 | +3 |
| extend_rental | 0/10 | 3/10 | +3 |
| extend_add_extras | 0/8 | 2/8 | +2 |
| report_damage | 0/5 | 2/5 | +2 |
| roadside | 0/10 | 2/10 | +2 |
| check_invoice | 7/8 | 8/8 | +1 |
| cancel_reservation | 8/12 | 5/12 | -3 |
| cancel_rebook | 1/8 | 1/8 | 0 |
| cancel_already | 1/3 | 1/3 | 0 |
| modify_insurance | 3/10 | 2/10 | -1 |
| modify_active | 2/4 | 2/4 | 0 |
| upgrade_category | 5/10 | 3/10 | -2 |
| apply_loyalty | 4/5 | 0/5 | -4 |
| loyalty_booking | 0/6 | 0/6 | 0 |
| issue_credit | 1/5 | 0/5 | -1 |
| check_reservation | 4/4 | 3/4 | -1 |
| find_by_email | 4/4 | 4/4 | 0 |
| list_extras | 4/4 | 2/4 | -2 |
| expired_license | 1/4 | 2/4 | +1 |
| luxury_underage | 0/3 | 1/3 | +1 |
| credit_over_limit | 0/3 | 1/3 | +1 |
| dispute_invoice | 1/4 | 1/4 | 0 |
| transfer_* | 0/4 | 2/4 | +2 |

### Results by Difficulty

| Difficulty | v1 | v2 |
|------------|----|----|
| Easy (a) | 21/73 (28.8%) | 38/73 (52.1%) |
| Hard (b) | 14/73 (19.2%) | 35/73 (47.9%) |
| Single variant | 18/48 (37.5%) | 18/48 (37.5%) |

### Remaining Failure Analysis (v2)

The 103 remaining failures in v2 are primarily model capability limitations:

| Pattern | Count | Top Task Types |
|---------|-------|----------------|
| Missing `modify_reservation` call | 18 | modify_insurance (8), upgrade_category (5) |
| Wrong args on `create_reservation` | 10 | create_reservation (5), one_way (3) |
| Missing `cancel_reservation` call | 10 | cancel_reservation (6), cancel_rebook (4) |
| Wrong args on `extend_rental` | 8 | extend_rental (7) |
| Tool errors (edge cases) | 8 | luxury_underage, expired_license, modify_active |
| Wrong args on `roadside_assistance` | 7 | roadside (7) |
| Missing `apply_loyalty_discount` | 7 | loyalty_booking (6) |
| Missing `transfer_to_human_agents` | 5 | dispute_invoice (3) |
| Wrong args on `issue_credit` | 4 | issue_credit (4) |
| Wrong args on `apply_loyalty_discount` | 4 | apply_loyalty (4) |

The largest improvement areas were tasks needing location discovery (`create_reservation` +17, `search_vehicles` +8) — directly attributable to the `list_locations` tool fix.
