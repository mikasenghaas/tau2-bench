from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tau2.domains.helpdesk.utils import HELPDESK_DB_PATH
from tau2.environment.db import DB

AccountStatus = Literal["active", "locked", "disabled"]
DeviceType = Literal["laptop", "desktop", "phone"]
DeviceStatus = Literal["active", "repair", "decommissioned"]
LicenseType = Literal["per_user", "per_device", "floating"]
LicenseStatus = Literal["active", "expired", "revoked"]
TicketPriority = Literal["low", "medium", "high", "critical"]
TicketStatus = Literal["open", "in_progress", "waiting", "resolved", "closed"]


class Employee(BaseModel):
    employee_id: str = Field(description="Unique identifier for the employee")
    name: str = Field(description="Employee's full name")
    email: str = Field(description="Employee's email address")
    department: str = Field(description="Department the employee belongs to")
    role: str = Field(description="Employee's job role/title")
    manager_id: Optional[str] = Field(
        None, description="Employee ID of the direct manager"
    )
    device_ids: List[str] = Field(
        default_factory=list, description="List of assigned device IDs"
    )
    software_licenses: List[str] = Field(
        default_factory=list, description="List of assigned software license IDs"
    )
    vpn_access: bool = Field(
        default=False, description="Whether employee has VPN access"
    )
    mfa_enabled: bool = Field(
        default=False, description="Whether multi-factor authentication is enabled"
    )
    account_status: AccountStatus = Field(
        default="active", description="Current account status"
    )
    last_password_reset: str = Field(
        description="Date of last password reset (YYYY-MM-DD)"
    )
    access_group_ids: List[str] = Field(
        default_factory=list,
        description="List of access group IDs the employee belongs to",
    )


class Device(BaseModel):
    device_id: str = Field(description="Unique identifier for the device")
    employee_id: Optional[str] = Field(
        None, description="ID of the employee the device is assigned to"
    )
    type: DeviceType = Field(description="Type of device")
    model: str = Field(description="Device model name")
    os: str = Field(description="Operating system")
    os_version: str = Field(description="Operating system version")
    serial_number: str = Field(description="Device serial number")
    status: DeviceStatus = Field(description="Current device status")
    assigned_date: Optional[str] = Field(
        None, description="Date the device was assigned (YYYY-MM-DD)"
    )
    warranty_expiry: str = Field(description="Warranty expiration date (YYYY-MM-DD)")
    installed_software: List[str] = Field(
        default_factory=list,
        description="List of software names installed on the device",
    )


class SoftwareLicense(BaseModel):
    license_id: str = Field(description="Unique identifier for the license")
    software_name: str = Field(description="Name of the software")
    version: str = Field(description="Software version")
    license_type: LicenseType = Field(description="Type of license")
    assigned_to: Optional[str] = Field(
        None,
        description="Employee ID (per_user) or device ID (per_device) the license is assigned to",
    )
    expiry_date: str = Field(description="License expiration date (YYYY-MM-DD)")
    status: LicenseStatus = Field(description="Current license status")


class Ticket(BaseModel):
    ticket_id: str = Field(description="Unique identifier for the ticket")
    employee_id: str = Field(description="ID of the employee who submitted the ticket")
    category: str = Field(
        description="Ticket category (e.g., account, hardware, software, network, access)"
    )
    priority: TicketPriority = Field(description="Ticket priority level")
    status: TicketStatus = Field(description="Current ticket status")
    description: str = Field(description="Description of the issue")
    created_at: str = Field(description="Ticket creation date (YYYY-MM-DD)")
    assigned_to: Optional[str] = Field(
        None, description="IT staff member assigned to the ticket"
    )
    resolution: Optional[str] = Field(None, description="Resolution description")


class AccessGroup(BaseModel):
    group_id: str = Field(description="Unique identifier for the access group")
    name: str = Field(description="Name of the access group")
    description: str = Field(
        description="Description of what access the group provides"
    )
    members: List[str] = Field(
        default_factory=list, description="List of employee IDs in the group"
    )
    permissions: List[str] = Field(
        default_factory=list,
        description="List of permissions granted by this group",
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether adding members requires manager/security approval",
    )


class SoftwareCatalog(BaseModel):
    software_name: str = Field(description="Name of the software")
    category: str = Field(description="Category (standard/non_standard/restricted)")
    available_licenses: int = Field(
        description="Number of unassigned licenses available"
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether this software requires manager approval",
    )


class HelpdeskDB(DB):
    """IT Helpdesk database."""

    employees: Dict[str, Employee] = Field(
        description="Dictionary of employees indexed by employee ID"
    )
    devices: Dict[str, Device] = Field(
        description="Dictionary of devices indexed by device ID"
    )
    software_licenses: Dict[str, SoftwareLicense] = Field(
        description="Dictionary of software licenses indexed by license ID"
    )
    tickets: Dict[str, Ticket] = Field(
        description="Dictionary of tickets indexed by ticket ID"
    )
    access_groups: Dict[str, AccessGroup] = Field(
        description="Dictionary of access groups indexed by group ID"
    )
    software_catalog: Dict[str, SoftwareCatalog] = Field(
        description="Dictionary of available software indexed by software name"
    )

    def get_statistics(self) -> dict[str, Any]:
        return {
            "num_employees": len(self.employees),
            "num_devices": len(self.devices),
            "num_software_licenses": len(self.software_licenses),
            "num_tickets": len(self.tickets),
            "num_access_groups": len(self.access_groups),
            "num_software_catalog": len(self.software_catalog),
        }


def get_db():
    return HelpdeskDB.load(HELPDESK_DB_PATH)
