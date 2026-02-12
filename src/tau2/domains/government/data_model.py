from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tau2.domains.government.utils import GOVERNMENT_DB_PATH
from tau2.environment.db import DB

PermitType = Literal["building", "parking", "event", "noise", "business"]
PermitStatus = Literal["pending", "approved", "denied", "expired", "revoked"]

LicenseType = Literal["business", "dog", "vendor", "liquor"]
LicenseStatus = Literal["active", "expired", "suspended", "revoked"]

TaxAccountType = Literal["property", "income", "business"]

CaseType = Literal["complaint", "request", "appeal"]
CaseCategory = Literal["noise", "pothole", "streetlight", "zoning", "parking", "waste"]
CaseStatus = Literal["open", "assigned", "in_progress", "resolved", "closed"]

ZoningType = Literal["residential", "commercial", "mixed"]


class Citizen(BaseModel):
    citizen_id: str = Field(description="Unique identifier for the citizen")
    name: str = Field(description="Full name")
    dob: str = Field(description="Date of birth (YYYY-MM-DD)")
    ssn_last4: str = Field(description="Last 4 digits of SSN")
    address: str = Field(description="Current residential address")
    email: str = Field(description="Email address")
    phone: str = Field(description="Phone number")
    household_id: str = Field(description="ID of the household this citizen belongs to")
    tax_account_ids: List[str] = Field(
        default_factory=list, description="List of tax account IDs"
    )
    permit_ids: List[str] = Field(
        default_factory=list, description="List of permit IDs"
    )
    license_ids: List[str] = Field(
        default_factory=list, description="List of license IDs"
    )
    case_ids: List[str] = Field(default_factory=list, description="List of case IDs")


class Household(BaseModel):
    household_id: str = Field(description="Unique identifier for the household")
    address: str = Field(description="Street address")
    members: List[str] = Field(
        default_factory=list, description="List of citizen IDs in this household"
    )
    property_tax_account_id: Optional[str] = Field(
        None, description="Property tax account ID for this household"
    )
    waste_collection_day: str = Field(
        description="Day of the week for waste collection"
    )
    zoning_type: ZoningType = Field(description="Zoning classification")


class Permit(BaseModel):
    permit_id: str = Field(description="Unique identifier for the permit")
    citizen_id: str = Field(description="ID of the citizen who applied")
    type: PermitType = Field(description="Type of permit")
    status: PermitStatus = Field(description="Current status of the permit")
    application_date: str = Field(
        description="Date the application was submitted (YYYY-MM-DD)"
    )
    decision_date: Optional[str] = Field(
        None, description="Date of approval or denial (YYYY-MM-DD)"
    )
    expiry_date: Optional[str] = Field(
        None, description="Date the permit expires (YYYY-MM-DD)"
    )
    conditions: Optional[str] = Field(
        None, description="Conditions attached to the permit"
    )
    fee_paid: float = Field(default=0.0, description="Fee paid for the permit")
    inspector_notes: Optional[str] = Field(None, description="Notes from the inspector")
    details: str = Field(default="", description="Details of the permit application")


class License(BaseModel):
    license_id: str = Field(description="Unique identifier for the license")
    citizen_id: str = Field(description="ID of the citizen who holds the license")
    type: LicenseType = Field(description="Type of license")
    status: LicenseStatus = Field(description="Current status of the license")
    issue_date: str = Field(description="Date the license was issued (YYYY-MM-DD)")
    expiry_date: str = Field(description="Date the license expires (YYYY-MM-DD)")
    fee_paid: float = Field(default=0.0, description="Fee paid for the license")
    renewal_eligible: bool = Field(
        default=True, description="Whether the license is eligible for renewal"
    )


class TaxAccount(BaseModel):
    account_id: str = Field(description="Unique identifier for the tax account")
    citizen_id: str = Field(description="ID of the citizen who owns the account")
    type: TaxAccountType = Field(description="Type of tax account")
    balance_due: float = Field(
        default=0.0, description="Outstanding balance due in dollars"
    )
    last_payment_date: Optional[str] = Field(
        None, description="Date of the last payment (YYYY-MM-DD)"
    )
    payment_plan_active: bool = Field(
        default=False, description="Whether a payment plan is active"
    )
    installments_remaining: int = Field(
        default=0, description="Number of installments remaining in the payment plan"
    )
    penalties: float = Field(
        default=0.0, description="Penalty amount accrued in dollars"
    )


class Case(BaseModel):
    case_id: str = Field(description="Unique identifier for the case")
    citizen_id: str = Field(description="ID of the citizen who filed the case")
    type: CaseType = Field(description="Type of case")
    category: CaseCategory = Field(description="Category of the case")
    status: CaseStatus = Field(description="Current status of the case")
    description: str = Field(description="Description of the case")
    created_at: str = Field(description="Date the case was created (YYYY-MM-DD)")
    assigned_department: Optional[str] = Field(
        None, description="Department ID assigned to handle the case"
    )
    resolution: Optional[str] = Field(None, description="Resolution description")


class Department(BaseModel):
    department_id: str = Field(description="Unique identifier for the department")
    name: str = Field(description="Department name")
    contact_email: str = Field(description="Department contact email")
    phone: str = Field(description="Department phone number")
    hours: str = Field(description="Operating hours")
    services: List[str] = Field(
        default_factory=list, description="List of services provided"
    )


class Fee(BaseModel):
    fee_id: str = Field(description="Unique identifier for the fee")
    type: str = Field(description="Type of fee (e.g., building_permit, dog_license)")
    amount: float = Field(description="Fee amount in dollars")
    description: str = Field(description="Description of the fee")


class GovernmentDB(DB):
    """Municipal government services database with citizens, households, permits,
    licenses, tax accounts, cases, departments, and fees."""

    citizens: Dict[str, Citizen] = Field(
        description="Dictionary of all citizens indexed by citizen ID"
    )
    households: Dict[str, Household] = Field(
        description="Dictionary of all households indexed by household ID"
    )
    permits: Dict[str, Permit] = Field(
        description="Dictionary of all permits indexed by permit ID"
    )
    licenses: Dict[str, License] = Field(
        description="Dictionary of all licenses indexed by license ID"
    )
    tax_accounts: Dict[str, TaxAccount] = Field(
        description="Dictionary of all tax accounts indexed by account ID"
    )
    cases: Dict[str, Case] = Field(
        description="Dictionary of all cases indexed by case ID"
    )
    departments: Dict[str, Department] = Field(
        description="Dictionary of all departments indexed by department ID"
    )
    fees: Dict[str, Fee] = Field(description="Dictionary of all fees indexed by fee ID")

    def get_statistics(self) -> dict[str, Any]:
        """Get the statistics of the database."""
        return {
            "num_citizens": len(self.citizens),
            "num_households": len(self.households),
            "num_permits": len(self.permits),
            "num_licenses": len(self.licenses),
            "num_tax_accounts": len(self.tax_accounts),
            "num_cases": len(self.cases),
            "num_departments": len(self.departments),
            "num_fees": len(self.fees),
        }


def get_db():
    return GovernmentDB.load(GOVERNMENT_DB_PATH)
