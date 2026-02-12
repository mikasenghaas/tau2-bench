#!/usr/bin/env python3
"""Generate IT helpdesk database (db.json + user_db.json).

Deterministic via random.seed(42). Uses only stdlib modules.

Usage:
    python generate_db.py
"""

import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

TODAY = datetime(2025, 10, 15)
HERE = Path(__file__).parent


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
# Step 1: Departments & Roles
# ═══════════════════════════════════════════════════════════════════════════
DEPARTMENTS = [
    {
        "name": "Engineering",
        "roles": [
            "Software Engineer",
            "Senior Engineer",
            "Tech Lead",
            "Engineering Manager",
        ],
        "weight": 30,
    },
    {
        "name": "Product",
        "roles": ["Product Manager", "Senior PM", "Product Director"],
        "weight": 10,
    },
    {
        "name": "Design",
        "roles": ["UI Designer", "UX Researcher", "Design Lead"],
        "weight": 8,
    },
    {
        "name": "Sales",
        "roles": ["Account Executive", "Sales Manager", "Sales Director"],
        "weight": 12,
    },
    {
        "name": "Marketing",
        "roles": ["Marketing Specialist", "Content Manager", "Marketing Director"],
        "weight": 8,
    },
    {"name": "HR", "roles": ["HR Specialist", "Recruiter", "HR Manager"], "weight": 6},
    {
        "name": "Finance",
        "roles": ["Accountant", "Financial Analyst", "Finance Manager"],
        "weight": 6,
    },
    {
        "name": "IT",
        "roles": ["IT Support", "System Administrator", "IT Manager"],
        "weight": 8,
    },
    {
        "name": "Legal",
        "roles": ["Legal Counsel", "Compliance Officer", "Legal Director"],
        "weight": 4,
    },
    {
        "name": "Operations",
        "roles": ["Operations Analyst", "Operations Manager", "VP Operations"],
        "weight": 8,
    },
]

dept_names = [d["name"] for d in DEPARTMENTS]
dept_weights = [d["weight"] for d in DEPARTMENTS]
dept_roles = {d["name"]: d["roles"] for d in DEPARTMENTS}

# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Employees (150)
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
    "Alex",
    "Priya",
    "Wei",
    "Fatima",
    "Raj",
    "Yuki",
    "Carlos",
    "Aisha",
    "Omar",
    "Sofia",
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
    "Chen",
    "Patel",
    "Kim",
    "Singh",
    "Tanaka",
    "Mueller",
    "Ali",
    "Okafor",
    "Ivanov",
    "Santos",
]

employees = {}
employee_names_set = set()
employee_ids_set = set()

# Pre-select indices for locked accounts (~5%), disabled (~2%)
locked_indices = set(random.sample(range(150), 8))
disabled_indices = set(
    random.sample([i for i in range(150) if i not in locked_indices], 3)
)

# Pre-select managers (one per department, plus a few extra)
managers = {}  # dept -> employee_id

for i in range(150):
    for _attempt in range(500):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        display_name = f"{first} {last}"
        if display_name not in employee_names_set:
            break
    else:
        raise RuntimeError("Could not find unique name")
    employee_names_set.add(display_name)

    base_id = f"{first.lower()}_{last.lower()}"
    eid = base_id
    employee_ids_set.add(eid)

    dept = random.choices(dept_names, weights=dept_weights, k=1)[0]
    roles = dept_roles[dept]
    role = random.choice(roles)

    # First employee in each department becomes manager
    if dept not in managers:
        role = [r for r in roles if "Manager" in r or "Director" in r or "Lead" in r]
        role = role[0] if role else roles[-1]
        managers[dept] = eid
    manager_id = managers.get(dept)
    if manager_id == eid:
        manager_id = None  # Don't be your own manager

    account_status = "active"
    if i in locked_indices:
        account_status = "locked"
    elif i in disabled_indices:
        account_status = "disabled"

    mfa_enabled = random.random() < 0.6
    vpn_access = random.random() < 0.7
    last_pw_reset = TODAY - timedelta(days=random.randint(1, 180))

    email = f"{first.lower()}.{last.lower()}@techcorp.com"

    employees[eid] = {
        "employee_id": eid,
        "name": display_name,
        "email": email,
        "department": dept,
        "role": role,
        "manager_id": manager_id,
        "device_ids": [],
        "software_licenses": [],
        "vpn_access": vpn_access,
        "mfa_enabled": mfa_enabled,
        "account_status": account_status,
        "last_password_reset": date_str(last_pw_reset),
        "access_group_ids": [],
    }

all_employee_ids = list(employees.keys())
active_employee_ids = [
    eid for eid in all_employee_ids if employees[eid]["account_status"] == "active"
]


# ═══════════════════════════════════════════════════════════════════════════
# Step 3: Devices (180)
# ═══════════════════════════════════════════════════════════════════════════
DEVICE_MODELS = {
    "laptop": [
        ("Dell XPS 15", "Windows", "11"),
        ("MacBook Pro 14", "macOS", "14.1"),
        ("ThinkPad X1 Carbon", "Windows", "11"),
        ("MacBook Air M2", "macOS", "14.0"),
        ("HP EliteBook 840", "Windows", "11"),
        ("Dell Latitude 5540", "Windows", "10"),
    ],
    "desktop": [
        ("Dell OptiPlex 7090", "Windows", "11"),
        ("iMac 24", "macOS", "14.1"),
        ("HP ProDesk 400", "Windows", "10"),
    ],
    "phone": [
        ("iPhone 15 Pro", "iOS", "17.1"),
        ("Samsung Galaxy S24", "Android", "14"),
        ("Google Pixel 8", "Android", "14"),
    ],
}

DEVICE_TYPE_WEIGHTS = [70, 15, 15]  # laptop, desktop, phone
DEVICE_TYPES = ["laptop", "desktop", "phone"]

STANDARD_SOFTWARE = ["Chrome", "Outlook", "Teams", "Slack", "Zoom", "1Password"]
DEV_SOFTWARE = ["VS Code", "Git", "Docker", "Postman", "IntelliJ IDEA"]
DESIGN_SOFTWARE = ["Figma", "Adobe Creative Suite", "Sketch"]
OFFICE_SOFTWARE = ["Microsoft Office", "Google Workspace"]

devices = {}
serial_counter = 1000

# Assign 1 laptop to each active employee, then distribute extras
for eid in all_employee_ids:
    dtype = "laptop"
    model_info = random.choice(DEVICE_MODELS[dtype])
    model_name, os_name, os_ver = model_info

    serial = f"SN-{serial_counter:06d}"
    serial_counter += 1

    last = employees[eid]["name"].split()[-1].lower()
    did = make_unique_id(f"dev_{last}_{dtype[:4]}", devices)

    assigned_date = TODAY - timedelta(days=random.randint(30, 730))
    warranty_days = random.choice([365, 730, 1095])  # 1, 2, or 3 year warranty
    warranty_expiry = assigned_date + timedelta(days=warranty_days)

    # Installed software based on department
    dept = employees[eid]["department"]
    installed = list(STANDARD_SOFTWARE)
    if dept == "Engineering":
        installed.extend(random.sample(DEV_SOFTWARE, min(3, len(DEV_SOFTWARE))))
    elif dept == "Design":
        installed.extend(random.sample(DESIGN_SOFTWARE, min(2, len(DESIGN_SOFTWARE))))
    installed.extend(random.sample(OFFICE_SOFTWARE, 1))
    installed = list(set(installed))

    status = "active"
    if employees[eid]["account_status"] == "disabled":
        status = "decommissioned"

    devices[did] = {
        "device_id": did,
        "employee_id": eid,
        "type": dtype,
        "model": model_name,
        "os": os_name,
        "os_version": os_ver,
        "serial_number": serial,
        "status": status,
        "assigned_date": date_str(assigned_date),
        "warranty_expiry": date_str(warranty_expiry),
        "installed_software": installed,
    }
    employees[eid]["device_ids"].append(did)

# Add some extra devices (phones, desktops) for ~20% of employees
extra_device_employees = random.sample(
    active_employee_ids, min(30, len(active_employee_ids))
)
for eid in extra_device_employees:
    dtype = random.choice(["desktop", "phone"])
    model_info = random.choice(DEVICE_MODELS[dtype])
    model_name, os_name, os_ver = model_info

    serial = f"SN-{serial_counter:06d}"
    serial_counter += 1

    last = employees[eid]["name"].split()[-1].lower()
    did = make_unique_id(f"dev_{last}_{dtype[:4]}", devices)

    assigned_date = TODAY - timedelta(days=random.randint(30, 365))
    warranty_expiry = assigned_date + timedelta(days=random.choice([365, 730]))

    devices[did] = {
        "device_id": did,
        "employee_id": eid,
        "type": dtype,
        "model": model_name,
        "os": os_name,
        "os_version": os_ver,
        "serial_number": serial,
        "status": "active",
        "assigned_date": date_str(assigned_date),
        "warranty_expiry": date_str(warranty_expiry),
        "installed_software": list(STANDARD_SOFTWARE),
    }
    employees[eid]["device_ids"].append(did)

# Mark ~5 devices as in repair
repair_candidates = [did for did, d in devices.items() if d["status"] == "active"]
random.shuffle(repair_candidates)
for did in repair_candidates[:5]:
    devices[did]["status"] = "repair"


# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Software Catalog & Licenses
# ═══════════════════════════════════════════════════════════════════════════
SOFTWARE_CATALOG = [
    {
        "software_name": "Jira",
        "category": "standard",
        "total_licenses": 120,
        "requires_approval": False,
    },
    {
        "software_name": "Confluence",
        "category": "standard",
        "total_licenses": 160,
        "requires_approval": False,
    },
    {
        "software_name": "GitHub Enterprise",
        "category": "standard",
        "total_licenses": 80,
        "requires_approval": False,
    },
    {
        "software_name": "Slack Pro",
        "category": "standard",
        "total_licenses": 150,
        "requires_approval": False,
    },
    {
        "software_name": "VS Code Pro",
        "category": "standard",
        "total_licenses": 60,
        "requires_approval": False,
    },
    {
        "software_name": "Zoom Business",
        "category": "standard",
        "total_licenses": 100,
        "requires_approval": False,
    },
    {
        "software_name": "Figma",
        "category": "standard",
        "total_licenses": 30,
        "requires_approval": False,
    },
    {
        "software_name": "Adobe Creative Suite",
        "category": "non_standard",
        "total_licenses": 15,
        "requires_approval": True,
    },
    {
        "software_name": "IntelliJ IDEA Ultimate",
        "category": "non_standard",
        "total_licenses": 20,
        "requires_approval": True,
    },
    {
        "software_name": "Tableau",
        "category": "non_standard",
        "total_licenses": 10,
        "requires_approval": True,
    },
    {
        "software_name": "AWS Admin Console",
        "category": "restricted",
        "total_licenses": 5,
        "requires_approval": True,
    },
    {
        "software_name": "CyberArk",
        "category": "restricted",
        "total_licenses": 3,
        "requires_approval": True,
    },
]

software_catalog = {}
for sw in SOFTWARE_CATALOG:
    software_catalog[sw["software_name"]] = {
        "software_name": sw["software_name"],
        "category": sw["category"],
        "available_licenses": sw["total_licenses"],
        "requires_approval": sw["requires_approval"],
    }

# Assign licenses based on department
software_licenses = {}
license_id_set = set()

DEPT_SOFTWARE = {
    "Engineering": [
        "Jira",
        "Confluence",
        "GitHub Enterprise",
        "VS Code Pro",
        "Slack Pro",
    ],
    "Product": ["Jira", "Confluence", "Slack Pro", "Zoom Business"],
    "Design": ["Jira", "Figma", "Slack Pro", "Confluence"],
    "Sales": ["Slack Pro", "Zoom Business", "Confluence"],
    "Marketing": ["Slack Pro", "Zoom Business", "Confluence", "Jira"],
    "HR": ["Slack Pro", "Zoom Business", "Confluence"],
    "Finance": ["Slack Pro", "Zoom Business", "Confluence"],
    "IT": ["Jira", "Confluence", "GitHub Enterprise", "Slack Pro", "VS Code Pro"],
    "Legal": ["Slack Pro", "Zoom Business", "Confluence"],
    "Operations": ["Jira", "Slack Pro", "Zoom Business", "Confluence"],
}

for eid, emp in employees.items():
    dept = emp["department"]
    sw_list = DEPT_SOFTWARE.get(dept, ["Slack Pro"])
    for sw_name in sw_list:
        if sw_name not in software_catalog:
            continue
        if software_catalog[sw_name]["available_licenses"] <= 0:
            continue

        last = emp["name"].split()[-1].lower()
        sw_slug = sw_name.lower().replace(" ", "_")
        base_lid = f"lic_{last}_{sw_slug}"
        lid = make_unique_id(base_lid, license_id_set)
        license_id_set.add(lid)

        expiry = TODAY + timedelta(days=random.randint(60, 400))
        status = "active"
        if emp["account_status"] == "disabled":
            status = "revoked"

        software_licenses[lid] = {
            "license_id": lid,
            "software_name": sw_name,
            "version": "latest",
            "license_type": "per_user",
            "assigned_to": eid,
            "expiry_date": date_str(expiry),
            "status": status,
        }
        employees[eid]["software_licenses"].append(lid)
        if status == "active":
            software_catalog[sw_name]["available_licenses"] -= 1

# Add some expired licenses (10)
expired_lic_candidates = [
    lid for lid, lic in software_licenses.items() if lic["status"] == "active"
]
random.shuffle(expired_lic_candidates)
for lid in expired_lic_candidates[:10]:
    software_licenses[lid]["status"] = "expired"
    software_licenses[lid]["expiry_date"] = date_str(
        TODAY - timedelta(days=random.randint(1, 90))
    )


# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Access Groups (10)
# ═══════════════════════════════════════════════════════════════════════════
ACCESS_GROUP_SPECS = [
    {
        "group_id": "jira_users",
        "name": "Jira Users",
        "description": "Access to Jira project management tool",
        "permissions": ["jira.read", "jira.write"],
        "requires_approval": False,
    },
    {
        "group_id": "confluence_users",
        "name": "Confluence Users",
        "description": "Access to Confluence wiki and documentation",
        "permissions": ["confluence.read", "confluence.write"],
        "requires_approval": False,
    },
    {
        "group_id": "github_users",
        "name": "GitHub Users",
        "description": "Access to GitHub Enterprise repositories",
        "permissions": ["github.read", "github.write", "github.pr"],
        "requires_approval": False,
    },
    {
        "group_id": "slack_users",
        "name": "Slack Users",
        "description": "Access to Slack messaging platform",
        "permissions": ["slack.read", "slack.write"],
        "requires_approval": False,
    },
    {
        "group_id": "zoom_users",
        "name": "Zoom Users",
        "description": "Access to Zoom video conferencing",
        "permissions": ["zoom.host", "zoom.join"],
        "requires_approval": False,
    },
    {
        "group_id": "vpn_users",
        "name": "VPN Users",
        "description": "Access to corporate VPN for remote work",
        "permissions": ["vpn.connect"],
        "requires_approval": False,
    },
    {
        "group_id": "staging_access",
        "name": "Staging Environment",
        "description": "Access to staging/testing environment",
        "permissions": ["staging.deploy", "staging.read"],
        "requires_approval": False,
    },
    {
        "group_id": "admin_access",
        "name": "Admin Access",
        "description": "Administrative access to production systems",
        "permissions": ["admin.full"],
        "requires_approval": True,
    },
    {
        "group_id": "security_tools",
        "name": "Security Tools",
        "description": "Access to security monitoring and audit tools",
        "permissions": ["security.audit", "security.monitor"],
        "requires_approval": True,
    },
    {
        "group_id": "production_db",
        "name": "Production Database",
        "description": "Direct access to production databases",
        "permissions": ["db.read", "db.write"],
        "requires_approval": True,
    },
]

access_groups = {}
for spec in ACCESS_GROUP_SPECS:
    access_groups[spec["group_id"]] = {
        "group_id": spec["group_id"],
        "name": spec["name"],
        "description": spec["description"],
        "members": [],
        "permissions": spec["permissions"],
        "requires_approval": spec["requires_approval"],
    }

# Assign employees to standard groups based on department
DEPT_GROUPS = {
    "Engineering": [
        "jira_users",
        "confluence_users",
        "github_users",
        "slack_users",
        "vpn_users",
        "staging_access",
    ],
    "Product": ["jira_users", "confluence_users", "slack_users", "zoom_users"],
    "Design": ["jira_users", "confluence_users", "slack_users", "zoom_users"],
    "Sales": ["slack_users", "zoom_users", "confluence_users"],
    "Marketing": ["slack_users", "zoom_users", "confluence_users", "jira_users"],
    "HR": ["slack_users", "zoom_users", "confluence_users"],
    "Finance": ["slack_users", "zoom_users", "confluence_users"],
    "IT": [
        "jira_users",
        "confluence_users",
        "github_users",
        "slack_users",
        "vpn_users",
        "staging_access",
    ],
    "Legal": ["slack_users", "zoom_users", "confluence_users"],
    "Operations": ["jira_users", "slack_users", "zoom_users", "confluence_users"],
}

for eid, emp in employees.items():
    if emp["account_status"] == "disabled":
        continue
    dept = emp["department"]
    groups = DEPT_GROUPS.get(dept, ["slack_users"])
    for gid in groups:
        if gid in access_groups:
            access_groups[gid]["members"].append(eid)
            employees[eid]["access_group_ids"].append(gid)

# Add a few IT/Engineering people to restricted groups
it_eng_employees = [
    eid
    for eid in active_employee_ids
    if employees[eid]["department"] in ("IT", "Engineering")
    and "Manager" in employees[eid]["role"]
    or "Lead" in employees[eid]["role"]
]
random.shuffle(it_eng_employees)
for eid in it_eng_employees[:3]:
    if eid not in access_groups["admin_access"]["members"]:
        access_groups["admin_access"]["members"].append(eid)
        employees[eid]["access_group_ids"].append("admin_access")


# ═══════════════════════════════════════════════════════════════════════════
# Step 6: Tickets (80)
# ═══════════════════════════════════════════════════════════════════════════
TICKET_TEMPLATES = [
    {
        "category": "account",
        "descriptions": [
            "Cannot log in to my account",
            "Need password reset",
            "Account keeps locking after login attempts",
            "Need MFA setup assistance",
            "Account access issues after returning from leave",
        ],
    },
    {
        "category": "hardware",
        "descriptions": [
            "Laptop running very slow",
            "Laptop screen flickering",
            "Keyboard not working properly",
            "Battery draining too fast",
            "External monitor not detected",
            "Laptop won't turn on",
        ],
    },
    {
        "category": "software",
        "descriptions": [
            "Need access to Jira",
            "VS Code keeps crashing",
            "Cannot install required development tools",
            "Software license expired",
            "Application not responding after update",
        ],
    },
    {
        "category": "network",
        "descriptions": [
            "VPN keeps disconnecting",
            "Cannot access internal websites",
            "Slow internet connection",
            "WiFi not connecting in office",
            "VPN certificate error",
        ],
    },
    {
        "category": "access",
        "descriptions": [
            "Need access to GitHub repository",
            "Cannot access staging environment",
            "Need Confluence editing permissions",
            "Request access to shared drive",
            "Need VPN access for remote work",
        ],
    },
]

tickets = {}
ticket_id_set = set()
PRIORITIES = ["low", "medium", "high", "critical"]
PRIORITY_WEIGHTS = [20, 45, 25, 10]
STATUSES = ["open", "in_progress", "waiting", "resolved", "closed"]
STATUS_WEIGHTS = [25, 20, 10, 25, 20]

for i in range(80):
    eid = random.choice(all_employee_ids)
    template = random.choice(TICKET_TEMPLATES)
    category = template["category"]
    description = random.choice(template["descriptions"])
    priority = random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS, k=1)[0]
    status = random.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]

    last = employees[eid]["name"].split()[-1].lower()
    base_tid = f"ticket_{last}_{category[:4]}"
    tid = make_unique_id(base_tid, ticket_id_set)
    ticket_id_set.add(tid)

    created = TODAY - timedelta(days=random.randint(0, 90))
    resolution = None
    if status in ("resolved", "closed"):
        resolution = "Issue resolved by IT support."
    assigned_to = random.choice(
        ["IT Support L1", "IT Support L2", "Network Team", None]
    )

    tickets[tid] = {
        "ticket_id": tid,
        "employee_id": eid,
        "category": category,
        "priority": priority,
        "status": status,
        "description": description,
        "created_at": date_str(created),
        "assigned_to": assigned_to,
        "resolution": resolution,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 7: Validate
# ═══════════════════════════════════════════════════════════════════════════
errors = []

# Foreign key checks
for did, dev in devices.items():
    if dev["employee_id"] and dev["employee_id"] not in employees:
        errors.append(f"Device {did}: employee {dev['employee_id']} not found")

for lid, lic in software_licenses.items():
    if lic["assigned_to"] and lic["assigned_to"] not in employees:
        errors.append(f"License {lid}: employee {lic['assigned_to']} not found")

for tid, ticket in tickets.items():
    if ticket["employee_id"] not in employees:
        errors.append(f"Ticket {tid}: employee {ticket['employee_id']} not found")

for gid, group in access_groups.items():
    for mid in group["members"]:
        if mid not in employees:
            errors.append(f"Group {gid}: member {mid} not found")

# Verify back-references
for eid, emp in employees.items():
    for did in emp["device_ids"]:
        if did not in devices:
            errors.append(f"Employee {eid}: device {did} not found")
    for lid in emp["software_licenses"]:
        if lid not in software_licenses:
            errors.append(f"Employee {eid}: license {lid} not found")
    for gid in emp["access_group_ids"]:
        if gid not in access_groups:
            errors.append(f"Employee {eid}: group {gid} not found")


# ═══════════════════════════════════════════════════════════════════════════
# Step 8: Statistics & Output
# ═══════════════════════════════════════════════════════════════════════════
dept_counts = defaultdict(int)
for e in employees.values():
    dept_counts[e["department"]] += 1

status_counts = defaultdict(int)
for e in employees.values():
    status_counts[e["account_status"]] += 1

device_type_counts = defaultdict(int)
for d in devices.values():
    device_type_counts[d["type"]] += 1

device_status_counts = defaultdict(int)
for d in devices.values():
    device_status_counts[d["status"]] += 1

ticket_status_counts = defaultdict(int)
for t in tickets.values():
    ticket_status_counts[t["status"]] += 1

license_status_counts = defaultdict(int)
for lic in software_licenses.values():
    license_status_counts[lic["status"]] += 1

print("=" * 60)
print("IT HELPDESK DATABASE GENERATION COMPLETE")
print("=" * 60)
print(f"\nEmployees:       {len(employees)}")
for dept, cnt in sorted(dept_counts.items()):
    print(f"  {dept}: {cnt}")
print(f"\n  Account statuses:")
for st, cnt in sorted(status_counts.items()):
    print(f"    {st}: {cnt}")
print(f"  MFA enabled:   {sum(1 for e in employees.values() if e['mfa_enabled'])}")
print(f"  VPN access:    {sum(1 for e in employees.values() if e['vpn_access'])}")
print(f"\nDevices:         {len(devices)}")
for dt, cnt in sorted(device_type_counts.items()):
    print(f"  {dt}: {cnt}")
for st, cnt in sorted(device_status_counts.items()):
    print(f"  status {st}: {cnt}")
print(f"\nSoftware Licenses: {len(software_licenses)}")
for st, cnt in sorted(license_status_counts.items()):
    print(f"  {st}: {cnt}")
print(f"\nAccess Groups:   {len(access_groups)}")
for gid, g in access_groups.items():
    print(
        f"  {g['name']}: {len(g['members'])} members (approval: {g['requires_approval']})"
    )
print(f"\nTickets:         {len(tickets)}")
for st, cnt in sorted(ticket_status_counts.items()):
    print(f"  {st}: {cnt}")

# Edge cases
locked = [e for e in employees.values() if e["account_status"] == "locked"]
disabled = [e for e in employees.values() if e["account_status"] == "disabled"]
no_mfa = [
    e
    for e in employees.values()
    if not e["mfa_enabled"] and e["account_status"] == "active"
]
expired_warranty = [
    d
    for d in devices.values()
    if d["warranty_expiry"] < date_str(TODAY) and d["status"] == "active"
]
expired_licenses = [
    lic for lic in software_licenses.values() if lic["status"] == "expired"
]

print(f"\n-- Edge Cases --")
print(f"  Locked accounts:           {len(locked)}")
print(f"  Disabled accounts:         {len(disabled)}")
print(f"  Active without MFA:        {len(no_mfa)}")
print(f"  Expired warranty devices:  {len(expired_warranty)}")
print(f"  Expired licenses:          {len(expired_licenses)}")

name_counts = defaultdict(int)
for e in employees.values():
    name_counts[e["name"]] += 1
duplicates = {n: c for n, c in name_counts.items() if c > 1}
print(f"  Duplicate names:           {len(duplicates)}")
if duplicates:
    for n, c in duplicates.items():
        print(f"    {n}: {c}")

if errors:
    print(f"\n!! VALIDATION ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  - {e}")
else:
    print("\nAll validation checks passed")


# ── Write db.json ────────────────────────────────────────────────────────
db = {
    "employees": employees,
    "devices": devices,
    "software_licenses": software_licenses,
    "tickets": tickets,
    "access_groups": access_groups,
    "software_catalog": software_catalog,
}

with open(HERE / "db.json", "w") as f:
    json.dump(db, f, indent=2)
print(f"\nWritten to {HERE / 'db.json'}")

# ── Write user_db.json (default workstation state) ───────────────────────
user_db = {
    "workstation": {
        "internet_connected": True,
        "vpn_connected": False,
        "vpn_error": None,
        "installed_software": {
            "Chrome": "120.0",
            "Outlook": "16.0",
            "Teams": "1.6",
            "Slack": "4.35",
        },
        "browser_cache_size_mb": 250.0,
        "needs_restart": False,
        "last_restart": None,
        "service_statuses": {
            "email": "accessible",
            "jira": "accessible",
            "confluence": "accessible",
            "github": "accessible",
            "vpn_portal": "accessible",
        },
    },
    "surroundings": {
        "employee_name": None,
        "employee_email": None,
        "employee_id": None,
        "is_remote": False,
        "account_locked": False,
        "password_expired": False,
    },
}

with open(HERE / "user_db.json", "w") as f:
    json.dump(user_db, f, indent=2)
print(f"Written to {HERE / 'user_db.json'}")
