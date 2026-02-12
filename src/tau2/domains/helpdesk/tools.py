"""Toolkit for the IT helpdesk domain."""

from datetime import datetime
from typing import Optional

from tau2.domains.helpdesk.data_model import (
    AccessGroup,
    Device,
    Employee,
    HelpdeskDB,
    SoftwareCatalog,
    SoftwareLicense,
    Ticket,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

REFERENCE_DATE = datetime(2025, 10, 15)


class HelpdeskTools(ToolKitBase):
    """Tools for the IT helpdesk domain."""

    db: HelpdeskDB

    def __init__(self, db: HelpdeskDB) -> None:
        super().__init__(db)

    # ── ID helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _make_unique_id(base: str, existing) -> str:
        if base not in existing:
            return base
        n = 2
        while f"{base}_{n}" in existing:
            n += 1
        return f"{base}_{n}"

    def _employee_last(self, employee_id: str) -> str:
        return self.db.employees[employee_id].name.split()[-1].lower()

    # ── READ tools ────────────────────────────────────────────────────────

    @is_tool(ToolType.READ)
    def find_employee_by_email(self, email: str) -> list[Employee]:
        """Find employees by email address (case-insensitive exact match).

        Args:
            email: The email address to search for

        Returns:
            A list of matching employees
        """
        email_lower = email.lower()
        return [e for e in self.db.employees.values() if e.email.lower() == email_lower]

    @is_tool(ToolType.READ)
    def find_employee_by_name(self, name: str) -> list[Employee]:
        """Find employees by name (case-insensitive partial match).

        Args:
            name: The name to search for

        Returns:
            A list of matching employees
        """
        name_lower = name.lower()
        return [e for e in self.db.employees.values() if name_lower in e.name.lower()]

    @is_tool(ToolType.READ)
    def get_employee_details(self, employee_id: str) -> Employee:
        """Get the full record for an employee.

        Args:
            employee_id: The ID of the employee

        Returns:
            The employee record

        Raises:
            ValueError: If the employee is not found
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        return self.db.employees[employee_id]

    @is_tool(ToolType.READ)
    def get_device_details(self, device_id: str) -> Device:
        """Get details for a specific device.

        Args:
            device_id: The ID of the device

        Returns:
            The device record

        Raises:
            ValueError: If the device is not found
        """
        if device_id not in self.db.devices:
            raise ValueError(f"Device {device_id} not found")
        return self.db.devices[device_id]

    @is_tool(ToolType.READ)
    def get_ticket(self, ticket_id: str) -> Ticket:
        """Get details for a specific support ticket.

        Args:
            ticket_id: The ID of the ticket

        Returns:
            The ticket record

        Raises:
            ValueError: If the ticket is not found
        """
        if ticket_id not in self.db.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")
        return self.db.tickets[ticket_id]

    @is_tool(ToolType.READ)
    def list_employee_tickets(self, employee_id: str) -> list[Ticket]:
        """List all tickets for an employee.

        Args:
            employee_id: The ID of the employee

        Returns:
            A list of tickets for the employee

        Raises:
            ValueError: If the employee is not found
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        return [t for t in self.db.tickets.values() if t.employee_id == employee_id]

    @is_tool(ToolType.READ)
    def check_software_license(
        self, employee_id: str, software_name: str
    ) -> list[SoftwareLicense]:
        """Check if an employee has a license for specific software.

        Args:
            employee_id: The ID of the employee
            software_name: The name of the software to check

        Returns:
            A list of matching licenses assigned to the employee

        Raises:
            ValueError: If the employee is not found
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        emp = self.db.employees[employee_id]
        return [
            self.db.software_licenses[lid]
            for lid in emp.software_licenses
            if lid in self.db.software_licenses
            and self.db.software_licenses[lid].software_name.lower()
            == software_name.lower()
        ]

    @is_tool(ToolType.READ)
    def get_access_group(self, group_id: str) -> AccessGroup:
        """Get details for a specific access group.

        Args:
            group_id: The ID of the access group

        Returns:
            The access group record

        Raises:
            ValueError: If the access group is not found
        """
        if group_id not in self.db.access_groups:
            raise ValueError(f"Access group {group_id} not found")
        return self.db.access_groups[group_id]

    @is_tool(ToolType.READ)
    def list_access_groups(self, employee_id: str) -> list[AccessGroup]:
        """List all access groups an employee belongs to.

        Args:
            employee_id: The ID of the employee

        Returns:
            A list of access groups

        Raises:
            ValueError: If the employee is not found
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        emp = self.db.employees[employee_id]
        return [
            self.db.access_groups[gid]
            for gid in emp.access_group_ids
            if gid in self.db.access_groups
        ]

    @is_tool(ToolType.READ)
    def get_software_catalog(self) -> list[SoftwareCatalog]:
        """Get the full software catalog showing available software and licensing info.

        Returns:
            A list of all software catalog entries
        """
        return list(self.db.software_catalog.values())

    # ── WRITE tools ───────────────────────────────────────────────────────

    @is_tool(ToolType.WRITE)
    def reset_password(self, employee_id: str) -> str:
        """Trigger a password reset for an employee. A temporary password will be
        sent to the employee's email.

        Requires identity verification (employee ID + department).

        Args:
            employee_id: The ID of the employee

        Returns:
            Confirmation message

        Raises:
            ValueError: If the employee is not found or account is disabled
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        emp = self.db.employees[employee_id]
        if emp.account_status == "disabled":
            raise ValueError(
                f"Cannot reset password for disabled account {employee_id}. "
                "Contact HR to re-enable the account first."
            )
        emp.last_password_reset = REFERENCE_DATE.strftime("%Y-%m-%d")
        return (
            f"Password reset initiated for {emp.name} ({employee_id}). "
            f"A temporary password has been sent to {emp.email}."
        )

    @is_tool(ToolType.WRITE)
    def unlock_account(self, employee_id: str) -> str:
        """Unlock a locked employee account.

        Args:
            employee_id: The ID of the employee

        Returns:
            Confirmation message

        Raises:
            ValueError: If the employee is not found or account is not locked
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        emp = self.db.employees[employee_id]
        if emp.account_status != "locked":
            raise ValueError(
                f"Account {employee_id} is not locked "
                f"(current status: {emp.account_status})."
            )
        emp.account_status = "active"
        return f"Account {employee_id} has been unlocked successfully."

    @is_tool(ToolType.WRITE)
    def enable_mfa(self, employee_id: str) -> str:
        """Enable multi-factor authentication for an employee.

        Args:
            employee_id: The ID of the employee

        Returns:
            Confirmation message

        Raises:
            ValueError: If the employee is not found or MFA already enabled
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        emp = self.db.employees[employee_id]
        if emp.mfa_enabled:
            raise ValueError(f"MFA is already enabled for employee {employee_id}.")
        if emp.account_status != "active":
            raise ValueError(
                f"Cannot enable MFA for account with status '{emp.account_status}'. "
                "Account must be active."
            )
        emp.mfa_enabled = True
        return (
            f"MFA has been enabled for {emp.name} ({employee_id}). "
            "Setup instructions have been sent to their email."
        )

    @is_tool(ToolType.WRITE)
    def grant_software_license(
        self, employee_id: str, software_name: str
    ) -> SoftwareLicense:
        """Assign a software license to an employee. Standard software is granted
        immediately. Non-standard software requires manager approval and will
        create a pending ticket.

        Args:
            employee_id: The ID of the employee
            software_name: The name of the software to grant

        Returns:
            The new or existing license record

        Raises:
            ValueError: If the employee is not found, software not in catalog,
                        no licenses available, or approval required
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        emp = self.db.employees[employee_id]

        # Check catalog
        sw_lower = software_name.lower()
        catalog_entry = None
        for cat in self.db.software_catalog.values():
            if cat.software_name.lower() == sw_lower:
                catalog_entry = cat
                break
        if catalog_entry is None:
            raise ValueError(
                f"Software '{software_name}' not found in catalog. "
                "Available software: " + ", ".join(self.db.software_catalog.keys())
            )

        # Check if already assigned
        existing = self.check_software_license(employee_id, software_name)
        active = [lic for lic in existing if lic.status == "active"]
        if active:
            raise ValueError(
                f"Employee {employee_id} already has an active license "
                f"for {software_name} ({active[0].license_id})."
            )

        # Check approval requirement
        if catalog_entry.requires_approval:
            raise ValueError(
                f"Software '{software_name}' requires manager approval. "
                "Please create a ticket with the employee's manager CC'd, "
                "or transfer to a human agent for approval processing."
            )

        # Check availability
        if catalog_entry.available_licenses <= 0:
            raise ValueError(
                f"No available licenses for '{software_name}'. "
                "Please create a ticket to request additional licenses."
            )

        # Create the license
        last = self._employee_last(employee_id)
        sw_slug = software_name.lower().replace(" ", "_")
        base_lid = f"lic_{last}_{sw_slug}"
        lid = self._make_unique_id(base_lid, self.db.software_licenses)
        license = SoftwareLicense(
            license_id=lid,
            software_name=catalog_entry.software_name,
            version="latest",
            license_type="per_user",
            assigned_to=employee_id,
            expiry_date="2026-10-15",
            status="active",
        )
        self.db.software_licenses[lid] = license
        emp.software_licenses.append(lid)
        catalog_entry.available_licenses -= 1
        return license

    @is_tool(ToolType.WRITE)
    def revoke_software_license(self, license_id: str) -> SoftwareLicense:
        """Revoke a software license.

        Args:
            license_id: The ID of the license to revoke

        Returns:
            The updated license record

        Raises:
            ValueError: If the license is not found or already revoked
        """
        if license_id not in self.db.software_licenses:
            raise ValueError(f"License {license_id} not found")
        lic = self.db.software_licenses[license_id]
        if lic.status == "revoked":
            raise ValueError(f"License {license_id} is already revoked.")
        lic.status = "revoked"

        # Remove from employee's list and return to pool
        if lic.assigned_to and lic.assigned_to in self.db.employees:
            emp = self.db.employees[lic.assigned_to]
            if license_id in emp.software_licenses:
                emp.software_licenses.remove(license_id)

        # Return to catalog pool
        for cat in self.db.software_catalog.values():
            if cat.software_name.lower() == lic.software_name.lower():
                cat.available_licenses += 1
                break

        return lic

    @is_tool(ToolType.WRITE)
    def create_ticket(
        self,
        employee_id: str,
        category: str,
        priority: str,
        description: str,
    ) -> Ticket:
        """Open a new support ticket for an employee.

        Args:
            employee_id: The ID of the employee
            category: Ticket category (account, hardware, software, network, access)
            priority: Priority level (low, medium, high, critical)
            description: Description of the issue

        Returns:
            The new ticket record

        Raises:
            ValueError: If the employee is not found or invalid category/priority
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")

        valid_categories = ["account", "hardware", "software", "network", "access"]
        if category not in valid_categories:
            raise ValueError(
                f"Invalid category '{category}'. Valid categories: {valid_categories}"
            )

        valid_priorities = ["low", "medium", "high", "critical"]
        if priority not in valid_priorities:
            raise ValueError(
                f"Invalid priority '{priority}'. Valid priorities: {valid_priorities}"
            )

        last = self._employee_last(employee_id)
        cat_slug = category[:4]
        base_tid = f"ticket_{last}_{cat_slug}"
        tid = self._make_unique_id(base_tid, self.db.tickets)
        ticket = Ticket(
            ticket_id=tid,
            employee_id=employee_id,
            category=category,
            priority=priority,
            status="open",
            description=description,
            created_at=REFERENCE_DATE.strftime("%Y-%m-%d"),
            assigned_to=None,
            resolution=None,
        )
        self.db.tickets[tid] = ticket
        return ticket

    @is_tool(ToolType.WRITE)
    def update_ticket(
        self,
        ticket_id: str,
        status: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> Ticket:
        """Update a support ticket's status and/or resolution.

        Args:
            ticket_id: The ID of the ticket
            status: New status (open, in_progress, waiting, resolved, closed)
            resolution: Resolution description (required when resolving)

        Returns:
            The updated ticket record

        Raises:
            ValueError: If the ticket is not found or invalid status
        """
        if ticket_id not in self.db.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")
        ticket = self.db.tickets[ticket_id]

        if status is not None:
            valid_statuses = ["open", "in_progress", "waiting", "resolved", "closed"]
            if status not in valid_statuses:
                raise ValueError(
                    f"Invalid status '{status}'. Valid statuses: {valid_statuses}"
                )
            if status == "resolved" and resolution is None:
                raise ValueError(
                    "Resolution description is required when resolving a ticket."
                )
            ticket.status = status

        if resolution is not None:
            ticket.resolution = resolution

        return ticket

    @is_tool(ToolType.WRITE)
    def add_to_access_group(self, employee_id: str, group_id: str) -> AccessGroup:
        """Add an employee to an access group.

        Args:
            employee_id: The ID of the employee
            group_id: The ID of the access group

        Returns:
            The updated access group record

        Raises:
            ValueError: If employee/group not found, already a member,
                        or approval required
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        if group_id not in self.db.access_groups:
            raise ValueError(f"Access group {group_id} not found")

        group = self.db.access_groups[group_id]
        emp = self.db.employees[employee_id]

        if employee_id in group.members:
            raise ValueError(
                f"Employee {employee_id} is already a member of {group.name}."
            )

        if group.requires_approval:
            raise ValueError(
                f"Access group '{group.name}' requires security team approval. "
                "Cannot grant access directly. Please create a ticket or "
                "transfer to a human agent."
            )

        group.members.append(employee_id)
        emp.access_group_ids.append(group_id)
        return group

    @is_tool(ToolType.WRITE)
    def remove_from_access_group(self, employee_id: str, group_id: str) -> AccessGroup:
        """Remove an employee from an access group.

        Args:
            employee_id: The ID of the employee
            group_id: The ID of the access group

        Returns:
            The updated access group record

        Raises:
            ValueError: If employee/group not found or not a member
        """
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        if group_id not in self.db.access_groups:
            raise ValueError(f"Access group {group_id} not found")

        group = self.db.access_groups[group_id]
        emp = self.db.employees[employee_id]

        if employee_id not in group.members:
            raise ValueError(f"Employee {employee_id} is not a member of {group.name}.")

        group.members.remove(employee_id)
        if group_id in emp.access_group_ids:
            emp.access_group_ids.remove(group_id)
        return group

    @is_tool(ToolType.WRITE)
    def request_device_replacement(self, device_id: str, reason: str) -> str:
        """Initiate a device replacement request. Only allowed if the device
        warranty is active or approved by IT manager.

        Args:
            device_id: The ID of the device to replace
            reason: Reason for replacement

        Returns:
            Confirmation message

        Raises:
            ValueError: If device not found or warranty expired without approval
        """
        if device_id not in self.db.devices:
            raise ValueError(f"Device {device_id} not found")

        device = self.db.devices[device_id]
        today = REFERENCE_DATE.strftime("%Y-%m-%d")

        if device.warranty_expiry < today:
            raise ValueError(
                f"Device {device_id} warranty expired on {device.warranty_expiry}. "
                "Replacement requires IT manager approval. "
                "Please create a ticket or transfer to a human agent."
            )

        # Create a ticket for the replacement
        if device.employee_id and device.employee_id in self.db.employees:
            last = self._employee_last(device.employee_id)
            base_tid = f"ticket_{last}_hard"
            tid = self._make_unique_id(base_tid, self.db.tickets)
            ticket = Ticket(
                ticket_id=tid,
                employee_id=device.employee_id,
                category="hardware",
                priority="medium",
                status="open",
                description=f"Device replacement requested for {device_id}: {reason}",
                created_at=REFERENCE_DATE.strftime("%Y-%m-%d"),
            )
            self.db.tickets[tid] = ticket

        device.status = "repair"
        return (
            f"Device replacement request submitted for {device_id} "
            f"({device.model}). Reason: {reason}. "
            "A new device will be provisioned within 3-5 business days."
        )

    # ── GENERIC tools ─────────────────────────────────────────────────────

    @is_tool(ToolType.GENERIC)
    def calculate(self, expression: str) -> str:
        """Calculate the result of a mathematical expression.

        Args:
            expression: The mathematical expression to calculate, such as '12.50 - 3.00'

        Returns:
            The result of the mathematical expression

        Raises:
            ValueError: If the expression is invalid
        """
        if not all(char in "0123456789+-*/(). " for char in expression):
            raise ValueError("Invalid characters in expression")
        return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))

    @is_tool(ToolType.GENERIC)
    def transfer_to_human_agents(self, summary: str) -> str:
        """Transfer the user to a human agent, with a summary of the user's issue.
        Only transfer if the user explicitly asks for a human agent
        or the issue cannot be resolved with available tools.

        Args:
            summary: A summary of the user's issue

        Returns:
            A message indicating the user has been transferred to a human agent
        """
        return "Transfer successful"

    # ── Assertion helpers (not exposed as tools) ──────────────────────────

    def assert_account_status(self, employee_id: str, expected_status: str) -> bool:
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        return self.db.employees[employee_id].account_status == expected_status

    def assert_mfa_enabled(self, employee_id: str, expected: bool) -> bool:
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        return self.db.employees[employee_id].mfa_enabled == expected

    def assert_has_software_license(
        self, employee_id: str, software_name: str, expected: bool
    ) -> bool:
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        licenses = self.check_software_license(employee_id, software_name)
        active = [lic for lic in licenses if lic.status == "active"]
        return (len(active) > 0) == expected

    def assert_license_status(self, license_id: str, expected_status: str) -> bool:
        if license_id not in self.db.software_licenses:
            raise ValueError(f"License {license_id} not found")
        return self.db.software_licenses[license_id].status == expected_status

    def assert_in_access_group(
        self, employee_id: str, group_id: str, expected: bool
    ) -> bool:
        if group_id not in self.db.access_groups:
            raise ValueError(f"Access group {group_id} not found")
        is_member = employee_id in self.db.access_groups[group_id].members
        return is_member == expected

    def assert_ticket_exists_for_employee(
        self, employee_id: str, category: str
    ) -> bool:
        return any(
            t.employee_id == employee_id and t.category == category
            for t in self.db.tickets.values()
        )

    def assert_ticket_status(self, ticket_id: str, expected_status: str) -> bool:
        if ticket_id not in self.db.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")
        return self.db.tickets[ticket_id].status == expected_status

    def assert_device_status(self, device_id: str, expected_status: str) -> bool:
        if device_id not in self.db.devices:
            raise ValueError(f"Device {device_id} not found")
        return self.db.devices[device_id].status == expected_status

    def assert_password_reset_date(self, employee_id: str, expected_date: str) -> bool:
        if employee_id not in self.db.employees:
            raise ValueError(f"Employee {employee_id} not found")
        return self.db.employees[employee_id].last_password_reset == expected_date
