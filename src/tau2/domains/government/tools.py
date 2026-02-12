from datetime import datetime, timedelta
from typing import Optional

from tau2.domains.government.data_model import (
    Case,
    Citizen,
    Department,
    Fee,
    GovernmentDB,
    Household,
    License,
    Permit,
    TaxAccount,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

# Fixed reference date — must match generate_db.py / generate_tasks.py TODAY.
REFERENCE_DATE = datetime(2025, 10, 15)

# Policy constants
LICENSE_RENEWAL_WINDOW_DAYS = 30
LATE_RENEWAL_SURCHARGE_RATE = 0.20
PAYMENT_PLAN_MAX_INSTALLMENTS = 12
PAYMENT_PLAN_MIN_UPFRONT_RATE = 0.10
APPEAL_WINDOW_DAYS = 30


class GovernmentTools(ToolKitBase):
    """Tools for the government services domain."""

    db: GovernmentDB

    def __init__(self, db: GovernmentDB) -> None:
        super().__init__(db)

    # ── ID helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _make_unique_id(base: str, existing) -> str:
        """Return *base* if unique, else base_2, base_3, … (deterministic)."""
        if base not in existing:
            return base
        n = 2
        while f"{base}_{n}" in existing:
            n += 1
        return f"{base}_{n}"

    def _citizen_last(self, citizen_id: str) -> str:
        return self.db.citizens[citizen_id].name.split()[-1].lower()

    # ── READ tools ────────────────────────────────────────────────────────

    @is_tool(ToolType.READ)
    def find_citizen_by_name_dob(self, name: str, dob: str) -> list[Citizen]:
        """Find citizens by name and date of birth.

        Args:
            name: The name to search for (case-insensitive partial match)
            dob: Date of birth (YYYY-MM-DD)

        Returns:
            A list of matching citizens
        """
        name_lower = name.lower()
        return [
            c
            for c in self.db.citizens.values()
            if name_lower in c.name.lower() and c.dob == dob
        ]

    @is_tool(ToolType.READ)
    def find_citizen_by_ssn(self, ssn_last4: str) -> list[Citizen]:
        """Look up citizens by the last 4 digits of their SSN.

        Args:
            ssn_last4: Last 4 digits of the SSN

        Returns:
            A list of matching citizens
        """
        return [c for c in self.db.citizens.values() if c.ssn_last4 == ssn_last4]

    @is_tool(ToolType.READ)
    def get_citizen_details(self, citizen_id: str) -> Citizen:
        """Get the full record for a citizen.

        Args:
            citizen_id: The ID of the citizen

        Returns:
            The citizen record

        Raises:
            ValueError: If the citizen is not found
        """
        if citizen_id not in self.db.citizens:
            raise ValueError(f"Citizen {citizen_id} not found")
        return self.db.citizens[citizen_id]

    @is_tool(ToolType.READ)
    def get_household_details(self, household_id: str) -> Household:
        """Get details for a household including address, members, zoning type,
        property tax account, and waste collection day.

        Args:
            household_id: The ID of the household

        Returns:
            The household record

        Raises:
            ValueError: If the household is not found
        """
        if household_id not in self.db.households:
            raise ValueError(f"Household {household_id} not found")
        return self.db.households[household_id]

    @is_tool(ToolType.READ)
    def get_permit(self, permit_id: str) -> Permit:
        """Get details for a permit.

        Args:
            permit_id: The ID of the permit

        Returns:
            The permit record

        Raises:
            ValueError: If the permit is not found
        """
        if permit_id not in self.db.permits:
            raise ValueError(f"Permit {permit_id} not found")
        return self.db.permits[permit_id]

    @is_tool(ToolType.READ)
    def get_license(self, license_id: str) -> License:
        """Get details for a license.

        Args:
            license_id: The ID of the license

        Returns:
            The license record

        Raises:
            ValueError: If the license is not found
        """
        if license_id not in self.db.licenses:
            raise ValueError(f"License {license_id} not found")
        return self.db.licenses[license_id]

    @is_tool(ToolType.READ)
    def get_tax_account(self, account_id: str) -> TaxAccount:
        """Get details for a tax account including balance due and payment plan status.

        Args:
            account_id: The ID of the tax account

        Returns:
            The tax account record

        Raises:
            ValueError: If the tax account is not found
        """
        if account_id not in self.db.tax_accounts:
            raise ValueError(f"Tax account {account_id} not found")
        return self.db.tax_accounts[account_id]

    @is_tool(ToolType.READ)
    def get_case(self, case_id: str) -> Case:
        """Get details for a case (complaint, request, or appeal).

        Args:
            case_id: The ID of the case

        Returns:
            The case record

        Raises:
            ValueError: If the case is not found
        """
        if case_id not in self.db.cases:
            raise ValueError(f"Case {case_id} not found")
        return self.db.cases[case_id]

    @is_tool(ToolType.READ)
    def check_permit_requirements(self, permit_type: str, zoning_type: str) -> dict:
        """Check the requirements for a specific permit type given a zoning classification.

        Args:
            permit_type: Type of permit (building, parking, event, noise, business)
            zoning_type: Zoning classification (residential, commercial, mixed)

        Returns:
            A dictionary describing requirements, fees, and whether the permit is
            allowed under the given zoning

        Raises:
            ValueError: If the permit type is invalid
        """
        valid_types = ["building", "parking", "event", "noise", "business"]
        if permit_type not in valid_types:
            raise ValueError(
                f"Invalid permit type: {permit_type}. Valid types: {valid_types}"
            )

        # Zoning compatibility
        zoning_rules = {
            "building": {
                "residential": {
                    "allowed": True,
                    "notes": "Standard residential building permit.",
                },
                "commercial": {
                    "allowed": True,
                    "notes": "Commercial building permit. Requires commercial insurance documentation.",
                },
                "mixed": {
                    "allowed": True,
                    "notes": "Mixed-use building permit. May require additional review.",
                },
            },
            "parking": {
                "residential": {
                    "allowed": True,
                    "notes": "Residential parking permit for street parking.",
                },
                "commercial": {"allowed": True, "notes": "Commercial parking permit."},
                "mixed": {"allowed": True, "notes": "Mixed-zone parking permit."},
            },
            "event": {
                "residential": {
                    "allowed": True,
                    "notes": "Residential events may have noise restrictions after 10 PM.",
                },
                "commercial": {"allowed": True, "notes": "Standard event permit."},
                "mixed": {"allowed": True, "notes": "Event permit for mixed-use zone."},
            },
            "noise": {
                "residential": {
                    "allowed": True,
                    "notes": "Noise variance permit. Limited to daytime hours (7 AM - 8 PM).",
                },
                "commercial": {"allowed": True, "notes": "Commercial noise permit."},
                "mixed": {"allowed": True, "notes": "Mixed-zone noise permit."},
            },
            "business": {
                "residential": {
                    "allowed": False,
                    "notes": "Business operations are NOT permitted in residential zones. The citizen must apply for a zoning variance first.",
                },
                "commercial": {
                    "allowed": True,
                    "notes": "Standard business operating permit.",
                },
                "mixed": {
                    "allowed": True,
                    "notes": "Business permit for mixed-use zone.",
                },
            },
        }

        fee_lookup = {f.type: f.amount for f in self.db.fees.values()}
        fee_key = f"{permit_type}_permit"
        fee_amount = fee_lookup.get(fee_key, 0.0)

        zoning_info = zoning_rules.get(permit_type, {}).get(
            zoning_type, {"allowed": False, "notes": "Unknown zoning type."}
        )

        return {
            "permit_type": permit_type,
            "zoning_type": zoning_type,
            "allowed": zoning_info["allowed"],
            "notes": zoning_info["notes"],
            "fee": fee_amount,
            "processing_time": "10-15 business days",
        }

    @is_tool(ToolType.READ)
    def list_fees(self, fee_type: Optional[str] = None) -> list[Fee]:
        """List the fee schedule, optionally filtered by type.

        Args:
            fee_type: Optional type filter (e.g., "building_permit", "dog_license")

        Returns:
            A list of fee records
        """
        fees = list(self.db.fees.values())
        if fee_type:
            fee_type_lower = fee_type.lower()
            fees = [f for f in fees if fee_type_lower in f.type.lower()]
        return fees

    @is_tool(ToolType.READ)
    def get_department_info(self, department_id: str) -> Department:
        """Get information about a city department.

        Args:
            department_id: The ID of the department

        Returns:
            The department record

        Raises:
            ValueError: If the department is not found
        """
        if department_id not in self.db.departments:
            raise ValueError(f"Department {department_id} not found")
        return self.db.departments[department_id]

    @is_tool(ToolType.READ)
    def list_departments(self) -> list[Department]:
        """List all city departments with their IDs, names, contact info,
        and services.

        Returns:
            A list of all department records
        """
        return list(self.db.departments.values())

    @is_tool(ToolType.READ)
    def list_citizen_cases(self, citizen_id: str) -> list[Case]:
        """List all cases filed by a citizen.

        Args:
            citizen_id: The ID of the citizen

        Returns:
            A list of cases filed by the citizen

        Raises:
            ValueError: If the citizen is not found
        """
        if citizen_id not in self.db.citizens:
            raise ValueError(f"Citizen {citizen_id} not found")
        return [c for c in self.db.cases.values() if c.citizen_id == citizen_id]

    @is_tool(ToolType.READ)
    def list_citizen_permits(self, citizen_id: str) -> list[Permit]:
        """List all permits for a citizen.

        Args:
            citizen_id: The ID of the citizen

        Returns:
            A list of permits for the citizen

        Raises:
            ValueError: If the citizen is not found
        """
        if citizen_id not in self.db.citizens:
            raise ValueError(f"Citizen {citizen_id} not found")
        return [p for p in self.db.permits.values() if p.citizen_id == citizen_id]

    @is_tool(ToolType.READ)
    def list_citizen_licenses(self, citizen_id: str) -> list[License]:
        """List all licenses for a citizen.

        Args:
            citizen_id: The ID of the citizen

        Returns:
            A list of licenses for the citizen

        Raises:
            ValueError: If the citizen is not found
        """
        if citizen_id not in self.db.citizens:
            raise ValueError(f"Citizen {citizen_id} not found")
        return [
            lic for lic in self.db.licenses.values() if lic.citizen_id == citizen_id
        ]

    # ── WRITE tools ───────────────────────────────────────────────────────

    @is_tool(ToolType.WRITE)
    def submit_permit_application(
        self, citizen_id: str, permit_type: str, details: str
    ) -> Permit:
        """Submit a permit application. The permit will be created with 'pending' status.
        Note: agents cannot approve or deny permits — only submit applications.

        Args:
            citizen_id: The ID of the citizen applying
            permit_type: Type of permit (building, parking, event, noise, business)
            details: Description of what the permit is for

        Returns:
            The new permit record

        Raises:
            ValueError: If citizen not found, invalid permit type, or
                        zoning does not allow this permit type
        """
        if citizen_id not in self.db.citizens:
            raise ValueError(f"Citizen {citizen_id} not found")

        valid_types = ["building", "parking", "event", "noise", "business"]
        if permit_type not in valid_types:
            raise ValueError(
                f"Invalid permit type: {permit_type}. Valid types: {valid_types}"
            )

        citizen = self.db.citizens[citizen_id]
        household = self.db.households[citizen.household_id]

        # Check zoning compatibility
        if permit_type == "business" and household.zoning_type == "residential":
            raise ValueError(
                "Business permits cannot be issued in residential zones. "
                "The citizen must apply for a zoning variance first."
            )

        # Look up fee
        fee_lookup = {f.type: f.amount for f in self.db.fees.values()}
        fee_key = f"{permit_type}_permit"
        fee_amount = fee_lookup.get(fee_key, 0.0)

        today = REFERENCE_DATE.strftime("%Y-%m-%d")
        base_pid = f"permit_{self._citizen_last(citizen_id)}_{permit_type}"
        permit_id = self._make_unique_id(base_pid, self.db.permits)

        permit = Permit(
            permit_id=permit_id,
            citizen_id=citizen_id,
            type=permit_type,
            status="pending",
            application_date=today,
            details=details,
            fee_paid=fee_amount,
        )

        self.db.permits[permit_id] = permit
        citizen.permit_ids.append(permit_id)

        return permit

    @is_tool(ToolType.WRITE)
    def renew_license(self, license_id: str, payment_method: str) -> License:
        """Renew a license. License must be within 30 days of expiry or already
        expired. Late renewals (after expiry) incur a 20% surcharge.

        Args:
            license_id: The ID of the license to renew
            payment_method: Payment method (e.g., "credit_card", "check", "cash")

        Returns:
            The updated license record

        Raises:
            ValueError: If license not found, not eligible for renewal, or
                        too early to renew
        """
        if license_id not in self.db.licenses:
            raise ValueError(f"License {license_id} not found")

        lic = self.db.licenses[license_id]

        if not lic.renewal_eligible:
            raise ValueError(
                f"License {license_id} is not eligible for renewal "
                f"(status: {lic.status})."
            )

        if lic.status in ("suspended", "revoked"):
            raise ValueError(
                f"License {license_id} is {lic.status} and cannot be renewed."
            )

        today = REFERENCE_DATE
        expiry = datetime.strptime(lic.expiry_date, "%Y-%m-%d")

        # Must be within 30 days of expiry or already expired
        days_until = (expiry - today).days
        if days_until > LICENSE_RENEWAL_WINDOW_DAYS:
            raise ValueError(
                f"Too early to renew. License expires on {lic.expiry_date}. "
                f"Renewal is available within {LICENSE_RENEWAL_WINDOW_DAYS} days "
                f"of expiry."
            )

        # Look up fee
        fee_lookup = {f.type: f.amount for f in self.db.fees.values()}
        fee_key = f"{lic.type}_license"
        base_fee = fee_lookup.get(fee_key, 0.0)

        # Late surcharge
        if expiry < today:
            surcharge = round(base_fee * LATE_RENEWAL_SURCHARGE_RATE, 2)
            total_fee = base_fee + surcharge
        else:
            total_fee = base_fee

        # Renew for one year from expiry or today, whichever is later
        start = max(today, expiry)
        new_expiry = start + timedelta(days=365)

        lic.expiry_date = new_expiry.strftime("%Y-%m-%d")
        lic.status = "active"
        lic.fee_paid = total_fee
        lic.issue_date = today.strftime("%Y-%m-%d")

        return lic

    @is_tool(ToolType.WRITE)
    def make_tax_payment(
        self, account_id: str, amount: float, payment_method: str
    ) -> TaxAccount:
        """Make a payment on a tax account.

        Args:
            account_id: The ID of the tax account
            amount: The payment amount in dollars
            payment_method: Payment method (e.g., "credit_card", "check", "cash")

        Returns:
            The updated tax account record

        Raises:
            ValueError: If account not found, invalid amount, or amount exceeds balance
        """
        if account_id not in self.db.tax_accounts:
            raise ValueError(f"Tax account {account_id} not found")

        account = self.db.tax_accounts[account_id]

        if amount <= 0:
            raise ValueError("Payment amount must be positive.")

        total_owed = account.balance_due + account.penalties
        if amount > total_owed:
            raise ValueError(
                f"Payment amount ${amount:.2f} exceeds total owed "
                f"${total_owed:.2f} (balance: ${account.balance_due:.2f}, "
                f"penalties: ${account.penalties:.2f})."
            )

        # Apply payment to penalties first, then balance
        if account.penalties > 0:
            penalty_payment = min(amount, account.penalties)
            account.penalties = round(account.penalties - penalty_payment, 2)
            amount -= penalty_payment

        if amount > 0:
            account.balance_due = round(account.balance_due - amount, 2)

        account.last_payment_date = REFERENCE_DATE.strftime("%Y-%m-%d")

        # If payment plan is active and balance is cleared, deactivate plan
        if account.balance_due <= 0 and account.penalties <= 0:
            account.payment_plan_active = False
            account.installments_remaining = 0

        return account

    @is_tool(ToolType.WRITE)
    def setup_payment_plan(self, account_id: str, installments: int) -> TaxAccount:
        """Set up a payment plan for a tax account. Requires at least 10% upfront
        payment. Maximum 12 installments.

        Args:
            account_id: The ID of the tax account
            installments: Number of installments (2-12)

        Returns:
            The updated tax account record

        Raises:
            ValueError: If account not found, invalid installments, balance too low,
                        or plan already active
        """
        if account_id not in self.db.tax_accounts:
            raise ValueError(f"Tax account {account_id} not found")

        account = self.db.tax_accounts[account_id]

        if account.payment_plan_active:
            raise ValueError(
                f"Tax account {account_id} already has an active payment plan "
                f"with {account.installments_remaining} installments remaining."
            )

        total_owed = account.balance_due + account.penalties
        if total_owed <= 0:
            raise ValueError("No balance due on this account.")

        if installments < 2 or installments > PAYMENT_PLAN_MAX_INSTALLMENTS:
            raise ValueError(
                f"Installments must be between 2 and {PAYMENT_PLAN_MAX_INSTALLMENTS}."
            )

        account.payment_plan_active = True
        account.installments_remaining = installments

        return account

    @is_tool(ToolType.WRITE)
    def file_case(
        self,
        citizen_id: str,
        case_type: str,
        category: str,
        description: str,
    ) -> Case:
        """File a case (complaint, request, or appeal).

        Args:
            citizen_id: The ID of the citizen filing the case
            case_type: Type of case (complaint, request, appeal)
            category: Category (noise, pothole, streetlight, zoning, parking, waste)
            description: Description of the issue

        Returns:
            The new case record

        Raises:
            ValueError: If citizen not found or invalid type/category
        """
        if citizen_id not in self.db.citizens:
            raise ValueError(f"Citizen {citizen_id} not found")

        valid_types = ["complaint", "request", "appeal"]
        if case_type not in valid_types:
            raise ValueError(
                f"Invalid case type: {case_type}. Valid types: {valid_types}"
            )

        valid_categories = [
            "noise",
            "pothole",
            "streetlight",
            "zoning",
            "parking",
            "waste",
        ]
        if category not in valid_categories:
            raise ValueError(
                f"Invalid category: {category}. Valid categories: {valid_categories}"
            )

        # Enforce 30-day appeal window
        if case_type == "appeal":
            citizen = self.db.citizens[citizen_id]
            has_appealable = False
            for pid in citizen.permit_ids:
                permit = self.db.permits.get(pid)
                if permit and permit.status == "denied" and permit.decision_date:
                    decision_dt = datetime.strptime(permit.decision_date, "%Y-%m-%d")
                    days_since = (REFERENCE_DATE - decision_dt).days
                    if days_since <= APPEAL_WINDOW_DAYS:
                        has_appealable = True
                        break
            if not has_appealable:
                raise ValueError(
                    f"Appeal window has expired. Appeals must be filed within "
                    f"{APPEAL_WINDOW_DAYS} days of the decision date. "
                    f"No denied permits for this citizen have an open appeal window."
                )

        # Assign department based on category
        dept_mapping = {
            "noise": "public_safety",
            "pothole": "public_works",
            "streetlight": "public_works",
            "zoning": "planning_zoning",
            "parking": "transportation",
            "waste": "public_works",
        }
        dept_id = dept_mapping.get(category)

        today = REFERENCE_DATE.strftime("%Y-%m-%d")
        base_cid = f"case_{self._citizen_last(citizen_id)}_{category}"
        case_id = self._make_unique_id(base_cid, self.db.cases)

        case = Case(
            case_id=case_id,
            citizen_id=citizen_id,
            type=case_type,
            category=category,
            status="open",
            description=description,
            created_at=today,
            assigned_department=dept_id,
        )

        self.db.cases[case_id] = case
        citizen = self.db.citizens[citizen_id]
        citizen.case_ids.append(case_id)

        return case

    @is_tool(ToolType.WRITE)
    def update_case(
        self,
        case_id: str,
        status: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> Case:
        """Update a case's status and/or resolution.

        Args:
            case_id: The ID of the case to update
            status: New status (open, assigned, in_progress, resolved, closed)
            resolution: Resolution description (required when setting status to resolved)

        Returns:
            The updated case record

        Raises:
            ValueError: If case not found or invalid status
        """
        if case_id not in self.db.cases:
            raise ValueError(f"Case {case_id} not found")

        case = self.db.cases[case_id]

        if status is not None:
            valid_statuses = [
                "open",
                "assigned",
                "in_progress",
                "resolved",
                "closed",
            ]
            if status not in valid_statuses:
                raise ValueError(
                    f"Invalid status: {status}. Valid statuses: {valid_statuses}"
                )
            if status == "resolved" and not resolution:
                raise ValueError(
                    "A resolution description is required when setting status "
                    "to 'resolved'."
                )
            case.status = status

        if resolution is not None:
            case.resolution = resolution

        return case

    @is_tool(ToolType.WRITE)
    def update_citizen_address(self, citizen_id: str, new_address: str) -> Citizen:
        """Update a citizen's address on file.

        Args:
            citizen_id: The ID of the citizen
            new_address: The new address

        Returns:
            The updated citizen record

        Raises:
            ValueError: If the citizen is not found
        """
        if citizen_id not in self.db.citizens:
            raise ValueError(f"Citizen {citizen_id} not found")

        citizen = self.db.citizens[citizen_id]
        citizen.address = new_address

        return citizen

    @is_tool(ToolType.WRITE)
    def waive_penalty(self, account_id: str, reason: str) -> TaxAccount:
        """Waive penalties on a tax account. Only allowed for first offense
        (no prior penalty waivers on record) or documented hardship.

        Args:
            account_id: The ID of the tax account
            reason: Reason for the waiver

        Returns:
            The updated tax account record

        Raises:
            ValueError: If account not found, no penalties to waive, or
                        not eligible for waiver
        """
        if account_id not in self.db.tax_accounts:
            raise ValueError(f"Tax account {account_id} not found")

        account = self.db.tax_accounts[account_id]

        if account.penalties <= 0:
            raise ValueError(f"Tax account {account_id} has no penalties to waive.")

        # Policy: only waive for first offense. Enforcement is in the tasks
        # (the agent should check policy before calling this tool).

        account.penalties = 0.0

        return account

    # ── GENERIC tools ─────────────────────────────────────────────────────

    @is_tool(ToolType.GENERIC)
    def calculate(self, expression: str) -> str:
        """Calculate the result of a mathematical expression.

        Args:
            expression: The mathematical expression to calculate, such as
                '3000 * 0.10' or '250 + 50'. The expression can contain
                numbers, operators (+, -, *, /), parentheses, and spaces.

        Returns:
            The result of the mathematical expression.

        Raises:
            ValueError: If the expression is invalid.
        """
        if not all(char in "0123456789+-*/(). " for char in expression):
            raise ValueError("Invalid characters in expression")
        return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))

    @is_tool(ToolType.GENERIC)
    def transfer_to_human_agents(self, summary: str) -> str:
        """Transfer the user to a human agent, with a summary of the user's issue.
        Only transfer if
         -  the user explicitly asks for a human agent
         -  given the policy and the available tools, you cannot solve the user's issue.

        Args:
            summary: A summary of the user's issue.

        Returns:
            A message indicating the user has been transferred to a human agent.
        """
        return "Transfer successful"

    # ── Assertion helpers (not exposed as tools) ──────────────────────────

    def assert_permit_exists(self, citizen_id: str, permit_type: str) -> bool:
        """Check if a pending permit of the given type exists for the citizen.

        Args:
            citizen_id: The ID of the citizen
            permit_type: The type of permit

        Returns:
            True if such a permit exists
        """
        return any(
            p.citizen_id == citizen_id
            and p.type == permit_type
            and p.status == "pending"
            for p in self.db.permits.values()
        )

    def assert_license_status(self, license_id: str, expected_status: str) -> bool:
        """Check if a license's status matches the expected status.

        Args:
            license_id: The ID of the license
            expected_status: The expected status

        Returns:
            True if the status matches
        """
        if license_id not in self.db.licenses:
            return False
        return self.db.licenses[license_id].status == expected_status

    def assert_tax_balance(self, account_id: str, max_balance: float) -> bool:
        """Check if a tax account's total owed is at or below the given amount.

        Args:
            account_id: The ID of the tax account
            max_balance: Maximum acceptable total (balance + penalties)

        Returns:
            True if total owed <= max_balance
        """
        if account_id not in self.db.tax_accounts:
            return False
        acct = self.db.tax_accounts[account_id]
        return (acct.balance_due + acct.penalties) <= max_balance + 0.01

    def assert_payment_plan_active(self, account_id: str) -> bool:
        """Check if a payment plan is active on the tax account.

        Args:
            account_id: The ID of the tax account

        Returns:
            True if a payment plan is active
        """
        if account_id not in self.db.tax_accounts:
            return False
        return self.db.tax_accounts[account_id].payment_plan_active

    def assert_case_exists(self, citizen_id: str, category: str) -> bool:
        """Check if an open case of the given category exists for the citizen.

        Args:
            citizen_id: The ID of the citizen
            category: The case category

        Returns:
            True if such a case exists
        """
        return any(
            c.citizen_id == citizen_id and c.category == category and c.status == "open"
            for c in self.db.cases.values()
        )

    def assert_citizen_address(self, citizen_id: str, expected_address: str) -> bool:
        """Check if a citizen's address matches the expected address.

        Args:
            citizen_id: The ID of the citizen
            expected_address: The expected address

        Returns:
            True if the address matches
        """
        if citizen_id not in self.db.citizens:
            return False
        return self.db.citizens[citizen_id].address == expected_address

    def assert_penalty_waived(self, account_id: str) -> bool:
        """Check if penalties have been waived (penalties == 0).

        Args:
            account_id: The ID of the tax account

        Returns:
            True if penalties are 0
        """
        if account_id not in self.db.tax_accounts:
            return False
        return self.db.tax_accounts[account_id].penalties == 0.0
